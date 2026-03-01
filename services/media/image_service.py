"""
Image processing service
Ported from cvert/src/main/converters/image.ts

cvert uses Sharp (Node.js); Python equivalent is Pillow.
Handles: convert, compress, resize
"""
import io
from pathlib import Path
from typing import Optional

from PIL import Image


# Map frontend format strings to Pillow format names
FORMAT_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "gif": "GIF",
    "bmp": "BMP",
    "avif": "AVIF",
}

# Pillow save kwargs per format (mirrors cvert quality/compression logic)
def _save_kwargs(fmt: str, quality: int = 80) -> dict:
    """Build Pillow save kwargs based on format and quality."""
    fmt_upper = FORMAT_MAP.get(fmt, fmt.upper())
    kwargs = {"format": fmt_upper}

    if fmt_upper == "JPEG":
        kwargs["quality"] = quality
        kwargs["optimize"] = True
    elif fmt_upper == "PNG":
        if quality < 100:
            # cvert uses palette-based quantization for PNG compression
            kwargs["optimize"] = True
        kwargs["compress_level"] = 9
    elif fmt_upper == "WEBP":
        kwargs["quality"] = quality
    elif fmt_upper == "AVIF":
        kwargs["quality"] = quality

    return kwargs


def convert_image(
    input_path: str,
    output_path: str,
    output_format: str,
) -> None:
    """
    Convert image to another format.
    Mirrors cvert convertImage — opens with Pillow and saves in target format.
    """
    img = Image.open(input_path)

    # Convert to RGB if saving to JPEG/BMP (no alpha support)
    if output_format.lower() in ("jpg", "jpeg", "bmp"):
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

    kwargs = _save_kwargs(output_format)
    img.save(output_path, **kwargs)


def compress_image(
    input_path: str,
    output_path: str,
    quality: int = 80,
    output_format: Optional[str] = None,
) -> None:
    """
    Compress image by reducing quality.
    cvert uses Sharp's quality param + mozjpeg; Pillow equivalent with optimize.
    """
    img = Image.open(input_path)

    if not output_format:
        output_format = Path(input_path).suffix.lstrip(".").lower()

    if output_format in ("jpg", "jpeg", "bmp"):
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

    kwargs = _save_kwargs(output_format, quality=quality)
    img.save(output_path, **kwargs)


def resize_image(
    input_path: str,
    output_path: str,
    width: int,
    height: int,
    output_format: Optional[str] = None,
) -> None:
    """
    Resize image to exact dimensions.
    cvert uses Sharp resize with fit:'inside'; here we use Pillow's LANCZOS.
    """
    img = Image.open(input_path)
    img = img.resize((width, height), Image.LANCZOS)

    if not output_format:
        output_format = Path(input_path).suffix.lstrip(".").lower()

    if output_format in ("jpg", "jpeg", "bmp"):
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

    kwargs = _save_kwargs(output_format)
    img.save(output_path, **kwargs)
