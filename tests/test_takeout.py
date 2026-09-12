import json
import os
import tempfile
import unittest

from server.scanner import (
    extract_takeout_metadata,
    get_all_files_on_disk,
    get_takeout_sidecar_state_on_disk,
    scan_specific_files,
)


class TakeoutMetadataTests(unittest.TestCase):
    def test_extracts_timestamp_location_description_and_favorite(self):
        metadata = extract_takeout_metadata({
            "photoTakenTime": {"timestamp": "1704164645"},
            "creationTime": {"timestamp": "1700000000"},
            "geoData": {
                "latitude": 47.3769,
                "longitude": 8.5417,
                "altitude": 408.2,
            },
            "description": "  Lake walk  ",
            "favorited": True,
        })

        self.assertEqual(metadata["taken_at"], "2024-01-02T03:04:05+00:00")
        self.assertEqual(metadata["timezone"], "UTC")
        self.assertEqual(metadata["latitude"], 47.3769)
        self.assertEqual(metadata["longitude"], 8.5417)
        self.assertEqual(metadata["altitude"], 408.2)
        self.assertEqual(metadata["description"], "Lake walk")
        self.assertEqual(metadata["is_favorite"], 1)

    def test_falls_back_to_exif_location_and_creation_time(self):
        metadata = extract_takeout_metadata({
            "photoTakenTime": {"timestamp": "invalid"},
            "creationTime": {"timestamp": "1704164645"},
            "geoData": {"latitude": 0, "longitude": 0, "altitude": 0},
            "geoDataExif": {"latitude": "1.25", "longitude": "-2.5"},
            "favorited": False,
        })

        self.assertEqual(metadata["taken_at"], "2024-01-02T03:04:05+00:00")
        self.assertEqual(metadata["latitude"], 1.25)
        self.assertEqual(metadata["longitude"], -2.5)
        self.assertEqual(metadata["is_favorite"], 0)


class TakeoutSidecarTests(unittest.TestCase):
    def write_json(self, directory: str, filename: str, data) -> str:
        path = os.path.join(directory, filename)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file)
        return path

    def test_scans_supplemental_metadata_without_indexing_json(self):
        with tempfile.TemporaryDirectory() as photos_dir:
            album = os.path.join(photos_dir, "Google Photos", "Camera")
            os.makedirs(album)
            media_name = "PXL_20240102_030405.jpg"
            with open(os.path.join(album, media_name), "wb") as file:
                file.write(b"not-a-real-jpeg")
            sidecar_name = f"{media_name}.supplemental-metadata.json"
            self.write_json(album, sidecar_name, {
                "title": media_name,
                "photoTakenTime": {"timestamp": "1704164645"},
                "description": "Imported from Google Photos",
                "favorited": True,
            })
            rel_media = os.path.join("Google Photos", "Camera", media_name)

            records = scan_specific_files(photos_dir, {rel_media})
            disk_paths = get_all_files_on_disk(photos_dir)
            sidecar_state = get_takeout_sidecar_state_on_disk(
                photos_dir, disk_paths
            )

            self.assertEqual(disk_paths, {rel_media})
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["taken_at"], "2024-01-02T03:04:05+00:00")
            self.assertEqual(records[0]["description"], "Imported from Google Photos")
            self.assertEqual(records[0]["is_favorite"], 1)
            self.assertEqual(records[0]["takeout_metadata"], 1)
            self.assertEqual(
                records[0]["takeout_sidecar"],
                os.path.join("Google Photos", "Camera", sidecar_name),
            )
            self.assertEqual(sidecar_state[rel_media][0], records[0]["takeout_sidecar"])
            self.assertEqual(
                sidecar_state[rel_media][1], records[0]["takeout_sidecar_mtime_ns"]
            )

    def test_matches_truncated_sidecar_name_using_title(self):
        with tempfile.TemporaryDirectory() as photos_dir:
            media_name = "A very long original filename from Google Photos 2024.jpg"
            with open(os.path.join(photos_dir, media_name), "wb") as file:
                file.write(b"not-a-real-jpeg")
            sidecar_name = "A very long original filename from Goo.json"
            self.write_json(photos_dir, sidecar_name, {
                "title": media_name,
                "photoTakenTime": {"timestamp": "1704164645"},
            })

            records = scan_specific_files(photos_dir, {media_name})

            self.assertEqual(records[0]["takeout_metadata"], 1)
            self.assertEqual(records[0]["takeout_sidecar"], sidecar_name)

    def test_ignores_album_and_malformed_json(self):
        with tempfile.TemporaryDirectory() as photos_dir:
            media_name = "photo.jpg"
            with open(os.path.join(photos_dir, media_name), "wb") as file:
                file.write(b"not-a-real-jpeg")
            self.write_json(photos_dir, f"{media_name}.json", {
                "title": media_name,
                "albumData": {"title": "Camera"},
            })
            with open(os.path.join(photos_dir, "broken.json"), "w", encoding="utf-8") as file:
                file.write("{")

            records = scan_specific_files(photos_dir, {media_name})
            state = get_takeout_sidecar_state_on_disk(photos_dir, {media_name})

            self.assertEqual(records[0]["takeout_metadata"], 0)
            self.assertIsNone(records[0]["takeout_sidecar"])
            self.assertEqual(state, {})


if __name__ == "__main__":
    unittest.main()
