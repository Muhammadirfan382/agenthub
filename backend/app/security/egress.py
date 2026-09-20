"""The egress gateway: the only way an agent's request leaves the server.

Every outbound request an agent causes is a server-side request forgery risk:
the URL comes from a model, and the model may have been told what to ask for by
a hostile document. This module assumes the worst about every URL it is given.

A request is made only when all of this holds:

* the scheme is ``https``, with no credentials in the URL and the default port;
* the host is a DNS name - never an IP literal - and is exactly one of the
  agent's allowed domains;
* **every** address the name resolves to is a public unicast address (no
  loopback, private, link-local, carrier-grade NAT, multicast, reserved,
  documentation, or IPv4-mapped/6to4 forms of those);
* the connection goes to one of the addresses checked above - the socket is
  pinned to it, while TLS still verifies the certificate for the real host
  name - so the name cannot be re-resolved to an internal address between the
  check and the request (DNS rebinding);
* the method is GET, no cookies or credentials are sent, redirects are never
  followed, and time and response size are bounded.

A refusal says which rule refused, so it can be audited and shown.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

import httpx2

USER_AGENT = "AgentHub-Egress/0.8 (+no-reply)"
MAX_URL_LENGTH = 2000
#: Response bodies beyond this are cut off, and the cut is reported.
MAX_RESPONSE_BYTES = 256 * 1024
CONNECT_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 15.0
#: Content the model may read. Anything else is refused rather than decoded.
TEXT_TYPES = ("text/", "application/json", "application/xml", "application/xhtml+xml")

EgressRule = Literal[
    "scheme",
    "credentials",
    "port",
    "host",
    "ip_literal",
    "not_allowed",
    "resolution",
    "private_address",
    "redirect",
    "content_type",
    "timeout",
    "connection",
    "url_length",
]


class EgressBlocked(Exception):
    """The request was refused before, or instead of, leaving the server."""

    def __init__(self, rule: EgressRule, message: str) -> None:
        super().__init__(message)
        self.rule: EgressRule = rule
        self.message = message


@dataclass(frozen=True)
class CheckedUrl:
    url: str
    host: str
    path_and_query: str


@dataclass(frozen=True)
class EgressResponse:
    url: str
    status: int
    content_type: str
    body: str
    truncated: bool
    #: The address actually connected to, for the audit trail.
    address: str


def check_url(url: str, allowed_domains: list[str]) -> CheckedUrl:
    """Static checks that need no network. Raises `EgressBlocked`."""
    if len(url) > MAX_URL_LENGTH:
        raise EgressBlocked("url_length", "The URL is too long.")
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        raise EgressBlocked("host", "The URL could not be parsed.") from None

    if parts.scheme != "https":
        raise EgressBlocked("scheme", "Only https URLs may be requested.")
    if parts.username or parts.password or "@" in parts.netloc:
        raise EgressBlocked("credentials", "URLs may not carry credentials.")
    if port not in (None, 443):
        raise EgressBlocked("port", "Only the default https port may be used.")

    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise EgressBlocked("host", "The URL has no host.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise EgressBlocked("ip_literal", "Requests must name a host, not an IP address.")

    allowed = {domain.rstrip(".").lower() for domain in allowed_domains}
    if host not in allowed:
        raise EgressBlocked("not_allowed", f"{host} is not one of this agent's allowed domains.")

    path = parts.path or "/"
    path_and_query = f"{path}?{parts.query}" if parts.query else path
    return CheckedUrl(
        url=f"https://{host}{path_and_query}", host=host, path_and_query=path_and_query
    )


def is_public_address(address: str) -> bool:
    """True only for globally routable unicast addresses."""
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address):
        # An IPv6 form of an IPv4 address is judged as that IPv4 address.
        embedded = ip.ipv4_mapped or ip.sixtofour
        if embedded is None and ip.teredo is not None:
            embedded = ip.teredo[1]
        if embedded is not None:
            return is_public_address(str(embedded))
    return bool(
        ip.is_global
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_loopback
        and not ip.is_link_local
        and not ip.is_private
    )


async def resolve(host: str) -> list[str]:
    """Every address the name resolves to, via the system resolver."""
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM), timeout=CONNECT_TIMEOUT_SECONDS
        )
    except (TimeoutError, OSError):
        raise EgressBlocked("resolution", f"{host} could not be resolved.") from None
    addresses = sorted({str(info[4][0]) for info in infos})
    if not addresses:
        raise EgressBlocked("resolution", f"{host} did not resolve to any address.")
    return addresses


def _pinned_url(address: str, path_and_query: str) -> str:
    ip = ipaddress.ip_address(address)
    netloc = f"[{ip}]" if isinstance(ip, ipaddress.IPv6Address) else str(ip)
    return f"https://{netloc}{path_and_query}"


class EgressGateway:
    """Makes checked, pinned, bounded GET requests. Nothing else leaves the server."""

    def __init__(
        self, *, transport: httpx2.AsyncBaseTransport | None = None, resolver: object = None
    ) -> None:
        self._transport = transport
        # Tests substitute a resolver; production always uses the system one.
        self._resolve = resolver if callable(resolver) else resolve

    async def get(self, url: str, allowed_domains: list[str]) -> EgressResponse:
        checked = check_url(url, allowed_domains)
        addresses = await self._resolve(checked.host)
        blocked = [address for address in addresses if not is_public_address(address)]
        if blocked:
            # One bad record is enough: an attacker controls which one is used.
            raise EgressBlocked(
                "private_address", f"{checked.host} resolves to a non-public address."
            )
        address = addresses[0]

        timeout = httpx2.Timeout(TOTAL_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
        async with httpx2.AsyncClient(
            transport=self._transport,
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,  # no proxies or netrc credentials from the environment
        ) as client:
            try:
                async with client.stream(
                    "GET",
                    _pinned_url(address, checked.path_and_query),
                    headers={
                        "Host": checked.host,
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json, text/*;q=0.9",
                    },
                    extensions={"sni_hostname": checked.host},
                ) as response:
                    if 300 <= response.status_code < 400:
                        raise EgressBlocked(
                            "redirect",
                            "The server answered with a redirect, which is not followed.",
                        )
                    content_type = response.headers.get("content-type", "").split(";")[0].strip()
                    if content_type and not content_type.lower().startswith(TEXT_TYPES):
                        raise EgressBlocked(
                            "content_type", f"{content_type} responses are not read."
                        )
                    body = bytearray()
                    truncated = False
                    async for chunk in response.aiter_bytes():
                        room = MAX_RESPONSE_BYTES - len(body)
                        if len(chunk) > room:
                            body.extend(chunk[:room])
                            truncated = True
                            break
                        body.extend(chunk)
                    status = response.status_code
            except httpx2.TimeoutException:
                raise EgressBlocked("timeout", f"{checked.host} did not answer in time.") from None
            except httpx2.HTTPError:
                raise EgressBlocked(
                    "connection", f"The connection to {checked.host} failed."
                ) from None

        return EgressResponse(
            url=checked.url,
            status=status,
            content_type=content_type or "unknown",
            body=body.decode("utf-8", errors="replace"),
            truncated=truncated,
            address=address,
        )


# --- choosing the gateway ----------------------------------------------------

_override: EgressGateway | None = None
_default = EgressGateway()


def get_egress() -> EgressGateway:
    return _override if _override is not None else _default


def use_egress(gateway: EgressGateway | None) -> None:
    """Substitutes the egress gateway. Tests use this; nothing else should."""
    global _override
    _override = gateway
