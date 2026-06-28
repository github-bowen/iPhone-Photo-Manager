# iPhone Photo Manager

*Read this in other languages: [English](README.md), [中文](README_zh.md).*

This is a lightweight, responsive web application for managing, organizing, and exploring your iPhone photos and videos. It organizes your media by timeline and automatically groups them by geocoded locations using embedded EXIF data.

## Demo
<p align="center">
  <img src="assets/demo1.png" width="80%" style="margin-bottom: 20px" />
  <br />
  <img src="assets/demo2.png" width="80%" />
</p>
*Demo showcasing timeline scrolling, location filtering, and language switching.*

### ✨ Features

A lightweight, local-first web gallery for your iPhone photos. It supports HEIC, Live Photos (MOV), and reverse geocoding without uploading any data to the cloud.

To use it, simply export your iPhone photos and copy them into your configured `PHOTOS_DIR` (default is `./photos` in the project root, which you can configure in your `.env` file). The tool will automatically scan the folder on startup.

**Expected Directory Structure:**

```text
iphone-photo-manager/
├── photos/                  # Your PHOTOS_DIR (configured in .env)
│   ├── 202601/              # (Optional) Group by year/month
│   │   ├── IMG_0001.HEIC
│   │   ├── IMG_0001.MOV     # Paired Live Photo video
│   │   └── IMG_0002.JPG
│   └── ...
├── server/                  # Python backend
│   ├── app.py               # FastAPI entrypoint, routing, background tasks
│   ├── database.py          # SQLite database schema and queries
│   ├── scanner.py           # File scanning and EXIF/MOV metadata extraction
│   ├── thumbnail.py         # WebP thumbnail generation
│   └── geocoder.py          # Offline reverse geocoding (reverse_geocoder + pycountry)
├── frontend/                # Vanilla HTML/CSS/JS frontend (No framework)
│   ├── index.html           # Page structure
│   ├── index.css            # Styles (Dark/Light themes, Mobile queries)
│   └── index.js             # Interaction logic, Gallery rendering, Modal, Sidebar
├── photos/                  # Photo storage directory (Organized by YYYYMM subfolders)
├── data/                    # Runtime data (auto-generated, gitignored)
│   ├── photos.db            # SQLite database
│   └── thumbnails/          # Cache for thumbnails and high-res renders
├── .env                     # Environment variables (do not commit)
├── .env.template            # Environment variables template
├── requirements.txt         # Python dependencies
├── stop.sh                  # Script to stop the server
└── ARCHITECTURE.md          # Architecture and design principles
```

### 🚀 Quick Start

#### 1. Requirements
Python 3.10+ is required.

```bash
# Clone the repository
git clone <repo-url>
cd iphone-photo-manager

# Install dependencies
pip install -r requirements.txt
```

#### 2. Configuration

```bash
# Copy the environment template and modify as needed
cp .env.template .env
```

Key configuration options (`.env`):

| Variable | Default | Description |
|---|---|---|
| `APP_LANGUAGE` | `zh` | UI Language: `zh` (Chinese) or `en` (English) |
| `APP_THEME` | `light` | UI Theme: `light` or `dark` |
| `PHOTOS_DIR` | `photos` | Photo directory path (relative to project root, or absolute) |
| `SERVER_HOST` | `127.0.0.1` | Bind address (use `0.0.0.0` for LAN access) |
| `SERVER_PORT` | `8000` | Server port |
| `SCAN_ON_STARTUP` | `True` | Whether to perform an incremental scan on startup |
| `LOAD_ORIGINAL_ON_CLICK`| `False` | Auto-load 4K high-res image when opening a single photo |
| `DB_PATH` | `data/photos.db` | SQLite database path |
| `THUMBNAIL_DIR` | `data/thumbnails` | Directory for caching thumbnails |

#### 3. Import Photos

Place your iPhone photos into the `photos/` directory, ideally grouped by year/month subfolders.
*(Hint: You can use AirDrop or USB to export directly. The system automatically pairs `.HEIC` and `.MOV` files for Live Photos).*

#### 4. Start the Server

```bash
PYTHONPATH=. python3 server/app.py
```

On the first launch, the server will automatically:
1. Scan files and extract EXIF metadata.
2. Generate WebP thumbnails in the background.
3. Perform offline reverse geocoding.

Once started, open your browser and navigate to: **http://127.0.0.1:8000**

#### 5. Stop the Server

```bash
./stop.sh
```

### 📖 User Guide
- **Browsing**: Scroll down to load more. Daily headers display your trajectory.
- **Timeline**: Click a month in the sidebar to filter. Click the arrow to expand and filter by a specific day.
- **Locations**: Click a country in the sidebar to view all photos from that country, or expand to select a specific city.
- **High-Res Viewing**: Click a photo to open the modal. If `LOAD_ORIGINAL_ON_CLICK` is false, click "View Original File" to render and cache the full-quality image.
