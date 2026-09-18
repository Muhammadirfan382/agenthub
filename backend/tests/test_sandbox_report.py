"""Judging a probe result.

The rule being tested throughout: a guarantee counts as kept only when the
container positively said so. Silence, `null` and a malformed answer are all
failures, because a sandbox that cannot describe itself has not been verified.
"""

from typing import Any

import pytest

from app.sandbox.report import NO_CAPABILITIES, evaluate, unavailable_report

EXPECTED_MEMORY_MB = 512
EXPECTED_PIDS = 128


def probe_payload(**overrides: dict[str, Any]) -> dict[str, Any]:
    """A payload from a sandbox where everything is as it should be."""
    payload: dict[str, Any] = {
        "identity": {"uid": 65532, "gid": 65532, "is_root": False, "groups": []},
        "filesystem": {
            "root_writable": False,
            "tmp_writable": True,
            "docker_socket_present": False,
            "host_mounts": [],
        },
        "privileges": {"capabilities": NO_CAPABILITIES, "no_new_privileges": True},
        "network": {"reachable": False, "dns_resolves": False},
        "limits": {
            "memory_bytes": EXPECTED_MEMORY_MB * 1024 * 1024,
            "process_limit": EXPECTED_PIDS,
        },
        "environment": {"names": ["PATH"], "unexpected": [], "suspicious": []},
    }
    for section, values in overrides.items():
        payload[section] = {**payload[section], **values}
    return payload


def judge(payload: dict[str, Any]) -> dict[str, bool]:
    """The verdict per check id, which is what every test below asserts on."""
    report = evaluate(payload, expected_memory_mb=EXPECTED_MEMORY_MB, expected_pids=EXPECTED_PIDS)
    return {check.id: check.passed for check in report.checks}


class TestAGoodSandbox:
    def test_every_guarantee_is_kept(self) -> None:
        report = evaluate(
            probe_payload(), expected_memory_mb=EXPECTED_MEMORY_MB, expected_pids=EXPECTED_PIDS
        )

        assert report.passed
        assert report.failures == []
        assert report.summary() == "13 of 13 isolation checks passed"

    def test_the_report_can_be_stored_and_read_back(self) -> None:
        document = evaluate(
            probe_payload(), expected_memory_mb=EXPECTED_MEMORY_MB, expected_pids=EXPECTED_PIDS
        ).as_dict()

        assert document["passed"] is True
        assert len(document["checks"]) == 13
        assert {"id", "label", "passed", "detail"} == set(document["checks"][0])


class TestOneThingWrong:
    """Each case breaks exactly one guarantee, and only that check may fail."""

    @pytest.mark.parametrize(
        ("check_id", "section", "values"),
        [
            ("non_root", "identity", {"uid": 0}),
            ("read_only_root", "filesystem", {"root_writable": True}),
            ("writable_scratch", "filesystem", {"tmp_writable": False}),
            ("no_capabilities", "privileges", {"capabilities": "0000003fffffffff"}),
            ("no_escalation", "privileges", {"no_new_privileges": False}),
            ("no_network", "network", {"reachable": True}),
            ("no_dns", "network", {"dns_resolves": True}),
            ("no_container_socket", "filesystem", {"docker_socket_present": True}),
            ("no_host_mounts", "filesystem", {"host_mounts": ["/host/etc"]}),
            ("no_secret_environment", "environment", {"suspicious": ["AWS_SECRET_ACCESS_KEY"]}),
            ("clean_environment", "environment", {"unexpected": ["DATABASE_URL"]}),
            ("memory_limit", "limits", {"memory_bytes": 8 * 1024 * 1024 * 1024}),
            ("process_limit", "limits", {"process_limit": 100_000}),
        ],
    )
    def test_the_matching_check_fails_and_no_other(
        self, check_id: str, section: str, values: dict[str, Any]
    ) -> None:
        verdicts = judge(probe_payload(**{section: values}))

        assert verdicts[check_id] is False
        assert [other for other, passed in verdicts.items() if not passed] == [check_id]

    def test_a_named_failure_says_which_promise_was_broken(self) -> None:
        report = evaluate(
            probe_payload(identity={"uid": 0}),
            expected_memory_mb=EXPECTED_MEMORY_MB,
            expected_pids=EXPECTED_PIDS,
        )

        assert not report.passed
        assert [check.label for check in report.failures] == ["Runs as an unprivileged user"]
        assert report.summary() == "12 of 13 isolation checks passed"


class TestSilenceIsNotAPass:
    def test_an_empty_answer_keeps_no_guarantee(self) -> None:
        verdicts = judge({})

        assert not any(verdicts.values())

    def test_a_missing_field_fails_its_own_check(self) -> None:
        payload = probe_payload()
        del payload["privileges"]["capabilities"]

        assert judge(payload)["no_capabilities"] is False

    @pytest.mark.parametrize("value", [None, "no", 0, "false"])
    def test_a_truthy_looking_non_boolean_does_not_count(self, value: object) -> None:
        # `root_writable: "false"` is a string, not a promise.
        assert judge(probe_payload(filesystem={"root_writable": value}))["read_only_root"] is False

    @pytest.mark.parametrize("value", [None, "65532", 65532.0])
    def test_a_user_id_that_is_not_an_integer_does_not_count(self, value: object) -> None:
        assert judge(probe_payload(identity={"uid": value}))["non_root"] is False

    def test_a_limit_reported_as_unlimited_fails(self) -> None:
        # cgroup v2 writes "max" rather than a number when nothing is capped.
        verdicts = judge(probe_payload(limits={"memory_bytes": "max", "process_limit": "max"}))

        assert verdicts["memory_limit"] is False
        assert verdicts["process_limit"] is False

    def test_a_malformed_payload_is_judged_rather_than_crashing(self) -> None:
        verdicts = judge({"identity": "root", "limits": [1, 2, 3], "network": None})

        assert not any(verdicts.values())


class TestNoRuntimeAtAll:
    def test_it_reports_a_single_honest_failure(self) -> None:
        report = unavailable_report("docker is not installed")

        assert not report.passed
        assert [check.id for check in report.checks] == ["runtime_available"]
        assert report.failures[0].detail == "docker is not installed"
        assert report.summary() == "0 of 1 isolation checks passed"
