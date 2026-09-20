"""The egress gateway: which URLs may leave the server, and how.

Nothing here touches a network. The resolver is replaced by a table and the
HTTP transport by a recorder, so every test can assert on the exact request that
would have gone out - or that none did.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx2
import pytest

from app.security.egress import (
    MAX_RESPONSE_BYTES,
    EgressBlocked,
    EgressGateway,
    check_url,
    is_public_address,
)

ALLOWED = ["api.example.com"]
PUBLIC = "93.184.215.14"


def resolver(table: dict[str, list[str]]) -> Callable[[str], Awaitable[list[str]]]:
    async def resolve(host: str) -> list[str]:
        if host not in table:
            raise EgressBlocked("resolution", f"{host} could not be resolved.")
        return table[host]

    return resolve


class Recorder:
    """An HTTP transport that answers from a script and remembers every request."""

    def __init__(self, response: httpx2.Response | Exception | None = None) -> None:
        self.requests: list[httpx2.Request] = []
        self.response = (
            response
            if response is not None
            else httpx2.Response(
                200, headers={"content-type": "application/json"}, json={"ok": True}
            )
        )

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def gateway(recorder: Recorder, table: dict[str, list[str]] | None = None) -> EgressGateway:
    return EgressGateway(
        transport=httpx2.MockTransport(recorder.handler),
        resolver=resolver(table if table is not None else {"api.example.com": [PUBLIC]}),
    )


def fetch(egress: EgressGateway, url: str, allowed: list[str] | None = None) -> Any:
    return asyncio.run(egress.get(url, ALLOWED if allowed is None else allowed))


class TestStaticChecks:
    @pytest.mark.parametrize(
        ("url", "rule"),
        [
            ("http://api.example.com/", "scheme"),
            ("file:///etc/passwd", "scheme"),
            ("gopher://api.example.com/", "scheme"),
            ("https://user:pass@api.example.com/", "credentials"),
            ("https://api.example.com@evil.example/", "credentials"),
            ("https://api.example.com:8443/", "port"),
            ("https://169.254.169.254/latest/meta-data/", "ip_literal"),
            ("https://[::1]/", "ip_literal"),
            ("https://127.0.0.1/", "ip_literal"),
            ("https://evil.example/", "not_allowed"),
            ("https://api.example.com.evil.example/", "not_allowed"),
            ("https://sub.api.example.com/", "not_allowed"),
            ("https:///no-host", "host"),
            ("https://api.example.com/" + "a" * 3000, "url_length"),
        ],
    )
    def test_a_url_breaking_a_rule_is_refused_by_that_rule(self, url: str, rule: str) -> None:
        with pytest.raises(EgressBlocked) as blocked:
            check_url(url, ALLOWED)

        assert blocked.value.rule == rule

    def test_an_allowed_url_is_normalised(self) -> None:
        checked = check_url("https://API.Example.com./v1/items?q=1", ALLOWED)

        assert (checked.host, checked.path_and_query) == ("api.example.com", "/v1/items?q=1")


class TestAddresses:
    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",
            "10.0.0.8",
            "172.16.4.2",
            "192.168.1.1",
            "169.254.169.254",
            "100.64.0.1",
            "0.0.0.0",  # noqa: S104  (checked as refused, never bound to)
            "192.0.2.1",
            "224.0.0.1",
            "::1",
            "fe80::1",
            "fd12:3456::1",
            "::ffff:10.0.0.1",
            "2002:c0a8:0101::1",
        ],
    )
    def test_internal_and_special_addresses_are_not_public(self, address: str) -> None:
        assert not is_public_address(address)

    @pytest.mark.parametrize("address", [PUBLIC, "2606:2800:21f:cb07:6820:80da:af6b:8b2c"])
    def test_public_unicast_addresses_are_public(self, address: str) -> None:
        assert is_public_address(address)


class TestRequests:
    def test_the_connection_is_pinned_to_the_checked_address(self) -> None:
        recorder = Recorder()

        response = fetch(gateway(recorder), "https://api.example.com/v1/status")

        request = recorder.requests[0]
        assert request.url.host == PUBLIC
        assert request.headers["host"] == "api.example.com"
        # TLS still verifies the certificate for the real name.
        assert request.extensions["sni_hostname"] == "api.example.com"
        assert (response.status, response.address) == (200, PUBLIC)

    def test_only_a_plain_get_is_sent(self) -> None:
        recorder = Recorder()

        fetch(gateway(recorder), "https://api.example.com/")

        request = recorder.requests[0]
        assert request.method == "GET"
        assert "cookie" not in request.headers
        assert "authorization" not in request.headers
        assert request.headers["user-agent"].startswith("AgentHub-Egress/")

    def test_a_name_that_resolves_inside_is_refused_before_connecting(self) -> None:
        recorder = Recorder()

        with pytest.raises(EgressBlocked) as blocked:
            fetch(gateway(recorder, {"api.example.com": ["10.0.0.5"]}), "https://api.example.com/")

        assert blocked.value.rule == "private_address"
        assert recorder.requests == []

    def test_one_internal_record_among_public_ones_is_enough_to_refuse(self) -> None:
        recorder = Recorder()

        with pytest.raises(EgressBlocked):
            fetch(
                gateway(recorder, {"api.example.com": [PUBLIC, "169.254.169.254"]}),
                "https://api.example.com/",
            )

        assert recorder.requests == []

    def test_redirects_are_not_followed(self) -> None:
        recorder = Recorder(
            httpx2.Response(302, headers={"location": "https://169.254.169.254/latest/"})
        )

        with pytest.raises(EgressBlocked) as blocked:
            fetch(gateway(recorder), "https://api.example.com/")

        assert blocked.value.rule == "redirect"
        assert len(recorder.requests) == 1

    def test_binary_content_is_not_read(self) -> None:
        recorder = Recorder(
            httpx2.Response(
                200, headers={"content-type": "application/octet-stream"}, content=b"\0"
            )
        )

        with pytest.raises(EgressBlocked) as blocked:
            fetch(gateway(recorder), "https://api.example.com/")

        assert blocked.value.rule == "content_type"

    def test_a_large_response_is_cut_off(self) -> None:
        recorder = Recorder(
            httpx2.Response(
                200,
                headers={"content-type": "text/plain"},
                content=b"x" * (MAX_RESPONSE_BYTES * 2),
            )
        )

        response = fetch(gateway(recorder), "https://api.example.com/")

        assert response.truncated
        assert len(response.body) == MAX_RESPONSE_BYTES

    @pytest.mark.parametrize(
        ("error", "rule"),
        [
            (httpx2.ConnectTimeout("slow"), "timeout"),
            (httpx2.ConnectError("refused"), "connection"),
        ],
    )
    def test_network_failures_are_reported_as_blocks(self, error: Exception, rule: str) -> None:
        with pytest.raises(EgressBlocked) as blocked:
            fetch(gateway(Recorder(error)), "https://api.example.com/")

        assert blocked.value.rule == rule

    def test_an_unresolvable_name_is_refused(self) -> None:
        with pytest.raises(EgressBlocked) as blocked:
            fetch(gateway(Recorder(), {}), "https://api.example.com/")

        assert blocked.value.rule == "resolution"
