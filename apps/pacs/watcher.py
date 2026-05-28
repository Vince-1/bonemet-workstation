"""Directory watcher: poll a watch_dir for new .dcm files, stage into incoming/, then ingest.

Usage:
    python -m apps.pacs.watcher --watch-dir /mnt/pacs_export/bone_scan
    python -m apps.pacs.watcher  # reads from config
"""
from __future__ import annotations

import argparse
import logging
import shutil
import signal
import sys
import time
from pathlib import Path
from typing import Any

import pydicom

from bonemet_core.settings import load_config

from apps.pacs.incoming import (
    file_is_stable,
    incoming_root,
    set_status,
    study_dir,
    write_meta,
)
from apps.pacs.ingester import process_one_study

logger = logging.getLogger("bonemet.pacs.watcher")

_running = True


def _stop(*_: Any) -> None:
    global _running
    _running = False
    logger.info("watcher shutting down …")


def _read_study_uid(dcm_path: Path) -> str:
    """Read StudyInstanceUID from DICOM without loading pixel data."""
    ds = pydicom.dcmread(str(dcm_path), force=True, stop_before_pixels=True)
    uid = str(getattr(ds, "StudyInstanceUID", "") or "").strip()
    return uid or dcm_path.stem


def _discover_new_dcms(watch_dir: Path, seen: set[Path]) -> list[Path]:
    found: list[Path] = []
    for p in watch_dir.rglob("*"):
        if p.suffix.lower() == ".dcm" and p.is_file() and p not in seen:
            found.append(p)
    return found


def _stage_file(data_root: Path, dcm_path: Path, *, settle_sec: float = 5.0) -> Path | None:
    """Copy a stable .dcm to incoming/{study_uid}/ and return the study dir."""
    if not file_is_stable(dcm_path, settle_sec):
        logger.debug("file not stable yet: %s", dcm_path)
        return None
    try:
        uid = _read_study_uid(dcm_path)
    except Exception as e:
        logger.warning("cannot read DICOM header from %s: %s", dcm_path, e)
        return None
    sdir = study_dir(data_root, uid)
    dest = sdir / dcm_path.name
    if not dest.exists():
        shutil.copy2(dcm_path, dest)
        logger.info("staged %s → %s", dcm_path.name, sdir.name)
    write_meta(sdir, source="watcher", watch_path=str(dcm_path))
    set_status(sdir, "pending")
    return sdir


def run_watcher(
    data_root: Path,
    watch_dir: Path,
    *,
    poll_interval: float = 10.0,
    settle_sec: float = 5.0,
    run_pipeline: bool = True,
    ingest_delay: float = 10.0,
) -> None:
    """Main polling loop."""
    logger.info("watching %s  (poll=%.0fs, settle=%.0fs)", watch_dir, poll_interval, settle_sec)
    watch_dir.mkdir(parents=True, exist_ok=True)
    incoming_root(data_root)

    seen: set[Path] = set()
    pending_studies: dict[str, float] = {}

    while _running:
        new_files = _discover_new_dcms(watch_dir, seen)
        for f in new_files:
            seen.add(f)
            sdir = _stage_file(data_root, f, settle_sec=settle_sec)
            if sdir and sdir.name not in pending_studies:
                pending_studies[sdir.name] = time.monotonic() + ingest_delay

        ready = [uid for uid, t in pending_studies.items() if time.monotonic() >= t]
        for uid in ready:
            del pending_studies[uid]
            sdir = incoming_root(data_root) / uid
            if sdir.is_dir():
                result = process_one_study(data_root, sdir, run_pipeline=run_pipeline)
                logger.info("ingest result for %s: %s", uid, result.get("status"))

        time.sleep(poll_interval)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    cfg = load_config()
    data_root: Path = cfg["_resolved"]["data_root"]
    pacs_cfg = cfg.get("pacs", {}).get("watcher", {})

    parser = argparse.ArgumentParser(description="BoneMet PACS directory watcher")
    parser.add_argument("--watch-dir", type=str, default=pacs_cfg.get("watch_dir", ""))
    parser.add_argument("--poll-interval", type=float, default=pacs_cfg.get("poll_interval_sec", 10))
    parser.add_argument("--settle-sec", type=float, default=pacs_cfg.get("settle_sec", 5))
    parser.add_argument("--no-pipeline", action="store_true")
    args = parser.parse_args()

    watch_dir_str = args.watch_dir
    if not watch_dir_str:
        print("错误: 未指定 watch_dir，请通过 --watch-dir 参数或 config pacs.watcher.watch_dir 配置", file=sys.stderr)
        sys.exit(1)

    run_watcher(
        data_root,
        Path(watch_dir_str),
        poll_interval=args.poll_interval,
        settle_sec=args.settle_sec,
        run_pipeline=not args.no_pipeline,
    )


if __name__ == "__main__":
    main()
