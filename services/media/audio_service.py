"""
Audio processing service
Ported from cvert/src/main/converters/audio.ts

Handles: convert, trim, merge, normalize
All operations use FFmpeg via asyncio subprocess.
"""
import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional


def _get_ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


# Codec map ported directly from cvert convertAudio
AUDIO_CODEC_MAP = {
    "mp3": ["-c:a", "libmp3lame"],
    "wav": ["-c:a", "pcm_s16le"],
    "flac": ["-c:a", "flac"],
    "aac": ["-c:a", "aac"],
    "ogg": ["-c:a", "libvorbis"],
    "m4a": ["-c:a", "aac"],
    "opus": ["-c:a", "libopus"],
}

# Bitrate presets
BITRATE_MAP = {
    "64k": "64k",
    "128k": "128k",
    "192k": "192k",
    "320k": "320k",
}


async def convert_audio(
    input_path: str,
    output_path: str,
    output_format: str,
    quality: Optional[str] = None,
) -> None:
    """
    Convert audio to another format with optional bitrate.
    Mirrors cvert convertAudio — uses codec map and bitrate settings.
    """
    args = [
        _get_ffmpeg(),
        "-i", input_path,
        "-vn",  # No video (from cvert)
        "-y",
    ]

    codec_args = AUDIO_CODEC_MAP.get(output_format, ["-c:a", "aac"])
    args.extend(codec_args)

    # Bitrate (cvert checks format-specific bitrate support)
    if quality and output_format in ("mp3", "aac", "ogg", "m4a", "opus"):
        bitrate = BITRATE_MAP.get(quality, quality)
        args.extend(["-b:a", bitrate])

    args.append(output_path)

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Audio conversion failed: {stderr.decode()[-500:]}")


async def trim_audio(
    input_path: str,
    output_path: str,
    start: str,
    end: str,
    output_format: Optional[str] = None,
) -> None:
    """
    Trim audio between start and end timestamps.
    Uses FFmpeg -ss/-to with codec copy for speed.
    """
    args = [
        _get_ffmpeg(),
        "-i", input_path,
        "-ss", start,
        "-to", end,
        "-y",
    ]

    # If output format differs, transcode; otherwise stream copy
    input_ext = Path(input_path).suffix.lstrip(".").lower()
    if output_format and output_format != input_ext:
        codec_args = AUDIO_CODEC_MAP.get(output_format, ["-c:a", "aac"])
        args.extend(codec_args)
    else:
        args.extend(["-c", "copy"])

    args.append(output_path)

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Audio trimming failed: {stderr.decode()[-500:]}")


async def merge_audio(
    input_paths: List[str],
    output_path: str,
    output_format: str = "mp3",
) -> None:
    """
    Merge multiple audio files in order.
    Uses FFmpeg concat demuxer (same approach as cvert hint).
    """
    # Create a temporary file list for FFmpeg concat
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for path in input_paths:
            # FFmpeg concat requires single-quoted paths with escaped quotes
            safe_path = path.replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")
        filelist_path = f.name

    try:
        args = [
            _get_ffmpeg(),
            "-f", "concat",
            "-safe", "0",
            "-i", filelist_path,
            "-y",
        ]

        codec_args = AUDIO_CODEC_MAP.get(output_format, ["-c:a", "aac"])
        args.extend(codec_args)
        args.append(output_path)

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Audio merge failed: {stderr.decode()[-500:]}")
    finally:
        os.unlink(filelist_path)


async def normalize_audio(
    input_path: str,
    output_path: str,
    output_format: Optional[str] = None,
) -> None:
    """
    Normalize audio volume using FFmpeg loudnorm filter.
    """
    args = [
        _get_ffmpeg(),
        "-i", input_path,
        "-af", "loudnorm",
        "-y",
    ]

    if output_format:
        codec_args = AUDIO_CODEC_MAP.get(output_format, ["-c:a", "aac"])
        args.extend(codec_args)

    args.append(output_path)

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"Audio normalization failed: {stderr.decode()[-500:]}")
