from __future__ import annotations

import threading
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

import yt_dlp

QUALITY_LABELS = ["4K", "2K", "1080p", "720p", "480p", "360p", "144p", "MP3"]

QUALITY_HEIGHTS = {
    "4K": 2160,
    "2K": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "144p": 144,
}

try:
    from yt_dlp.utils import DownloadCancelled as _CancelledError
except ImportError:
    class _CancelledError(Exception):
        pass


@dataclass
class MediaInfo:
    title: str = "Unknown title"
    duration: Optional[float] = None
    thumbnail: Optional[str] = None
    is_audio_only: bool = False
    media_type: str = "Video"
    available: List[str] = field(default_factory=list)
    url: str = ""

    @property
    def duration_str(self) -> str:
        if self.duration is None:
            return "N/A"
        total = int(self.duration)
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"


def _get_download_dir() -> Path:
    try:
        from android.storage import primary_external_storage_path
        base = Path(primary_external_storage_path()) / "Download" / "NovaDownloader"
    except Exception:
        base = Path.home() / "downloads" / "NovaDownloader"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _ffmpeg_path() -> Optional[str]:
    candidates = [
        Path(__file__).parent / "ffmpeg",
        Path(__file__).parent.parent / "ffmpeg",
    ]
    for d in candidates:
        exe = d / "ffmpeg"
        if exe.exists():
            return str(exe)
    return None


class Downloader:
    def __init__(self) -> None:
        self._cancel_event = threading.Event()

    def analyse(self, url: str) -> MediaInfo:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "ffmpeg_location": _ffmpeg_path(),
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = info.get("formats") or []
        video_formats = [f for f in formats if f.get("vcodec") not in (None, "none")]
        audio_formats = [f for f in formats if f.get("acodec") not in (None, "none")]

        is_audio_only = not video_formats
        available: List[str] = []

        if not is_audio_only:
            heights_asc = sorted(QUALITY_HEIGHTS.items(), key=lambda kv: kv[1])
            present_labels: set[str] = set()
            for fh in {f.get("height") or 0 for f in video_formats}:
                if fh <= 0:
                    continue
                best = None
                for label, th in heights_asc:
                    if fh >= th:
                        best = label
                if best:
                    present_labels.add(best)
            if present_labels:
                available = [label for label in QUALITY_LABELS if label in present_labels]
            else:
                max_height = max((f.get("height") or 0) for f in video_formats)
                for label, height in QUALITY_HEIGHTS.items():
                    if max_height >= height:
                        available.append(label)

        if audio_formats:
            available.append("MP3")

        available = [label for label in QUALITY_LABELS if label in available]

        return MediaInfo(
            title=info.get("title") or "Unknown title",
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
            is_audio_only=is_audio_only,
            media_type="Audio" if is_audio_only else "Video",
            available=available,
            url=url,
        )

    def download(
        self,
        url: str,
        quality: str,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Path:
        self._cancel_event.clear()
        output_dir = output_dir or _get_download_dir()
        output_dir.mkdir(parents=True, exist_ok=True)

        if quality not in QUALITY_LABELS:
            raise ValueError(f"Unsupported quality: {quality}")

        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "outtmpl": str(output_dir / "%(title).150B.%(ext)s"),
            "ffmpeg_location": _ffmpeg_path(),
            "merge_output_format": "mp4",
            "progress_hooks": [self._make_hook(progress_callback, quality)],
        }

        if quality == "MP3":
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ]
        else:
            height = QUALITY_HEIGHTS[quality]
            options["format"] = (
                f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
                f"/bestvideo[height<={height}]+bestaudio"
                f"/best[height<={height}]"
                f"/best"
            )

        if progress_callback:
            progress_callback({"stage": "connecting", "message": "Connecting..."})
            progress_callback({"stage": "info", "message": "Getting video information..."})

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)

        if quality == "MP3":
            mp3_files = sorted(
                output_dir.glob("*.mp3"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            return mp3_files[0] if mp3_files else output_dir / "audio.mp3"

        downloads = info.get("requested_downloads")
        if downloads and downloads[0].get("filepath"):
            return Path(downloads[0]["filepath"])
        return output_dir

    def cancel(self) -> None:
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _make_hook(
        self, callback: Optional[Callable[[Dict[str, Any]], None]], quality: str
    ) -> Callable[[Dict[str, Any]], None]:
        def hook(d: Dict[str, Any]) -> None:
            if self._cancel_event.is_set():
                raise _CancelledError("Download cancelled by user")

            status = d.get("status")
            payload: Dict[str, Any] = {}

            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                payload = {
                    "stage": "downloading",
                    "message": "Downloading video..." if quality != "MP3" else "Downloading audio...",
                    "downloaded": downloaded,
                    "total": total,
                    "speed": d.get("speed"),
                    "eta": d.get("eta"),
                    "percent": (downloaded / total * 100.0) if total else 0.0,
                }
            elif status == "finished":
                payload = {
                    "stage": "merging" if quality != "MP3" else "converting",
                    "message": "Merging audio..." if quality != "MP3" else "Converting to MP3...",
                }

            if payload and callback:
                callback(payload)

        return hook