"""Process pipeline jobs from data/queue/pending.jsonl."""
from __future__ import annotations

import logging
import time

from bonemet_core.pipeline import run_case_pipeline
from bonemet_core.queue import pop_next_job
from bonemet_core.settings import load_config
from bonemet_core.storage.case_bundle import case_dir, read_json, write_meta
from bonemet_core.validate import require_models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bonemet.worker")


def main() -> None:
    cfg = load_config()
    data_root = cfg["_resolved"]["data_root"]
    require_models(data_root)
    logger.info("worker started data_root=%s (models OK)", data_root)

    while True:
        job = pop_next_job(data_root)
        if not job:
            time.sleep(2)
            continue
        if job.get("type") != "pipeline":
            logger.warning("unknown job %s", job)
            continue
        uid = job["study_uid"]
        try:
            result = run_case_pipeline(
                data_root, uid, cfg, reset_review=bool(job.get("reset_review"))
            )
            logger.info("pipeline done %s %s", uid, result)
        except Exception:
            logger.exception("pipeline failed %s", uid)
            try:
                meta_path = case_dir(data_root, uid) / "meta.json"
                if meta_path.is_file():
                    meta = read_json(meta_path)
                    meta["pipeline_status"] = "failed"
                    write_meta(data_root, uid, meta)
            except Exception:
                logger.exception("failed to update meta for %s", uid)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
