"""Tests for Control Plane — release flow, feature flags."""

import pytest
from vasini.control.release import (
    ReleaseManager, Release, ReleaseStage, PromotionResult,
    RollbackResult, RollbackReason,
)
from vasini.control.flags import FeatureFlagStore, FeatureFlag


class TestReleaseStages:
    def test_all_stages_exist(self):
        assert ReleaseStage.DRAFT.value == "draft"
        assert ReleaseStage.VALIDATED.value == "validated"
        assert ReleaseStage.STAGED.value == "staged"
        assert ReleaseStage.PROD.value == "prod"
        assert ReleaseStage.ROLLED_BACK.value == "rolled_back"

    def test_create_release(self):
        release = Release(
            pack_id="senior-python-dev",
            version="1.0.0",
            stage=ReleaseStage.DRAFT,
        )
        assert release.pack_id == "senior-python-dev"
        assert release.stage == ReleaseStage.DRAFT


class TestReleaseManager:
    def test_create_release(self):
        mgr = ReleaseManager()
        release = mgr.create_release("pack-1", "1.0.0")
        assert release.stage == ReleaseStage.DRAFT

    def test_promote_draft_to_validated(self):
        mgr = ReleaseManager()
        release = mgr.create_release("pack-1", "1.0.0")
        result = mgr.promote(release.id, eval_score=0.90)
        assert result.success
        assert result.new_stage == ReleaseStage.VALIDATED

    def test_promote_draft_fails_low_score(self):
        mgr = ReleaseManager()
        release = mgr.create_release("pack-1", "1.0.0")
        result = mgr.promote(release.id, eval_score=0.70)
        assert not result.success
        assert "score" in result.reason.lower()

    def test_promote_validated_to_staged(self):
        mgr = ReleaseManager()
        release = mgr.create_release("pack-1", "1.0.0")
        mgr.promote(release.id, eval_score=0.90)
        result = mgr.promote(release.id)
        assert result.success
        assert result.new_stage == ReleaseStage.STAGED

    def test_promote_staged_to_prod(self):
        mgr = ReleaseManager()
        release = mgr.create_release("pack-1", "1.0.0")
        mgr.promote(release.id, eval_score=0.90)
        mgr.promote(release.id)
        result = mgr.promote(release.id, approved_by="platform-lead")
        assert result.success
        assert result.new_stage == ReleaseStage.PROD

    def test_promote_staged_to_prod_requires_approval(self):
        mgr = ReleaseManager()
        release = mgr.create_release("pack-1", "1.0.0")
        mgr.promote(release.id, eval_score=0.90)
        mgr.promote(release.id)
        result = mgr.promote(release.id)
        assert not result.success
        assert "approval" in result.reason.lower()

    def test_invalid_promotion_skipping_stage(self):
        mgr = ReleaseManager()
        release = mgr.create_release("pack-1", "1.0.0")
        result = mgr.promote(release.id)
        assert not result.success

    def test_rollback(self):
        mgr = ReleaseManager()
        release = mgr.create_release("pack-1", "1.0.0")
        mgr.promote(release.id, eval_score=0.90)
        mgr.promote(release.id)
        mgr.promote(release.id, approved_by="lead")
        result = mgr.rollback(release.id, reason=RollbackReason.SLO_BREACH)
        assert result.success
        updated = mgr.get_release(release.id)
        assert updated.stage == ReleaseStage.ROLLED_BACK

    def test_rollback_draft_fails(self):
        mgr = ReleaseManager()
        release = mgr.create_release("pack-1", "1.0.0")
        result = mgr.rollback(release.id, reason=RollbackReason.ERROR_RATE)
        assert not result.success

    def test_get_current_prod_release(self):
        mgr = ReleaseManager()
        r1 = mgr.create_release("pack-1", "1.0.0")
        mgr.promote(r1.id, eval_score=0.90)
        mgr.promote(r1.id)
        mgr.promote(r1.id, approved_by="lead")
        current = mgr.get_current_prod("pack-1")
        assert current is not None
        assert current.version == "1.0.0"

    def test_list_releases(self):
        mgr = ReleaseManager()
        mgr.create_release("pack-1", "1.0.0")
        mgr.create_release("pack-1", "1.1.0")
        releases = mgr.list_releases("pack-1")
        assert len(releases) == 2


class TestFeatureFlags:
    def test_create_flag(self):
        store = FeatureFlagStore()
        flag = store.create("dark-mode", enabled=True)
        assert flag.name == "dark-mode"
        assert flag.enabled

    def test_get_flag(self):
        store = FeatureFlagStore()
        store.create("feature-x", enabled=False)
        flag = store.get("feature-x")
        assert flag is not None
        assert not flag.enabled

    def test_is_enabled_global(self):
        store = FeatureFlagStore()
        store.create("feature-x", enabled=True)
        assert store.is_enabled("feature-x") is True

    def test_is_enabled_disabled(self):
        store = FeatureFlagStore()
        store.create("feature-x", enabled=False)
        assert store.is_enabled("feature-x") is False

    def test_tenant_override(self):
        store = FeatureFlagStore()
        store.create("feature-x", enabled=False)
        store.set_tenant_override("feature-x", "tenant-1", True)
        assert store.is_enabled("feature-x", tenant_id="tenant-1") is True
        assert store.is_enabled("feature-x", tenant_id="tenant-2") is False

    def test_percentage_rollout(self):
        store = FeatureFlagStore()
        store.create("gradual", enabled=True, rollout_percentage=50)
        result = store.is_enabled("gradual", tenant_id="test-tenant")
        assert isinstance(result, bool)

    def test_unknown_flag_returns_false(self):
        store = FeatureFlagStore()
        assert store.is_enabled("nonexistent") is False

    def test_list_flags(self):
        store = FeatureFlagStore()
        store.create("a", enabled=True)
        store.create("b", enabled=False)
        flags = store.list_all()
        assert len(flags) == 2
