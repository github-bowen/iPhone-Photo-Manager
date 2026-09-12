import asyncio
import os
import sqlite3
import tempfile
import unittest

import server.database as database


class DatabaseMigrationTests(unittest.TestCase):
    def test_adds_scanner_columns_to_existing_database(self):
        old_schema = database.SCHEMA
        for column in database.MIGRATIONS:
            lines = old_schema.splitlines(keepends=True)
            old_schema = "".join(
                line for line in lines if not line.lstrip().startswith(f"{column} ")
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "photos.db")
            conn1 = sqlite3.connect(db_path)
            try:
                conn1.executescript(old_schema)
            finally:
                conn1.close()

            original_path = database.DB_PATH
            database.DB_PATH = db_path
            try:
                asyncio.run(database.init_db())
            finally:
                database.DB_PATH = original_path

            conn2 = sqlite3.connect(db_path)
            try:
                columns = {
                    row[1] for row in conn2.execute("PRAGMA table_info(photos)")
                }
            finally:
                conn2.close()

            self.assertTrue(set(database.MIGRATIONS).issubset(columns))

    def test_upsert_preserves_location_name(self):
        async def run_test():
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = os.path.join(temp_dir, "photos.db")
                original_path = database.DB_PATH
                database.DB_PATH = db_path
                try:
                    await database.init_db()
                    db = await database.get_db()
                    try:
                        # Insert a photo and assign location_name
                        await database.insert_photo(db, {
                            "filepath": "202401/test.jpg",
                            "filename": "test.jpg",
                            "directory": "202401",
                            "file_type": "JPG",
                            "file_size": 1000,
                            "latitude": 39.9,
                            "longitude": 116.4,
                        })
                        await db.execute("UPDATE photos SET location_name = 'Beijing, China' WHERE filepath = '202401/test.jpg'")
                        await db.commit()

                        # Re-scan (upsert) with same coordinates, no location_name in photo_data
                        await database.upsert_photo(db, {
                            "filepath": "202401/test.jpg",
                            "filename": "test.jpg",
                            "directory": "202401",
                            "file_type": "JPG",
                            "file_size": 1000,
                            "latitude": 39.9,
                            "longitude": 116.4,
                            "description": "Updated desc",
                            "is_favorite": 1,
                        })

                        rows = await db.execute_fetchall("SELECT location_name, description, is_favorite FROM photos WHERE filepath = '202401/test.jpg'")
                        self.assertEqual(rows[0][0], "Beijing, China")
                        self.assertEqual(rows[0][1], "Updated desc")
                        self.assertEqual(rows[0][2], 1)

                        # Test filtering by is_favorite
                        favs, total = await database.get_photos(db, is_favorite=True)
                        self.assertEqual(total, 1)
                        self.assertEqual(favs[0]["filepath"], "202401/test.jpg")

                        non_favs, total = await database.get_photos(db, is_favorite=False)
                        self.assertEqual(total, 0)
                    finally:
                        await db.close()
                finally:
                    database.DB_PATH = original_path

        asyncio.run(run_test())

    def test_set_and_toggle_photo_favorite(self):
        async def run_test():
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = os.path.join(temp_dir, "photos.db")
                original_path = database.DB_PATH
                database.DB_PATH = db_path
                try:
                    await database.init_db()
                    db = await database.get_db()
                    try:
                        # Insert a photo with a paired Live Photo MOV
                        photo_id = await database.insert_photo(db, {
                            "filepath": "202609/IMG_0001.HEIC",
                            "filename": "IMG_0001.HEIC",
                            "directory": "202609",
                            "file_type": "HEIC",
                            "file_size": 2048,
                            "is_live_photo": 1,
                            "live_photo_mov": "202609/IMG_0001.MOV",
                        })
                        await database.insert_photo(db, {
                            "filepath": "202609/IMG_0001.MOV",
                            "filename": "IMG_0001.MOV",
                            "directory": "202609",
                            "file_type": "MOV",
                            "file_size": 1048576,
                        })

                        # Toggle to favorite (0 -> 1)
                        new_fav = await database.set_photo_favorite(db, photo_id)
                        self.assertEqual(new_fav, 1)

                        # Verify photo and paired MOV are favorited
                        p = await database.get_photo_by_id(db, photo_id)
                        self.assertEqual(p["is_favorite"], 1)
                        mov_rows = await db.execute_fetchall("SELECT is_favorite FROM photos WHERE filepath = '202609/IMG_0001.MOV'")
                        self.assertEqual(mov_rows[0][0], 1)

                        # Toggle back (1 -> 0)
                        new_fav = await database.set_photo_favorite(db, photo_id)
                        self.assertEqual(new_fav, 0)
                        p = await database.get_photo_by_id(db, photo_id)
                        self.assertEqual(p["is_favorite"], 0)

                        # Explicitly set to 1
                        new_fav = await database.set_photo_favorite(db, photo_id, True)
                        self.assertEqual(new_fav, 1)

                        # Explicitly set to 0
                        new_fav = await database.set_photo_favorite(db, photo_id, False)
                        self.assertEqual(new_fav, 0)
                    finally:
                        await db.close()
                finally:
                    database.DB_PATH = original_path

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
