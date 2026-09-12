import os
import tempfile
import unittest
from PIL import Image

from server.scanner import (
    SCAN_VERSION,
    _decode_user_comment,
    parse_xmp_metadata,
    scan_specific_files,
)


class TestIosMetadata(unittest.TestCase):
    def test_decode_user_comment_ascii(self):
        val = b"ASCII\x00\x00\x00Hello Sunset"
        self.assertEqual(_decode_user_comment(val), "Hello Sunset")

    def test_decode_user_comment_unicode_utf16le(self):
        val = b"UNICODE\x00" + "美丽日落".encode("utf-16le")
        self.assertEqual(_decode_user_comment(val), "美丽日落")

    def test_decode_user_comment_undefined_prefix(self):
        val = b"\x00" * 8 + "Tokyo Tower".encode("utf-8")
        self.assertEqual(_decode_user_comment(val), "Tokyo Tower")

    def test_decode_user_comment_raw_utf8_and_str(self):
        self.assertEqual(_decode_user_comment(b"Golden Gate"), "Golden Gate")
        self.assertEqual(_decode_user_comment("Mount Fuji"), "Mount Fuji")
        self.assertIsNone(_decode_user_comment(None))
        self.assertIsNone(_decode_user_comment(b""))

    def test_parse_xmp_description_and_rating(self):
        xmp = b"""<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xmp="http://ns.adobe.com/xap/1.0/">
   <dc:description>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">A trip to Kyoto</rdf:li>
    </rdf:Alt>
   </dc:description>
   <xmp:Rating>5</xmp:Rating>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>"""
        meta = parse_xmp_metadata(xmp)
        self.assertEqual(meta.get("description"), "A trip to Kyoto")
        self.assertEqual(meta.get("is_favorite"), 1)

    def test_parse_xmp_apple_favorite(self):
        xmp_attr = b"""<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:apple-fi="http://ns.apple.com/faceinfo/1.0/"
    apple-fi:Favorite="1">
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>"""
        meta = parse_xmp_metadata(xmp_attr)
        self.assertEqual(meta.get("is_favorite"), 1)

        xmp_tag = b"""<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:apple-fi="http://ns.apple.com/faceinfo/1.0/">
    <apple-fi:Favorite>1</apple-fi:Favorite>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>"""
        meta2 = parse_xmp_metadata(xmp_tag)
        self.assertEqual(meta2.get("is_favorite"), 1)

    def test_parse_xmp_low_rating_not_favorite(self):
        xmp = b"""<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/">
   <xmp:Rating>3</xmp:Rating>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>"""
        meta = parse_xmp_metadata(xmp)
        self.assertNotIn("is_favorite", meta)

    def test_xmp_sidecar_integration(self):
        with tempfile.TemporaryDirectory() as photos_dir:
            album = os.path.join(photos_dir, "202609")
            os.makedirs(album)

            img_path = os.path.join(album, "IMG_5500.JPG")
            img = Image.new("RGB", (20, 20), color=(255, 0, 0))
            img.save(img_path, format="JPEG")
            img.close()

            xmp_path = os.path.join(album, "IMG_5500.JPG.xmp")
            with open(xmp_path, "w", encoding="utf-8") as f:
                f.write("""<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:apple-fi="http://ns.apple.com/faceinfo/1.0/"
    apple-fi:Favorite="1">
   <dc:description>
    <rdf:Alt><rdf:li>Sidecar caption</rdf:li></rdf:Alt>
   </dc:description>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>""")

            records = scan_specific_files(photos_dir, {os.path.join("202609", "IMG_5500.JPG")})
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["description"], "Sidecar caption")
            self.assertEqual(records[0]["is_favorite"], 1)
            self.assertEqual(records[0]["scan_version"], SCAN_VERSION)

    def test_jpg_live_photo_pairing(self):
        with tempfile.TemporaryDirectory() as photos_dir:
            album = os.path.join(photos_dir, "202609")
            os.makedirs(album)

            img_path = os.path.join(album, "IMG_6001.JPG")
            img = Image.new("RGB", (20, 20), color=(0, 255, 0))
            img.save(img_path, format="JPEG")
            img.close()

            mov_path = os.path.join(album, "IMG_6001.MOV")
            with open(mov_path, "wb") as f:
                f.write(b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  ")

            records = scan_specific_files(photos_dir, {os.path.join("202609", "IMG_6001.JPG")})
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["is_live_photo"], 1)
            self.assertEqual(records[0]["live_photo_mov"], os.path.join("202609", "IMG_6001.MOV"))


if __name__ == "__main__":
    unittest.main()
