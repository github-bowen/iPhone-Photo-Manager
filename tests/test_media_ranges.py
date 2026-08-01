import os
import tempfile
import unittest

from fastapi import HTTPException

from server.app import _iter_file_range, _parse_byte_range


class MediaRangeTests(unittest.TestCase):
    def test_parses_open_closed_and_suffix_ranges(self):
        self.assertEqual(_parse_byte_range(None, 100), (0, 99))
        self.assertEqual(_parse_byte_range("bytes=10-19", 100), (10, 19))
        self.assertEqual(_parse_byte_range("bytes=90-", 100), (90, 99))
        self.assertEqual(_parse_byte_range("bytes=-10", 100), (90, 99))

    def test_rejects_range_outside_payload(self):
        with self.assertRaises(HTTPException) as context:
            _parse_byte_range("bytes=100-110", 100)
        self.assertEqual(context.exception.status_code, 416)
        with self.assertRaises(HTTPException):
            _parse_byte_range("bytes=-0", 100)

    def test_reads_only_requested_file_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "media.bin")
            with open(path, "wb") as file:
                file.write(b"0123456789")
            self.assertEqual(b"".join(_iter_file_range(path, 3, 4)), b"3456")


if __name__ == "__main__":
    unittest.main()
