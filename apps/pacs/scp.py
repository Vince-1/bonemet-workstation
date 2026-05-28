"""DICOM C-STORE SCP: receive studies pushed from PACS.

Usage:
    python -m apps.pacs.scp
    python -m apps.pacs.scp --port 11112 --ae-title BONEMET
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

from pynetdicom import AE, evt
from pynetdicom.sop_class import (
    NuclearMedicineImageStorage,
    SecondaryCaptureImageStorage,
)

from bonemet_core.settings import load_config

from apps.pacs.incoming import (
    incoming_root,
    set_status,
    study_dir,
    write_meta,
)
from apps.pacs.ingester import process_one_study

logger = logging.getLogger("bonemet.pacs.scp")

_INGEST_DELAY = 10.0


class SCPServer:
    def __init__(
        self,
        data_root: Path,
        *,
        ae_title: str = "BONEMET",
        port: int = 11112,
        run_pipeline: bool = True,
    ) -> None:
        self.data_root = data_root
        self.ae_title = ae_title
        self.port = port
        self.run_pipeline = run_pipeline

        self._pending_lock = threading.Lock()
        self._pending_studies: dict[str, float] = {}
        self._running = True
        self._ae: AE | None = None
        self._ingest_thread: threading.Thread | None = None

    def _handle_store(self, event: Any) -> int:
        """Handle incoming C-STORE request."""
        ds = event.dataset
        ds.file_meta = event.file_meta

        study_uid = str(getattr(ds, "StudyInstanceUID", "") or "").strip()
        sop_uid = str(getattr(ds, "SOPInstanceUID", "") or "").strip()
        calling_ae = str(getattr(event.assoc, "requestor", None) or "").strip()
        if hasattr(event.assoc, "requestor") and hasattr(event.assoc.requestor, "ae_title"):
            calling_ae = event.assoc.requestor.ae_title.strip()

        if not study_uid:
            study_uid = sop_uid or "UNKNOWN"

        sdir = study_dir(self.data_root, study_uid)
        dest = sdir / f"{sop_uid}.dcm"
        ds.save_as(str(dest), write_like_original=False)
        write_meta(sdir, source="scp", calling_ae=calling_ae)
        set_status(sdir, "pending")

        logger.info("received %s/%s from %s", study_uid[:12], sop_uid[:12], calling_ae or "?")

        with self._pending_lock:
            self._pending_studies[study_uid] = time.monotonic() + _INGEST_DELAY

        return 0x0000  # Success

    def _ingest_loop(self) -> None:
        """Background thread: ingest studies after delay."""
        while self._running:
            ready: list[str] = []
            with self._pending_lock:
                now = time.monotonic()
                ready = [uid for uid, t in self._pending_studies.items() if now >= t]
                for uid in ready:
                    del self._pending_studies[uid]

            for uid in ready:
                sdir = incoming_root(self.data_root) / uid
                if sdir.is_dir():
                    result = process_one_study(self.data_root, sdir, run_pipeline=self.run_pipeline)
                    logger.info("ingest result for %s: %s", uid[:12], result.get("status"))

            time.sleep(2.0)

    def start(self) -> None:
        ae = AE(ae_title=self.ae_title)

        transfer_syntaxes = [
            "1.2.840.10008.1.2",       # Implicit VR Little Endian
            "1.2.840.10008.1.2.1",     # Explicit VR Little Endian
            "1.2.840.10008.1.2.2",     # Explicit VR Big Endian
        ]
        ae.add_supported_context(NuclearMedicineImageStorage, transfer_syntaxes)
        ae.add_supported_context(SecondaryCaptureImageStorage, transfer_syntaxes)
        # General-purpose: accept any SOP class via the Verification SOP
        ae.add_supported_context("1.2.840.10008.1.1", transfer_syntaxes)

        handlers = [(evt.EVT_C_STORE, self._handle_store)]

        self._ingest_thread = threading.Thread(target=self._ingest_loop, daemon=True)
        self._ingest_thread.start()

        logger.info("SCP starting  AE=%s  port=%d", self.ae_title, self.port)
        self._ae = ae
        ae.start_server(("0.0.0.0", self.port), evt_handlers=handlers, block=True)

    def stop(self) -> None:
        self._running = False
        if self._ae:
            self._ae.shutdown()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    cfg = load_config()
    data_root: Path = cfg["_resolved"]["data_root"]
    scp_cfg = cfg.get("pacs", {}).get("scp", {})

    parser = argparse.ArgumentParser(description="BoneMet DICOM C-STORE SCP")
    parser.add_argument("--port", type=int, default=scp_cfg.get("port", 11112))
    parser.add_argument("--ae-title", type=str, default=scp_cfg.get("ae_title", "BONEMET"))
    parser.add_argument("--no-pipeline", action="store_true")
    args = parser.parse_args()

    server = SCPServer(
        data_root,
        ae_title=args.ae_title,
        port=args.port,
        run_pipeline=not args.no_pipeline,
    )

    def _shutdown(*_: Any) -> None:
        server.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    server.start()


if __name__ == "__main__":
    main()
