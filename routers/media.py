"""
Media Tools Router
Implements all endpoints from MEDIA_TOOLS_SPEC.md

Video:  convert, extract-audio, to-gif, compress
Audio:  convert, trim, merge, normalize
Image:  convert, compress, resize
PDF:    merge, split, compress, images-to-pdf, pdf-to-images
"""
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.auth import get_current_user, AuthenticatedUser
import services.media.video_service as video_service
import services.media.audio_service as audio_service
import services.media.image_service as image_service
import services.media.pdf_service as pdf_service


router = APIRouter(
    prefix="/api/v1/media",
    tags=["Media Tools"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Max upload sizes (bytes) as suggested in spec
MAX_VIDEO_SIZE = 200 * 1024 * 1024   # 200 MB
MAX_AUDIO_SIZE = 50 * 1024 * 1024    # 50 MB
MAX_IMAGE_SIZE = 20 * 1024 * 1024    # 20 MB
MAX_PDF_SIZE   = 50 * 1024 * 1024    # 50 MB

TEMP_DIR = os.path.join(tempfile.gettempdir(), "ktufy_media")
os.makedirs(TEMP_DIR, exist_ok=True)


def _job_dir() -> str:
    """Create a unique temporary directory for a processing job."""
    d = os.path.join(TEMP_DIR, uuid.uuid4().hex)
    os.makedirs(d, exist_ok=True)
    return d


async def _save_upload(file: UploadFile, dest: str, max_size: int) -> None:
    """Save an uploaded file to disk, enforcing size limit."""
    total = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1 MB chunks
            total += len(chunk)
            if total > max_size:
                os.unlink(dest)
                max_mb = max_size // (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Max size: {max_mb}MB.",
                )
            f.write(chunk)


def _cleanup(job_dir: str) -> None:
    """Schedule cleanup of temp directory (best-effort)."""
    try:
        shutil.rmtree(job_dir, ignore_errors=True)
    except Exception:
        pass


def _file_response(path: str, filename: str, media_type: str = "application/octet-stream", job_dir: str = None):
    """Return a FileResponse that cleans up temp files in the background."""
    bg = BackgroundTask(_cleanup, job_dir) if job_dir else None
    return FileResponse(
        path=path,
        filename=filename,
        media_type=media_type,
        background=bg,
    )


# ---------------------------------------------------------------------------
# 1. VIDEO TOOLS  /api/v1/media/video/
# ---------------------------------------------------------------------------

@router.post("/video/convert", summary="Convert video format")
async def video_convert(
    file: UploadFile = File(...),
    output_format: str = Form(...),
    quality: str = Form("original"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Convert video to another format/resolution."""
    if output_format not in ("mp4", "mkv", "avi", "mov", "webm", "flv"):
        raise HTTPException(400, detail=f"Unsupported format: {output_format}")

    job_dir = _job_dir()
    input_ext = Path(file.filename or "video.mp4").suffix or ".mp4"
    input_path = os.path.join(job_dir, f"input{input_ext}")
    output_path = os.path.join(job_dir, f"output.{output_format}")

    await _save_upload(file, input_path, MAX_VIDEO_SIZE)
    try:
        await video_service.convert_video(input_path, output_path, output_format, quality)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "video").stem + f".{output_format}"
    return _file_response(output_path, out_name, f"video/{output_format}", job_dir)


@router.post("/video/extract-audio", summary="Extract audio from video")
async def video_extract_audio(
    file: UploadFile = File(...),
    output_format: str = Form(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Extract the audio track from a video file."""
    if output_format not in ("mp3", "aac", "wav", "ogg", "flac"):
        raise HTTPException(400, detail=f"Unsupported audio format: {output_format}")

    job_dir = _job_dir()
    input_ext = Path(file.filename or "video.mp4").suffix or ".mp4"
    input_path = os.path.join(job_dir, f"input{input_ext}")
    output_path = os.path.join(job_dir, f"audio.{output_format}")

    await _save_upload(file, input_path, MAX_VIDEO_SIZE)
    try:
        await video_service.extract_audio(input_path, output_path, output_format)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "video").stem + f".{output_format}"
    return _file_response(output_path, out_name, f"audio/{output_format}", job_dir)


@router.post("/video/to-gif", summary="Convert video to GIF")
async def video_to_gif(
    file: UploadFile = File(...),
    fps: int = Form(10),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Convert a video to an animated GIF."""
    if fps not in (5, 10, 15, 24):
        fps = 10  # default fallback

    job_dir = _job_dir()
    input_ext = Path(file.filename or "video.mp4").suffix or ".mp4"
    input_path = os.path.join(job_dir, f"input{input_ext}")
    output_path = os.path.join(job_dir, "output.gif")

    await _save_upload(file, input_path, MAX_VIDEO_SIZE)
    try:
        await video_service.video_to_gif(input_path, output_path, fps)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "video").stem + ".gif"
    return _file_response(output_path, out_name, "image/gif", job_dir)


@router.post("/video/compress", summary="Compress video")
async def video_compress(
    file: UploadFile = File(...),
    quality: str = Form(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Compress video by reducing resolution."""
    if quality not in ("1080p", "720p", "480p", "360p"):
        raise HTTPException(400, detail=f"Unsupported quality: {quality}")

    job_dir = _job_dir()
    input_ext = Path(file.filename or "video.mp4").suffix or ".mp4"
    input_path = os.path.join(job_dir, f"input{input_ext}")
    output_path = os.path.join(job_dir, f"compressed{input_ext}")

    await _save_upload(file, input_path, MAX_VIDEO_SIZE)
    try:
        await video_service.compress_video(input_path, output_path, quality)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "video").stem + f"_compressed{input_ext}"
    return _file_response(output_path, out_name, "video/mp4", job_dir)


# ---------------------------------------------------------------------------
# 2. AUDIO TOOLS  /api/v1/media/audio/
# ---------------------------------------------------------------------------

@router.post("/audio/convert", summary="Convert audio format")
async def audio_convert(
    file: UploadFile = File(...),
    output_format: str = Form(...),
    quality: str = Form("192k"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Convert audio to another format with optional bitrate."""
    if output_format not in ("mp3", "aac", "wav", "ogg", "flac", "m4a"):
        raise HTTPException(400, detail=f"Unsupported format: {output_format}")

    job_dir = _job_dir()
    input_ext = Path(file.filename or "audio.mp3").suffix or ".mp3"
    input_path = os.path.join(job_dir, f"input{input_ext}")
    output_path = os.path.join(job_dir, f"output.{output_format}")

    await _save_upload(file, input_path, MAX_AUDIO_SIZE)
    try:
        await audio_service.convert_audio(input_path, output_path, output_format, quality)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "audio").stem + f".{output_format}"
    return _file_response(output_path, out_name, f"audio/{output_format}", job_dir)


@router.post("/audio/trim", summary="Trim audio")
async def audio_trim(
    file: UploadFile = File(...),
    start: str = Form(...),
    end: str = Form(...),
    output_format: str = Form(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Trim audio between start and end timestamps."""
    job_dir = _job_dir()
    input_ext = Path(file.filename or "audio.mp3").suffix or ".mp3"
    input_path = os.path.join(job_dir, f"input{input_ext}")

    ext = output_format if output_format else input_ext.lstrip(".")
    output_path = os.path.join(job_dir, f"trimmed.{ext}")

    await _save_upload(file, input_path, MAX_AUDIO_SIZE)
    try:
        await audio_service.trim_audio(input_path, output_path, start, end, output_format)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "audio").stem + f"_trimmed.{ext}"
    return _file_response(output_path, out_name, f"audio/{ext}", job_dir)


@router.post("/audio/merge", summary="Merge audio files")
async def audio_merge(
    files: List[UploadFile] = File(...),
    output_format: str = Form("mp3"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Merge multiple audio files in order."""
    if len(files) < 2:
        raise HTTPException(400, detail="At least 2 audio files are required.")

    job_dir = _job_dir()
    input_paths = []

    for i, f in enumerate(files):
        ext = Path(f.filename or f"audio{i}.mp3").suffix or ".mp3"
        path = os.path.join(job_dir, f"input_{i}{ext}")
        await _save_upload(f, path, MAX_AUDIO_SIZE)
        input_paths.append(path)

    output_path = os.path.join(job_dir, f"merged.{output_format}")
    try:
        await audio_service.merge_audio(input_paths, output_path, output_format)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    return _file_response(output_path, f"merged.{output_format}", f"audio/{output_format}", job_dir)


@router.post("/audio/normalize", summary="Normalize audio volume")
async def audio_normalize(
    file: UploadFile = File(...),
    output_format: str = Form(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Normalize audio volume using loudnorm."""
    job_dir = _job_dir()
    input_ext = Path(file.filename or "audio.mp3").suffix or ".mp3"
    input_path = os.path.join(job_dir, f"input{input_ext}")

    ext = output_format if output_format else input_ext.lstrip(".")
    output_path = os.path.join(job_dir, f"normalized.{ext}")

    await _save_upload(file, input_path, MAX_AUDIO_SIZE)
    try:
        await audio_service.normalize_audio(input_path, output_path, output_format)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "audio").stem + f"_normalized.{ext}"
    return _file_response(output_path, out_name, f"audio/{ext}", job_dir)


# ---------------------------------------------------------------------------
# 3. IMAGE TOOLS  /api/v1/media/image/
# ---------------------------------------------------------------------------

@router.post("/image/convert", summary="Convert image format")
async def image_convert(
    file: UploadFile = File(...),
    output_format: str = Form(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Convert image to another format."""
    if output_format not in ("jpg", "png", "webp", "avif", "gif", "bmp"):
        raise HTTPException(400, detail=f"Unsupported format: {output_format}")

    job_dir = _job_dir()
    input_ext = Path(file.filename or "image.png").suffix or ".png"
    input_path = os.path.join(job_dir, f"input{input_ext}")
    output_path = os.path.join(job_dir, f"output.{output_format}")

    await _save_upload(file, input_path, MAX_IMAGE_SIZE)
    try:
        image_service.convert_image(input_path, output_path, output_format)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "image").stem + f".{output_format}"
    return _file_response(output_path, out_name, f"image/{output_format}", job_dir)


@router.post("/image/compress", summary="Compress image")
async def image_compress(
    file: UploadFile = File(...),
    quality: int = Form(80),
    output_format: str = Form(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Compress image by reducing quality."""
    if not (1 <= quality <= 100):
        raise HTTPException(400, detail="Quality must be between 1 and 100.")

    job_dir = _job_dir()
    input_ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    input_path = os.path.join(job_dir, f"input{input_ext}")

    ext = output_format if output_format else input_ext.lstrip(".")
    output_path = os.path.join(job_dir, f"compressed.{ext}")

    await _save_upload(file, input_path, MAX_IMAGE_SIZE)
    try:
        image_service.compress_image(input_path, output_path, quality, output_format)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "image").stem + f"_compressed.{ext}"
    return _file_response(output_path, out_name, f"image/{ext}", job_dir)


@router.post("/image/resize", summary="Resize image")
async def image_resize(
    file: UploadFile = File(...),
    width: int = Form(...),
    height: int = Form(...),
    output_format: str = Form(None),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Resize image to exact dimensions."""
    if width < 1 or height < 1:
        raise HTTPException(400, detail="Width and height must be positive integers.")

    job_dir = _job_dir()
    input_ext = Path(file.filename or "image.jpg").suffix or ".jpg"
    input_path = os.path.join(job_dir, f"input{input_ext}")

    ext = output_format if output_format else input_ext.lstrip(".")
    output_path = os.path.join(job_dir, f"resized.{ext}")

    await _save_upload(file, input_path, MAX_IMAGE_SIZE)
    try:
        image_service.resize_image(input_path, output_path, width, height, output_format)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "image").stem + f"_resized.{ext}"
    return _file_response(output_path, out_name, f"image/{ext}", job_dir)


# ---------------------------------------------------------------------------
# 4. PDF TOOLS  /api/v1/media/pdf/
# ---------------------------------------------------------------------------

@router.post("/pdf/merge", summary="Merge PDFs")
async def pdf_merge(
    files: List[UploadFile] = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Merge multiple PDFs in order."""
    if len(files) < 2:
        raise HTTPException(400, detail="At least 2 PDF files are required.")

    job_dir = _job_dir()
    input_paths = []

    for i, f in enumerate(files):
        path = os.path.join(job_dir, f"input_{i}.pdf")
        await _save_upload(f, path, MAX_PDF_SIZE)
        input_paths.append(path)

    output_path = os.path.join(job_dir, "merged.pdf")
    try:
        await pdf_service.merge_pdfs(input_paths, output_path)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    return _file_response(output_path, "merged.pdf", "application/pdf", job_dir)


@router.post("/pdf/split", summary="Split PDF")
async def pdf_split(
    file: UploadFile = File(...),
    ranges: str = Form(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Split PDF into parts by page ranges. Returns a ZIP archive."""
    job_dir = _job_dir()
    input_path = os.path.join(job_dir, "input.pdf")
    output_path = os.path.join(job_dir, "split.zip")

    await _save_upload(file, input_path, MAX_PDF_SIZE)
    try:
        await pdf_service.split_pdf(input_path, output_path, ranges)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "document").stem + "_split.zip"
    return _file_response(output_path, out_name, "application/zip", job_dir)


@router.post("/pdf/compress", summary="Compress PDF")
async def pdf_compress(
    file: UploadFile = File(...),
    quality: str = Form("print"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Compress PDF with specified quality level."""
    if quality not in ("screen", "print", "high", "max"):
        raise HTTPException(400, detail=f"Unsupported quality: {quality}")

    job_dir = _job_dir()
    input_path = os.path.join(job_dir, "input.pdf")
    output_path = os.path.join(job_dir, "compressed.pdf")

    await _save_upload(file, input_path, MAX_PDF_SIZE)
    try:
        await pdf_service.compress_pdf(input_path, output_path, quality)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "document").stem + "_compressed.pdf"
    return _file_response(output_path, out_name, "application/pdf", job_dir)


@router.post("/pdf/images-to-pdf", summary="Images to PDF")
async def pdf_images_to_pdf(
    files: List[UploadFile] = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Combine multiple images into a single PDF."""
    if not files:
        raise HTTPException(400, detail="At least 1 image file is required.")

    job_dir = _job_dir()
    input_paths = []

    for i, f in enumerate(files):
        ext = Path(f.filename or f"image{i}.jpg").suffix or ".jpg"
        path = os.path.join(job_dir, f"input_{i}{ext}")
        await _save_upload(f, path, MAX_IMAGE_SIZE)
        input_paths.append(path)

    output_path = os.path.join(job_dir, "combined.pdf")
    try:
        await pdf_service.images_to_pdf(input_paths, output_path)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    return _file_response(output_path, "combined.pdf", "application/pdf", job_dir)


@router.post("/pdf/pdf-to-images", summary="PDF to Images")
async def pdf_to_images(
    file: UploadFile = File(...),
    output_format: str = Form("jpg"),
    quality: str = Form("print"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Convert each PDF page to an image. Returns a ZIP archive."""
    if output_format not in ("jpg", "png", "webp"):
        raise HTTPException(400, detail=f"Unsupported format: {output_format}")
    if quality not in ("screen", "print", "high"):
        raise HTTPException(400, detail=f"Unsupported quality: {quality}")

    job_dir = _job_dir()
    input_path = os.path.join(job_dir, "input.pdf")
    output_path = os.path.join(job_dir, "pages.zip")

    await _save_upload(file, input_path, MAX_PDF_SIZE)
    try:
        await pdf_service.pdf_to_images(input_path, output_path, output_format, quality)
    except Exception as e:
        _cleanup(job_dir)
        raise HTTPException(500, detail=str(e))

    out_name = Path(file.filename or "document").stem + "_pages.zip"
    return _file_response(output_path, out_name, "application/zip", job_dir)
