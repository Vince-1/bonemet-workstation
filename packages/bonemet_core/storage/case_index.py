"""SQLite index for case list (fast worklist; case_bundle remains source of truth)."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from bonemet_core.storage.case_bundle import case_dir, read_json


def index_db_path(data_root: Path) -> Path:
    p = data_root / "cases" / "index.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect(data_root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(index_db_path(data_root)))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(data_root: Path) -> None:
    with _connect(data_root) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                study_uid TEXT PRIMARY KEY,
                patient_display_id TEXT,
                status TEXT,
                pipeline_status TEXT,
                review_task_count INTEGER DEFAULT 0,
                rev INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cases_updated ON cases(updated_at DESC)")
        conn.commit()


def upsert_case(data_root: Path, meta: dict[str, Any]) -> None:
    uid = meta.get("study_uid")
    if not uid:
        return
    init_db(data_root)
    with _connect(data_root) as conn:
        conn.execute(
            """
            INSERT INTO cases (
                study_uid, patient_display_id, status, pipeline_status,
                review_task_count, rev, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(study_uid) DO UPDATE SET
                patient_display_id=excluded.patient_display_id,
                status=excluded.status,
                pipeline_status=excluded.pipeline_status,
                review_task_count=excluded.review_task_count,
                rev=excluded.rev,
                created_at=COALESCE(cases.created_at, excluded.created_at),
                updated_at=excluded.updated_at
            """,
            (
                uid,
                meta.get("patient_display_id"),
                meta.get("status"),
                meta.get("pipeline_status"),
                int(meta.get("review_task_count") or 0),
                int(meta.get("rev") or 0),
                meta.get("created_at"),
                meta.get("updated_at"),
            ),
        )
        conn.commit()


def delete_case(data_root: Path, study_uid: str) -> None:
    init_db(data_root)
    with _connect(data_root) as conn:
        conn.execute("DELETE FROM cases WHERE study_uid = ?", (study_uid,))
        conn.commit()


def list_cases(
    data_root: Path,
    *,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    init_db(data_root)
    sql = "SELECT * FROM cases"
    params: list[Any] = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    sql += " ORDER BY updated_at DESC, study_uid DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(int(limit))
    with _connect(data_root) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def _row_from_meta(meta: dict[str, Any]) -> tuple:
    return (
        meta.get("study_uid"),
        meta.get("patient_display_id"),
        meta.get("status"),
        meta.get("pipeline_status"),
        int(meta.get("review_task_count") or 0),
        int(meta.get("rev") or 0),
        meta.get("created_at"),
        meta.get("updated_at"),
    )


def rebuild_from_disk(data_root: Path) -> int:
    """Scan case_bundle/ and refresh index. Returns number of cases indexed."""
    root = data_root / "cases" / "case_bundle"
    init_db(data_root)
    n = 0
    with _connect(data_root) as conn:
        conn.execute("DELETE FROM cases")
        if root.is_dir():
            for d in sorted(root.iterdir()):
                if not d.is_dir() or not (d / "meta.json").is_file():
                    continue
                meta = read_json(d / "meta.json")
                meta.setdefault("study_uid", d.name)
                conn.execute(
                    """
                    INSERT INTO cases (
                        study_uid, patient_display_id, status, pipeline_status,
                        review_task_count, rev, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _row_from_meta(meta),
                )
                n += 1
        conn.commit()
    return n


def ensure_index(data_root: Path) -> None:
    """If index empty but bundles exist, rebuild once."""
    init_db(data_root)
    root = data_root / "cases" / "case_bundle"
    if not root.is_dir():
        return
    with _connect(data_root) as conn:
        count = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    if count == 0 and any(root.iterdir()):
        rebuild_from_disk(data_root)
