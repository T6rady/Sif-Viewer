import codecs
import hashlib
from pathlib import Path
import tempfile
import unittest

from core.file_reader import FileReadError, decode_text, read_file


class FileReaderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "test.sif"

    def read_bytes(self, data):
        self.path.write_bytes(data)
        return read_file(self.path)

    def test_exact_whitespace_and_line_endings(self):
        data = b"SF=Sample\r\nST=  A title  \r\n\r\nPN=ABC\rPD=Equals=kept\n"
        result = self.read_bytes(data)
        self.assertEqual(result.text, data.decode("ascii"))
        self.assertEqual(result.line_count, 5)
        self.assertEqual(result.size, len(data))
        self.assertEqual(result.newline_style, "CRLF, CR, LF")
        self.assertEqual(result.path, self.path.absolute())

    def test_empty_and_final_newlines(self):
        for data, count in ((b"", 0), (b"a", 1), (b"a\n", 1), (b"\n", 1),
                            (b"a\r\n\r\n", 2), (b"a\rb", 2)):
            with self.subTest(data=data):
                self.assertEqual(self.read_bytes(data).line_count, count)

    def test_utf8(self):
        text = "PD=Café – chair 日本語\r\n"
        result = self.read_bytes(text.encode("utf-8"))
        self.assertEqual(result.text, text)
        self.assertEqual(result.encoding, "UTF-8")

    def test_bom_encodings(self):
        text = "PD=Café 日本語\r\n"
        for bom, codec in ((codecs.BOM_UTF8, "utf-8"),
                           (codecs.BOM_UTF16_LE, "utf-16-le"),
                           (codecs.BOM_UTF16_BE, "utf-16-be"),
                           (codecs.BOM_UTF32_LE, "utf-32-le"),
                           (codecs.BOM_UTF32_BE, "utf-32-be")):
            with self.subTest(codec=codec):
                result = self.read_bytes(bom + text.encode(codec))
                self.assertEqual(result.text, text)
                self.assertIn("BOM", result.encoding)

    def test_windows_1252_is_labelled_assumed(self):
        text = "PD=Café ‘chair’ €\r\n"
        result = self.read_bytes(text.encode("cp1252"))
        self.assertEqual(result.text, text)
        self.assertIn("assumed", result.encoding)
        self.assertIn("ambiguous", result.encoding_note)

    def test_binary_is_rejected(self):
        for data in (b"MZ\x00\x01", b"PK\x03\x04", b"text\x7f", b"\x81\xfe", b"\x1b[0m"):
            with self.subTest(data=data), self.assertRaises(FileReadError):
                self.read_bytes(data)

    def test_invalid_marked_unicode_is_rejected(self):
        for data in (codecs.BOM_UTF8 + b"\xff", codecs.BOM_UTF16_LE + b"\x00",
                     codecs.BOM_UTF32_BE + b"\0\0\0"):
            with self.subTest(data=data), self.assertRaises(FileReadError):
                self.read_bytes(data)

    def test_unicode_binary_controls_are_rejected(self):
        with self.assertRaises(FileReadError):
            decode_text(codecs.BOM_UTF16_LE + "A\0B".encode("utf-16-le"))

    def test_size_limit(self):
        self.path.write_bytes(b"a" * 101)
        with self.assertRaisesRegex(FileReadError, "limit"):
            read_file(self.path, max_bytes=100)

    def test_missing_and_directory(self):
        with self.assertRaisesRegex(FileReadError, "Cannot read"):
            read_file(self.path)
        with self.assertRaises(FileReadError):
            read_file(self.path.parent)

    def test_original_bytes_and_mtime_unchanged(self):
        data = codecs.BOM_UTF8 + b"SF=A\r\nST= \r\n"
        self.path.write_bytes(data)
        before = self.path.stat()
        checksum = hashlib.sha256(data).hexdigest()
        read_file(self.path)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), checksum)
        self.assertEqual(self.path.stat().st_mtime_ns, before.st_mtime_ns)


if __name__ == "__main__":
    unittest.main()
