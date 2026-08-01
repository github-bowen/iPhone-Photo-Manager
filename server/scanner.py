"""
File scanner module for the iPhone Photo Manager.
Scans photos directory, extracts EXIF metadata from HEIC/JPG/PNG files,
and parses MOV metadata.
"""

import os
import struct
import datetime
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# Register HEIC support with Pillow
import pillow_heif
pillow_heif.register_heif_opener()
if hasattr(pillow_heif, "register_avif_opener"):
    pillow_heif.register_avif_opener()

logger = logging.getLogger(__name__)

SCAN_VERSION = 2
IMAGE_EXTENSIONS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp", ".avif"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".3gp"}
SIDECAR_EXTENSIONS = {".aae"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | SIDECAR_EXTENSIONS


def _determine_taken_at(filepath: str, exif_date: Optional[str] = None) -> str:
    """
    3-step date determination logic:
    1. Extract Year and Month from Directory (or mtime fallback).
    2. Try extracting precise Date and Time from EXIF or Filename.
    3. If precise date/time unavailable, set to YYYY-MM-00T00:00:00 ('xxxx年xx月未确定日期').
    """
    filename = os.path.basename(filepath)
    dirname = os.path.basename(os.path.dirname(filepath))

    # --- Step 1: Extract Year and Month from Directory (or mtime fallback) ---
    year = None
    month = None

    m_dir = re.search(r'(19\d{2}|20\d{2})[-_]?([01]\d)', dirname)
    if m_dir:
        y, m = int(m_dir.group(1)), int(m_dir.group(2))
        if 1900 <= y <= 2100 and 1 <= m <= 12:
            year, month = f"{y:04d}", f"{m:02d}"

    if not year or not month:
        try:
            mtime = os.path.getmtime(filepath)
            dt_m = datetime.datetime.fromtimestamp(mtime)
            year, month = f"{dt_m.year:04d}", f"{dt_m.month:02d}"
        except Exception:
            dt_n = datetime.datetime.now()
            year, month = f"{dt_n.year:04d}", f"{dt_n.month:02d}"

    # --- Step 2: Try extracting precise Date and Time ---
    if exif_date:
        try:
            cleaned = exif_date.replace(":", "-", 2) if exif_date.count(":") >= 2 and "T" not in exif_date else exif_date
            dt_exif = datetime.datetime.fromisoformat(cleaned[:19])
            return dt_exif.isoformat()
        except ValueError:
            pass

    # 2a. Check WeChat mmexport Unix timestamp (e.g. mmexport1661820820127)
    m_mm = re.search(r'mmexport(\d{10,13})', filename)
    if m_mm:
        ts = int(m_mm.group(1))
        if ts > 1e11:
            ts /= 1000.0
        try:
            dt = datetime.datetime.fromtimestamp(ts)
            if 2000 <= dt.year <= 2030:
                return dt.isoformat()
        except Exception:
            pass

    # 2b. Check Filename starting with MMDD_HHMMSS (e.g. 0830_122200_...) using Step 1 Year
    if year:
        m_fn_start = re.search(r'^(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[-_]([01]\d|2[0-3])([0-5]\d)([0-5]\d)', filename)
        if m_fn_start:
            try:
                dt = datetime.datetime(
                    int(year), int(m_fn_start.group(1)), int(m_fn_start.group(2)),
                    int(m_fn_start.group(3)), int(m_fn_start.group(4)), int(m_fn_start.group(5))
                )
                return dt.isoformat()
            except ValueError:
                pass

    # 2c. From Filename with YYYYMMDD_HHMMSS or YYYY-MM-DD_HHMMSS (bounded by non-digits)
    m_fn = re.search(r'(?<!\d)(19\d{2}|20\d{2})[-_]?(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])[-_]?([01]\d|2[0-3])[-_]?([0-5]\d)[-_]?([0-5]\d)(?!\d)', filename)
    if m_fn:
        try:
            dt = datetime.datetime(
                int(m_fn.group(1)), int(m_fn.group(2)), int(m_fn.group(3)),
                int(m_fn.group(4)), int(m_fn.group(5)), int(m_fn.group(6))
            )
            return dt.isoformat()
        except ValueError:
            pass

    # 2d. From Filename with YYYYMMDD or YYYY-MM-DD (bounded by non-digits)
    m_fn2 = re.search(r'(?<!\d)(19\d{2}|20\d{2})[-_]?(0[1-9]|1[0-2])[-_]?(0[1-9]|[12]\d|3[01])(?!\d)', filename)
    if m_fn2:
        try:
            dt = datetime.datetime(int(m_fn2.group(1)), int(m_fn2.group(2)), int(m_fn2.group(3)))
            return dt.isoformat()
        except ValueError:
            pass

    # --- Step 3: If Step 2 fails, set to YYYY-MM-99T23:59:59 ---
    return f"{year}-{month}-99T23:59:59"


def get_all_files_on_disk(photos_dir: str) -> set[str]:
    """Fast recursive directory traversal to get all valid photo file paths."""
    valid_paths = set()
    photos_dir = os.path.realpath(photos_dir)

    for root, _, files in os.walk(photos_dir):
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].upper()
            if ext.lower() in SUPPORTED_EXTENSIONS:
                filepath = os.path.join(root, fname)
                if os.path.isfile(filepath):
                    rel_path = os.path.relpath(filepath, photos_dir)
                    valid_paths.add(rel_path)
                    
    return valid_paths


def scan_specific_files(photos_dir: str, target_paths: set[str]) -> list[dict]:
    """Extract metadata only for the specifically requested paths."""
    results = []
    photos_dir = os.path.realpath(photos_dir)
    
    # Group target_paths by directory
    dir_to_files = {}
    for rel_path in target_paths:
        subdir_name, fname = os.path.split(rel_path)
        if subdir_name not in dir_to_files:
            dir_to_files[subdir_name] = []
        dir_to_files[subdir_name].append(fname)
        
    for subdir_name, new_fnames in dir_to_files.items():
        subdir_path = os.path.join(photos_dir, subdir_name)
        if not os.path.isdir(subdir_path):
            continue
            
        # Get full list of files in this directory to handle pairings (e.g. .MOV exists)
        files_in_dir = set(os.listdir(subdir_path))
        files_by_lower = {name.lower(): name for name in files_in_dir}
        
        for fname in new_fnames:
            filepath = os.path.join(subdir_path, fname)
            ext = os.path.splitext(fname)[1].upper()
            
            file_type = ext.lstrip(".").upper()
            if file_type == "JPEG":
                file_type = "JPG"
                
            stat = os.stat(filepath)
            photo_data = {
                "filepath": os.path.join(subdir_name, fname),
                "filename": fname,
                "directory": subdir_name,
                "file_type": file_type,
                "file_size": stat.st_size,
                "scan_version": SCAN_VERSION,
                "is_live_photo": 0,
                "live_photo_mov": None,
                "is_motion_photo": 0,
                "motion_photo_offset": None,
                "motion_photo_length": None,
                "motion_photo_mime": None,
                "is_screenshot": 0,
                "is_edited": 0,
                "original_file": None,
            }
            
            # Detect edited versions (IMG_E*)
            if fname.startswith("IMG_E"):
                photo_data["is_edited"] = 1
                orig_name = fname.replace("IMG_E", "IMG_", 1)
                if orig_name in files_in_dir:
                    photo_data["original_file"] = os.path.join(subdir_name, orig_name)

            # Detect Live Photo pairs
            stem = os.path.splitext(fname)[0]
            mov_name = files_by_lower.get(f"{stem}.mov".lower())
            if file_type in ("HEIC", "HEIF") and mov_name:
                photo_data["is_live_photo"] = 1
                photo_data["live_photo_mov"] = os.path.join(subdir_name, mov_name)

            # Extract metadata
            if file_type in ("HEIC", "HEIF", "JPG", "PNG", "WEBP", "AVIF"):
                meta = extract_image_metadata(filepath, file_type)
                photo_data.update(meta)
                motion_meta = extract_motion_photo_metadata(filepath)
                if motion_meta:
                    photo_data.update(motion_meta)
            elif file_type in ("MOV", "MP4", "3GP"):
                meta = extract_video_metadata(filepath)
                photo_data.update(meta)
            elif file_type == "AAE":
                meta = extract_aae_metadata(filepath)
                photo_data.update(meta)

            # Detect screenshots
            path_parts = {part.lower() for part in subdir_name.split(os.sep)}
            name_lower = fname.lower()
            if (
                "screenshots" in path_parts
                or "screenshot" in name_lower
                or name_lower.startswith(("screencap", "screen_shot", "screen-shot"))
            ):
                photo_data["is_screenshot"] = 1
            elif file_type == "PNG" and photo_data.get("width") and photo_data.get("height"):
                w, h = photo_data["width"], photo_data["height"]
                # Common iPhone screenshot sizes
                if (w, h) in ((1179, 2556), (2556, 1179), (1170, 2532), (2532, 1170),
                              (1284, 2778), (2778, 1284), (1290, 2796), (2796, 1290)):
                    photo_data["is_screenshot"] = 1

            results.append(photo_data)

    return results


def extract_image_metadata(filepath: str, file_type: str) -> dict:
    """Extract EXIF metadata from an image file."""
    meta = {}

    try:
        img = Image.open(filepath)
        meta["width"] = img.size[0]
        meta["height"] = img.size[1]

        exif = img.getexif()
        if not exif:
            # For HEIC, try raw binary parsing as fallback
            if file_type in ("HEIC", "HEIF"):
                raw_meta = _parse_heic_exif_raw(filepath)
                meta.update(raw_meta)
        else:
            # Basic IFD0 tags
            meta["camera_make"] = exif.get(271)  # Make
            meta["camera_model"] = exif.get(272)  # Model

            # EXIF IFD
            from PIL.ExifTags import IFD
            exif_ifd = exif.get_ifd(IFD.Exif)
            if exif_ifd:
                dt_orig = exif_ifd.get(36867)  # DateTimeOriginal
                dt_dig = exif_ifd.get(36868)   # DateTimeDigitized
                dt = dt_orig or dt_dig or exif.get(306)  # DateTime

                if dt:
                    # Convert "2026:05:08 13:14:21" to ISO format
                    try:
                        parsed = datetime.datetime.strptime(dt[:19], "%Y:%m:%d %H:%M:%S")
                        meta["taken_at"] = parsed.isoformat()
                    except ValueError:
                        meta["taken_at"] = dt

                # Timezone
                tz = exif_ifd.get(36880) or exif_ifd.get(36881)  # OffsetTime / OffsetTimeOriginal
                if tz:
                    meta["timezone"] = tz

                # Lens
                lens = exif_ifd.get(42036)  # LensModel
                if lens:
                    meta["lens_model"] = lens

            # GPS IFD
            gps_ifd = exif.get_ifd(IFD.GPSInfo)
            if gps_ifd:
                lat = _parse_gps_coord(gps_ifd.get(2), gps_ifd.get(1))  # GPSLatitude, GPSLatitudeRef
                lng = _parse_gps_coord(gps_ifd.get(4), gps_ifd.get(3))  # GPSLongitude, GPSLongitudeRef
                if lat is not None:
                    meta["latitude"] = lat
                if lng is not None:
                    meta["longitude"] = lng

                alt = gps_ifd.get(6)  # GPSAltitude
                if alt is not None:
                    try:
                        meta["altitude"] = float(alt)
                    except (TypeError, ValueError):
                        pass

        img.close()
    except Exception as e:
        logger.debug("Failed to extract metadata from %s: %s", filepath, e)
        # Try raw parsing for HEIC files
        if file_type in ("HEIC", "HEIF"):
            raw_meta = _parse_heic_exif_raw(filepath)
            meta.update(raw_meta)

    meta["taken_at"] = _determine_taken_at(filepath, meta.get("taken_at"))

    return meta


def _xml_local_name(name: str) -> str:
    """Return the local portion of an XML namespace-qualified name."""
    return name.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _motion_xmp_values(data: bytes) -> tuple[Optional[bool], Optional[int], Optional[int], Optional[str]]:
    """Read modern and legacy Motion Photo fields from XMP packets."""
    motion_flag = None
    video_length = None
    legacy_offset = None
    video_mime = None

    packets = re.findall(
        rb"<(?:[A-Za-z_][\w.-]*:)?xmpmeta\b.*?</(?:[A-Za-z_][\w.-]*:)?xmpmeta>",
        data,
        flags=re.DOTALL,
    )
    for packet in packets:
        try:
            root = ET.fromstring(packet)
        except ET.ParseError:
            continue

        for element in root.iter():
            attrs = {_xml_local_name(key): value for key, value in element.attrib.items()}
            if "MotionPhoto" in attrs:
                try:
                    motion_flag = int(attrs["MotionPhoto"]) == 1
                except ValueError:
                    motion_flag = False
            if "MicroVideo" in attrs and motion_flag is None:
                try:
                    motion_flag = int(attrs["MicroVideo"]) == 1
                except ValueError:
                    pass
            if "MicroVideoOffset" in attrs:
                try:
                    legacy_offset = int(attrs["MicroVideoOffset"])
                except ValueError:
                    pass
            if attrs.get("Semantic", "").lower() == "motionphoto":
                try:
                    video_length = int(attrs.get("Length", ""))
                except ValueError:
                    pass
                video_mime = attrs.get("Mime") or video_mime

    # Some vendor XMP uses malformed/unbound prefixes. Keep a narrow fallback
    # over individual XML tags so those files remain importable.
    text = data.decode("latin-1", errors="ignore")
    flag_match = re.search(r"(?:G?Camera:)?MotionPhoto\s*=\s*['\"](-?\d+)['\"]", text)
    if flag_match:
        motion_flag = int(flag_match.group(1)) == 1
    elif motion_flag is None:
        micro_match = re.search(r"(?:G?Camera:)?MicroVideo\s*=\s*['\"](\d+)['\"]", text)
        if micro_match:
            motion_flag = int(micro_match.group(1)) == 1

    offset_match = re.search(r"(?:G?Camera:)?MicroVideoOffset\s*=\s*['\"](\d+)['\"]", text)
    if offset_match:
        legacy_offset = int(offset_match.group(1))

    for tag in re.findall(r"<[^>]+>", text):
        if re.search(r"(?:Item:)?Semantic\s*=\s*['\"]MotionPhoto['\"]", tag, re.IGNORECASE):
            length_match = re.search(r"(?:Item:)?Length\s*=\s*['\"](\d+)['\"]", tag)
            mime_match = re.search(r"(?:Item:)?Mime\s*=\s*['\"]([^'\"]+)['\"]", tag)
            if length_match:
                video_length = int(length_match.group(1))
            if mime_match:
                video_mime = mime_match.group(1)
            break

    return motion_flag, video_length, legacy_offset, video_mime


def _is_iso_video_at(filepath: str, offset: int, length: int) -> bool:
    """Validate that a proposed embedded range starts with an ISO video box."""
    if offset < 0 or length < 12:
        return False
    try:
        with open(filepath, "rb") as file:
            file.seek(offset)
            header = file.read(16)
        return len(header) >= 8 and header[4:8] in (b"ftyp", b"moov", b"mdat")
    except OSError:
        return False


def _find_embedded_video_after_marker(filepath: str, file_size: int) -> Optional[tuple[int, int]]:
    """Locate legacy Samsung MotionPhoto_Data payloads near the end of a JPEG."""
    tail_size = min(file_size, 64 * 1024 * 1024)
    try:
        with open(filepath, "rb") as file:
            file.seek(file_size - tail_size)
            tail = file.read(tail_size)
    except OSError:
        return None

    marker_pos = tail.rfind(b"MotionPhoto_Data")
    search_start = marker_pos + len(b"MotionPhoto_Data") if marker_pos >= 0 else 0
    ftyp_pos = tail.find(b"ftyp", search_start)
    if ftyp_pos < 4 or (marker_pos < 0 and b"MotionPhoto" not in tail[:ftyp_pos]):
        return None

    offset = file_size - tail_size + ftyp_pos - 4
    length = file_size - offset
    return (offset, length) if _is_iso_video_at(filepath, offset, length) else None


def extract_motion_photo_metadata(filepath: str) -> dict:
    """Locate an Android Motion Photo video without modifying the source file."""
    try:
        file_size = os.path.getsize(filepath)
        with open(filepath, "rb") as file:
            head = file.read(min(file_size, 8 * 1024 * 1024))
    except OSError:
        return {}

    motion_flag, video_length, legacy_offset, video_mime = _motion_xmp_values(head)
    if motion_flag is False:
        return {}

    candidates = []
    if video_length:
        candidates.append((file_size - video_length, video_length))
    if legacy_offset and legacy_offset != video_length:
        candidates.append((file_size - legacy_offset, legacy_offset))

    for offset, length in candidates:
        if length <= file_size and _is_iso_video_at(filepath, offset, length):
            return {
                "is_motion_photo": 1,
                "motion_photo_offset": offset,
                "motion_photo_length": length,
                "motion_photo_mime": video_mime if video_mime in ("video/mp4", "video/quicktime") else "video/mp4",
            }

    if motion_flag or b"MotionPhoto_Data" in head:
        marker_result = _find_embedded_video_after_marker(filepath, file_size)
        if marker_result:
            offset, length = marker_result
            return {
                "is_motion_photo": 1,
                "motion_photo_offset": offset,
                "motion_photo_length": length,
                "motion_photo_mime": video_mime if video_mime in ("video/mp4", "video/quicktime") else "video/mp4",
            }

    return {}


def _parse_heic_exif_raw(filepath: str) -> dict:
    """Parse EXIF from HEIC file by searching for TIFF header in binary data."""
    meta = {}
    try:
        with open(filepath, "rb") as f:
            data = f.read(60000)  # EXIF is usually in the first 50KB

        # Search for big-endian TIFF header
        for marker, endian_char in [(b"MM\x00\x2a", ">"), (b"II\x2a\x00", "<")]:
            idx = data.find(marker)
            if idx == -1:
                continue

            ifd_offset = struct.unpack(f"{endian_char}I", data[idx + 4 : idx + 8])[0]
            ifd0 = _read_ifd(data, idx, ifd_offset, endian_char)

            # Make, Model, DateTime
            if 0x010F in ifd0:
                meta["camera_make"] = ifd0[0x010F]
            if 0x0110 in ifd0:
                meta["camera_model"] = ifd0[0x0110]
            if 0x0132 in ifd0:
                dt = ifd0[0x0132]
                if isinstance(dt, str):
                    try:
                        parsed = datetime.datetime.strptime(dt[:19], "%Y:%m:%d %H:%M:%S")
                        meta["taken_at"] = parsed.isoformat()
                    except ValueError:
                        meta["taken_at"] = dt

            # EXIF IFD
            if 0x8769 in ifd0:
                exif_ifd = _read_ifd(data, idx, ifd0[0x8769], endian_char)
                if 0x9003 in exif_ifd:  # DateTimeOriginal
                    dt = exif_ifd[0x9003]
                    if isinstance(dt, str):
                        try:
                            parsed = datetime.datetime.strptime(dt[:19], "%Y:%m:%d %H:%M:%S")
                            meta["taken_at"] = parsed.isoformat()
                        except ValueError:
                            pass
                if 0x9010 in exif_ifd:  # OffsetTime
                    meta["timezone"] = exif_ifd[0x9010]
                if 0x9011 in exif_ifd:  # OffsetTimeOriginal
                    meta["timezone"] = exif_ifd[0x9011]
                if 0xA434 in exif_ifd:  # LensModel
                    meta["lens_model"] = exif_ifd[0xA434]

            # GPS IFD
            if 0x8825 in ifd0:
                gps_ifd = _read_ifd(data, idx, ifd0[0x8825], endian_char)
                lat = _parse_gps_from_raw(gps_ifd, 2, 1, endian_char, data, idx)
                lng = _parse_gps_from_raw(gps_ifd, 4, 3, endian_char, data, idx)
                if lat is not None:
                    meta["latitude"] = lat
                if lng is not None:
                    meta["longitude"] = lng

                if 6 in gps_ifd and isinstance(gps_ifd[6], str) and "/" in gps_ifd[6]:
                    try:
                        parts = gps_ifd[6].split("/")
                        meta["altitude"] = int(parts[0]) / int(parts[1])
                    except (ValueError, ZeroDivisionError):
                        pass

            break
    except Exception as e:
        logger.debug("Raw HEIC EXIF parsing failed for %s: %s", filepath, e)

    return meta


def _read_ifd(data: bytes, tiff_start: int, ifd_offset: int, endian: str) -> dict:
    """Read an IFD (Image File Directory) from TIFF data."""
    result = {}
    abs_offset = tiff_start + ifd_offset
    if abs_offset + 2 > len(data):
        return result

    num_entries = struct.unpack(f"{endian}H", data[abs_offset : abs_offset + 2])[0]
    type_sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8, 12: 8}

    for i in range(min(num_entries, 50)):
        entry_off = abs_offset + 2 + i * 12
        if entry_off + 12 > len(data):
            break

        tag = struct.unpack(f"{endian}H", data[entry_off : entry_off + 2])[0]
        type_id = struct.unpack(f"{endian}H", data[entry_off + 2 : entry_off + 4])[0]
        count = struct.unpack(f"{endian}I", data[entry_off + 4 : entry_off + 8])[0]
        value_raw = data[entry_off + 8 : entry_off + 12]

        total_size = count * type_sizes.get(type_id, 1)

        if total_size <= 4:
            value_data = value_raw[:total_size]
        else:
            val_offset = struct.unpack(f"{endian}I", value_raw)[0]
            abs_val = tiff_start + val_offset
            if abs_val + total_size <= len(data):
                value_data = data[abs_val : abs_val + total_size]
            else:
                value_data = b""

        if type_id == 2 and value_data:  # ASCII
            result[tag] = value_data.decode("ascii", errors="replace").rstrip("\x00")
        elif type_id == 3 and len(value_data) >= 2:  # SHORT
            result[tag] = struct.unpack(f"{endian}H", value_data[:2])[0]
        elif type_id == 4 and len(value_data) >= 4:  # LONG
            result[tag] = struct.unpack(f"{endian}I", value_data[:4])[0]
        elif type_id == 5 and len(value_data) >= 8:  # RATIONAL
            vals = []
            for j in range(count):
                if len(value_data) >= (j + 1) * 8:
                    n = struct.unpack(f"{endian}I", value_data[j * 8 : j * 8 + 4])[0]
                    d = struct.unpack(f"{endian}I", value_data[j * 8 + 4 : j * 8 + 8])[0]
                    vals.append(f"{n}/{d}")
            result[tag] = vals if len(vals) > 1 else (vals[0] if vals else "")
        elif type_id == 10 and len(value_data) >= 8:  # SRATIONAL
            vals = []
            for j in range(count):
                if len(value_data) >= (j + 1) * 8:
                    n = struct.unpack(f"{endian}i", value_data[j * 8 : j * 8 + 4])[0]
                    d = struct.unpack(f"{endian}i", value_data[j * 8 + 4 : j * 8 + 8])[0]
                    vals.append(f"{n}/{d}")
            result[tag] = vals if len(vals) > 1 else (vals[0] if vals else "")
        else:
            result[tag] = f"<type={type_id},count={count}>"

    return result


def _parse_gps_coord(dms_tuple, ref: Optional[str]) -> Optional[float]:
    """Convert GPS DMS tuple from Pillow EXIF to decimal degrees."""
    if dms_tuple is None or ref is None:
        return None
    try:
        if isinstance(dms_tuple, tuple) and len(dms_tuple) == 3:
            d = float(dms_tuple[0])
            m = float(dms_tuple[1])
            s = float(dms_tuple[2])
            decimal = d + m / 60.0 + s / 3600.0
            if ref in ("S", "W"):
                decimal = -decimal
            return round(decimal, 8)
    except (TypeError, ValueError, IndexError):
        pass
    return None


def _parse_gps_from_raw(
    gps_ifd: dict, coord_tag: int, ref_tag: int, endian: str, data: bytes, tiff_start: int
) -> Optional[float]:
    """Parse GPS coordinate from raw IFD data (rational format like '55/1')."""
    ref = gps_ifd.get(ref_tag)
    coord = gps_ifd.get(coord_tag)
    if ref is None or coord is None:
        return None

    try:
        if isinstance(coord, list) and len(coord) == 3:
            parts = []
            for c in coord:
                if isinstance(c, str) and "/" in c:
                    n, d = c.split("/")
                    parts.append(int(n) / int(d) if int(d) != 0 else 0)
                else:
                    parts.append(float(c))
            decimal = parts[0] + parts[1] / 60.0 + parts[2] / 3600.0
            if ref in ("S", "W"):
                decimal = -decimal
            return round(decimal, 8)
    except (TypeError, ValueError, IndexError, ZeroDivisionError):
        pass
    return None


def extract_video_metadata(filepath: str) -> dict:
    """Extract creation time, GPS, duration and dimensions from ISO video files."""
    meta = {}
    try:
        file_size = os.path.getsize(filepath)
        tail_bytes = min(1024 * 1024, file_size)

        with open(filepath, "rb") as f:
            # Read first and last parts of the file to find ISO 6709 GPS
            head_data = f.read(min(file_size, 5 * 1024 * 1024))
            import re
            match = re.search(rb'([+-]\d{2,4}\.\d{2,6})([+-]\d{2,4}\.\d{2,6})', head_data)
            if not match and file_size > 5 * 1024 * 1024:
                f.seek(max(0, file_size - 1 * 1024 * 1024))
                gps_data = head_data + f.read()
                match = re.search(rb'([+-]\d{2,4}\.\d{2,6})([+-]\d{2,4}\.\d{2,6})', gps_data)
            
            if match:
                meta["latitude"] = float(match.group(1))
                meta["longitude"] = float(match.group(2))

            # Keep reading for duration in moov atom
            f.seek(max(0, file_size - tail_bytes))
            tail_data = f.read()

        data = head_data if file_size <= len(head_data) else head_data + tail_data

        moov_idx = data.find(b"moov")
        if moov_idx >= 4:
            moov_data = data[moov_idx - 4 :]

            # Find mvhd atom
            mvhd_idx = moov_data.find(b"mvhd")
            if mvhd_idx >= 4:
                version = moov_data[mvhd_idx + 4]
                if version == 0 and mvhd_idx + 24 <= len(moov_data):
                    creation = struct.unpack(">I", moov_data[mvhd_idx + 8 : mvhd_idx + 12])[0]
                    timescale = struct.unpack(">I", moov_data[mvhd_idx + 16 : mvhd_idx + 20])[0]
                    duration = struct.unpack(">I", moov_data[mvhd_idx + 20 : mvhd_idx + 24])[0]

                    creation_dt = datetime.datetime(1904, 1, 1) + datetime.timedelta(seconds=creation)
                    if 1980 <= creation_dt.year <= 2100:
                        meta["taken_at"] = creation_dt.isoformat()
                    if timescale > 0:
                        meta["duration"] = round(duration / timescale, 1)
                elif version == 1 and mvhd_idx + 36 <= len(moov_data):
                    creation = struct.unpack(">Q", moov_data[mvhd_idx + 8 : mvhd_idx + 16])[0]
                    timescale = struct.unpack(">I", moov_data[mvhd_idx + 24 : mvhd_idx + 28])[0]
                    duration = struct.unpack(">Q", moov_data[mvhd_idx + 28 : mvhd_idx + 36])[0]
                    creation_dt = datetime.datetime(1904, 1, 1) + datetime.timedelta(seconds=creation)
                    if 1980 <= creation_dt.year <= 2100:
                        meta["taken_at"] = creation_dt.isoformat()
                    if timescale > 0:
                        meta["duration"] = round(duration / timescale, 1)

            # Try to get dimensions from tkhd
            tkhd_idx = moov_data.find(b"tkhd")
            if tkhd_idx >= 4:
                tkhd_version = moov_data[tkhd_idx + 4]
                if tkhd_version == 0:
                    # Width and height are fixed-point 16.16 values in tkhd v0.
                    w_off = tkhd_idx + 76
                    if w_off + 8 <= len(moov_data):
                        w_fixed = struct.unpack(">I", moov_data[w_off : w_off + 4])[0]
                        h_fixed = struct.unpack(">I", moov_data[w_off + 4 : w_off + 8])[0]
                        meta["width"] = w_fixed >> 16
                        meta["height"] = h_fixed >> 16

        if not meta.get("duration") or not meta.get("width") or not meta.get("height"):
            try:
                import cv2
                cap = cv2.VideoCapture(filepath)
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if not meta.get("duration") and fps > 0 and frame_count > 0:
                    meta["duration"] = round(frame_count / fps, 1)
                if not meta.get("width"):
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    if width > 0:
                        meta["width"] = width
                if not meta.get("height"):
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    if height > 0:
                        meta["height"] = height
                cap.release()
            except Exception:
                pass

    except Exception as e:
        logger.debug("Failed to extract MOV metadata from %s: %s", filepath, e)

    meta["taken_at"] = _determine_taken_at(filepath, meta.get("taken_at"))

    return meta


def extract_mov_metadata(filepath: str) -> dict:
    """Backward-compatible alias for callers using the old MOV-specific name."""
    return extract_video_metadata(filepath)


def extract_aae_metadata(filepath: str) -> dict:
    """Extract basic metadata from an AAE sidecar file."""
    meta = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(10000)

        # Extract timestamp
        date_match = re.search(r"<date>([\d\-T:Z]+)</date>", content)
        if date_match:
            meta["taken_at"] = date_match.group(1)

        meta["is_edited"] = 1
    except Exception as e:
        logger.debug("Failed to parse AAE file %s: %s", filepath, e)

    meta["taken_at"] = _determine_taken_at(filepath, meta.get("taken_at"))

    return meta
