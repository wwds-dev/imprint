"""Checks the cloud worker's paths and Imprint's cross-device sidecar name."""

import hashlib
import unittest

from cloud.contracts import ebook_parts, progress_filename, updated_progress


class ContractTests(unittest.TestCase):
    def test_progress_file_matches_imprint_format(self):
        name, size = "Example_Book.mp3", 1234567
        expected = hashlib.sha256(f"{name}\n{size}".encode()).hexdigest() + ".json"
        self.assertEqual(progress_filename(name, str(size)), expected)
        self.assertEqual(progress_filename(name, size), expected)

    def test_ebook_path_accepts_nested_drive_folder(self):
        self.assertEqual(ebook_parts("Fiction/Example.epub"), ("Fiction", "Example.epub"))

    def test_ebook_path_rejects_traversal_and_unsupported_formats(self):
        for path in ("../secret.epub", "/root/book.epub", "folder/../book.epub",
                     "folder\\book.epub", "book.azw3", ""):
            with self.subTest(path=path), self.assertRaises(ValueError):
                ebook_parts(path)

    def test_phone_progress_keeps_imprint_marks_and_finishes_at_same_threshold(self):
        before = {"marks": [{"position_ms": 1234, "title": "Chapter"}]}
        saved = updated_progress(before, "Book.mp3", 99000, 100000,
                                 "Book", "2026-09-29T10:00:00+00:00")
        self.assertEqual(saved["marks"], before["marks"])
        self.assertTrue(saved["finished"])
        self.assertEqual(saved["file_name"], "Book.mp3")
        self.assertEqual(before, {"marks": [{"position_ms": 1234, "title": "Chapter"}]})
        updated = updated_progress(saved, "Book.mp3", 50000, 0, "Book", "later")
        self.assertEqual(updated["duration_ms"], 100000)
        self.assertFalse(updated["finished"])


if __name__ == "__main__":
    unittest.main()
