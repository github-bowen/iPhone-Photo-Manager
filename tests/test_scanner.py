import os
import struct
import tempfile
import unittest

from server.scanner import (
    SCAN_VERSION,
    extract_motion_photo_metadata,
    get_all_files_on_disk,
    scan_specific_files,
)


def fake_mp4() -> bytes:
    return struct.pack(">I4s4sI4s", 20, b"ftyp", b"isom", 0, b"mp42")


def modern_xmp(video_length: int, enabled: int = 1) -> bytes:
    return f"""
<x:xmpmeta xmlns:x="adobe:ns:meta/"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:Camera="http://ns.google.com/photos/1.0/camera/"
 xmlns:Container="http://ns.google.com/photos/1.0/container/"
 xmlns:Item="http://ns.google.com/photos/1.0/container/item/">
 <rdf:RDF>
  <rdf:Description Camera:MotionPhoto="{enabled}" Camera:MotionPhotoVersion="1">
   <Container:Directory><rdf:Seq>
    <rdf:li Item:Mime="image/jpeg" Item:Semantic="Primary" Item:Length="0"/>
    <rdf:li Item:Mime="video/mp4" Item:Semantic="MotionPhoto" Item:Length="{video_length}"/>
   </rdf:Seq></Container:Directory>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
""".encode()


class MotionPhotoTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write(self, name: str, content: bytes) -> str:
        path = os.path.join(self.temp_dir.name, name)
        with open(path, "wb") as file:
            file.write(content)
        return path

    def test_detects_standard_container_length(self):
        video = fake_mp4()
        image = b"\xff\xd8" + modern_xmp(len(video)) + b"\xff\xd9"
        path = self.write("PXL_20260801_120000_MP.jpg", image + video)

        metadata = extract_motion_photo_metadata(path)

        self.assertEqual(metadata["is_motion_photo"], 1)
        self.assertEqual(metadata["motion_photo_offset"], len(image))
        self.assertEqual(metadata["motion_photo_length"], len(video))
        self.assertEqual(metadata["motion_photo_mime"], "video/mp4")

    def test_detects_legacy_microvideo_offset(self):
        video = fake_mp4()
        xmp = f"""
<x:xmpmeta xmlns:x="adobe:ns:meta/"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:GCamera="http://ns.google.com/photos/1.0/camera/">
 <rdf:RDF><rdf:Description GCamera:MicroVideo="1"
  GCamera:MicroVideoOffset="{len(video)}"/></rdf:RDF>
</x:xmpmeta>
""".encode()
        image = b"\xff\xd8" + xmp + b"\xff\xd9"
        path = self.write("legacy.jpg", image + video)

        metadata = extract_motion_photo_metadata(path)

        self.assertEqual(metadata["motion_photo_offset"], len(image))
        self.assertEqual(metadata["motion_photo_length"], len(video))

    def test_detects_samsung_marker(self):
        video = fake_mp4()
        image = b"\xff\xd8still-image\xff\xd9MotionPhoto_Data"
        path = self.write("samsung.jpg", image + video)

        metadata = extract_motion_photo_metadata(path)

        self.assertEqual(metadata["motion_photo_offset"], len(image))
        self.assertEqual(metadata["motion_photo_length"], len(video))

    def test_rejects_disabled_or_missing_video(self):
        path = self.write("disabled.jpg", b"\xff\xd8" + modern_xmp(20, enabled=0) + b"\xff\xd9")
        self.assertEqual(extract_motion_photo_metadata(path), {})


class AndroidImportTests(unittest.TestCase):
    def test_discovers_android_extensions_and_screenshot_names(self):
        with tempfile.TemporaryDirectory() as photos_dir:
            album = os.path.join(photos_dir, "202608")
            os.makedirs(album)
            filenames = ["photo.webp", "clip.mp4", "camera.heif", "modern.avif", "old.3gp"]
            for filename in filenames:
                with open(os.path.join(album, filename), "wb") as file:
                    file.write(b"not-media")
            with open(os.path.join(album, "ignored.txt"), "wb") as file:
                file.write(b"ignored")

            paths = get_all_files_on_disk(photos_dir)

            self.assertEqual(paths, {os.path.join("202608", name) for name in filenames})

            screenshot = "Screenshot_20260801_120000.webp"
            with open(os.path.join(album, screenshot), "wb") as file:
                file.write(b"not-media")
            records = scan_specific_files(
                photos_dir, {os.path.join("202608", screenshot)}
            )
            self.assertEqual(records[0]["is_screenshot"], 1)
            self.assertEqual(records[0]["scan_version"], SCAN_VERSION)


if __name__ == "__main__":
    unittest.main()
