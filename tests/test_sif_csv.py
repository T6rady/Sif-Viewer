import codecs
import csv
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.csv_exporter import ExportCancelled
from core.file_reader import read_file
from core.sif_csv import HEADINGS, ConversionError, export_reversible_csv, import_reversible_csv
from core.sif_parser import parse_sif
from tests.test_sif_parser import VALID


class ReversibleCsvTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "source.sif"
        self.csv = self.root / "source.sif.csv"
        self.output = self.root / "converted.sif"

    def export(self, data=VALID.encode()):
        self.source.write_bytes(data)
        document = read_file(self.source)
        export_reversible_csv(self.csv, document)
        return document

    def rows(self):
        with self.csv.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.reader(stream))

    def save_rows(self, rows):
        with self.csv.open("w", encoding="utf-8-sig", newline="") as stream:
            csv.writer(stream).writerows(rows)

    def round_trip(self, data):
        document = self.export(data)
        modified = self.source.stat().st_mtime_ns
        import_reversible_csv(self.csv, self.output, self.source)
        self.assertEqual(self.output.read_bytes(), data)
        self.assertEqual(self.source.read_bytes(), data)
        self.assertEqual(self.source.stat().st_mtime_ns, modified)
        return document

    def test_all_supported_encodings_and_boms(self):
        for encoding, bom in (("utf-8", b""), ("utf-8", codecs.BOM_UTF8),
                              ("utf-16-le", codecs.BOM_UTF16_LE), ("utf-16-be", codecs.BOM_UTF16_BE),
                              ("utf-32-le", codecs.BOM_UTF32_LE), ("utf-32-be", codecs.BOM_UTF32_BE),
                              ("cp1252", b"")):
            with self.subTest(encoding=encoding, bom=bom):
                self.round_trip(bom + (VALID + "PS=Café €\r\n").encode(encoding))
        self.assertIn("assumed", next(row[4] for row in self.rows() if row[3] == "encoding_note"))

    def test_empty_files_bom_only_and_final_line_endings(self):
        for data in (b"", codecs.BOM_UTF8, codecs.BOM_UTF16_BE, b"\r\n", b"\n\n", b"SF=A",
                     b"SF=A\r\n\t  \rPN=0001\nMC=\r\nPD=Equals=a=b  \rPL=001.2300"):
            with self.subTest(data=data):
                self.round_trip(data)

    def test_options_attributes_unknowns_and_missing_versus_blank(self):
        text = VALID.replace("MC=ABC", "MC=").replace("QT=2.0\n", "")
        text += 'ON=001\nOD=Blue | green, "woven"  \nAN=\nAD=\nPS=001.2300\nON=\nOD=\nPS=\n'
        self.round_trip(text.encode())
        fields = [row for row in self.rows() if row[0] == "field"]
        self.assertEqual([row[3] for row in fields][-8:], ["ON", "OD", "AN", "AD", "PS", "ON", "OD", "PS"])
        self.assertEqual([row[4] for row in fields if row[3] == "MC"], [""])
        self.assertFalse(any(row[3] == "QT" for row in fields))
        result = parse_sif(read_file(self.output).text)
        self.assertTrue(result.available)
        self.assertEqual(len(result.warnings), 2)
        self.assertTrue(all(w.text.startswith("Item 1:") for w in result.warnings))

    def test_literal_unsupported_text_is_preserved_without_expanding_table_support(self):
        data = b"unsupported\r\n  PN=literal\r\n\r\n=foo\n"
        self.round_trip(data)
        self.assertFalse(parse_sif(read_file(self.output).text).available)

    def test_sequence_controls_order_after_spreadsheet_sort(self):
        self.export()
        rows = self.rows()
        self.save_rows([rows[0], *reversed(rows[1:])])
        import_reversible_csv(self.csv, self.output)
        self.assertEqual(self.output.read_bytes(), VALID.encode())

    def test_export_uses_loaded_snapshot(self):
        document = self.export()
        self.source.write_bytes(b"changed externally")
        export_reversible_csv(self.csv, document)
        import_reversible_csv(self.csv, self.output)
        self.assertEqual(self.output.read_bytes(), VALID.encode())
        self.assertEqual(self.source.read_bytes(), b"changed externally")

    def test_source_paths_and_hardlink_aliases_are_protected(self):
        document = self.export()
        alias_csv = self.root / "alias.csv"
        alias_sif = self.root / "alias.sif"
        os.link(self.source, alias_csv)
        os.link(self.source, alias_sif)
        for target in (self.source, alias_csv):
            with self.subTest(target=target), self.assertRaises(ConversionError):
                export_reversible_csv(target, document)
        for target in (self.source, alias_sif, self.csv):
            with self.subTest(target=target), self.assertRaises(ConversionError):
                import_reversible_csv(self.csv, target, self.source)
        self.assertEqual(self.source.read_bytes(), VALID.encode())
        csv_alias = self.root / "csv-alias.sif"
        os.link(self.csv, csv_alias)
        with self.assertRaises(ConversionError):
            import_reversible_csv(self.csv, csv_alias)

    def test_structural_errors_leave_existing_destination_intact(self):
        self.export()
        original = self.rows()
        self.output.write_bytes(b"keep existing")
        changes = [
            lambda rows: rows[0].__setitem__(0, "Item"),
            lambda rows: rows[1].__setitem__(4, "ori-sif-csv/99"),
            lambda rows: rows.append(rows[1].copy()),
            lambda rows: rows[2].__setitem__(4, "arbitrary-codec"),
            lambda rows: rows[3].__setitem__(4, "invalid"),
            lambda rows: rows[-1].__setitem__(1, "0"),
            lambda rows: rows[-1].__setitem__(1, "100"),
            lambda rows: rows[-1].__setitem__(1, rows[-2][1]),
            lambda rows: rows[-1].__setitem__(2, "42"),
            lambda rows: rows[-1].__setitem__(3, "bad code"),
            lambda rows: rows[-1].__setitem__(4, "one\ntwo"),
            lambda rows: rows[-1].__setitem__(5, "invalid"),
            lambda rows: rows[-2].__setitem__(5, "NONE"),
            lambda rows: rows[-1].append("extra"),
            lambda rows: rows[-1].__setitem__(0, "unsupported"),
        ]
        for change in changes:
            rows = [row.copy() for row in original]
            change(rows)
            self.save_rows(rows)
            with self.subTest(rows=rows[-1]), self.assertRaises(ConversionError):
                import_reversible_csv(self.csv, self.output)
            self.assertEqual(self.output.read_bytes(), b"keep existing")
            self.assertEqual(list(self.root.glob(".sif-convert-*")), [])

    def test_encoding_edits_never_replace_characters(self):
        self.export((VALID + "PS=Café\n").encode("cp1252"))
        rows = self.rows()
        rows[-1][4] = "日本語"
        self.save_rows(rows)
        with self.assertRaisesRegex(ConversionError, "Item 1:.*No characters were replaced"):
            import_reversible_csv(self.csv, self.output)
        self.assertFalse(self.output.exists())

    def test_control_characters_and_invalid_utf8_are_rejected(self):
        self.export()
        rows = self.rows()
        rows[-1][4] = "binary\0value"
        self.save_rows(rows)
        with self.assertRaises(ConversionError):
            import_reversible_csv(self.csv, self.output)
        self.csv.write_bytes(b"\xff")
        with self.assertRaises(ConversionError):
            import_reversible_csv(self.csv, self.output)

    def test_large_field_exceeds_standard_csv_parser_default(self):
        self.round_trip(VALID.encode() + b"PS=" + b"a" * 150_000)

    def test_structure_limits_preserve_existing_conversion_destinations(self):
        self.export()
        self.output.write_bytes(b'keep')
        for name, maximum in (('MAX_TEXT_LINES', 2), ('MAX_LINE_CHARACTERS', 8)):
            with self.subTest(limit=name), patch('core.sif_csv.' + name, maximum):
                with self.assertRaises(ConversionError):
                    import_reversible_csv(self.csv, self.output)
            self.assertEqual(self.output.read_bytes(), b'keep')
            self.assertEqual(list(self.root.glob('.sif-convert-*')), [])

    def test_many_csv_columns_fail_before_large_row_allocation(self):
        self.csv.write_text(','.join(HEADINGS) + '\n' + ',' * 10000, encoding='utf-8')
        with patch('core.sif_csv.MAX_LINE_CHARACTERS', 64):
            with self.assertRaisesRegex(ConversionError, 'physical-line'):
                import_reversible_csv(self.csv, self.output)
        self.assertFalse(self.output.exists())

    def test_literal_rows_cannot_hide_fields_and_unicode_requires_bom(self):
        self.export()
        original = self.rows()
        for kind, code, value, eol in (("text", "", "PN=hidden", "LF"),
                                        ("text", "", "", "NONE"),
                                        ("text", "PS", "literal", "LF")):
            rows = [row.copy() for row in original]
            rows[-1][0], rows[-1][3], rows[-1][4], rows[-1][5] = kind, code, value, eol
            self.save_rows(rows)
            with self.assertRaises(ConversionError):
                import_reversible_csv(self.csv, self.output)
        rows = [row.copy() for row in original]
        rows[2][4] = "utf-16-le"
        self.save_rows(rows)
        with self.assertRaisesRegex(ConversionError, "BOM"):
            import_reversible_csv(self.csv, self.output)
        self.csv.write_text(','.join(original[0]) + '\n"unterminated', encoding="utf-8")
        with self.assertRaises(ConversionError):
            import_reversible_csv(self.csv, self.output)

    def test_limits_in_both_directions_preserve_destinations(self):
        document = self.export()
        original = self.csv.read_bytes()
        with patch("core.sif_csv.MAX_CSV_BYTES", 10):
            with self.assertRaises(ConversionError):
                export_reversible_csv(self.csv, document)
            with self.assertRaises(ConversionError):
                import_reversible_csv(self.csv, self.output)
        self.assertEqual(self.csv.read_bytes(), original)
        with patch("core.sif_csv.MAX_FILE_BYTES", 10):
            with self.assertRaises(ConversionError):
                import_reversible_csv(self.csv, self.output)
        self.assertFalse(self.output.exists())

    def test_cancel_and_replace_failure_preserve_existing_destinations(self):
        document = self.export()
        self.output.write_bytes(b"keep")
        before = self.csv.read_bytes()
        operations = [lambda cancelled: export_reversible_csv(self.csv, document, cancelled),
                      lambda cancelled: import_reversible_csv(self.csv, self.output, self.source, cancelled)]
        for operation in operations:
            for cancel in (Mock(return_value=True), Mock(side_effect=[False, False, True])):
                with self.assertRaises(ExportCancelled):
                    operation(cancel)
            with patch("core.sif_csv.os.replace", side_effect=PermissionError("File open in Excel")):
                with self.assertRaisesRegex(ConversionError, "Excel"):
                    operation(lambda: False)
            self.assertEqual(self.csv.read_bytes(), before)
            self.assertEqual(self.output.read_bytes(), b"keep")
            self.assertEqual(list(self.root.glob(".sif-convert-*")), [])

    @unittest.skipUnless(os.environ.get("SIF_TEST_FILE"), "Set SIF_TEST_FILE to test a private SIF")
    def test_private_file_byte_identical_round_trip(self):
        source = Path(os.environ["SIF_TEST_FILE"])
        before = source.stat().st_mtime_ns
        digest = hashlib.sha256(source.read_bytes()).digest()
        export_reversible_csv(self.csv, read_file(source))
        import_reversible_csv(self.csv, self.output, source)
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).digest(), digest)
        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), digest)
        self.assertEqual(source.stat().st_mtime_ns, before)
