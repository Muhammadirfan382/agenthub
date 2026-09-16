import pytest
from pydantic import ValidationError

from app.core.config import DEV_DATABASE_URL, Settings
from app.services.risk import derive_risk, permission_risk


class TestPermissionRisk:
    def test_scales_with_the_access_level(self) -> None:
        assert permission_risk("web_access", "read_only") == "low"
        assert permission_risk("web_access", "restricted") == "medium"
        assert permission_risk("web_access", "allowed") == "high"

    def test_code_execution_is_always_critical(self) -> None:
        assert permission_risk("code_execution", "restricted") == "critical"
        assert permission_risk("code_execution", "allowed") == "critical"


class TestDeriveRisk:
    def test_denying_everything_is_the_lowest_risk(self) -> None:
        level, score = derive_risk(
            [{"capability": "web_access", "level": "denied", "risk": "medium"}]
        )
        assert (level, score) == ("low", 5)

    def test_unguarded_high_risk_scores_higher_than_approval_gated(self) -> None:
        guarded = derive_risk([{"level": "allowed", "risk": "high", "requiresApproval": True}])
        unguarded = derive_risk([{"level": "allowed", "risk": "high", "requiresApproval": False}])

        assert guarded[0] == unguarded[0] == "high"
        assert unguarded[1] > guarded[1]

    def test_the_highest_granted_risk_wins(self) -> None:
        level, _ = derive_risk(
            [
                {"level": "allowed", "risk": "low", "requiresApproval": False},
                {"level": "restricted", "risk": "critical", "requiresApproval": True},
            ]
        )
        assert level == "critical"


class TestSettings:
    def test_production_requires_an_explicit_database_url(self) -> None:
        with pytest.raises(ValidationError, match="DATABASE_URL must be set"):
            Settings(environment="production", _env_file=None)

    def test_development_falls_back_to_a_local_file_database(self) -> None:
        settings = Settings(environment="development", _env_file=None)

        assert settings.resolved_database_url == DEV_DATABASE_URL
        assert settings.is_sqlite is True

    def test_masks_the_password_for_logging(self) -> None:
        settings = Settings(
            environment="production",
            database_url="postgresql+asyncpg://agenthub:sup3rsecret@db.internal:5432/agenthub",
            _env_file=None,
        )

        assert "sup3rsecret" not in settings.safe_database_url
        assert settings.safe_database_url.endswith("@db.internal:5432/agenthub")
        assert settings.is_sqlite is False
