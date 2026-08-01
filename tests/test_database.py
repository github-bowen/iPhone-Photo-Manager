import asyncio
import os
import sqlite3
import tempfile
import unittest

import server.database as database


class DatabaseMigrationTests(unittest.TestCase):
    def test_adds_motion_photo_columns_to_existing_database(self):
        old_schema = database.SCHEMA
        for line in (
            "    is_motion_photo INTEGER DEFAULT 0,\n",
            "    motion_photo_offset INTEGER,\n",
            "    motion_photo_length INTEGER,\n",
            "    motion_photo_mime TEXT,\n",
        ):
            old_schema = old_schema.replace(line, "")

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "photos.db")
            with sqlite3.connect(db_path) as connection:
                connection.executescript(old_schema)

            original_path = database.DB_PATH
            database.DB_PATH = db_path
            try:
                asyncio.run(database.init_db())
            finally:
                database.DB_PATH = original_path

            with sqlite3.connect(db_path) as connection:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(photos)")
                }

            self.assertTrue(set(database.MIGRATIONS).issubset(columns))


if __name__ == "__main__":
    unittest.main()
