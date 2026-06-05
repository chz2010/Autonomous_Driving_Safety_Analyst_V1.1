"""
ingest_all.py — run both ingestion pipelines in sequence.

Usage:
    python ingest_all.py                   # ingest everything
    python ingest_all.py --reset           # wipe both DBs first
    python ingest_all.py --only videos     # only video pipeline
    python ingest_all.py --only standards  # only standards pipeline
"""

import argparse
import logging
import sys
import time

from config import cfg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def print_banner(title: str) -> None:
    width = 60
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def run(only: str | None = None, reset: bool = False) -> None:
    if sys.version_info >= (3, 13):
        raise RuntimeError(
            "This project should be run with Python 3.11 or 3.12. "
            "Your current Python is "
            f"{sys.version.split()[0]} at {sys.executable}. "
            "Activate the project environment first: source .venv/bin/activate"
        )

    cfg.validate()

    print_banner("ADAS Safety Bot — Ingestion Pipeline")
    print(f"  Embedding model : {cfg.EMBEDDING_MODEL}")
    print(f"  Video DB path   : {cfg.CHROMA_VIDEO_DB_PATH}")
    print(f"  Standards DB    : {cfg.CHROMA_STANDARDS_DB_PATH}")
    print(f"  Reset DBs       : {reset}")

    # ── Video pipeline ───────────────────────────────────
    if only in (None, "videos"):
        from ingestion.video_ingestion import ingest_videos

        print_banner("Step 1 / 2 — YouTube video ingestion")
        t0 = time.time()
        vs_video = ingest_videos(reset=reset)
        elapsed = time.time() - t0
        count = vs_video._collection.count()
        print(f"\n  Video DB ready  : {count} chunks  ({elapsed:.1f}s)")

    # ── Standards pipeline ───────────────────────────────
    if only in (None, "standards"):
        from ingestion.standards_ingestion import ingest_standards

        print_banner("Step 2 / 2 — ISO standards ingestion")
        t0 = time.time()
        vs_standards = ingest_standards(reset=reset)
        elapsed = time.time() - t0
        count = vs_standards._collection.count()
        print(f"\n  Standards DB ready : {count} chunks  ({elapsed:.1f}s)")

    print_banner("Ingestion complete — both vector DBs are ready")
    print("  Next step: python agent/agent.py\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ADAS Safety Bot ingestion pipelines")
    parser.add_argument(
        "--only",
        choices=["videos", "standards"],
        default=None,
        help="Run only one pipeline (default: both)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe existing vector DBs before ingesting",
    )
    args = parser.parse_args()
    run(only=args.only, reset=args.reset)
