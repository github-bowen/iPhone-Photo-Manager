import asyncio
import os
import tempfile
import unittest

import server.database as database
from server.scanner import parse_xmp_metadata, _scan_single_file


class PhotoClassificationTests(unittest.TestCase):
    def test_database_category_filters(self):
        async def run_test():
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = os.path.join(temp_dir, "photos.db")
                original_path = database.DB_PATH
                database.DB_PATH = db_path
                try:
                    await database.init_db()
                    db = await database.get_db()
                    try:
                        # 1. Normal photo (JPG, is_screenshot=0)
                        await database.insert_photo(db, {
                            "filepath": "202609/IMG_0001.JPG",
                            "filename": "IMG_0001.JPG",
                            "directory": "202609",
                            "file_type": "JPG",
                            "file_size": 1000,
                            "is_screenshot": 0,
                        })

                        # 2. Normal photo in PNG format (PNG, is_screenshot=0, like IMG_9856.PNG)
                        await database.insert_photo(db, {
                            "filepath": "202609/IMG_9856.PNG",
                            "filename": "IMG_9856.PNG",
                            "directory": "202609",
                            "file_type": "PNG",
                            "file_size": 2000,
                            "width": 1010,
                            "height": 714,
                            "is_screenshot": 0,
                        })

                        # 3. Screenshot in PNG format (PNG, is_screenshot=1, like IMG_9886.PNG)
                        await database.insert_photo(db, {
                            "filepath": "202609/IMG_9886.PNG",
                            "filename": "IMG_9886.PNG",
                            "directory": "202609",
                            "file_type": "PNG",
                            "file_size": 3000,
                            "width": 1179,
                            "height": 2556,
                            "is_screenshot": 1,
                        })

                        # 4. Screenshot in JPG format (JPG, is_screenshot=1)
                        await database.insert_photo(db, {
                            "filepath": "202609/Screenshot_20260912.jpg",
                            "filename": "Screenshot_20260912.jpg",
                            "directory": "202609",
                            "file_type": "JPG",
                            "file_size": 1500,
                            "is_screenshot": 1,
                        })

                        # 5. Video file (MOV, is_screenshot=0)
                        await database.insert_photo(db, {
                            "filepath": "202609/IMG_0002.MOV",
                            "filename": "IMG_0002.MOV",
                            "directory": "202609",
                            "file_type": "MOV",
                            "file_size": 50000,
                            "is_screenshot": 0,
                        })

                        # --- Test Category: photos ---
                        # Should include IMG_0001.JPG and IMG_9856.PNG (both are non-screenshot still images)
                        # Should EXCLUDE IMG_9886.PNG (screenshot), Screenshot_20260912.jpg (screenshot), and IMG_0002.MOV (video)
                        photos, total = await database.get_photos(db, category="photos")
                        photo_names = {p["filename"] for p in photos}
                        self.assertEqual(total, 2)
                        self.assertIn("IMG_0001.JPG", photo_names)
                        self.assertIn("IMG_9856.PNG", photo_names)
                        self.assertNotIn("IMG_9886.PNG", photo_names)
                        self.assertNotIn("Screenshot_20260912.jpg", photo_names)
                        self.assertNotIn("IMG_0002.MOV", photo_names)

                        # --- Test Category: screenshots ---
                        # Should include IMG_9886.PNG (PNG screenshot) and Screenshot_20260912.jpg (JPG screenshot)
                        # Should EXCLUDE IMG_9856.PNG (PNG photo) and IMG_0001.JPG (JPG photo)
                        screenshots, total_s = await database.get_photos(db, category="screenshots")
                        screenshot_names = {p["filename"] for p in screenshots}
                        self.assertEqual(total_s, 2)
                        self.assertIn("IMG_9886.PNG", screenshot_names)
                        self.assertIn("Screenshot_20260912.jpg", screenshot_names)
                        self.assertNotIn("IMG_9856.PNG", screenshot_names)
                        self.assertNotIn("IMG_0001.JPG", screenshot_names)

                        # Test screenshots=True query param backward compatibility
                        screenshots_compat, total_sc = await database.get_photos(db, is_screenshot=True)
                        self.assertEqual(total_sc, 2)
                        compat_names = {p["filename"] for p in screenshots_compat}
                        self.assertEqual(compat_names, screenshot_names)

                        # --- Test Category: videos ---
                        videos, total_v = await database.get_photos(db, category="videos")
                        video_names = {p["filename"] for p in videos}
                        self.assertEqual(total_v, 1)
                        self.assertIn("IMG_0002.MOV", video_names)

                        # --- Test Compound Category: photos,videos ---
                        pv, total_pv = await database.get_photos(db, category="photos,videos")
                        pv_names = {p["filename"] for p in pv}
                        self.assertEqual(total_pv, 3)
                        self.assertIn("IMG_0001.JPG", pv_names)
                        self.assertIn("IMG_9856.PNG", pv_names)
                        self.assertIn("IMG_0002.MOV", pv_names)
                        self.assertNotIn("IMG_9886.PNG", pv_names)
                        self.assertNotIn("Screenshot_20260912.jpg", pv_names)

                        # --- Test Category: all ---
                        all_items, total_all = await database.get_photos(db)
                        self.assertEqual(total_all, 5)

                    finally:
                        await db.close()
                finally:
                    database.DB_PATH = original_path

        asyncio.run(run_test())

    def test_xmp_user_comment_screenshot_detection(self):
        xmp_xml = """<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 6.0.0">
   <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <rdf:Description rdf:about=""
            xmlns:exif="http://ns.adobe.com/exif/1.0/">
         <exif:UserComment>Screenshot</exif:UserComment>
      </rdf:Description>
   </rdf:RDF>
</x:xmpmeta>"""
        meta = parse_xmp_metadata(xmp_xml)
        self.assertEqual(meta.get("is_screenshot"), 1)

    def test_xmp_user_comment_non_screenshot(self):
        xmp_xml = """<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="XMP Core 6.0.0">
   <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      <rdf:Description rdf:about=""
            xmlns:exif="http://ns.adobe.com/exif/1.0/">
         <exif:UserComment>Sunset at the beach</exif:UserComment>
      </rdf:Description>
   </rdf:RDF>
</x:xmpmeta>"""
        meta = parse_xmp_metadata(xmp_xml)
        self.assertIsNone(meta.get("is_screenshot"))


    def test_api_category_endpoint(self):
        from server.app import api_get_photos

        async def run_test():
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = os.path.join(temp_dir, "photos.db")
                orig_path = database.DB_PATH
                database.DB_PATH = db_path
                try:
                    await database.init_db()
                    db = await database.get_db()
                    try:
                        await database.insert_photo(db, {
                            "filepath": "202609/IMG_9856.PNG",
                            "filename": "IMG_9856.PNG",
                            "directory": "202609",
                            "file_type": "PNG",
                            "file_size": 2000,
                            "width": 1010,
                            "height": 714,
                            "is_screenshot": 0,
                        })
                        await database.insert_photo(db, {
                            "filepath": "202609/IMG_9886.PNG",
                            "filename": "IMG_9886.PNG",
                            "directory": "202609",
                            "file_type": "PNG",
                            "file_size": 3000,
                            "width": 1179,
                            "height": 2556,
                            "is_screenshot": 1,
                        })

                        # 1. Query category="photos" -> should include IMG_9856.PNG and exclude IMG_9886.PNG
                        res_photos = await api_get_photos(category="photos")
                        names_photos = {p["filename"] for p in res_photos["photos"]}
                        self.assertEqual(res_photos["total"], 1)
                        self.assertIn("IMG_9856.PNG", names_photos)
                        self.assertNotIn("IMG_9886.PNG", names_photos)

                        # 2. Query category="screenshots" -> should include IMG_9886.PNG and exclude IMG_9856.PNG
                        res_screenshots = await api_get_photos(category="screenshots")
                        names_screenshots = {p["filename"] for p in res_screenshots["photos"]}
                        self.assertEqual(res_screenshots["total"], 1)
                        self.assertIn("IMG_9886.PNG", names_screenshots)
                        self.assertNotIn("IMG_9856.PNG", names_screenshots)
                    finally:
                        await db.close()
                finally:
                    database.DB_PATH = orig_path

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()

