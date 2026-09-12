import asyncio
import os
import tempfile
import unittest
from fastapi import HTTPException

import server.database as database
from server.app import api_toggle_photo_favorite, FavoriteUpdate


class FavoriteApiTests(unittest.TestCase):
    def test_favorite_api_endpoint(self):
        async def run_test():
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = os.path.join(temp_dir, "photos.db")
                orig_path = database.DB_PATH
                database.DB_PATH = db_path
                try:
                    await database.init_db()
                    db = await database.get_db()
                    try:
                        photo_id = await database.insert_photo(db, {
                            "filepath": "202609/sunset.jpg",
                            "filename": "sunset.jpg",
                            "directory": "202609",
                            "file_type": "JPG",
                            "file_size": 1024,
                            "is_favorite": 0,
                        })

                        # 1. Toggle to 1 via API
                        res = await api_toggle_photo_favorite(photo_id)
                        self.assertEqual(res["success"], True)
                        self.assertEqual(res["is_favorite"], 1)

                        # 2. Toggle to 0 via API
                        res = await api_toggle_photo_favorite(photo_id)
                        self.assertEqual(res["success"], True)
                        self.assertEqual(res["is_favorite"], 0)

                        # 3. Explicitly set to 1 via payload
                        res = await api_toggle_photo_favorite(photo_id, FavoriteUpdate(is_favorite=True))
                        self.assertEqual(res["is_favorite"], 1)

                        # 4. Explicitly set to 0 via payload
                        res = await api_toggle_photo_favorite(photo_id, FavoriteUpdate(is_favorite=False))
                        self.assertEqual(res["is_favorite"], 0)

                        # 5. Non-existent photo should raise 404
                        with self.assertRaises(HTTPException) as ctx:
                            await api_toggle_photo_favorite(999999)
                        self.assertEqual(ctx.exception.status_code, 404)
                    finally:
                        await db.close()
                finally:
                    database.DB_PATH = orig_path

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
