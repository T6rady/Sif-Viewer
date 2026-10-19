import hashlib
import os
from pathlib import Path
import unittest

from core.file_reader import read_file
from core.sif_parser import extended_list_price, numeric_value, parse_sif


PRODUCT = "PN=CHAIR-01\nPD=Chair = blue  \nMC=ABC\nQT=2.0\nPL=100.50\n"
VALID = "SF=Test project\nST=\n" + PRODUCT


class ParserTests(unittest.TestCase):
    def test_exporter_metadata_and_numeric_leading_codes(self):
        text = "SF=Example\nST=CompassSIF\nDT=9/18/2026\nTM=10:58 AM\nNR=0\nDT=\n" + PRODUCT + "3D=\n3D=model\n"
        result = parse_sif(text)
        self.assertTrue(result.available, result.reason)
        self.assertEqual(result.headers[-4:], (("DT", "9/18/2026"), ("TM", "10:58 AM"), ("NR", "0"), ("DT", "")))
        self.assertEqual(result.records[0].unknown, (("3D", ""), ("3D", "model")))
        self.assertEqual(result.unknown_codes, ("3D",))
        self.assertEqual(len(result.records), 1)
        self.assertFalse(parse_sif("DT=example\n" + PRODUCT).available)

    def test_repeated_side_marks_preserve_values_and_product_boundaries(self):
        from core.table_data import record_value
        result = parse_sif(VALID + "TG=Room 1\nTG=  Chair  \nTG=\nTG=Room 1\n" + PRODUCT + "TG=Desk\n")
        self.assertTrue(result.available, result.reason)
        self.assertEqual(result.records[0].tags, ("Room 1", "  Chair  ", "", "Room 1"))
        self.assertEqual(record_value(result.records[0], "TG"), "Room 1 |   Chair   |  | Room 1")
        self.assertEqual(result.records[1].tags, ("Desk",))
        self.assertEqual(record_value(result.records[1], "TG"), "Desk")
        self.assertEqual(parse_sif(VALID).records[0].tags, ())

    def test_documented_fields(self):
        result = parse_sif(VALID)
        self.assertTrue(result.available, result.reason)
        self.assertEqual(result.records[0].fields,
                         {"PN": "CHAIR-01", "PD": "Chair = blue  ", "MC": "ABC", "QT": "2.0", "PL": "100.50"})
        self.assertEqual(result.records[0].line, 3)
        self.assertEqual(result.records[0].item, 1)
        self.assertEqual(result.headers, (("SF", "Test project"), ("ST", "")))

    def test_products_need_no_blank_separator(self):
        result = parse_sif(VALID + PRODUCT.replace("CHAIR-01", "DESK-02"))
        self.assertTrue(result.available, result.reason)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(result.records[1].fields["PN"], "DESK-02")
        self.assertEqual(result.records[1].item, 2)

    def test_order_after_pn_and_line_endings(self):
        for newline in ("\r\n", "\n", "\r"):
            result = parse_sif(newline.join(("ST=Title", "PN=X", "PL=2", "QT=.5", "MC=ABC", "PD=Desk")))
            self.assertTrue(result.available, result.reason)

    def test_options_and_attributes_are_paired_in_order(self):
        result = parse_sif(VALID + "ON=A\nOD=Black\nON=B\n\nOD=  Fabric  \nAN=NOTE\nAD=Handle with care\n")
        self.assertTrue(result.available, result.reason)
        self.assertEqual(result.records[0].options, (("A", "Black"), ("B", "  Fabric  ")))
        self.assertEqual(result.records[0].attributes, (("NOTE", "Handle with care"),))

    def test_unknown_fields_are_retained_without_names(self):
        result = parse_sif(VALID + "PS=0.0\nWT=0\nPS=a=b\n")
        self.assertTrue(result.available, result.reason)
        self.assertEqual(result.unknown_codes, ("PS", "WT"))
        self.assertEqual(result.records[0].unknown, (("PS", "0.0"), ("WT", "0"), ("PS", "a=b")))
        self.assertNotIn("PS", result.records[0].fields)

    def test_missing_required_fields_are_warnings(self):
        for code in ("PD", "MC", "QT", "PL"):
            text = "\n".join(line for line in VALID.splitlines() if not line.startswith(code + "="))
            result = parse_sif(text)
            self.assertTrue(result.available, result.reason)
            self.assertNotIn(code, result.records[0].fields)
            self.assertEqual(len(result.warnings), 1)
            self.assertIn(code, result.warnings[0].message)
            self.assertIn("missing", result.warnings[0].message)
            self.assertEqual(result.warnings[0].line, 3)

    def test_empty_fields_warn_at_their_exact_source_line(self):
        for code in ("PN", "PD", "MC", "QT", "PL"):
            lines = VALID.splitlines()
            line_number = next(i for i, line in enumerate(lines, 1) if line.startswith(code + "="))
            lines[line_number - 1] = code + "=  "
            result = parse_sif("\n".join(lines))
            self.assertTrue(result.available, result.reason)
            self.assertEqual(result.records[0].fields[code], "  ")
            self.assertEqual(result.warnings[0].line, line_number)
            self.assertIn("empty", result.warnings[0].message)

    def test_incomplete_products_do_not_hide_other_products(self):
        result = parse_sif(VALID + "PN=INCOMPLETE\n" + PRODUCT)
        self.assertTrue(result.available, result.reason)
        self.assertEqual(len(result.records), 3)
        self.assertEqual(len(result.records[1].warnings), 4)
        self.assertFalse(result.records[0].warnings)
        self.assertFalse(result.records[2].warnings)
        self.assertEqual(result.records[1].fields, {"PN": "INCOMPLETE"})
        self.assertTrue(all(warning.text.startswith("Item 2:") for warning in result.records[1].warnings))

    def test_ambiguous_structures_are_rejected(self):
        for text in (VALID + "ON=A\n", VALID + "OD=Black\n",
                     VALID + "AN=X\nOD=wrong\n", VALID + "ON=A\nQT=2\nOD=B\n",
                     VALID + "ST=another\n", "SF=A\nSF=B\n" + PRODUCT,
                     "PD=prelude\n" + VALID, PRODUCT, "SF=X\n", "hello", "", " \n\t",
                     VALID + " continuation\n", VALID + " =unknown\n"):
            with self.subTest(text=text):
                result = parse_sif(text)
                self.assertFalse(result.available)
                self.assertEqual(result.records, ())
                self.assertIn("Raw View remains available", result.reason)

    def test_invalid_numeric_fields(self):
        for value in ("NaN", "Infinity", "$100", "1,000", "1e4", "1.2.3"):
            with self.subTest(value=value):
                result = parse_sif(VALID.replace("QT=2.0", "QT=" + value))
                self.assertTrue(result.available, result.reason)
                self.assertEqual(result.records[0].fields["QT"], value)
                self.assertIn("not a plain decimal", result.warnings[0].message)
                self.assertEqual(extended_list_price(result.records[0]), "")

    def test_repeated_fields_preserve_all_values_without_guessing_numbers(self):
        result = parse_sif(VALID + "GC=Group A\nGC=Group B\nQT=8\n" + PRODUCT)
        self.assertTrue(result.available, result.reason)
        first, second = result.records
        self.assertEqual(first.fields["GC"], "Group A | Group B")
        self.assertEqual(first.repeated_fields, (("GC", "Group A"), ("GC", "Group B"), ("QT", "2.0"), ("QT", "8")))
        self.assertEqual(extended_list_price(first), "")
        self.assertTrue(first.warnings)
        self.assertFalse(second.repeated_fields)
        self.assertEqual(extended_list_price(second), "201.000")

    def test_numeric_values_remain_strings(self):
        result = parse_sif(VALID.replace("PL=100.50", "PL=00100.500"))
        self.assertEqual(result.records[0].fields["PL"], "00100.500")
        self.assertLess(numeric_value("2.0"), numeric_value("10.0"))

    def test_extended_list_price_is_exact_and_missing_is_not_zero(self):
        for quantity, price, expected in (("2.0", "100.50", "201.000"),
                                          ("0", "100.50", "0.00"),
                                          ("1.25", "0.1234", "0.154250"),
                                          ("", "100.50", ""), ("2", "", "")):
            with self.subTest(quantity=quantity, price=price):
                row = parse_sif(VALID.replace("QT=2.0", "QT=" + quantity)
                               .replace("PL=100.50", "PL=" + price)).records[0]
                self.assertEqual(extended_list_price(row), expected)
                self.assertEqual(row.fields["QT"], quantity)
                self.assertEqual(row.fields["PL"], price)
        row = parse_sif(VALID.replace("QT=2.0", "QT=123456789012345678901234567890")
                       .replace("PL=100.50", "PL=10")).records[0]
        self.assertEqual(extended_list_price(row), "1234567890123456789012345678900")

    def test_catalog_product_line_code(self):
        result = parse_sif(VALID + "GC=EC\n")
        self.assertTrue(result.available, result.reason)
        self.assertEqual(result.records[0].fields["GC"], "EC")
        self.assertNotIn("GC", result.unknown_codes)

    @unittest.skipUnless(os.environ.get("SIF_TEST_FILE"), "Set SIF_TEST_FILE to test a private real SIF without copying it.")
    def test_real_supplied_file_is_read_only(self):
        path = Path(os.environ["SIF_TEST_FILE"])
        before = path.stat()
        digest = hashlib.sha256(path.read_bytes()).digest()
        document = read_file(path)
        result = parse_sif(document.text)
        self.assertTrue(result.available, result.reason)
        self.assertGreater(len(result.records), 0)
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(), digest)
        self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)


if __name__ == "__main__":
    unittest.main()
