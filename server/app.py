"""
iPhone Photo Manager — FastAPI Application
Main server that provides API endpoints for photo browsing, searching,
and thumbnail serving.
"""

import asyncio
import os
import logging
import mimetypes
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from deep_translator import GoogleTranslator

from server.database import (
    init_db, get_db, insert_photo, update_photo,
    get_photos, get_photo_by_id, get_timeline, get_locations,
    get_photo_count, get_photos_without_thumbnails,
    get_photos_without_location, get_all_filepaths, delete_photo_by_filepath
)
from server.scanner import get_all_files_on_disk, scan_specific_files
from server.thumbnail import generate_thumbnail, get_thumbnail_path, thumbnail_exists
from server.geocoder import reverse_geocode, batch_reverse_geocode

# Translation cache
_translation_cache = {}

async def translate_text(text: str) -> str:
    if not text:
        return text
    if text in _translation_cache:
        return _translation_cache[text]
    try:
        translated = await asyncio.to_thread(
            GoogleTranslator(source='en', target='zh-CN').translate, text
        )
        _translation_cache[text] = translated
        return translated
    except Exception as e:
        logger.error("Translation failed for '%s': %s", text, e)
        return text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

_photos_env = os.getenv("PHOTOS_DIR", "photos")
if os.path.isabs(_photos_env):
    PHOTOS_DIR = os.path.realpath(_photos_env)
else:
    PHOTOS_DIR = os.path.realpath(os.path.join(PROJECT_DIR, _photos_env))

FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")

APP_LANGUAGE = os.getenv("APP_LANGUAGE", "zh")
APP_THEME = os.getenv("APP_THEME", "light")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
HTTP_CACHE_MAX_AGE = int(os.getenv("HTTP_CACHE_MAX_AGE", 86400))
SCAN_ON_STARTUP = os.getenv("SCAN_ON_STARTUP", "True").lower() in ("true", "1", "yes")
LOAD_ORIGINAL_ON_CLICK = os.getenv("LOAD_ORIGINAL_ON_CLICK", "False").lower() in ("true", "1", "yes")

# Scan state
scan_state = {
    "status": "idle",  # idle, scanning, generating_thumbnails, geocoding, complete
    "progress": 0,
    "total": 0,
    "message": "",
}


# --- Security Middleware ---

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # CSP: allow self, Google Fonts for styling
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' blob:; "
            "media-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "frame-ancestors 'none'"
        )
        return response


# --- App Lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()

    # Check if we need initial scan
    db = await get_db()
    count = await get_photo_count(db)
    await db.close()

    if count == 0:
        logger.info("No photos in database. Starting initial scan...")
        asyncio.create_task(_run_full_scan())
    elif SCAN_ON_STARTUP:
        logger.info("SCAN_ON_STARTUP enabled. Updating index...")
        asyncio.create_task(_run_full_scan())
    else:
        logger.info("Database has %d photos. Skipping initial scan.", count)
        # Still check for pending thumbnails and geocoding
        asyncio.create_task(_process_pending_tasks())

    yield


app = FastAPI(title="iPhone Photo Manager", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)


# --- Background Tasks ---

async def _run_full_scan():
    """Run a full scan of the photos directory."""
    global scan_state
    scan_state = {"status": "scanning", "progress": 0, "total": 0, "message": "Scanning files..."}

    try:
        # Phase 1: Fast directory traversal
        logger.info("Phase 1: Scanning file tree...")
        db = await get_db()
        
        disk_paths = await asyncio.to_thread(get_all_files_on_disk, PHOTOS_DIR)
        existing_paths = await get_all_filepaths(db)
        
        missing_paths = existing_paths - disk_paths
        new_paths = disk_paths - existing_paths
        
        scan_state["total"] = len(new_paths)
        scan_state["message"] = f"Found {len(new_paths)} new files. Updating index..."

        # Remove missing photos first
        if missing_paths:
            logger.info("Found %d missing files. Removing from database...", len(missing_paths))
            for path in missing_paths:
                await delete_photo_by_filepath(db, path)

        # Process new files
        if new_paths:
            logger.info("Found %d new files. Extracting metadata...", len(new_paths))
            new_files_data = await asyncio.to_thread(scan_specific_files, PHOTOS_DIR, new_paths)
            for i, photo_data in enumerate(new_files_data):
                await insert_photo(db, photo_data)
                scan_state["progress"] = i + 1
                if (i + 1) % 100 == 0:
                    logger.info("Imported %d / %d new files", i + 1, len(new_paths))

        await db.close()
        logger.info("Phase 1 complete: %d active files on disk.", len(disk_paths))

        # Phase 2: Generate thumbnails
        await _generate_all_thumbnails()

        # Phase 3: Geocode locations
        await _geocode_all_photos()

        scan_state = {
            "status": "complete",
            "progress": scan_state["total"],
            "total": scan_state["total"],
            "message": "Scan complete!",
        }
        logger.info("Full scan complete.")

    except Exception as e:
        logger.error("Scan failed: %s", e)
        scan_state = {"status": "error", "progress": 0, "total": 0, "message": str(e)}


async def _process_pending_tasks():
    """Process any pending thumbnails and geocoding."""
    await _generate_all_thumbnails()
    await _geocode_all_photos()
    global scan_state
    scan_state["status"] = "idle"
    scan_state["message"] = ""


async def _generate_all_thumbnails():
    """Generate thumbnails for all photos that don't have them."""
    global scan_state
    scan_state["status"] = "generating_thumbnails"
    scan_state["message"] = "Generating thumbnails..."

    db = await get_db()
    batch_size = 20
    total_generated = 0

    while True:
        photos = await get_photos_without_thumbnails(db, limit=100)
        if not photos:
            break

        async def process_photo(photo):
            success = await asyncio.to_thread(
                generate_thumbnail,
                photo["id"],
                photo["filepath"],
                photo["file_type"],
            )
            return photo["id"], success

        results = await asyncio.gather(*(process_photo(p) for p in photos))

        for photo_id, success in results:
            if success:
                await update_photo(db, photo_id, {"has_thumbnail": 1})
                total_generated += 1
            else:
                await update_photo(db, photo_id, {"has_thumbnail": -1})

        scan_state["message"] = f"Generated {total_generated} thumbnails..."
        logger.info("Generated %d thumbnails so far...", total_generated)

    await db.close()
    logger.info("Thumbnail generation complete: %d generated.", total_generated)


async def _geocode_all_photos():
    """Geocode all photos that have GPS but no location name."""
    global scan_state
    scan_state["status"] = "geocoding"
    scan_state["message"] = "Geocoding locations..."

    db = await get_db()
    photos = await get_photos_without_location(db)

    if not photos:
        await db.close()
        return

    logger.info("Geocoding %d photos...", len(photos))

    # Batch geocode
    coords = [(p["latitude"], p["longitude"]) for p in photos]
    locations = await asyncio.to_thread(batch_reverse_geocode, coords)

    for photo, location in zip(photos, locations):
        if location:
            await update_photo(db, photo["id"], {"location_name": location})

    await db.close()
    logger.info("Geocoding complete: %d locations resolved.", sum(1 for l in locations if l))


# --- API Endpoints ---

@app.get("/api/photos")
async def api_get_photos(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    file_type: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    screenshots: Optional[bool] = Query(None),
    lang: Optional[str] = Query(None),
):
    """Get paginated list of photos with optional filters."""
    db = await get_db()
    try:
        photos, total = await get_photos(
            db,
            page=page,
            per_page=per_page,
            file_type=file_type,
            location_name=location,
            city=city,
            country=country,
            date_from=date_from,
            date_to=date_to,
            is_screenshot=screenshots,
        )
        target_lang = lang if lang else os.getenv("APP_LANGUAGE", "zh")
        if target_lang == "zh":
            unique_locs = {p["location_name"] for p in photos if p.get("location_name")}
            translations = await asyncio.gather(*(translate_text(loc) for loc in unique_locs))
            trans_map = dict(zip(unique_locs, translations))
            for p in photos:
                if p.get("location_name"):
                    p["display_location"] = trans_map[p["location_name"]]
        else:
            for p in photos:
                p["display_location"] = p.get("location_name")
        return {
            "photos": photos,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        }
    finally:
        await db.close()


@app.get("/api/photos/{photo_id}")
async def api_get_photo(photo_id: int):
    """Get a single photo's details."""
    db = await get_db()
    try:
        photo = await get_photo_by_id(db, photo_id)
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")
        if os.getenv("APP_LANGUAGE", "zh") == "zh" and photo.get("location_name"):
            photo["display_location"] = await translate_text(photo["location_name"])
        else:
            photo["display_location"] = photo.get("location_name")
        return photo
    finally:
        await db.close()


@app.get("/api/photos/{photo_id}/file")
async def api_get_photo_file(photo_id: int):
    """Serve the original photo file."""
    db = await get_db()
    try:
        photo = await get_photo_by_id(db, photo_id)
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        filepath = photo["filepath"]
        full_path = os.path.realpath(os.path.join(PHOTOS_DIR, filepath))

        # Security: verify path is within PHOTOS_DIR
        if not full_path.startswith(os.path.realpath(PHOTOS_DIR) + os.sep):
            raise HTTPException(status_code=403, detail="Access denied")

        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="File not found")

        # Determine media type
        ext = os.path.splitext(filepath)[1].lower()
        media_types = {
            ".heic": "image/heic",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".mov": "video/quicktime",
        }
        media_type = media_types.get(ext, "application/octet-stream")

        return FileResponse(
            full_path,
            media_type=media_type,
            headers={
                "Cache-Control": f"public, max-age={HTTP_CACHE_MAX_AGE}",
                "Content-Disposition": f'inline; filename="{photo["filename"]}"'
            }
        )
    finally:
        await db.close()

@app.get("/api/photos/{photo_id}/render")
async def api_get_photo_render(photo_id: int):
    """Render the full-quality original photo in a browser-supported format (JPEG)."""
    db = await get_db()
    try:
        photo = await get_photo_by_id(db, photo_id)
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        filepath = photo["filepath"]
        full_path = os.path.realpath(os.path.join(PHOTOS_DIR, filepath))

        if not full_path.startswith(os.path.realpath(PHOTOS_DIR) + os.sep):
            raise HTTPException(status_code=403, detail="Access denied")

        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="File not found")

        ext = os.path.splitext(filepath)[1].lower()
        if ext in (".jpg", ".jpeg", ".png"):
            return FileResponse(
                full_path,
                media_type="image/jpeg" if "jpg" in ext or "jpeg" in ext else "image/png",
                headers={"Cache-Control": f"public, max-age={HTTP_CACHE_MAX_AGE}"}
            )

        # For HEIC, cache the rendered JPEG on disk to speed up subsequent loads
        from server.thumbnail import THUMBNAIL_DIR
        render_dir = os.path.join(THUMBNAIL_DIR, "render")
        os.makedirs(render_dir, exist_ok=True)
        
        cached_path = os.path.join(render_dir, f"{photo_id}.jpg")
        
        if os.path.exists(cached_path):
            return FileResponse(
                cached_path,
                media_type="image/jpeg",
                headers={"Cache-Control": f"public, max-age={HTTP_CACHE_MAX_AGE}"}
            )

        import io
        from PIL import Image
        import pillow_heif
        pillow_heif.register_heif_opener()

        def convert_to_jpeg():
            img = Image.open(full_path)
            exif = img.getexif()
            if exif:
                orientation = exif.get(274)
                if orientation:
                    rotation_map = {3: 180, 6: 270, 8: 90}
                    if orientation in rotation_map:
                        img = img.rotate(rotation_map[orientation], expand=True)
                    elif orientation in (2, 4, 5, 7):
                        img = img.transpose(Image.FLIP_LEFT_RIGHT)
                        if orientation in (5, 7):
                            img = img.rotate(90 if orientation == 5 else 270, expand=True)
            
            if img.mode != "RGB":
                img = img.convert("RGB")
                
            # Limit max size to 4K to speed up JPEG encoding and reduce memory footprint
            # while still maintaining visually "full" quality on modern screens.
            img.thumbnail((3840, 3840), Image.Resampling.LANCZOS)
                
            # Save to cache file with quality=85
            img.save(cached_path, format="JPEG", quality=85, optimize=True)
            
        await asyncio.to_thread(convert_to_jpeg)
        
        return FileResponse(
            cached_path,
            media_type="image/jpeg",
            headers={"Cache-Control": f"public, max-age={HTTP_CACHE_MAX_AGE}"}
        )

    finally:
        await db.close()

@app.get("/api/photos/{photo_id}/live-video")
async def api_get_live_video(photo_id: int):
    """Serve the paired MOV file for a Live Photo."""
    db = await get_db()
    try:
        photo = await get_photo_by_id(db, photo_id)
        if not photo or not photo.get("live_photo_mov"):
            raise HTTPException(status_code=404, detail="Live Photo video not found")

        filepath = photo["live_photo_mov"]
        full_path = os.path.realpath(os.path.join(PHOTOS_DIR, filepath))

        if not full_path.startswith(os.path.realpath(PHOTOS_DIR) + os.sep):
            raise HTTPException(status_code=403, detail="Access denied")

        if not os.path.exists(full_path):
            raise HTTPException(status_code=404, detail="Video file not found on disk")

        return FileResponse(
            full_path,
            media_type="video/quicktime",
            headers={"X-Content-Type-Options": "nosniff"},
        )
    finally:
        await db.close()


@app.get("/api/photos/{photo_id}/thumbnail/{size}")
async def api_get_thumbnail(photo_id: int, size: str):
    """Serve a thumbnail image."""
    if size not in ("small", "medium"):
        raise HTTPException(status_code=400, detail="Invalid size. Use 'small' or 'medium'.")

    db = await get_db()
    try:
        photo = await get_photo_by_id(db, photo_id)
        if not photo:
            raise HTTPException(status_code=404, detail="Photo not found")

        thumb_path = get_thumbnail_path(photo["filepath"], size)

        if not os.path.exists(thumb_path):
            # Try to generate on-demand
            success = await asyncio.to_thread(
                generate_thumbnail, photo_id, photo["filepath"], photo["file_type"]
            )
            if success:
                await update_photo(db, photo_id, {"has_thumbnail": 1})
            else:
                raise HTTPException(status_code=500, detail="Failed to generate thumbnail")
    finally:
        await db.close()

    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    # ETag based on file modification time for cache busting
    stat = os.stat(thumb_path)
    etag = f'"{int(stat.st_mtime)}-{stat.st_size}"'

    return FileResponse(
        thumb_path,
        media_type="image/webp",
        headers={
            "Cache-Control": f"public, max-age={HTTP_CACHE_MAX_AGE}",
            "ETag": etag,
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/api/timeline")
async def api_get_timeline():
    """Get photo counts grouped by date."""
    db = await get_db()
    try:
        return await get_timeline(db)
    finally:
        await db.close()


@app.get("/api/locations")
async def api_get_locations(lang: str = None):
    """Get unique locations with photo counts."""
    db = await get_db()
    try:
        locations = await get_locations(db)
        target_lang = lang if lang else os.getenv("APP_LANGUAGE", "zh")
        if target_lang == "zh":
            unique_locs = {loc["location_name"] for loc in locations if loc.get("location_name")}
            translations = await asyncio.gather(*(translate_text(loc) for loc in unique_locs))
            trans_map = dict(zip(unique_locs, translations))
            for loc in locations:
                if loc.get("location_name"):
                    loc["display_location"] = trans_map[loc["location_name"]]
        else:
            for loc in locations:
                loc["display_location"] = loc.get("location_name")
        return locations
    finally:
        await db.close()


@app.get("/api/scan/status")
async def get_scan_status():
    """Get the current status of background scanning."""
    return scan_state


@app.get("/api/config")
async def get_config():
    """Get frontend configuration."""
    return {
        "language": APP_LANGUAGE,
        "theme": APP_THEME,
        "load_original_on_click": LOAD_ORIGINAL_ON_CLICK
    }


@app.post("/api/scan/start")
async def api_start_scan():
    """Start an incremental scan."""
    if scan_state["status"] in ("scanning", "generating_thumbnails", "geocoding"):
        return {"message": "Scan already in progress", "status": scan_state["status"]}

    asyncio.create_task(_run_full_scan())
    return {"message": "Scan started"}


# --- Static Files ---
# Serve frontend files
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# --- Error Handling ---

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Generic error handler that doesn't expose internal details."""
    logger.error("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred"},
    )


if __name__ == "__main__":
    import uvicorn
    # Start the server
    uvicorn.run(
        "server.app:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="info",
    )
