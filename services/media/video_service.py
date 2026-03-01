"""
Video processing service
Ported from cvert/src/main/converters/video.ts

Handles: convert, extract-audio, video-to-gif, compress
All operations use FFmpeg via asyncio subprocess.
"""
import asyncio
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MediaInfo:
    duration: float
    width: int
    height: int
    video_codec: str
    audio_codec: str
    bitrate: int
    fps: float
    size: int
    filename: str
    format: str


def _get_ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def _get_ffprobe() -> str:
    return shutil.which("ffprobe") or "ffprobe"


async def get_media_info(file_path: str) -> MediaInfo:
    """Get media file information via ffprobe (mirrors cvert getMediaInfo)."""
    args = [
        _get_ffprobe(),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {stderr.decode()}")

    info = json.loads(stdout.decode())
    video_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    fmt = info.get("format", {})

    fps_val = 0.0
    r_frame_rate = video_stream.get("r_frame_rate", "")
    if r_frame_rate:
        parts = r_frame_rate.split("/")
        if len(parts) == 2:
            fps_val = float(parts[0]) / float(parts[1]) if float(parts[1]) else 0
        else:
            fps_val = float(parts[0]) if parts[0] else 0

    return MediaInfo(
        duration=float(fmt.get("duration", 0)),
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        video_codec=video_stream.get("codec_name", ""),
        audio_codec=audio_stream.get("codec_name", ""),
        bitrate=int(fmt.get("bit_rate", 0)),
        fps=fps_val,
        size=int(fmt.get("size", 0)),
        filename=os.path.basename(file_path),
        format=Path(file_path).suffix.lstrip(".").lower(),
    )


# Codec map ported from cvert
CODEC_MAP = {
    "mp4": ["-c:v", "libx264", "-c:a", "aac"],
    "avi": ["-c:v", "libxvid", "-c:a", "libmp3lame"],
    "mkv": ["-c:v", "libx264", "-c:a", "aac"],
    "mov": ["-c:v", "libx264", "-c:a", "aac"],
    "webm": ["-c:v", "libvpx-vp9", "-c:a", "libopus"],
    "flv": ["-c:v", "libx264", "-c:a", "aac"],
}

# Resolution presets
RESOLUTION_MAP = {
    "1080p": "1920:1080",
    "720p": "1280:720",
    "480p": "854:480",
    "360p": "640:360",
}


async def convert_video(
    input_path: str,
    output_path: str,
    output_format: str,
    quality: Optional[str] = None,
) -> None:
    """
    Convert video to another format/resolution.
    Mirrors cvert convertVideo logic with codec map and CRF-based quality.
    """
    args = [_get_ffmpeg(), "-i", input_path, "-y"]

    codec_args = CODEC_MAP.get(output_format, ["-c:v", "libx264", "-c:a", "aac"])
    args.extend(codec_args)

    # Resolution / quality filter
    filters = []
    if quality and quality != "original" and quality in RESOLUTION_MAP:
        w, h = RESOLUTION_MAP[quality].split(":")
        filters.append(f"scale={w}:{h}")

    if filters:
        args.extend(["-vf", ",".join(filters)])

    # Reasonable CRF
    if output_format == "webm":
        args.extend(["-crf", "30", "-b:v", "0"])
    else:
        args.extend(["-crf", "23"])

    args.append(output_path)

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Video conversion failed: {stderr.decode()[-500:]}")


async def extract_audio(
    input_path: str,
    output_path: str,
    output_format: str,
) -> None:
    """
    Extract audio track from video.
    Mirrors cvert extractAudio — strips video, copies/transcodes audio.
    """
    # Audio codec mapping
    audio_codec_map = {
        "mp3": ["-c:a", "libmp3lame"],
        "aac": ["-c:a", "aac"],
        "wav": ["-c:a", "pcm_s16le"],
        "ogg": ["-c:a", "libvorbis"],
        "flac": ["-c:a", "flac"],
    }
    codec_args = audio_codec_map.get(output_format, ["-c:a", "aac"])

    args = [
        _get_ffmpeg(),
        "-i", input_path,
        "-vn",  # No video
        "-y",
        *codec_args,
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {stderr.decode()[-500:]}")


async def video_to_gif(
    input_path: str,
    output_path: str,
    fps: int = 10,
) -> None:
    """
    Convert video to GIF using two-pass palette approach.
    Directly ported from cvert convertToGif — uses palettegen+paletteuse for quality.
    """
    # Two-pass palette approach from cvert for high quality GIFs
    complex_filter = (
        f"fps={fps},scale=480:-1:flags=lanczos,"
        f"split[s0][s1];[s0]palettegen=max_colors=256:stats_mode=diff[p];"
        f"[s1][p]paletteuse=dither=bayer:bayer_scale=5"
    )

    args = [
        _get_ffmpeg(),
        "-i", input_path,
        "-y",
        "-lavfi", complex_filter,
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"GIF conversion failed: {stderr.decode()[-500:]}")


async def compress_video(
    input_path: str,
    output_path: str,
    quality: str,
) -> None:
    """
    Compress video by scaling down resolution with CRF encoding.
    Uses the same resolution map + CRF approach from cvert.
    """
    resolution = RESOLUTION_MAP.get(quality)
    if not resolution:
        raise ValueError(f"Invalid quality: {quality}. Choose from: {list(RESOLUTION_MAP.keys())}")

    w, h = resolution.split(":")

    args = [
        _get_ffmpeg(),
        "-i", input_path,
        "-y",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-vf", f"scale={w}:{h}",
        "-crf", "23",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Video compression failed: {stderr.decode()[-500:]}")
