"""
utils/db_inspector.py — inspect and test both vector databases.

Usage:
    python utils/db_inspector.py --db videos    --query "sensor fusion ADAS"
    python utils/db_inspector.py --db standards --query "ASIL decomposition"
    python utils/db_inspector.py --db standards --query "AEB" --filter "ISO 26262"
    python utils/db_inspector.py --stats        # print chunk counts for both DBs
"""

import argparse
import sys
from pathlib import Path
from textwrap import shorten

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from ingestion.video_ingestion import get_vector_store as get_video_store
from ingestion.standards_ingestion import get_vector_store as get_standards_store


SEP = "─" * 70


def print_stats() -> None:
    """Print chunk counts and sample metadata for both collections."""
    print(f"\n{'='*70}")
    print("  Vector DB stats")
    print(f"{'='*70}")

    for label, get_store in [
        ("Video DB", get_video_store),
        ("Standards DB", get_standards_store),
    ]:
        store = get_store()
        count = store._collection.count()
        print(f"\n  {label}  →  {count} chunks")

        if count > 0:
            # Peek at first 3 items
            sample = store._collection.get(limit=3, include=["metadatas", "documents"])
            for i, (doc, meta) in enumerate(zip(sample["documents"], sample["metadatas"])):
                print(f"\n    [{i+1}] {shorten(doc, 80, placeholder='…')}")
                for k, v in meta.items():
                    print(f"         {k:<18}: {v}")


def search(db: str, query: str, k: int = 4, filter_standard: str | None = None) -> None:
    """Run a similarity search and pretty-print results."""
    print(f"\n{SEP}")
    print(f"  DB        : {db}")
    print(f"  Query     : {query}")
    if filter_standard:
        print(f"  Filter    : standard = '{filter_standard}'")
    print(f"  Top-k     : {k}")
    print(SEP)

    if db == "videos":
        from ingestion.video_ingestion import get_retriever
        retriever = get_retriever(k=k)
    else:
        from ingestion.standards_ingestion import get_retriever
        retriever = get_retriever(k=k, filter_standard=filter_standard)

    results = retriever.invoke(query)

    if not results:
        print("  No results found.")
        return

    for i, doc in enumerate(results, 1):
        print(f"\n  Result {i}")
        print(f"  {'─'*50}")

        # Print metadata based on DB type
        meta = doc.metadata
        if db == "videos":
            print(f"  Title    : {meta.get('title', 'N/A')}")
            print(f"  Channel  : {meta.get('channel', 'N/A')}")
            print(f"  Category : {meta.get('category', 'N/A')}")
            print(f"  Tags     : {meta.get('tags', 'N/A')}")
            ts = meta.get('timestamp_start', 0)
            url = meta.get('url', '')
            if url and ts:
                print(f"  Link     : {url}&t={int(ts)}s")
        else:
            print(f"  Standard : {meta.get('standard', 'N/A')}")
            print(f"  Part     : {meta.get('part', 'N/A')}")
            print(f"  Clause   : {meta.get('clause', 'N/A')}")
            print(f"  Section  : {meta.get('section_title', 'N/A')}")
            print(f"  ASIL     : {meta.get('asil_level', 'N/A')}")
            print(f"  Page     : {meta.get('page', 'N/A')}")

        print(f"\n  Content  : {shorten(doc.page_content, 300, placeholder='…')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect vector databases")
    parser.add_argument("--stats", action="store_true", help="Print DB stats")
    parser.add_argument("--db", choices=["videos", "standards"], help="Which DB to search")
    parser.add_argument("--query", type=str, help="Search query")
    parser.add_argument("--k", type=int, default=4, help="Number of results")
    parser.add_argument("--filter", type=str, dest="filter_standard",
                        help="Filter by standard name, e.g. 'ISO 26262'")
    args = parser.parse_args()

    if args.stats:
        print_stats()
    elif args.db and args.query:
        search(args.db, args.query, k=args.k, filter_standard=args.filter_standard)
    else:
        parser.print_help()
