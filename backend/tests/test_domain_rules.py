import pytest
from pydantic import ValidationError

from app.core.config import DEV_DATABASE_URL, Settings
from app.core.errors import ForbiddenError, UnprocessableError
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import (
    configure_password_cost,
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)
from app.schemas.enums import CAPABILITY_KEYS
from app.schemas.registry import PermissionGrant
from app.services.authorization import can, has_role, require
from app.services.registry_service import normalise_grants, unusable_tools
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

    def test_production_refuses_weak_password_hashing(self) -> None:
        with pytest.raises(ValidationError, match="PASSWORD_HASH_COST_EXPONENT"):
            Settings(
                environment="production",
                database_url="postgresql+asyncpg://user@db.invalid/agenthub",
                password_hash_cost_exponent=8,
                _env_file=None,
            )

    def test_masks_the_password_for_logging(self) -> None:
        settings = Settings(
            environment="production",
            database_url="postgresql+asyncpg://agenthub:sup3rsecret@db.internal:5432/agenthub",
            _env_file=None,
        )

        assert "sup3rsecret" not in settings.safe_database_url
        assert settings.safe_database_url.endswith("@db.internal:5432/agenthub")
        assert settings.is_sqlite is False


class TestPasswordHashing:
    def test_the_same_password_hashes_differently_every_time(self) -> None:
        configure_password_cost(8)

        first, second = (
            hash_password("a-long-enough-password"),
            hash_password("a-long-enough-password"),
        )

        assert first != second  # the salt differs
        assert verify_password("a-long-enough-password", first)
        assert verify_password("a-long-enough-password", second)

    def test_the_hash_reveals_nothing_about_the_password(self) -> None:
        configure_password_cost(8)

        encoded = hash_password("correct-horse-battery-staple")

        assert "correct" not in encoded
        assert encoded.startswith("scrypt$n=256,r=8,p=1$")

    def test_rejects_a_wrong_password_and_a_damaged_hash(self) -> None:
        configure_password_cost(8)
        encoded = hash_password("a-long-enough-password")

        assert verify_password("not-it", encoded) is False
        assert verify_password("a-long-enough-password", "") is False
        assert verify_password("a-long-enough-password", "bcrypt$x$y$z") is False
        assert verify_password("a-long-enough-password", encoded[:-4]) is False

    def test_a_stored_hash_keeps_working_after_the_cost_changes(self) -> None:
        configure_password_cost(8)
        encoded = hash_password("a-long-enough-password")

        configure_password_cost(10)

        # Parameters travel with the hash, so old passwords still verify.
        assert verify_password("a-long-enough-password", encoded)
        configure_password_cost(8)


class TestSessionTokens:
    def test_tokens_are_unique_and_stored_only_as_fingerprints(self) -> None:
        first, second = new_session_token(), new_session_token()

        assert first != second
        assert len(hash_token(first)) == 64
        assert hash_token(first) == hash_token(first)
        assert hash_token(first) != hash_token(second)
        assert first not in hash_token(first)


class TestPermissionMatrix:
    def test_roles_are_ordered(self) -> None:
        assert has_role("owner", "admin") is True
        assert has_role("admin", "member") is True
        assert has_role("member", "admin") is False
        assert has_role("viewer", "member") is False

    def test_a_viewer_may_only_read(self) -> None:
        assert can("viewer", "agent:read") is True
        assert can("viewer", "execution:read") is True
        assert can("viewer", "member:read") is True
        assert can("viewer", "agent:create") is False
        assert can("viewer", "agent:update") is False

    def test_owning_an_agent_lets_a_member_change_it(self) -> None:
        assert can("member", "agent:update", owns_resource=True) is True
        assert can("member", "agent:delete", owns_resource=True) is True
        assert can("member", "agent:execute", owns_resource=True) is True
        assert can("member", "agent:update", owns_resource=False) is False

    def test_ownership_never_grants_unrelated_actions(self) -> None:
        assert can("member", "member:manage", owns_resource=True) is False
        assert can("admin", "organization:manage", owns_resource=True) is False
        assert can("viewer", "agent:update", owns_resource=True) is False

    def test_require_raises_for_a_refused_action(self) -> None:
        with pytest.raises(ForbiddenError):
            require("viewer", "agent:create")

        require("admin", "agent:create")  # does not raise


class TestLoginThrottling:
    def test_allows_the_limit_then_blocks(self) -> None:
        limiter = SlidingWindowLimiter(limit=3, window_seconds=60)

        for _ in range(3):
            assert limiter.check("someone@example.com") is True
            limiter.record("someone@example.com")

        assert limiter.check("someone@example.com") is False
        assert limiter.retry_after_seconds("someone@example.com") > 0
        # Another key is unaffected.
        assert limiter.check("other@example.com") is True

    def test_a_reset_clears_the_key(self) -> None:
        limiter = SlidingWindowLimiter(limit=1, window_seconds=60)
        limiter.record("someone@example.com")
        assert limiter.check("someone@example.com") is False

        limiter.reset("someone@example.com")

        assert limiter.check("someone@example.com") is True


def manifest_asking_for(**levels: str) -> dict[str, object]:
    """A manifest that requests the given levels, and nothing else."""
    return {
        "tools": ["web_search"],
        "requiredPermissions": [
            {
                "capability": capability,
                "level": levels.get(capability, "denied"),
                "requiresApproval": capability == "code_execution",
                "scope": "Requested by the publisher",
                "risk": "low",
            }
            for capability in CAPABILITY_KEYS
        ],
    }


class TestGrantNormalisation:
    def test_missing_capabilities_are_denied_not_omitted(self) -> None:
        grants = normalise_grants(manifest_asking_for(web_access="allowed"), [])

        assert len(grants) == len(CAPABILITY_KEYS)
        assert {grant["level"] for grant in grants} == {"denied"}
        assert all(grant["scope"] == "Not granted" for grant in grants)

    def test_a_capability_absent_from_the_manifest_is_refused(self) -> None:
        manifest: dict[str, object] = {"tools": [], "requiredPermissions": []}

        with pytest.raises(UnprocessableError, match="did not ask for"):
            normalise_grants(
                manifest,
                [PermissionGrant(capability="web_access", level="read_only", scope="Anything")],
            )

    def test_risk_is_recomputed_and_never_taken_from_the_client(self) -> None:
        grants = normalise_grants(
            manifest_asking_for(web_access="allowed"),
            [
                PermissionGrant(
                    capability="web_access",
                    level="allowed",
                    scope="Everything on the public web",
                    risk="low",
                )
            ],
        )

        granted = next(grant for grant in grants if grant["capability"] == "web_access")
        assert granted["risk"] == "high"

    def test_the_same_capability_cannot_be_granted_twice(self) -> None:
        manifest = manifest_asking_for(web_access="restricted")
        duplicate = PermissionGrant(
            capability="web_access", level="read_only", scope="Documentation"
        )

        with pytest.raises(UnprocessableError, match="only once"):
            normalise_grants(manifest, [duplicate, duplicate])


class TestUnusableTools:
    def test_reports_tools_whose_capability_is_denied(self) -> None:
        manifest = manifest_asking_for(web_access="restricted")
        denied = normalise_grants(manifest, [])
        allowed = normalise_grants(
            manifest,
            [
                PermissionGrant(
                    capability="web_access", level="restricted", scope="Allow-listed docs"
                )
            ],
        )

        assert unusable_tools(manifest, denied) == ["web_search"]
        assert unusable_tools(manifest, allowed) == []
