"""
Database module for the iPhone Photo Manager.
Manages SQLite database for photo metadata storage and retrieval.
"""

import aiosqlite
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

_db_env = os.getenv("DB_PATH", "data/photos.db")
if os.path.isabs(_db_env):
    DB_PATH = os.path.realpath(_db_env)
else:
    DB_PATH = os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), _db_env))


SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    directory TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    width INTEGER,
    height INTEGER,
    taken_at TEXT,
    timezone TEXT,
    latitude REAL,
    longitude REAL,
    altitude REAL,
    location_name TEXT,
    camera_make TEXT,
    camera_model TEXT,
    lens_model TEXT,
    duration REAL,
    is_live_photo INTEGER DEFAULT 0,
    live_photo_mov TEXT,
    is_screenshot INTEGER DEFAULT 0,
    is_edited INTEGER DEFAULT 0,
    original_file TEXT,
    has_thumbnail INTEGER DEFAULT 0,
    scan_version INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_taken_at ON photos(taken_at);
CREATE INDEX IF NOT EXISTS idx_location ON photos(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_location_name ON photos(location_name);
CREATE INDEX IF NOT EXISTS idx_file_type ON photos(file_type);
CREATE INDEX IF NOT EXISTS idx_directory ON photos(directory);
CREATE INDEX IF NOT EXISTS idx_is_live_photo ON photos(is_live_photo);
"""


async def init_db():
    """Initialize the database and create tables if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def insert_photo(db: aiosqlite.Connection, photo_data: dict) -> Optional[int]:
    """Insert a photo record. Returns the row id or None if already exists."""
    columns = ", ".join(photo_data.keys())
    placeholders = ", ".join(["?"] * len(photo_data))
    try:
        cursor = await db.execute(
            f"INSERT OR IGNORE INTO photos ({columns}) VALUES ({placeholders})",
            list(photo_data.values()),
        )
        await db.commit()
        return cursor.lastrowid if cursor.lastrowid else None
    except Exception:
        return None


async def update_photo(db: aiosqlite.Connection, photo_id: int, updates: dict):
    """Update a photo record by id."""
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    await db.execute(
        f"UPDATE photos SET {set_clause} WHERE id = ?",
        list(updates.values()) + [photo_id],
    )
    await db.commit()


async def get_all_filepaths(db: aiosqlite.Connection) -> set[str]:
    """Get all filepaths currently in the database."""
    rows = await db.execute_fetchall("SELECT filepath FROM photos")
    return {row[0] for row in rows}

async def delete_photo_by_filepath(db: aiosqlite.Connection, filepath: str):
    """Delete a photo record by filepath."""
    await db.execute("DELETE FROM photos WHERE filepath = ?", (filepath,))
    await db.commit()

async def get_photos(
    db: aiosqlite.Connection,
    page: int = 1,
    per_page: int = 50,
    file_type: Optional[str] = None,
    location_name: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_screenshot: Optional[bool] = None,
) -> tuple[list[dict], int]:
    """Get paginated photos with optional filters. Returns (photos, total_count)."""
    conditions = ["file_type != 'AAE'"]
    params = []

    # Exclude edited duplicates (IMG_E*) from main listing;
    # they can still be viewed via their original's detail.
    conditions.append("is_edited = 0")

    # Exclude Live-Photo MOV sidecar files from the grid;
    # they are played inline when the paired HEIC is hovered.
    conditions.append(
        "NOT (file_type = 'MOV' AND id IN "
        "(SELECT p2.id FROM photos p2 "
        " INNER JOIN photos p3 ON p3.live_photo_mov = p2.filepath "
        " WHERE p2.file_type = 'MOV'))"
    )

    if file_type:
        conditions.append("file_type = ?")
        params.append(file_type.upper())

    if location_name:
        conditions.append("location_name = ?")
        params.append(location_name)

    if city:
        cq = "Zuerich" if city == "Zurich" else city
        conditions.append("(location_name LIKE ? OR location_name LIKE ?)")
        params.extend([f"{cq}%", f"% {cq}%"])

    if country:
        conditions.append("(location_name = ? OR location_name LIKE ?)")
        params.extend([country, f"%, {country}"])

    if date_from:
        conditions.append("taken_at >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("taken_at <= ?")
        params.append(date_to)

    if is_screenshot is not None:
        conditions.append("is_screenshot = ?")
        params.append(1 if is_screenshot else 0)

    where = " AND ".join(conditions)

    # Get total count
    count_row = await db.execute_fetchall(
        f"SELECT COUNT(*) as cnt FROM photos WHERE {where}", params
    )
    total = count_row[0][0] if count_row else 0

    # Get paginated results
    offset = (page - 1) * per_page
    rows = await db.execute_fetchall(
        f"SELECT * FROM photos WHERE {where} ORDER BY taken_at DESC, filename ASC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    )

    photos = [dict(row) for row in rows]
    return photos, total


async def get_photo_by_id(db: aiosqlite.Connection, photo_id: int) -> Optional[dict]:
    """Get a single photo by id."""
    rows = await db.execute_fetchall(
        "SELECT * FROM photos WHERE id = ?", [photo_id]
    )
    return dict(rows[0]) if rows else None


async def get_timeline(db: aiosqlite.Connection) -> list[dict]:
    """Get photo counts grouped by date."""
    rows = await db.execute_fetchall(
        """SELECT date(taken_at) as date, COUNT(*) as count
           FROM photos
           WHERE taken_at IS NOT NULL AND file_type != 'AAE' AND is_edited = 0
           GROUP BY date(taken_at)
           ORDER BY date DESC"""
    )
    return [dict(row) for row in rows]


async def get_locations(db: aiosqlite.Connection) -> list[dict]:
    """Get unique locations with photo counts."""
    rows = await db.execute_fetchall(
        """SELECT location_name, COUNT(*) as count,
                  AVG(latitude) as avg_lat, AVG(longitude) as avg_lng
           FROM photos
           WHERE location_name IS NOT NULL AND file_type != 'AAE' AND is_edited = 0
           GROUP BY location_name
           ORDER BY count DESC"""
    )
    return [dict(row) for row in rows]


async def get_photo_count(db: aiosqlite.Connection) -> int:
    """Get total number of scanned photos."""
    rows = await db.execute_fetchall("SELECT COUNT(*) FROM photos")
    return rows[0][0] if rows else 0


async def clear_all_locations(db: aiosqlite.Connection):
    """Clear all location_name entries so they can be re-geocoded."""
    await db.execute("UPDATE photos SET location_name = NULL")
    await db.commit()


async def get_photos_without_thumbnails(db: aiosqlite.Connection, limit: int = 50) -> list[dict]:
    """Get photos that need thumbnail generation."""
    rows = await db.execute_fetchall(
        "SELECT * FROM photos WHERE has_thumbnail = 0 AND file_type IN ('HEIC', 'JPG', 'PNG', 'MOV') LIMIT ?",
        [limit],
    )
    return [dict(row) for row in rows]


async def get_photos_without_location(db: aiosqlite.Connection) -> list[dict]:
    """Get photos that have GPS but no location name."""
    rows = await db.execute_fetchall(
        "SELECT id, latitude, longitude FROM photos WHERE latitude IS NOT NULL AND location_name IS NULL"
    )
    return [dict(row) for row in rows]
