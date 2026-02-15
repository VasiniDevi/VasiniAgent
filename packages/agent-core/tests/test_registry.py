"""Tests for Pack Registry — publish, validate, version lookup."""

import pytest
from vasini.registry.store import (
    PackRegistry, PackArtifact, PublishResult,
    PackNotFoundError, VersionConflictError,
)


class TestPackRegistry:
    def test_publish_pack(self):
        registry = PackRegistry()
        result = registry.publish(
            pack_id="senior-python-dev",
            version="1.0.0",
            manifest={"schema_version": "1.0", "pack_id": "senior-python-dev", "risk_level": "medium"},
            layers={"soul": "content", "role": "content"},
            author="test-author",
        )
        assert result.success
        assert result.version == "1.0.0"

    def test_publish_validates_required_fields(self):
        registry = PackRegistry()
        result = registry.publish(
            pack_id="bad-pack",
            version="1.0.0",
            manifest={},
            layers={},
            author="test",
        )
        assert not result.success
        assert "schema_version" in result.reason.lower() or "pack_id" in result.reason.lower()

    def test_publish_same_version_rejected(self):
        registry = PackRegistry()
        registry.publish(
            pack_id="pack-1", version="1.0.0",
            manifest={"schema_version": "1.0", "pack_id": "pack-1", "risk_level": "low"},
            layers={"soul": "v1"}, author="a",
        )
        result = registry.publish(
            pack_id="pack-1", version="1.0.0",
            manifest={"schema_version": "1.0", "pack_id": "pack-1", "risk_level": "low"},
            layers={"soul": "v1-modified"}, author="a",
        )
        assert not result.success
        assert "immutable" in result.reason.lower() or "exists" in result.reason.lower()

    def test_get_artifact(self):
        registry = PackRegistry()
        registry.publish(
            pack_id="pack-1", version="1.0.0",
            manifest={"schema_version": "1.0", "pack_id": "pack-1", "risk_level": "low"},
            layers={"soul": "content"}, author="author-1",
        )
        artifact = registry.get("pack-1", "1.0.0")
        assert artifact is not None
        assert artifact.pack_id == "pack-1"
        assert artifact.version == "1.0.0"
        assert artifact.author == "author-1"

    def test_get_nonexistent_returns_none(self):
        registry = PackRegistry()
        assert registry.get("nonexistent", "1.0.0") is None

    def test_get_latest(self):
        registry = PackRegistry()
        for v in ["1.0.0", "1.1.0", "2.0.0"]:
            registry.publish(
                pack_id="pack-1", version=v,
                manifest={"schema_version": "1.0", "pack_id": "pack-1", "risk_level": "low"},
                layers={"soul": f"v{v}"}, author="a",
            )
        latest = registry.get_latest("pack-1")
        assert latest is not None
        assert latest.version == "2.0.0"

    def test_list_versions(self):
        registry = PackRegistry()
        for v in ["1.0.0", "1.1.0", "2.0.0"]:
            registry.publish(
                pack_id="pack-1", version=v,
                manifest={"schema_version": "1.0", "pack_id": "pack-1", "risk_level": "low"},
                layers={}, author="a",
            )
        versions = registry.list_versions("pack-1")
        assert versions == ["1.0.0", "1.1.0", "2.0.0"]

    def test_list_versions_empty(self):
        registry = PackRegistry()
        assert registry.list_versions("unknown") == []

    def test_artifact_is_immutable(self):
        registry = PackRegistry()
        registry.publish(
            pack_id="pack-1", version="1.0.0",
            manifest={"schema_version": "1.0", "pack_id": "pack-1", "risk_level": "low"},
            layers={"soul": "original"}, author="a",
        )
        artifact = registry.get("pack-1", "1.0.0")
        assert artifact.layers["soul"] == "original"

    def test_signature_field_stored(self):
        registry = PackRegistry()
        registry.publish(
            pack_id="pack-1", version="1.0.0",
            manifest={"schema_version": "1.0", "pack_id": "pack-1", "risk_level": "low"},
            layers={}, author="a", signature="sig-abc-123",
        )
        artifact = registry.get("pack-1", "1.0.0")
        assert artifact.signature == "sig-abc-123"
