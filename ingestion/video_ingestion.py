"""
ingestion/video_ingestion.py

Pipeline — YouTube videos → Chroma vector DB (video_db)

Flow:
  YouTube URL list
      ↓  youtube-transcript-api
  Timestamped transcript segments + metadata
      ↓  RecursiveCharacterTextSplitter
  Chunks (400 tok, 50 overlap)
      ↓  OpenAIEmbeddings (text-embedding-3-small)
  Chroma collection: adas_videos

Metadata stored per chunk:
  - video_id       : YouTube video ID (e.g. "dQw4w9WgXcQ")
  - title          : video title
  - channel        : channel name
  - url            : full YouTube URL
  - timestamp_start: start time of chunk in video (seconds)
  - timestamp_end  : end time of chunk in video (seconds)
  - source         : "youtube"
  - category       : e.g. "adas", "perception", "planning"
  - tags           : comma-separated topics, e.g. "perception,imitation_learning"
"""

import os
import re
import csv
import logging
from pathlib import Path
from typing import Optional
from tqdm import tqdm

from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.schema import Document
from youtube_transcript_api import YouTubeTranscriptApi

from config import PROJECT_DIR, cfg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

LOCAL_TRANSCRIPT_DIR = PROJECT_DIR / "transcripts"
VIDEO_CATALOG_PATH = PROJECT_DIR / "videos.csv"


# ── Fallback/example video list ──────────────────────────────────────────────
# Main project metadata should live in videos.csv. The ingestion pipeline loads
# videos.csv first and uses this list only if videos.csv is missing or empty.
#
# This list is intentionally kept as a small starter/example for future users
# who want to try the video pipeline before creating a full videos.csv catalog.
# It is also used by ingestion/whisper_transcription.py when running --all.
# The current URL/channel/category/tag values below are example metadata only;
# for the real project database, maintain the complete video information in
# videos.csv instead.
#
# Format: { "url": "...", "channel": "...", "category": "...", "tags": "..." }
TARGET_VIDEOS = [
    # ADAS & Autonomous Driving fundamentals
    {
        "url": "https://www.youtube.com/watch?v=Z8C2vn1VVzU&t=315s",
        "channel": "Waymo",
        "category": "robotaxi_safety",
        "tags": "robotaxi,driverless,operational_safety",
    },
    {
        "url": "https://www.youtube.com/watch?v=j0z4FweCy4M",
        "channel": "Tesla",
        "category": "camera_only_perception",
        "tags": "vision,neural_networks,occupancy",
    },
    {
        "url": "https://www.youtube.com/watch?v=hx7BXih7zx8",
        "channel": "Andrej Karpathy",
        "category": "perception",
        "tags": "imitation_learning,deep_learning,computer_vision",
    },
    {
        "url": "https://www.youtube.com/watch?v=IHH47nZ7FZU",
        "channel": "MIT OpenCourseWare",
        "category": "autonomous_driving_lecture",
        "tags": "planning,perception,control",
    },
    {
        "url": "https://www.youtube.com/watch?v=Q0nGo2-y0xY",
        "channel": "Mobileye",
        "category": "safety_model",
        "tags": "rss,safety_model,formal_rules",
    },
    # Add more here ↓
]


def load_video_catalog(catalog_path: Path = VIDEO_CATALOG_PATH) -> list[dict]:
    """Load videos from videos.csv if it exists; otherwise use TARGET_VIDEOS."""
    if not catalog_path.exists():
        return TARGET_VIDEOS

    videos: list[dict] = []
    with catalog_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            url = (row.get("url") or "").strip()
            video_id = (row.get("video_id") or "").strip()
            if not url and video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
            if not url:
                continue

            videos.append(
                {
                    "url": url,
                    "channel": (row.get("channel") or "Unknown").strip() or "Unknown",
                    "category": (row.get("category") or "uncategorized").strip() or "uncategorized",
                    "tags": (row.get("tags") or "").strip(),
                    "title": (row.get("title") or "").strip(),
                    "notes": (row.get("notes") or "").strip(),
                }
            )

    return videos or TARGET_VIDEOS


def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from any YouTube URL format."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def _timestamp_to_seconds(timestamp: str) -> float:
    """Convert a VTT timestamp such as 00:01:23.456 to seconds."""
    parts = timestamp.replace(",", ".").split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    return float(parts[0])


def _load_local_transcript(
    video_id: str,
    url: str,
    channel: str,
    category: str,
    title: str | None = None,
    tags: str = "",
    notes: str = "",
) -> list[Document]:
    """
    Load a local transcript fallback from transcripts/{video_id}.vtt or .txt.

    This is useful when YouTube rate-limits transcript requests. You can download
    or paste transcripts into the local transcripts directory and still run the
    same vector ingestion pipeline.
    """
    vtt_path = LOCAL_TRANSCRIPT_DIR / f"{video_id}.vtt"
    txt_path = LOCAL_TRANSCRIPT_DIR / f"{video_id}.txt"
    local_vtt_candidates = [vtt_path, *sorted(LOCAL_TRANSCRIPT_DIR.glob(f"{video_id}*.vtt"))]
    local_txt_candidates = [txt_path, *sorted(LOCAL_TRANSCRIPT_DIR.glob(f"{video_id}*.txt"))]

    def metadata(start: float, end: float) -> dict:
        return {
            "video_id": video_id,
            "url": url,
            "channel": channel,
            "category": category,
            "tags": tags,
            "notes": notes,
            "source": "local_transcript",
            "title": title or f"{channel} video {video_id}",
            "timestamp_start": start,
            "timestamp_end": end,
        }

    vtt_source = next((path for path in local_vtt_candidates if path.exists()), None)
    if vtt_source:
        docs: list[Document] = []
        current_start: float | None = None
        current_end: float | None = None
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_start, current_end, current_lines
            text = " ".join(current_lines).strip()
            if text and current_start is not None and current_end is not None:
                docs.append(Document(page_content=text, metadata=metadata(current_start, current_end)))
            current_start = None
            current_end = None
            current_lines = []

        for raw_line in vtt_source.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")):
                flush()
                continue
            if "-->" in line:
                flush()
                start_text, end_text = line.split("-->", 1)
                current_start = _timestamp_to_seconds(start_text.strip())
                current_end = _timestamp_to_seconds(end_text.strip().split()[0])
                continue
            if current_start is not None:
                current_lines.append(re.sub(r"<[^>]+>", "", line))

        flush()
        log.info(f"Loaded local VTT transcript: {vtt_source} ({len(docs)} segments)")
        return docs

    txt_source = next((path for path in local_txt_candidates if path.exists()), None)
    if txt_source:
        text = txt_source.read_text(encoding="utf-8").strip()
        if text:
            log.info(f"Loaded local text transcript: {txt_source}")
            return [Document(page_content=text, metadata=metadata(0, 0))]

    raise FileNotFoundError(
        f"No transcript available for {video_id}. Tried YouTube and local files: "
        f"{vtt_path} or {txt_path}"
    )


def load_transcript(
    url: str,
    channel: str,
    category: str,
    title: str | None = None,
    tags: str = "",
    notes: str = "",
) -> list[Document]:
    """
    Load timestamped transcript segments from YouTube.

    Local transcript files are preferred because they may be Whisper-generated
    and higher quality than auto captions. If no local transcript exists, the
    loader falls back to youtube-transcript-api.
    """
    video_id = extract_video_id(url)

    try:
        return _load_local_transcript(
            video_id,
            url,
            channel,
            category,
            title=title,
            tags=tags,
            notes=notes,
        )
    except FileNotFoundError:
        pass

    try:
        transcript_api = YouTubeTranscriptApi()
        transcript = transcript_api.fetch(video_id, languages=["en"]).to_raw_data()
    except Exception as exc:
        log.warning(
            "YouTube transcript fetch failed for %s (%s). Trying local transcript fallback.",
            video_id,
            exc.__class__.__name__,
        )
        return _load_local_transcript(
            video_id,
            url,
            channel,
            category,
            title=title,
            tags=tags,
            notes=notes,
        )

    docs = []
    for segment in transcript:
        start = float(segment.get("start", 0))
        duration = float(segment.get("duration", 0))
        text = segment.get("text", "").strip()
        if not text:
            continue

        docs.append(
            Document(
                page_content=text,
                metadata={
                    "video_id": video_id,
                    "url": url,
                    "channel": channel,
                    "category": category,
                    "tags": tags,
                    "notes": notes,
                    "source": "youtube",
                    "title": title or f"{channel} video {video_id}",
                    "timestamp_start": start,
                    "timestamp_end": start + duration,
                },
            )
        )

    log.info(f"Loaded transcript: {channel} {video_id} ({len(docs)} segments)")
    return docs


def chunk_documents(docs: list[Document]) -> list[Document]:
    """Group timestamped transcript segments into retrieval-sized chunks."""
    if not docs:
        return []

    chunks: list[Document] = []
    current_text: list[str] = []
    current_start = docs[0].metadata["timestamp_start"]
    current_end = docs[0].metadata["timestamp_end"]
    base_meta = docs[0].metadata.copy()

    def flush() -> None:
        if not current_text:
            return
        metadata = base_meta.copy()
        metadata["timestamp_start"] = current_start
        metadata["timestamp_end"] = current_end
        chunks.append(Document(page_content=" ".join(current_text), metadata=metadata))

    for doc in docs:
        segment_text = doc.page_content
        proposed_length = len(" ".join([*current_text, segment_text]))

        if current_text and proposed_length > cfg.VIDEO_CHUNK_SIZE:
            flush()

            overlap_text = " ".join(current_text)[-cfg.VIDEO_CHUNK_OVERLAP :].strip()
            current_text = [overlap_text, segment_text] if overlap_text else [segment_text]
            current_start = doc.metadata["timestamp_start"]
        else:
            current_text.append(segment_text)

        current_end = doc.metadata["timestamp_end"]
        base_meta = doc.metadata.copy()

    flush()
    log.info(f"Split into {len(chunks)} chunks")
    return chunks


def get_vector_store() -> Chroma:
    """Return (or create) the persistent Chroma video collection."""
    os.makedirs(cfg.CHROMA_VIDEO_DB_PATH, exist_ok=True)

    embeddings = OpenAIEmbeddings(
        model=cfg.EMBEDDING_MODEL,
        openai_api_key=cfg.OPENAI_API_KEY,
    )

    return Chroma(
        collection_name=cfg.VIDEO_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=cfg.CHROMA_VIDEO_DB_PATH,
    )


def ingest_videos(
    videos: Optional[list[dict]] = None,
    reset: bool = False,
) -> Chroma:
    """
    Main entry point.

    Args:
        videos : list of video dicts (url, channel, category, optional tags/title/notes).
                 Defaults to TARGET_VIDEOS if None.
        reset  : if True, wipe the collection before ingesting.

    Returns:
        Chroma vector store ready for retrieval.
    """
    cfg.validate()
    videos = videos or load_video_catalog()

    vector_store = get_vector_store()

    if reset:
        log.warning("Resetting video vector store — all existing documents will be deleted.")
        vector_store.delete_collection()
        vector_store = get_vector_store()

    all_chunks: list[Document] = []

    for video in tqdm(videos, desc="Processing videos"):
        try:
            docs = load_transcript(
                url=video["url"],
                channel=video["channel"],
                category=video["category"],
                title=video.get("title"),
                tags=video.get("tags", ""),
                notes=video.get("notes", ""),
            )
            chunks = chunk_documents(docs)
            all_chunks.extend(chunks)
        except Exception as e:
            log.error(f"Failed to process {video['url']}: {e}")
            continue

    if all_chunks:
        # Add in batches to avoid hitting rate limits
        batch_size = 50
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i : i + batch_size]
            vector_store.add_documents(batch)
            log.info(f"Added batch {i // batch_size + 1} ({len(batch)} chunks)")

    log.info(
        f"Video ingestion complete. "
        f"Total chunks stored: {len(all_chunks)} "
        f"in collection '{cfg.VIDEO_COLLECTION_NAME}'"
    )
    return vector_store


def get_retriever(k: int = 4):
    """
    Return a retriever over the video DB.
    k = number of chunks to retrieve per query.
    """
    vector_store = get_vector_store()
    return vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest YouTube videos into the video vector DB")
    parser.add_argument("--reset", action="store_true", help="Wipe DB before ingesting")
    parser.add_argument("--url", type=str, help="Ingest a single video URL")
    parser.add_argument("--channel", type=str, default="Unknown", help="Channel name for single URL")
    parser.add_argument("--category", type=str, default="adas", help="Category for single URL")
    parser.add_argument("--tags", type=str, default="", help="Comma-separated tags for single URL")
    args = parser.parse_args()

    if args.url:
        videos = [
            {
                "url": args.url,
                "channel": args.channel,
                "category": args.category,
                "tags": args.tags,
                "title": "",
                "notes": "",
            }
        ]
    else:
        videos = None  # use default TARGET_VIDEOS

    ingest_videos(videos=videos, reset=args.reset)
