# NCUACG/club/images.py
"""
上傳圖片的處理：轉正方向、縮小、去掉 EXIF（裡面可能有拍照地點的 GPS）、存成 JPEG。
前端上傳前已經先縮過一次，這裡是保險：直接打 API 上傳原圖也不會塞爆硬碟。
"""
from __future__ import annotations

import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 單張原圖上限
PHOTO_MAX_SIDE = 1920
THUMB_MAX_SIDE = 480
WORK_IMAGE_MAX_SIDE = 2560


def _open(upload) -> Image.Image:
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError(f"圖片太大了（上限 {MAX_UPLOAD_BYTES // 1024 // 1024} MB）")
    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("看不懂這個圖片檔，請用 JPG 或 PNG") from exc
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        # 透明的地方鋪白底，不然轉 JPEG 會變黑
        image = image.convert("RGBA")
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.getchannel("A"))
        return background
    return image.convert("RGB")


def _jpeg(image: Image.Image, max_side: int, name: str) -> ContentFile:
    copy = image.copy()
    copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    # 不傳 exif 參數，存出來的檔案就沒有 EXIF
    copy.save(buffer, format="JPEG", quality=85, optimize=True)
    return ContentFile(buffer.getvalue(), name=name)


def process_photo(upload, folder: str) -> tuple[ContentFile, ContentFile, int, int]:
    """社課照片：回傳（照片、縮圖、寬、高）。檔名是 folder/隨機碼.jpg。"""
    image = _open(upload)
    key = uuid.uuid4().hex
    full = _jpeg(image, PHOTO_MAX_SIDE, f"{folder}/{key}.jpg")
    thumb = _jpeg(image, THUMB_MAX_SIDE, f"{folder}/{key}_thumb.jpg")
    width, height = Image.open(BytesIO(full.read())).size
    full.seek(0)
    return full, thumb, width, height


def process_work_image(upload) -> tuple[ContentFile, ContentFile]:
    """成果牆的圖片作品：回傳（圖片、縮圖）。"""
    image = _open(upload)
    key = uuid.uuid4().hex
    return _jpeg(image, WORK_IMAGE_MAX_SIDE, f"{key}.jpg"), _jpeg(image, THUMB_MAX_SIDE, f"{key}_thumb.jpg")


def process_thumbnail(upload) -> ContentFile:
    """另外上傳的縮圖（影片作品用）。"""
    return _jpeg(_open(upload), THUMB_MAX_SIDE, f"{uuid.uuid4().hex}_thumb.jpg")
