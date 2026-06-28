"""
Thumbnail generation module for the iPhone Photo Manager.
Generates WebP thumbnails at two sizes: small (200px) and medium (800px).
"""

import os
import logging
import hashlib
from PIL import Image

# Ensure HEIC support is registered
import pillow_heif
pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_thumb_env = os.getenv("THUMBNAIL_DIR", "data/thumbnails")
if os.path.isabs(_thumb_env):
    THUMBNAIL_DIR = os.path.realpath(_thumb_env)
else:
    THUMBNAIL_DIR = os.path.realpath(os.path.join(BASE_DIR, _thumb_env))

PHOTOS_DIR = os.path.join(BASE_DIR, "photos")

SIZES = {
    "small": int(os.getenv("THUMBNAIL_SMALL_SIZE", "200")),
    "medium": int(os.getenv("THUMBNAIL_MEDIUM_SIZE", "800")),
}

THUMBNAIL_QUALITY = int(os.getenv("THUMBNAIL_QUALITY", "80"))

def get_thumbnail_name(filepath: str) -> str:
    """Get a safe filename for a thumbnail based on its path."""
    return os.path.basename(filepath) + ".webp"

def get_thumbnail_path(filepath: str, size: str) -> str:
    """Get the filesystem path for a thumbnail, preserving folder structure."""
    rel_dir = os.path.dirname(filepath)
    return os.path.join(THUMBNAIL_DIR, size, rel_dir, get_thumbnail_name(filepath))


def thumbnail_exists(filepath: str, size: str) -> bool:
    """Check if a thumbnail already exists."""
    return os.path.exists(get_thumbnail_path(filepath, size))


def generate_thumbnail(photo_id: int, filepath: str, file_type: str) -> bool:
    """
    Generate thumbnails for a photo at all sizes.
    Returns True if successful.
    """
    # Quick disk check
    if thumbnail_exists(filepath, "small") and thumbnail_exists(filepath, "medium"):
        return True

    # Resolve the full path securely
    full_path = os.path.realpath(os.path.join(PHOTOS_DIR, filepath))
    if not full_path.startswith(os.path.realpath(PHOTOS_DIR) + os.sep):
        logger.warning("Path traversal attempt blocked: %s", filepath)
        return False

    if not os.path.exists(full_path):
        logger.warning("File not found: %s", full_path)
        return False

    try:
        if file_type == "MOV":
            return _generate_mov_thumbnail(filepath, full_path)
        else:
            return _generate_image_thumbnail(filepath, full_path)
    except Exception as e:
        logger.error("Failed to generate thumbnail for %s: %s", filepath, e)
        return False


def _generate_image_thumbnail(filepath: str, full_path: str) -> bool:
    """Generate thumbnails from an image file (HEIC, JPG, PNG)."""
    try:
        img = Image.open(full_path)

        # Handle EXIF orientation
        try:
            exif = img.getexif()
            orientation = exif.get(274)  # Orientation tag
            if orientation:
                rotation_map = {
                    3: 180,
                    6: 270,
                    8: 90,
                }
                if orientation in rotation_map:
                    img = img.rotate(rotation_map[orientation], expand=True)
                elif orientation in (2, 4, 5, 7):
                    # Mirror cases
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    if orientation == 4:
                        img = img.rotate(180, expand=True)
                    elif orientation == 5:
                        img = img.rotate(270, expand=True)
                    elif orientation == 7:
                        img = img.rotate(90, expand=True)
        except Exception:
            pass

        # Convert to RGB if necessary (handles RGBA, P mode etc.)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        for size_name, max_dim in SIZES.items():
            out_path = get_thumbnail_path(filepath, size_name)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            # Calculate dimensions maintaining aspect ratio
            w, h = img.size
            if w >= h:
                new_w = max_dim
                new_h = int(h * (max_dim / w))
            else:
                new_h = max_dim
                new_w = int(w * (max_dim / h))

            thumb = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            thumb.save(out_path, "WEBP", quality=THUMBNAIL_QUALITY)

        return True
    except Exception as e:
        logger.error("Error generating image thumbnail for %s: %s", full_path, e)
        return False


def _generate_mov_thumbnail(filepath: str, full_path: str) -> bool:
    """
    Generate thumbnail for MOV. Since ffmpeg isn't available, we create a
    placeholder image with a video icon to ensure the UI doesn't crash.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (800, 800), color=(40, 40, 40))
        draw = ImageDraw.Draw(img)
        # Draw a simple play triangle
        draw.polygon([(300, 250), (300, 550), (550, 400)], fill=(200, 200, 200))
        
        # Create a generic placeholder for both sizes
        for size_name, max_dim in SIZES.items():
            out_path = get_thumbnail_path(filepath, size_name)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            thumb = img.resize((max_dim, max_dim), Image.LANCZOS)
            thumb.save(out_path, "WEBP", quality=80)
            thumb.close()
            
        img.close()
        return True
    except Exception as e:
        logger.error("Failed to generate generic video thumbnail: %s", e)
        return False
