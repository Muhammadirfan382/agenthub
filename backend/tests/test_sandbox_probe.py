"""The program that runs inside the sandbox.

Most of what the probe does can only be observed from inside a container, but
its judgement about the environment is ordinary Python and is worth pinning
down here: it decides what counts as "something from the host leaked in", and
getting that wrong either hides a leak or cries wolf about the image's own
variables.

The probe is loaded from agents/sandbox by path, because it is shipped in the
image rather than installed as part of the backend package.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

PROBE_PATH = Path(__file__).resolve().parents[2] / "agents" / "sandbox" / "probe.py"


def load_probe() -> ModuleType:
    specification = importlib.util.spec_from_file_location("agenthub_sandbox_probe", PROBE_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def probe() -> ModuleType:
    return load_probe()


def report_for(probe: ModuleType, environment: dict[str, str]) -> dict[str, Any]:
    probe.os.environ = environment
    result: dict[str, Any] = probe.environment_report()
    return result


def test_the_probe_is_where_the_image_expects_it() -> None:
    assert PROBE_PATH.is_file()


class TestWhatCountsAsALeak:
    def test_the_image_s_own_variables_are_not_a_leak(self, probe: ModuleType) -> None:
        report = report_for(
            probe,
            {
                "PATH": "/usr/local/bin",
                "HOME": "/home/agent",
                "HOSTNAME": "sandbox",
                "LANG": "C.UTF-8",
                "GPG_KEY": "A035C8C19219BA821ECEA86B64E628F8D684696D",
                "PYTHON_VERSION": "3.13.1",
                "PYTHON_SHA256": "abc123",
                "PYTHON_PIP_VERSION": "24.3.1",
            },
        )

        assert report["unexpected"] == []
        assert report["suspicious"] == []

    def test_a_package_signing_key_is_not_mistaken_for_one_of_ours(self, probe: ModuleType) -> None:
        # GPG_KEY contains "KEY", but it is baked into the base image and is
        # not a credential of the host's.
        assert report_for(probe, {"GPG_KEY": "A035C8C1"})["suspicious"] == []

    def test_anything_the_image_did_not_set_is_reported(self, probe: ModuleType) -> None:
        report = report_for(probe, {"PATH": "/usr/local/bin", "TZ": "UTC"})

        assert report["unexpected"] == ["TZ"]
        assert report["suspicious"] == []

    @pytest.mark.parametrize(
        "name",
        [
            "AWS_SECRET_ACCESS_KEY",
            "DATABASE_URL",
            "GITHUB_TOKEN",
            "ANTHROPIC_API_KEY",
            "SESSION_SECRET",
            "POSTGRES_PASSWORD",
        ],
    )
    def test_a_host_credential_is_named_as_such(self, probe: ModuleType, name: str) -> None:
        report = report_for(probe, {"PATH": "/usr/local/bin", name: "value"})

        assert report["suspicious"] == [name]
        assert name in report["unexpected"]

    def test_the_full_list_of_names_is_reported_but_not_their_values(
        self, probe: ModuleType
    ) -> None:
        report = report_for(probe, {"PATH": "/usr/local/bin", "GITHUB_TOKEN": "ghp_secret_value"})

        assert report["names"] == ["GITHUB_TOKEN", "PATH"]
        assert "ghp_secret_value" not in str(report)
