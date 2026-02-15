"""Pack Registry — immutable artifact store.

Publish: validates manifest, stores artifact, rejects duplicate versions.
No Sigstore verification in MVP — signature stored as metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

_REQUIRED_MANIFEST_FIELDS = ["schema_version", "pack_id", "risk_level"]


@dataclass
class PackArtifact:
    pack_id: str
    version: str
    manifest: dict
    layers: dict[str, str]
    author: str
    signature: str = ""
    published_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PackNotFoundError(Exception):
    pass


class VersionConflictError(Exception):
    pass


@dataclass
class PublishResult:
    success: bool
    version: str = ""
    reason: str = ""


class PackRegistry:
    def __init__(self) -> None:
        self._artifacts: dict[str, dict[str, PackArtifact]] = {}

    def publish(
        self,
        pack_id: str,
        version: str,
        manifest: dict,
        layers: dict[str, str],
        author: str,
        signature: str = "",
    ) -> PublishResult:
        missing = [f for f in _REQUIRED_MANIFEST_FIELDS if f not in manifest]
        if missing:
            return PublishResult(success=False, reason=f"Missing required fields: {', '.join(missing)}")

        if pack_id in self._artifacts and version in self._artifacts[pack_id]:
            return PublishResult(success=False, reason=f"Version {version} already exists (immutable)")

        artifact = PackArtifact(
            pack_id=pack_id,
            version=version,
            manifest=manifest,
            layers=dict(layers),
            author=author,
            signature=signature,
        )

        if pack_id not in self._artifacts:
            self._artifacts[pack_id] = {}
        self._artifacts[pack_id][version] = artifact

        return PublishResult(success=True, version=version)

    def get(self, pack_id: str, version: str) -> PackArtifact | None:
        return self._artifacts.get(pack_id, {}).get(version)

    def get_latest(self, pack_id: str) -> PackArtifact | None:
        versions = self._artifacts.get(pack_id, {})
        if not versions:
            return None
        latest_version = sorted(versions.keys())[-1]
        return versions[latest_version]

    def list_versions(self, pack_id: str) -> list[str]:
        return sorted(self._artifacts.get(pack_id, {}).keys())
