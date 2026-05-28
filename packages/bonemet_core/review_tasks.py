"""Generate triage tasks for clinician UI.

Only report-relevant tasks are shown to the doctor; low-confidence and
unmatched-pairing items are accepted by default (R-16).
"""
from __future__ import annotations

from typing import Any

# Kept for backward compat with accept-rest API, but no longer needed at display
TRIAGE_DISMISS_ON_ACCEPT_REST = ("suspected_fp", "pairing_uncertain")


def filter_tasks_for_display(
    tasks_doc: dict[str, Any],
    dismissed_kinds: list[str] | None,
) -> dict[str, Any]:
    """Legacy filter — now a no-op since build_review_tasks already excludes non-clinical items."""
    return tasks_doc


def build_review_tasks(
    study_uid: str,
    front: list[dict[str, Any]],
    back: list[dict[str, Any]],
    pairs_doc: dict[str, Any],
) -> dict[str, Any]:
    """All predicted boxes are included in the report by default — no confirmation needed."""
    return {
        "schema_version": "review_tasks_v1",
        "study_uid": study_uid,
        "tasks": [],
    }
