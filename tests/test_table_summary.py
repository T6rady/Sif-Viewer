from decimal import Decimal
import unittest

from core.sif_parser import parse_sif
from core.table_summary import summarize
from tests.test_sif_parser import PRODUCT, VALID


class SummaryTests(unittest.TestCase):
    def test_exact_totals_and_partial_values(self):
        rows = parse_sif(VALID + PRODUCT.replace("QT=2.0", "QT=0") +
                         PRODUCT.replace("PL=100.50", "PL=")).records
        totals = summarize(rows)
        self.assertEqual(totals.count, 3)
        self.assertEqual(totals.quantity, Decimal("4"))
        self.assertEqual(totals.extended, Decimal("201.000"))
        self.assertEqual(totals.quantity_missing, 0)
        self.assertEqual(totals.extended_missing, 1)

    def test_no_records_or_missing_operands_are_not_zero(self):
        self.assertIsNone(summarize(()).quantity)
        rows = parse_sif(VALID.replace("QT=2.0", "QT=")).records
        totals = summarize(rows)
        self.assertIsNone(totals.quantity)
        self.assertIsNone(totals.extended)
        self.assertEqual(totals.quantity_missing, 1)
        self.assertEqual(totals.extended_missing, 1)

    def test_different_decimal_scales_keep_precision(self):
        rows = parse_sif(VALID.replace("QT=2.0", "QT=123456789012345678901234567890") +
                         PRODUCT.replace("QT=2.0", "QT=0.00000001")).records
        self.assertEqual(summarize(rows).quantity, Decimal("123456789012345678901234567890.00000001"))
