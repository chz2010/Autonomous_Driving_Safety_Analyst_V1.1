"""
Download YouTube audio and transcribe it with local Whisper.

Usage:
    python -m ingestion.whisper_transcription --all
    python -m ingestion.whisper_transcription --url "https://www.youtube.com/watch?v=..."
    python -m ingestion.whisper_transcription --all --cookies-from-browser chrome
    python -m ingestion.whisper_transcription --audio-file ./audio/video.mp4 --video-id Q0nGo2-y0xY
    python -m ingestion.whisper_transcription --audio-dir ./audio

Outputs:
    audio/{video_id}.m4a
    transcripts/{video_id}.txt
    transcripts/{video_id}.vtt
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable

import imageio_ffmpeg
import whisper
import yt_dlp

from ingestion.video_ingestion import TARGET_VIDEOS, extract_video_id


PROJECT_DIR = Path(__file__).resolve().parents[1]
AUDIO_DIR = PROJECT_DIR / "audio"
TRANSCRIPT_DIR = PROJECT_DIR / "transcripts"
BIN_DIR = PROJECT_DIR / ".bin"
SUPPORTED_AUDIO_SUFFIXES = {".mp3", ".m4a", ".webm", ".wav", ".mp4", ".aac", ".ogg", ".flac"}


def _ensure_ffmpeg_on_path() -> None:
    """Expose imageio-ffmpeg's bundled binary to Whisper and yt-dlp."""
    ffmpeg_path = Path(imageio_ffmpeg.get_ffmpeg_exe())
    BIN_DIR.mkdir(exist_ok=True)
    ffmpeg_link = BIN_DIR / "ffmpeg"
    if not ffmpeg_link.exists():
        ffmpeg_link.symlink_to(ffmpeg_path)
    os.environ["PATH"] = f"{BIN_DIR}{os.pathsep}{ffmpeg_path.parent}{os.pathsep}{os.environ.get('PATH', '')}"


def _format_timestamp(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"


def _write_vtt(video_id: str, segments: list[dict]) -> Path:
    path = TRANSCRIPT_DIR / f"{video_id}.vtt"
    lines = ["WEBVTT", ""]
    for segment in segments:
        start = _format_timestamp(float(segment["start"]))
        end = _format_timestamp(float(segment["end"]))
        text = segment["text"].strip()
        if not text:
            continue
        lines.extend([f"{start} --> {end}", text, ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_txt(video_id: str, segments: list[dict]) -> Path:
    path = TRANSCRIPT_DIR / f"{video_id}.txt"
    lines = []
    for segment in segments:
        start = _format_timestamp(float(segment["start"]))
        text = segment["text"].strip()
        if text:
            lines.append(f"{start} {text}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def download_audio(
    url: str,
    overwrite: bool = False,
    cookies_from_browser: str | None = None,
) -> Path:
    """Download the best available audio for a YouTube URL."""
    video_id = extract_video_id(url)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    output_template = str(AUDIO_DIR / f"{video_id}.%(ext)s")
    existing = sorted(AUDIO_DIR.glob(f"{video_id}.*"))
    if existing and not overwrite:
        return existing[0]

    options = {
        "format": "bestaudio/best[acodec!=none]/18/best",
        "outtmpl": output_template,
        "quiet": False,
        "noplaylist": True,
        "overwrites": overwrite,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    }
    if cookies_from_browser:
        options["cookiesfrombrowser"] = (cookies_from_browser,)

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded = Path(ydl.prepare_filename(info))

    return downloaded


def transcribe_audio(
    audio_path: Path,
    video_id: str,
    model_name: str = "base",
    language: str = "en",
) -> tuple[Path, Path]:
    """Transcribe one audio file and write text + VTT transcripts."""
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path), language=language, fp16=False)
    segments = result.get("segments", [])
    txt_path = _write_txt(video_id, segments)
    vtt_path = _write_vtt(video_id, segments)
    return txt_path, vtt_path


def transcribe_url(url: str, model_name: str = "base", overwrite: bool = False) -> None:
    video_id = extract_video_id(url)
    txt_path = TRANSCRIPT_DIR / f"{video_id}.txt"
    vtt_path = TRANSCRIPT_DIR / f"{video_id}.vtt"

    if txt_path.exists() and vtt_path.exists() and not overwrite:
        print(f"Skipping {video_id}: transcripts already exist.")
        return

    audio_path = download_audio(url, overwrite=overwrite)
    print(f"Transcribing {video_id} with Whisper model '{model_name}'...")
    txt_path, vtt_path = transcribe_audio(audio_path, video_id, model_name=model_name)
    print(f"Wrote {txt_path}")
    print(f"Wrote {vtt_path}")


def transcribe_url_safe(
    url: str,
    model_name: str = "base",
    overwrite: bool = False,
    cookies_from_browser: str | None = None,
) -> bool:
    """Transcribe one URL and return False instead of stopping the whole batch on failure."""
    video_id = extract_video_id(url)
    try:
        txt_path = TRANSCRIPT_DIR / f"{video_id}.txt"
        vtt_path = TRANSCRIPT_DIR / f"{video_id}.vtt"

        if txt_path.exists() and vtt_path.exists() and not overwrite:
            print(f"Skipping {video_id}: transcripts already exist.")
            return True

        audio_path = download_audio(
            url,
            overwrite=overwrite,
            cookies_from_browser=cookies_from_browser,
        )
        print(f"Transcribing {video_id} with Whisper model '{model_name}'...")
        txt_path, vtt_path = transcribe_audio(audio_path, video_id, model_name=model_name)
        print(f"Wrote {txt_path}")
        print(f"Wrote {vtt_path}")
        return True
    except Exception as exc:
        print(f"[ERROR] Failed to transcribe {video_id}: {exc}")
        return False


def infer_video_id_from_audio_path(path: Path) -> str:
    """Infer a YouTube video ID from a file name, trimming optional timestamp suffixes."""
    stem = path.stem
    return stem.split("&", 1)[0]


def iter_audio_files(audio_dir: Path) -> Iterable[Path]:
    for path in sorted(audio_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES:
            yield path


def iter_urls(use_all: bool, url: str | None) -> Iterable[str]:
    if url:
        yield url
    if use_all:
        for video in TARGET_VIDEOS:
            yield video["url"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Download audio and transcribe videos with Whisper")
    parser.add_argument("--all", action="store_true", help="Transcribe all TARGET_VIDEOS")
    parser.add_argument("--url", help="Transcribe one YouTube URL")
    parser.add_argument("--audio-file", type=Path, help="Transcribe a local audio/video file")
    parser.add_argument("--audio-dir", type=Path, help="Transcribe all supported audio/video files in a folder")
    parser.add_argument("--video-id", help="Video ID to use when transcribing --audio-file")
    parser.add_argument("--model", default="base", help="Whisper model: tiny, base, small, medium, large")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing audio/transcripts")
    parser.add_argument(
        "--cookies-from-browser",
        choices=["brave", "chrome", "chromium", "edge", "firefox", "opera", "safari", "vivaldi", "whale"],
        help="Use browser cookies for yt-dlp, useful for YouTube 403/429 errors.",
    )
    args = parser.parse_args()

    if not args.all and not args.url and not args.audio_file and not args.audio_dir:
        parser.error("Use --all, --url, --audio-file, or --audio-dir")
    if args.audio_file and not args.video_id:
        parser.error("--audio-file requires --video-id")

    _ensure_ffmpeg_on_path()

    if args.audio_file:
        txt_path, vtt_path = transcribe_audio(
            args.audio_file,
            args.video_id,
            model_name=args.model,
        )
        print(f"Wrote {txt_path}")
        print(f"Wrote {vtt_path}")
        return

    if args.audio_dir:
        failures = 0
        for audio_path in iter_audio_files(args.audio_dir):
            video_id = infer_video_id_from_audio_path(audio_path)
            txt_path = TRANSCRIPT_DIR / f"{video_id}.txt"
            vtt_path = TRANSCRIPT_DIR / f"{video_id}.vtt"
            if txt_path.exists() and vtt_path.exists() and not args.overwrite:
                print(f"Skipping {video_id}: transcripts already exist.")
                continue
            try:
                print(f"Transcribing {audio_path.name} as {video_id} with Whisper model '{args.model}'...")
                txt_path, vtt_path = transcribe_audio(audio_path, video_id, model_name=args.model)
                print(f"Wrote {txt_path}")
                print(f"Wrote {vtt_path}")
            except Exception as exc:
                failures += 1
                print(f"[ERROR] Failed to transcribe {audio_path}: {exc}")
        if failures:
            raise SystemExit(f"{failures} local file(s) failed.")
        return

    failures = 0
    for video_url in iter_urls(args.all, args.url):
        ok = transcribe_url_safe(
            video_url,
            model_name=args.model,
            overwrite=args.overwrite,
            cookies_from_browser=args.cookies_from_browser,
        )
        failures += 0 if ok else 1

    if failures:
        raise SystemExit(f"{failures} video(s) failed. Try --cookies-from-browser chrome or use existing local audio files.")


if __name__ == "__main__":
    main()
