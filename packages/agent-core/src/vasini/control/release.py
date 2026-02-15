"""Release management — draft->validated->staged->prod state machine.

Promotion rules:
  draft -> validated: eval_score >= 0.85
  validated -> staged: manual promotion
  staged -> prod: requires approved_by (Platform Lead sign-off)

Rollback: any stage except DRAFT -> ROLLED_BACK
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ReleaseStage(Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    STAGED = "staged"
    PROD = "prod"
    ROLLED_BACK = "rolled_back"


class RollbackReason(Enum):
    SLO_BREACH = "slo_breach"
    ERROR_RATE = "error_rate"
    BUDGET_EXCEEDED = "budget_exceeded"
    MANUAL = "manual"
    INCIDENT = "incident"


_PROMOTION_ORDER = [ReleaseStage.DRAFT, ReleaseStage.VALIDATED, ReleaseStage.STAGED, ReleaseStage.PROD]


@dataclass
class Release:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pack_id: str = ""
    version: str = ""
    stage: ReleaseStage = ReleaseStage.DRAFT
    eval_score: float | None = None
    approved_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PromotionResult:
    success: bool
    new_stage: ReleaseStage | None = None
    reason: str = ""


@dataclass
class RollbackResult:
    success: bool
    reason: str = ""


class ReleaseManager:
    MIN_EVAL_SCORE = 0.85

    def __init__(self) -> None:
        self._releases: dict[str, Release] = {}

    def create_release(self, pack_id: str, version: str) -> Release:
        release = Release(
            id=str(uuid.uuid4()),
            pack_id=pack_id,
            version=version,
            stage=ReleaseStage.DRAFT,
        )
        self._releases[release.id] = release
        return release

    def get_release(self, release_id: str) -> Release | None:
        return self._releases.get(release_id)

    def promote(
        self,
        release_id: str,
        eval_score: float | None = None,
        approved_by: str | None = None,
    ) -> PromotionResult:
        release = self._releases.get(release_id)
        if not release:
            return PromotionResult(success=False, reason="Release not found")

        current_idx = _PROMOTION_ORDER.index(release.stage) if release.stage in _PROMOTION_ORDER else -1
        if current_idx < 0 or current_idx >= len(_PROMOTION_ORDER) - 1:
            return PromotionResult(success=False, reason=f"Cannot promote from {release.stage.value}")

        next_stage = _PROMOTION_ORDER[current_idx + 1]

        # Promotion rules
        if release.stage == ReleaseStage.DRAFT:
            if eval_score is None or eval_score < self.MIN_EVAL_SCORE:
                return PromotionResult(
                    success=False,
                    reason=f"Score {eval_score} below minimum {self.MIN_EVAL_SCORE}",
                )
            release.eval_score = eval_score

        if next_stage == ReleaseStage.PROD:
            if not approved_by:
                return PromotionResult(success=False, reason="Production promotion requires approval")
            release.approved_by = approved_by

        release.stage = next_stage
        release.updated_at = datetime.now(timezone.utc)
        return PromotionResult(success=True, new_stage=next_stage)

    def rollback(self, release_id: str, reason: RollbackReason) -> RollbackResult:
        release = self._releases.get(release_id)
        if not release:
            return RollbackResult(success=False, reason="Release not found")
        if release.stage == ReleaseStage.DRAFT:
            return RollbackResult(success=False, reason="Cannot rollback a draft release")
        release.stage = ReleaseStage.ROLLED_BACK
        release.updated_at = datetime.now(timezone.utc)
        return RollbackResult(success=True)

    def get_current_prod(self, pack_id: str) -> Release | None:
        for r in self._releases.values():
            if r.pack_id == pack_id and r.stage == ReleaseStage.PROD:
                return r
        return None

    def list_releases(self, pack_id: str) -> list[Release]:
        return [r for r in self._releases.values() if r.pack_id == pack_id]
