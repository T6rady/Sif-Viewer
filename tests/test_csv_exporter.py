import csv
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.csv_exporter import CsvExportError, ExportCancelled, export_csv
from core.file_reader import read_file
from core.sif_parser import parse_sif
from tests.test_sif_parser import VALID


class CsvExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "source.sif"
        self.source.write_bytes(VALID.encode())
        self.target = self.root / "export.csv"
        self.records = parse_sif(VALID).records

    def read_rows(self):
        with self.target.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.reader(stream))

    def write(self, **kwargs):
        return export_csv(kwargs.pop("path", self.target), ("Product", "Description", "Price", "Extended"),
                          ("PN", "PD", "PL", "extended_list"), kwargs.pop("records", self.records),
                          self.source, **kwargs)

    def test_unicode_csv_quoting_whitespace_and_exact_numbers(self):
        fields = dict(self.records[0].fields, PN="000123", PD='Café, 48" chair\r\nSecond line  ')
        record = replace(self.records[0], fields=fields, item=42)
        original, modified = self.source.read_bytes(), self.source.stat().st_mtime_ns
        self.assertEqual(self.write(records=(record,)), 1)
        self.assertTrue(self.target.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertEqual(self.read_rows(), [["Item", "Product", "Description", "Price", "Extended"],
                                          ["42", "000123", fields["PD"], "100.50", "201.000"]])
        self.assertTrue(self.target.read_bytes().endswith(b"\r\n"))
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(self.source.stat().st_mtime_ns, modified)

    def test_repeated_options_attributes_unknowns_and_blanks(self):
        text = VALID.replace("MC=ABC", "MC=") + 'ON=A\nOD=Wood, oak\nON=B\nOD=Blue "fabric"\nAN=Note\nAD=Care\nPS=1\nPS=2\n'
        record = parse_sif(text).records[0]
        codes = ("MC", "options_count", "option_codes", "option_descriptions", "attributes", "raw:PS", "warnings")
        export_csv(self.target, codes, codes, (record,), self.source)
        row = self.read_rows()[1]
        self.assertEqual(row[1:7], ["", "2", "A | B", 'Wood, oak | Blue "fabric"', "Note : Care", "1 | 2"])
        self.assertIn("Item 1:", row[7])

    def test_source_and_sif_destinations_are_protected(self):
        original = self.source.read_bytes()
        for target in (self.source, self.root / "other.sif"):
            with self.subTest(target=target), self.assertRaises(CsvExportError):
                self.write(path=target)
        alias = self.root / "alias.csv"
        os.link(self.source, alias)
        with self.assertRaises(CsvExportError):
            self.write(path=alias)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(alias.read_bytes(), original)

    def test_failed_replace_preserves_existing_csv_and_removes_temporary(self):
        self.target.write_bytes(b"Existing CSV")
        with patch("core.csv_exporter.os.replace", side_effect=PermissionError("File is open in Excel")):
            with self.assertRaisesRegex(CsvExportError, "open in Excel"):
                self.write()
        self.assertEqual(self.target.read_bytes(), b"Existing CSV")
        self.assertEqual(list(self.root.glob(".sif-csv-*")), [])
        self.assertEqual(self.write(), 1)
        self.assertEqual(len(self.read_rows()), 2)

    def test_cancel_preserves_destination_and_removes_temporary(self):
        self.target.write_bytes(b"Keep this")
        for side_effect in ([True], [False, True]):
            with self.subTest(side_effect=side_effect):
                with self.assertRaises(ExportCancelled):
                    self.write(cancelled=Mock(side_effect=side_effect))
                self.assertEqual(self.target.read_bytes(), b"Keep this")
                self.assertEqual(list(self.root.glob(".sif-csv-*")), [])

    def test_invalid_columns_and_unwritable_destination(self):
        with self.assertRaises(CsvExportError):
            export_csv(self.target, (), (), self.records, self.source)
        with self.assertRaises(CsvExportError):
            self.write(path=self.root / "missing-folder" / "export.csv")
        self.assertFalse(self.target.exists())

    def test_real_supplied_file_exports_all_items_without_changing_source(self):
        source = os.environ.get("SIF_TEST_FILE")
        if not source:
            self.skipTest("Set SIF_TEST_FILE to test a real contract furniture SIF")
        document = read_file(source)
        original = document.path.read_bytes()
        modified = document.path.stat().st_mtime_ns
        records = parse_sif(document.text).records
        self.assertEqual(export_csv(self.target, ("Manufacturer", "Product", "Options"),
                                    ("MC", "PN", "options"), records, document.path), len(records))
        rows = self.read_rows()
        self.assertEqual(len(rows), len(records) + 1)
        for record, row in zip(records, rows[1:]):
            self.assertEqual(row[:3], [str(record.item), record.fields.get("MC", ""), record.fields.get("PN", "")])
        self.assertEqual(document.path.read_bytes(), original)
        self.assertEqual(document.path.stat().st_mtime_ns, modified)
