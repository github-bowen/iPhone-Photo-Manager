# Architecture & Design Principles

*Read this in other languages: [English](ARCHITECTURE.md), [中文](ARCHITECTURE_zh.md).*

This document explains the technical architecture, data flows, module design, and key implementation details of the iPhone Photo Manager.

### 1. Overall Architecture

```text
┌─────────────────────────────────────────────────────┐
│                    Browser (Frontend)                 │
│  index.html + index.css + index.js                   │
│  ─ Static files served by FastAPI StaticFiles         │
│  ─ Vanilla JS, no framework dependencies              │
└────────────────────┬────────────────────────────────┘
                     │ HTTP REST API
                     ▼
┌─────────────────────────────────────────────────────┐
│               FastAPI Server (Backend)                │
│  server/app.py                                       │
│  ├── API Routing         (GET /api/photos, etc.)      │
│  ├── Background Tasks    (asyncio.create_task)        │
│  └── Security Middleware (CSP, X-Frame-Options)       │
├──────────┬──────────┬──────────┬─────────────────────┤
│ scanner  │ thumbnail│ geocoder │ database            │
│ .py      │ .py      │ .py      │ .py                 │
└──────────┴──────────┴──────────┴─────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                  Data Storage Layer                   │
│  data/photos.db     — SQLite (async via aiosqlite)    │
│  data/thumbnails/   — WebP / JPEG cache               │
│  photos/            — Original photos (Read-only)     │
└─────────────────────────────────────────────────────┘
```

**Design Principles:**
1. **Local-First**: All processing happens on your device. No data leaves your machine.
2. **Zero-Config Import**: Just drop photos into the `photos/` directory.
3. **Incremental**: Only processes new or deleted files, avoiding redundant computations.
4. **Offline Capability**: Geocoding uses an offline engine; no external API keys needed.

### 2. Startup & Data Flow

#### 2.1 Startup Process
When `app.py` starts, it initializes the SQLite schema. Based on the database count and the `SCAN_ON_STARTUP` environment variable, it either triggers a full incremental scan or just processes pending background tasks (missing thumbnails/geocoding).

#### 2.2 Full Scan Process
The scan has three phases, with real-time progress broadcasted via `/api/scan/status`:
1. **File Indexing**: Calculates the difference between disk files and database records to insert or delete entries.
2. **Thumbnail Generation**: Concurrently generates WebP thumbnails (small and medium sizes).
3. **Geocoding**: Batch reverse geocoding utilizing clustered coordinates and `reverse_geocoder`.

#### 2.3 High-Res Rendering (HEIC)
When requesting the full-quality image via `/api/photos/{id}/render`:
- Standard JPG/PNGs are streamed directly.
- HEIC files are loaded via `pillow_heif`, scaled safely to 4K resolution (to reduce memory overhead while maintaining full visual fidelity), converted to JPEG, and cached on disk. Subsequent requests are served instantly from the cache.

### 3. Module Details

#### 3.1 `scanner.py` — File Scanning & Metadata
Extracts EXIF metadata from images and parses QuickTime atoms from MOV files directly (without FFmpeg). Pairs `.HEIC` files with corresponding `.MOV` files automatically to identify Live Photos.

#### 3.2 `thumbnail.py` — Thumbnail Generation
Mirrors the original photo directory structure inside the cache. Utilizes Pillow to correct EXIF orientation and generates highly optimized WebP images.

#### 3.3 `geocoder.py` — Offline Geocoding
Uses a KD-Tree based offline reverse geocoder. Coordinates are rounded to 2 decimal places (approx. 1.1km precision) for clustering and deduplication.

#### 3.4 `database.py` — SQLite Layer
A single `photos` table with 24 columns covering file info, GPS, EXIF parameters, and metadata tags. Async access via `aiosqlite`.

#### 3.5 Frontend Architecture (`index.js`)
A single-page application built with Vanilla JS.
- **Infinite Scrolling**: Uses `IntersectionObserver`.
- **Mobile Responsive**: Implements a sliding sidebar drawer using CSS transforms.
- **Live Photos**: Hovering over a thumbnail dynamically creates a `<video autoplay>` overlay.
- **Timeline & Locations**: Tree-based filtering (Month -> Day, Country -> City).
