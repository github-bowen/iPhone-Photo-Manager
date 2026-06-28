"""
File scanner module for the iPhone Photo Manager.
Scans photos directory, extracts EXIF metadata from HEIC/JPG/PNG files,
and parses MOV metadata.
"""

import os
import struct
import datetime
import logging
from typing import Optional
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

# Register HEIC support with Pillow
import pillow_heif
pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".heic", ".jpg", ".jpeg", ".png", ".mov", ".aae"}


def get_all_files_on_disk(photos_dir: str) -> set[str]:
    """Extremely fast directory traversal to get all valid photo file paths."""
    valid_paths = set()
    photos_dir = os.path.realpath(photos_dir)

    for direntry in sorted(os.scandir(photos_dir), key=lambda e: e.name):
        if not direntry.is_dir():
            continue
            
        subdir_path = direntry.path
        for fname in os.listdir(subdir_path):
            ext = os.path.splitext(fname)[1].upper()
            if ext in {".HEIC", ".JPG", ".JPEG", ".PNG", ".MOV", ".AAE"}:
                filepath = os.path.join(subdir_path, fname)
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
            }
            
            # Detect edited versions (IMG_E*)
            if fname.startswith("IMG_E"):
                photo_data["is_edited"] = 1
                orig_name = fname.replace("IMG_E", "IMG_", 1)
                if orig_name in files_in_dir:
                    photo_data["original_file"] = os.path.join(subdir_name, orig_name)

            # Detect Live Photo pairs
            stem = os.path.splitext(fname)[0]
            if file_type == "HEIC" and f"{stem}.MOV" in files_in_dir:
                photo_data["is_live_photo"] = 1
                photo_data["live_photo_mov"] = os.path.join(subdir_name, f"{stem}.MOV")

            # Extract metadata
            if file_type in ("HEIC", "JPG", "PNG"):
                meta = extract_image_metadata(filepath, file_type)
                photo_data.update(meta)
            elif file_type == "MOV":
                meta = extract_mov_metadata(filepath)
                photo_data.update(meta)
            elif file_type == "AAE":
                meta = extract_aae_metadata(filepath)
                photo_data.update(meta)

            # Detect screenshots
            if file_type == "PNG" and photo_data.get("width") and photo_data.get("height"):
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
            if file_type == "HEIC":
                return {**meta, **_parse_heic_exif_raw(filepath)}
            return meta

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
        if file_type == "HEIC":
            raw_meta = _parse_heic_exif_raw(filepath)
            meta.update(raw_meta)

    return meta


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


def extract_mov_metadata(filepath: str) -> dict:
    """Extract creation time and duration from a MOV file."""
    meta = {}
    try:
        file_size = os.path.getsize(filepath)
        tail_bytes = min(200000, file_size)

        with open(filepath, "rb") as f:
            # Read first and last parts of the file to find ISO 6709 GPS
            data = f.read(min(file_size, 5 * 1024 * 1024))
            import re
            match = re.search(rb'([+-]\d{2,4}\.\d{2,6})([+-]\d{2,4}\.\d{2,6})', data)
            if not match and file_size > 5 * 1024 * 1024:
                f.seek(max(0, file_size - 1 * 1024 * 1024))
                data += f.read()
                match = re.search(rb'([+-]\d{2,4}\.\d{2,6})([+-]\d{2,4}\.\d{2,6})', data)
            
            if match:
                meta["latitude"] = float(match.group(1))
                meta["longitude"] = float(match.group(2))

            # Keep reading for duration in moov atom
            f.seek(max(0, file_size - tail_bytes))
            data = f.read()

        moov_idx = data.find(b"moov")
        if moov_idx < 4:
            return meta

        moov_data = data[moov_idx - 4 :]

        # Find mvhd atom
        mvhd_idx = moov_data.find(b"mvhd")
        if mvhd_idx < 4:
            return meta

        version = moov_data[mvhd_idx + 4]
        if version == 0:
            creation = struct.unpack(">I", moov_data[mvhd_idx + 8 : mvhd_idx + 12])[0]
            timescale = struct.unpack(">I", moov_data[mvhd_idx + 16 : mvhd_idx + 20])[0]
            duration = struct.unpack(">I", moov_data[mvhd_idx + 20 : mvhd_idx + 24])[0]

            # Convert Mac epoch (1904-01-01) to datetime
            mac_epoch = datetime.datetime(1904, 1, 1)
            creation_dt = mac_epoch + datetime.timedelta(seconds=creation)
            meta["taken_at"] = creation_dt.isoformat()

            if timescale > 0:
                meta["duration"] = round(duration / timescale, 1)

        # Try to get dimensions from tkhd
        tkhd_idx = moov_data.find(b"tkhd")
        if tkhd_idx >= 4:
            tkhd_version = moov_data[tkhd_idx + 4]
            if tkhd_version == 0:
                # Width and height are at offset 76-84 in tkhd v0 (as fixed-point 16.16)
                w_off = tkhd_idx + 4 + 1 + 3 + 4 + 4 + 4 + 4 + 8 + 36 + 8  # = tkhd + 76
                if w_off + 8 <= len(moov_data):
                    w_fixed = struct.unpack(">I", moov_data[w_off : w_off + 4])[0]
                    h_fixed = struct.unpack(">I", moov_data[w_off + 4 : w_off + 8])[0]
                    meta["width"] = w_fixed >> 16
                    meta["height"] = h_fixed >> 16

    except Exception as e:
        logger.debug("Failed to extract MOV metadata from %s: %s", filepath, e)

    return meta


def extract_aae_metadata(filepath: str) -> dict:
    """Extract basic metadata from an AAE sidecar file."""
    meta = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(10000)

        # Extract timestamp
        import re
        date_match = re.search(r"<date>([\d\-T:Z]+)</date>", content)
        if date_match:
            meta["taken_at"] = date_match.group(1)

        meta["is_edited"] = 1
    except Exception as e:
        logger.debug("Failed to parse AAE file %s: %s", filepath, e)

    return meta
