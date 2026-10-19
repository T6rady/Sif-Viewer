import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from core.file_reader import FileReadError, read_file
from core.resource_limits import ProcessingCancelled, ResourceLimitError, text_lines
from core.sif_parser import extended_list_price, numeric_value, parse_sif
from core.table_summary import summarize
from tests.test_sif_parser import VALID, PRODUCT


class ResourceLimitTests(unittest.TestCase):
    def test_streamed_lines_preserve_mixed_endings_and_final_line(self):
        self.assertEqual(list(text_lines('a\r\n\rb\nc')), [(1, 'a', '\r\n'), (2, '', '\r'), (3, 'b', '\n'), (4, 'c', '')])
        self.assertEqual(list(text_lines('')), [])

    def test_text_limit_boundaries(self):
        with patch('core.resource_limits.MAX_LINE_CHARACTERS', 4):
            self.assertEqual(list(text_lines('1234\n'))[0][1], '1234')
            with self.assertRaisesRegex(ResourceLimitError, 'Line 1'):
                list(text_lines('12345'))
        with patch('core.resource_limits.MAX_TEXT_LINES', 2):
            self.assertEqual(len(list(text_lines('a\nb\n'))), 2)
            with self.assertRaisesRegex(ResourceLimitError, 'physical-line'):
                list(text_lines('a\nb\nc'))

    def test_table_limits_do_not_return_a_partial_table(self):
        cases = [('MAX_PRODUCTS', 2, VALID + PRODUCT, VALID + PRODUCT * 2),
                 ('MAX_UNKNOWN_CODES', 2, VALID + 'XX=a\nXY=b\n', VALID + 'XX=a\nXY=b\nXZ=c\n'),
                 ('MAX_PRODUCT_FIELDS', 5, VALID, VALID + 'XX=a\n'),
                 ('MAX_PRODUCT_CHARACTERS', 100, VALID, VALID + 'XX=' + 'x' * 100),
                 ('MAX_HEADER_FIELDS', 2, VALID, 'SF=x\nST=\nDT=x\n' + PRODUCT),
                 ('MAX_HEADER_CHARACTERS', 100, VALID, 'SF=' + 'x' * 100 + '\n' + PRODUCT)]
        for name, maximum, accepted, rejected in cases:
            with self.subTest(limit=name), patch('core.sif_parser.' + name, maximum):
                self.assertTrue(parse_sif(accepted).available)
                result = parse_sif(rejected)
                self.assertFalse(result.available)
                self.assertEqual(result.records, ())
                self.assertIn('limit', result.reason)

    def test_repeated_scalar_values_are_joined_once_without_loss(self):
        values = [str(i) for i in range(2000)]
        result = parse_sif(VALID + ''.join('GC=' + v + '\n' for v in values))
        self.assertTrue(result.available, result.reason)
        self.assertEqual(result.records[0].fields['GC'], ' | '.join(values))
        self.assertEqual(result.records[0].repeated_fields, tuple(('GC', v) for v in values))

    def test_numeric_limit_warns_but_keeps_source_and_safe_totals_exact(self):
        self.assertIsNotNone(numeric_value('9' * 256))
        self.assertIsNone(numeric_value('9' * 257))
        result = parse_sif(VALID.replace('QT=2.0', 'QT=' + '9' * 257))
        self.assertTrue(result.available)
        self.assertEqual(result.records[0].fields['QT'], '9' * 257)
        self.assertIn('numeric limit', result.warnings[0].message)
        self.assertEqual(extended_list_price(result.records[0]), '')
        valid = parse_sif(VALID.replace('QT=2.0', 'QT=' + '9' * 256).replace('PL=100.50', 'PL=' + '9' * 256))
        expected = str(int('9' * 256) ** 2)
        self.assertEqual(extended_list_price(valid.records[0]), expected)
        self.assertEqual(format(summarize(valid.records).extended, 'f'), expected)

    def test_parser_cancels_during_work(self):
        calls = 0
        def cancelled():
            nonlocal calls
            calls += 1
            return calls == 4
        with self.assertRaises(ProcessingCancelled):
            parse_sif(VALID * 100, cancelled)
        self.assertEqual(calls, 4)

    def test_reader_rejects_unsafe_raw_structure_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'example.sif'
            source.write_bytes(b'12345')
            with patch('core.resource_limits.MAX_LINE_CHARACTERS', 4):
                with self.assertRaisesRegex(FileReadError, 'character limit'):
                    read_file(source)
            self.assertEqual(source.read_bytes(), b'12345')
