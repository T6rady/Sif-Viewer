"""Headless Qt integration checks; no third-party test dependencies."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import csv
from decimal import Decimal
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPlainTextEdit

from core.sif_parser import parse_sif
from core.file_reader import read_file
from core.sif_csv import export_reversible_csv, import_reversible_csv
from tests.test_sif_parser import VALID, PRODUCT
from ui.main_window import MainWindow


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        default_check = patch("ui.main_window.is_default_sif_app", return_value=False)
        default_check.start()
        self.addCleanup(default_check.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "test.sif"
        self.path.write_bytes(VALID.replace("\n", "\r\n").encode("utf-8"))
        self.settings = QSettings(str(Path(self.directory.name) / "preferences.ini"), QSettings.Format.IniFormat)
        self.window = MainWindow(settings=self.settings)
        self.window.show()

    def tearDown(self):
        self.wait_for(lambda: self.window._worker is None and self.window._export_worker is None and not self.window._busy)
        self.window.close()
        self.app.processEvents()
        self.window.deleteLater()
        self.directory.cleanup()

    def wait_for(self, predicate, seconds=30):
        deadline = time.monotonic() + seconds
        while not predicate():
            self.app.processEvents()
            QTest.qWait(2)
            if time.monotonic() > deadline:
                self.fail("Timed out waiting for GUI work")
        self.app.processEvents()

    def open_file(self):
        self.window.open_path(self.path)
        self.wait_for(lambda: not self.window._busy and self.window._worker is None)

    def test_open_search_copy_metadata_and_read_only(self):
        original = self.path.read_bytes()
        modified = self.path.stat().st_mtime_ns
        self.open_file()
        self.assertEqual(self.window.raw.toPlainText(), original.decode().replace("\r\n", "\n"))
        self.assertIn(str(len(original)), self.window.metadata.text())
        self.assertIn("7 lines", self.window.metadata.text())
        self.assertEqual(self.window.file_path.text(), str(self.path))
        self.assertTrue(self.window.raw.isReadOnly())
        self.window.raw_action.trigger()
        self.window.search.setText("chair")
        QTest.keyClick(self.window.search, Qt.Key.Key_Return)
        self.assertEqual(self.window.raw.textCursor().selectedText(), "CHAIR")
        self.window.find_next()
        self.assertEqual(self.window.raw.textCursor().selectedText(), "Chair")
        self.window.raw.copy()
        self.assertEqual(self.app.clipboard().text(), "Chair")
        self.window.match_case.setChecked(True)
        self.window.search.setText("chair")
        self.window.find_next()
        self.assertEqual(self.window.statusBar().currentMessage(), "No matches")
        self.window.search.setText("CHAIR")
        self.window.find_next(True)
        self.assertEqual(self.window.raw.textCursor().selectedText(), "CHAIR")
        self.window.wrap_action.setChecked(True)
        self.assertEqual(self.window.raw.lineWrapMode(), QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.path.stat().st_mtime_ns, modified)

    def test_reversible_export_ignores_filter_columns_and_current_view(self):
        self.open_file()
        self.window.search.setText("no matching products")
        self.window._apply_filter()
        self.window.raw_action.trigger()
        target = Path(self.directory.name) / "roundtrip.sif.csv"
        with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=(str(target), "CSV")):
            self.window.reversible_action.trigger()
        self.wait_for(lambda: self.window._export_worker is None)
        output = Path(self.directory.name) / "new.sif"
        import_reversible_csv(target, output, self.path)
        self.assertEqual(output.read_bytes(), self.path.read_bytes())

    def test_csv_conversion_from_startup_opens_generated_sif_with_item_warnings(self):
        self.assertTrue(self.window.convert_sif_action.isEnabled())
        self.assertFalse(self.window.reversible_action.isEnabled())
        self.path.write_bytes((VALID + PRODUCT.replace("MC=ABC", "MC=")).encode())
        original = self.path.read_bytes()
        source = Path(self.directory.name) / "test.sif.csv"
        target = Path(self.directory.name) / "test-converted.sif"
        export_reversible_csv(source, read_file(self.path))
        with patch("ui.main_window.QFileDialog.getOpenFileName", return_value=(str(source), "CSV")), \
                patch("ui.main_window.QFileDialog.getSaveFileName", return_value=(str(target), "SIF")) as save:
            self.window.convert_sif_action.trigger()
            self.assertEqual(Path(save.call_args.args[2]), target)
        self.wait_for(lambda: self.window._export_worker is None and self.window._worker is None and not self.window._busy)
        self.assertEqual(self.window.current_file.path, target)
        self.assertTrue(self.window.parse_result.available)
        self.assertEqual(self.window.parse_result.warnings[0].text, "Item 2: Manufacturer code (MC) is empty.")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(target.read_bytes(), original)

    def test_conversion_dialog_cancellation_and_suffix(self):
        self.open_file()
        with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=("", "")):
            self.window.reversible_action.trigger()
        with patch("ui.main_window.QFileDialog.getOpenFileName", return_value=("", "")):
            self.window.convert_sif_action.trigger()
        self.assertIsNone(self.window._export_worker)
        target = Path(self.directory.name) / "reversible"
        with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=(str(target), "")):
            self.window.reversible_action.trigger()
        self.wait_for(lambda: self.window._export_worker is None)
        self.assertTrue(target.with_suffix(".csv").exists())
        with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=(str(target), "")), \
                patch("ui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            self.window.reversible_action.trigger()
        self.assertIsNone(self.window._export_worker)

    def test_conversion_errors_keep_open_document_and_source(self):
        self.open_file()
        original = self.path.read_bytes()
        source = Path(self.directory.name) / "readable.csv"
        source.write_text("Item,Product\n1,CHAIR\n", encoding="utf-8")
        target = Path(self.directory.name) / "failed.sif"
        with patch("ui.main_window.QMessageBox.warning") as warning:
            self.window.start_conversion(target, source)
            self.wait_for(lambda: self.window._export_worker is None)
            self.assertIn("readable table export", warning.call_args.args[2])
        self.assertFalse(target.exists())
        self.assertEqual(self.window.current_file.path, self.path)
        reversible = Path(self.directory.name) / "source.sif.csv"
        export_reversible_csv(reversible, self.window.current_file)
        with patch("ui.main_window.QMessageBox.warning") as warning:
            self.window.start_conversion(self.path, reversible)
            self.wait_for(lambda: self.window._export_worker is None)
            self.assertIn("opened SIF", warning.call_args.args[2])
        self.assertEqual(self.path.read_bytes(), original)

    def test_conversion_worker_keeps_ui_responsive_and_blocks_concurrent_open(self):
        self.path.write_bytes(("SF=Large\n" + PRODUCT * 6000).encode())
        self.open_file()
        target = Path(self.directory.name) / "large.sif.csv"
        beats = []
        heartbeat = QTimer()
        heartbeat.setInterval(5)
        heartbeat.timeout.connect(lambda: beats.append(time.monotonic()))
        heartbeat.start()
        self.window.start_conversion(target)
        self.assertFalse(self.window.open_action.isEnabled())
        self.assertFalse(self.window.convert_sif_action.isEnabled())
        self.window.open_path(Path(self.directory.name) / "missing.sif")
        self.assertFalse(self.window._busy)
        self.wait_for(lambda: self.window._export_worker is None)
        heartbeat.stop()
        self.assertGreater(len(beats), 1)
        self.assertTrue(self.window.open_action.isEnabled())
        self.assertEqual(self.window.current_file.path, self.path)
        output = Path(self.directory.name) / "large-converted.sif"
        self.window.start_conversion(output, target)
        self.wait_for(lambda: self.window._export_worker is None and self.window._worker is None and not self.window._busy)
        self.assertEqual(output.read_bytes(), self.path.read_bytes())
        self.assertEqual(len(self.window.parse_result.records), 6000)

    def test_reversible_export_is_available_when_table_is_unsupported(self):
        self.path.write_bytes(b"uninterpreted dialect\r\n\r\nPN=X\n")
        self.open_file()
        self.assertFalse(self.window.parse_result.available)
        self.assertTrue(self.window.reversible_action.isEnabled())
        target = Path(self.directory.name) / "unsupported.csv"
        self.window.start_conversion(target)
        self.wait_for(lambda: self.window._export_worker is None)
        output = Path(self.directory.name) / "unsupported-copy.sif"
        import_reversible_csv(target, output)
        self.assertEqual(output.read_bytes(), self.path.read_bytes())

    def test_closing_during_conversion_cancels_without_replacing_destination(self):
        self.open_file()
        target = Path(self.directory.name) / "cancelled.csv"
        target.write_bytes(b"keep existing")
        entered, release = threading.Event(), threading.Event()

        def blocked_export(path, document, cancelled):
            entered.set()
            release.wait(5)
            return export_reversible_csv(path, document, cancelled)

        with patch("ui.main_window.export_reversible_csv", side_effect=blocked_export):
            self.window.start_conversion(target)
            try:
                self.wait_for(entered.is_set)
                self.window.close()
                self.assertTrue(self.window._closing)
                self.assertFalse(self.window.isVisible())
            finally:
                release.set()
            self.wait_for(lambda: self.window._export_worker is None)
        self.assertEqual(target.read_bytes(), b"keep existing")

    def test_file_dialog_wiring(self):
        with patch("ui.main_window.QFileDialog.getOpenFileName", return_value=(str(self.path), "SIF files")):
            self.window.open_action.trigger()
        self.wait_for(lambda: not self.window._busy)
        self.assertEqual(self.window.current_file.path, self.path)

    def test_default_app_button_opens_windows_settings_without_a_file(self):
        self.assertTrue(self.window.default_app_button.isEnabled())
        with patch("ui.main_window.QMessageBox.information") as information, \
                patch("ui.main_window.QDesktopServices.openUrl", return_value=True) as open_url:
            self.window.default_app_button.click()
        self.assertEqual(open_url.call_args.args[0].toString(), "ms-settings:defaultapps")
        self.assertIn(".sif", information.call_args.args[2])
        self.assertIn("install", information.call_args.args[2])
        self.assertIsNone(self.window.current_file)

    def test_default_app_button_updates_when_returning_from_settings(self):
        self.assertFalse(self.window.default_app_button.isHidden())
        with patch("ui.main_window.is_default_sif_app", return_value=True), \
                patch.object(self.window, "isActiveWindow", return_value=True):
            self.window.changeEvent(QEvent(QEvent.Type.ActivationChange))
        self.assertTrue(self.window.default_app_button.isHidden())
        with patch("ui.main_window.is_default_sif_app", return_value=False), \
                patch.object(self.window, "isActiveWindow", return_value=True):
            self.window.changeEvent(QEvent(QEvent.Type.ActivationChange))
        self.assertFalse(self.window.default_app_button.isHidden())

    def test_default_app_button_is_hidden_at_startup_when_already_default(self):
        with patch("ui.main_window.is_default_sif_app", return_value=True):
            window = MainWindow(settings=self.settings)
        try:
            self.assertTrue(window.default_app_button.isHidden())
        finally:
            window.close()
            window.deleteLater()

    def test_default_app_settings_failure_explains_manual_steps_and_preserves_source(self):
        self.open_file()
        original = self.path.read_bytes()
        modified = self.path.stat().st_mtime_ns
        with patch("ui.main_window.QMessageBox.information"), \
                patch("ui.main_window.QDesktopServices.openUrl", return_value=False), \
                patch("ui.main_window.QMessageBox.warning") as warning:
            self.window.default_app_button.click()
        self.assertIn("Default apps", warning.call_args.args[2])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.path.stat().st_mtime_ns, modified)

    def test_drag_and_drop(self):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.path))])
        enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime,
                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.window.dragEnterEvent(enter)
        self.assertTrue(enter.isAccepted())
        drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.window.dropEvent(drop)
        self.wait_for(lambda: not self.window._busy)
        self.assertEqual(self.window.current_file.path, self.path)
        mime.setUrls([QUrl("https://example.com/test.sif")])
        self.assertIsNone(self.window._drop_path(mime))

    def test_table_numeric_sort_and_verified_cells(self):
        self.path.write_text(VALID + PRODUCT.replace("QT=2.0", "QT=10.0") + "WT=0\n", encoding="utf-8")
        self.open_file()
        self.window.table_action.trigger()
        self.assertEqual(self.window.stack.currentIndex(), 1)
        model = self.window.table.model
        proxy = self.window.table.proxy
        self.assertEqual(model.rowCount(), 2)
        self.assertIn("WT", self.window.table.unknown_button.text())
        self.assertNotIn("WT", model.columns)
        qt_column = model.columns.index("QT")
        proxy.sort(qt_column, Qt.SortOrder.DescendingOrder)
        self.assertEqual(proxy.index(0, qt_column).data(), "10.0")
        proxy.sort(qt_column, Qt.SortOrder.AscendingOrder)
        self.assertEqual(proxy.index(0, qt_column).data(), "2.0")
        self.window.table.table.setCurrentIndex(proxy.index(0, qt_column))
        QTest.keyClick(self.window.table.table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.app.clipboard().text(), "2.0")
        extended = model.columns.index("extended_list")
        proxy.sort(extended, Qt.SortOrder.DescendingOrder)
        self.assertEqual(proxy.index(0, extended).data(), "1005.000")
        self.assertIn("QT × PL", model.headerData(extended, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole))

    def test_split_options_attributes_and_raw_fields(self):
        text = VALID + "ON=A\nOD=Black\nON=B\nOD=Fabric\nAN=NOTE\nAD=Care\nPS=90.0\nPS=85.0\nWT=0\n"
        self.path.write_bytes(text.encode())
        self.open_file()
        model = self.window.table.model
        expected = {"option_codes": "A | B", "option_descriptions": "Black | Fabric",
                    "attribute_codes": "NOTE", "attribute_descriptions": "Care",
                    "raw:PS": "90.0 | 85.0", "raw:WT": "0", "extended_list": "201.000"}
        for code, value in expected.items():
            with self.subTest(code=code):
                self.assertEqual(model.index(0, model.columns.index(code)).data(), value)
        self.assertIn("uninterpreted", model.headerData(model.columns.index("raw:PS"), Qt.Orientation.Horizontal))
        self.assertEqual(self.path.read_bytes(), text.encode())

    def test_columns_menu_show_hide_reset_and_reload(self):
        self.open_file()
        view = self.window.table
        columns = view.model.columns
        self.assertFalse(view.table.isColumnHidden(columns.index("options_count")))
        self.assertTrue(view.table.isColumnHidden(columns.index("option_descriptions")))
        self.assertTrue(view.table.isColumnHidden(columns.index("GC")))
        view._column_actions["PD"].trigger()
        self.assertTrue(view.table.isColumnHidden(columns.index("PD")))
        self.open_file()
        self.assertTrue(view.table.isColumnHidden(view.model.columns.index("PD")))
        view.columns_menu.actions()[0].trigger()
        self.assertTrue(all(not view.table.isColumnHidden(i) for i in range(view.model.columnCount())))
        self.assertEqual(view.model.index(0, view.model.columns.index("GC")).data(), "")
        header = view.table.horizontalHeader()
        header.moveSection(header.visualIndex(view.model.columns.index("PD")), 0)
        view.columns_menu.actions()[1].trigger()
        self.assertFalse(view.table.isColumnHidden(view.model.columns.index("PD")))
        self.assertTrue(view.table.isColumnHidden(view.model.columns.index("GC")))
        self.assertEqual(header.visualIndex(0), 0)

    def test_copy_follows_visible_column_order(self):
        self.open_file()
        view = self.window.table
        for code in view.model.columns:
            view.set_column_visible(code, code in ("PN", "QT", "extended_list"))
        header = view.table.horizontalHeader()
        for position, code in enumerate(("PN", "QT", "extended_list")):
            header.moveSection(header.visualIndex(view.model.columns.index(code)), position)
        view.table.selectAll()
        QTest.keyClick(view.table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.app.clipboard().text(), "CHAIR-01\t2.0\t201.000")

    def test_malformed_and_empty_still_have_raw_view(self):
        for contents in ("unknown format\n", ""):
            self.path.write_text(contents, encoding="utf-8")
            self.open_file()
            self.assertEqual(self.window.raw.toPlainText(), contents)
            self.assertFalse(self.window.parse_result.available)
            self.assertFalse(self.window.table.table.isVisible())
            self.assertIn("Table View unavailable", self.window.notice.text())

    def test_missing_fields_are_visible_highlighted_and_follow_sorting(self):
        incomplete = PRODUCT.replace("PN=CHAIR-01", "PN=INCOMPLETE").replace("MC=ABC", "MC=").replace("PL=100.50\n", "")
        self.path.write_bytes((VALID + incomplete).encode())
        original = self.path.read_bytes()
        self.open_file()
        self.assertTrue(self.window.parse_result.available)
        self.window.table_action.trigger()
        self.assertTrue(self.window.table.table.isVisible())
        model = self.window.table.model
        proxy = self.window.table.proxy
        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.columns[0], "warnings")
        self.assertIn("MC", model.index(1, 0).data())
        self.assertIn("PL", model.index(1, 0).data())
        self.assertIn("Item 2:", model.index(1, 0).data())
        self.assertNotIn("line", model.index(1, 0).data())
        self.assertIn("Raw text line 10", model.index(1, 0).data(Qt.ItemDataRole.ToolTipRole))
        self.assertEqual(model.index(1, model.columns.index("MC")).data(), "")
        self.assertEqual(model.index(1, model.columns.index("PL")).data(), "")
        self.assertIsNotNone(model.index(1, 1).data(Qt.ItemDataRole.BackgroundRole))
        self.assertEqual(model.index(0, 1).data(Qt.ItemDataRole.BackgroundRole).name(), "#edf0ff")
        proxy.sort(model.columns.index("PN"), Qt.SortOrder.DescendingOrder)
        self.assertIn("MC", proxy.index(0, 0).data())
        self.assertIn("Item 2:", proxy.index(0, 0).data())
        self.assertEqual(proxy.headerData(0, Qt.Orientation.Vertical), 2)
        self.assertIsNotNone(proxy.index(0, 1).data(Qt.ItemDataRole.BackgroundRole))
        highlighted = {selection.cursor.blockNumber() + 1 for selection in self.window.raw.extraSelections()}
        self.assertEqual(highlighted, {8, 10})
        self.assertIn("Table View is available with warnings", self.window.notice.text())
        self.window.search.setText("INCOMPLETE")
        self.window.find_next()
        self.assertEqual(self.window.raw.textCursor().selectedText(), "INCOMPLETE")
        self.assertEqual(self.path.read_bytes(), original)
        # A subsequent clean load removes warnings and stale highlights.
        self.path.write_bytes(VALID.encode())
        self.open_file()
        self.assertEqual(self.window.raw.extraSelections(), [])
        self.assertNotIn("warnings", model.columns)

    def test_binary_error_keeps_previous_document(self):
        self.open_file()
        previous = self.window.raw.toPlainText()
        self.path.write_bytes(b"MZ\x00\x01")
        with patch("ui.main_window.QMessageBox.warning") as warning:
            self.open_file()
            warning.assert_called_once()
            self.assertIn("binary", warning.call_args.args[2])
        self.assertEqual(self.window.raw.toPlainText(), previous)

    def test_chunk_boundary_preserves_crlf(self):
        text = "A" * 32767 + "\r\n" + " B  \r\n"
        self.path.write_bytes(text.encode())
        self.open_file()
        self.assertEqual(self.window.raw.toPlainText(), text.replace("\r\n", "\n"))

    def test_filter_updates_totals_details_and_preserves_item_numbers(self):
        text = VALID + PRODUCT.replace("CHAIR-01", "DESK-02").replace("QT=2.0", "QT=3.0") + "ON=W\nOD=Walnut\n"
        self.path.write_bytes(text.encode())
        self.open_file()
        self.assertEqual(self.window.stack.currentIndex(), 1)
        self.window.search.setText("walnut")
        self.wait_for(lambda: self.window.table.proxy.rowCount() == 1)
        view = self.window.table
        self.assertEqual(view.proxy.headerData(0, Qt.Orientation.Vertical), 2)
        self.assertEqual(view.details.record.item, 2)
        self.assertEqual(view.totals_model.summary.quantity, Decimal("3"))
        self.assertEqual(view.totals_model.summary.extended, Decimal("301.500"))
        self.assertEqual(view.note.text(), "1 of 2 products")
        self.window.match_case.setChecked(True)
        self.wait_for(lambda: view.proxy.rowCount() == 0)
        self.assertIsNone(view.details.record)
        self.window.match_case.setChecked(False)
        self.wait_for(lambda: view.proxy.rowCount() == 1)
        self.window.search.setText("[")  # Literal text, never a regular expression.
        self.wait_for(lambda: view.proxy.rowCount() == 0)
        self.window.search.clear()
        self.wait_for(lambda: view.proxy.rowCount() == 2)
        self.assertEqual(view.totals_model.summary.quantity, Decimal("5"))
        self.assertEqual(self.path.read_bytes(), text.encode())

    def test_details_keep_all_options_and_can_jump_to_raw(self):
        pairs = "".join(f"ON=CODE-{i}\nOD=Description {i}\n" for i in range(18))
        self.path.write_bytes((VALID + pairs + "AN=NOTE\nAD=Care instructions\nPS=9\n").encode())
        self.open_file()
        details = self.window.table.details
        self.assertEqual(details.record.item, 1)
        self.assertEqual(details.sections["options"][3].rowCount(), 18)
        self.assertEqual(details.sections["attributes"][3].index(0, 1).data(), "Care instructions")
        self.assertEqual(details.sections["unknown"][3].index(0, 0).data(), "PS")
        details.copy_pairs("options")
        self.assertEqual(len(self.app.clipboard().text().splitlines()), 18)
        self.assertIn("CODE-17\tDescription 17", self.app.clipboard().text())
        details.raw_button.click()
        self.assertEqual(self.window.stack.currentIndex(), 0)
        self.assertEqual(self.window.raw.textCursor().blockNumber(), 2)
        metrics = self.window.raw.fontMetrics()
        self.assertEqual(metrics.horizontalAdvance("W"), metrics.horizontalAdvance("i"))

    def test_currency_and_path_controls_do_not_modify_source(self):
        original = self.path.read_bytes()
        self.open_file()
        view = self.window.table
        self.assertEqual(view.currency.currentText(), "Not set")
        self.assertEqual(view.details.values["extended"].text(), "201.00")
        view.currency.setCurrentText("USD")
        self.assertEqual(view.details.values["extended"].text(), "USD 201.00")
        self.assertEqual(view.model.index(0, view.model.columns.index("PL")).data(), "100.50")
        self.assertNotIn("USD", self.window.raw.toPlainText())
        self.window.copy_path.click()
        self.assertEqual(self.app.clipboard().text(), str(self.path))
        self.assertEqual(self.path.read_bytes(), original)
        self.open_file()
        self.assertEqual(view.currency.currentText(), "Not set")

    def test_keyboard_navigation_and_warning_link_use_original_items(self):
        self.path.write_bytes((VALID + PRODUCT.replace("CHAIR-01", "Z-LAST").replace("MC=ABC", "MC=")).encode())
        self.open_file()
        view = self.window.table
        column = view.model.columns.index("PN")
        view.proxy.sort(column, Qt.SortOrder.DescendingOrder)
        view.table.setCurrentIndex(view.proxy.index(0, column))
        self.assertEqual(view.details.record.item, 2)
        QTest.keyClick(view.table, Qt.Key.Key_Down)
        self.assertEqual(view.details.record.item, 1)
        self.window.search.setText("CHAIR-01")
        self.wait_for(lambda: view.proxy.rowCount() == 1)
        view.warning_button.click()
        self.assertEqual(self.window.search.text(), "")
        self.assertEqual(view.proxy.rowCount(), 2)
        self.assertEqual(view.details.record.item, 2)
        self.assertEqual(view.details.values["MC"].text(), "")
        self.assertIn("Item 2", view.details.warnings.text())

    def test_large_file_all_text_loaded_with_event_loop_heartbeat(self):
        text = "SF=Large synthetic test\n" + PRODUCT * 20000
        self.path.write_bytes(text.encode("utf-8"))
        heartbeats = []
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: heartbeats.append(time.monotonic()))
        timer.start()
        start = time.monotonic()
        self.open_file()
        timer.stop()
        self.assertEqual(self.window.raw.toPlainText(), text)
        self.assertEqual(self.window.table.model.rowCount(), 20000)
        self.assertGreater(len(heartbeats), 5)
        points = [start] + heartbeats + [time.monotonic()]
        longest = max(b - a for a, b in zip(points, points[1:]))
        self.assertLess(longest, 1.5, f"Event loop stalled for {longest:.2f}s")
        print(f"\nLarge-file check: {len(text):,} bytes, 20,000 products, "
              f"{len(heartbeats)} GUI heartbeats, longest gap {longest:.3f}s")

    def test_csv_export_matches_filter_sort_column_order_and_original_items(self):
        self.path.write_bytes((VALID.replace("CHAIR-01", "KEEP-A")
                               + PRODUCT.replace("CHAIR-01", "KEEP-Z").replace("MC=ABC", "MC=")
                               + PRODUCT.replace("CHAIR-01", "OTHER")).encode())
        self.open_file()
        original = self.path.read_bytes()
        view = self.window.table
        for code in view.model.columns:
            view.set_column_visible(code, code in ("MC", "PN", "extended_list"))
        header = view.table.horizontalHeader()
        for position, code in enumerate(("PN", "extended_list", "MC")):
            header.moveSection(header.visualIndex(view.model.columns.index(code)), position)
        view.proxy.sort(view.model.columns.index("PN"), Qt.SortOrder.DescendingOrder)
        self.window.search.setText("KEEP-")  # Export must flush the pending filter immediately.
        target = Path(self.directory.name) / "export.csv"
        with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=(str(target), "CSV files (*.csv)")):
            self.window.export_button.click()
        self.wait_for(lambda: self.window._export_worker is None)
        with target.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows, [["Item", "Product number (PN)", "Extended list price (calculated)", "Manufacturer code (MC)"],
                                ["2", "KEEP-Z", "201.000", ""], ["1", "KEEP-A", "201.000", "ABC"]])
        self.assertIn("Exported 2 products", self.window.statusBar().currentMessage())
        self.assertEqual(self.path.read_bytes(), original)
        self.assertTrue(self.window.export_action.isEnabled())

    def test_csv_export_cancel_unavailable_empty_filter_and_no_columns(self):
        self.assertFalse(self.window.export_action.isEnabled())
        self.open_file()
        with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=("", "")):
            self.window.export_action.trigger()
        self.assertIsNone(self.window._export_worker)
        self.window.raw_action.trigger()
        self.assertFalse(self.window.export_action.isEnabled())
        self.window.table_action.trigger()
        self.window.search.setText("No such product")
        with patch("ui.main_window.QFileDialog.getSaveFileName") as dialog:
            self.window.export_action.trigger()
            dialog.assert_not_called()
        self.assertIn("No products match", self.window.statusBar().currentMessage())
        self.window.search.clear()
        for code in self.window.table.model.columns:
            self.window.table.set_column_visible(code, False)
        with patch("ui.main_window.QFileDialog.getSaveFileName") as dialog:
            self.window.export_action.trigger()
            dialog.assert_not_called()
        self.assertIn("Show at least one column", self.window.statusBar().currentMessage())
        self.path.write_text("Unknown format", encoding="utf-8")
        self.open_file()
        self.assertFalse(self.window.export_action.isEnabled())

    def test_csv_export_reports_error_and_protects_source(self):
        self.open_file()
        original = self.path.read_bytes()
        with patch("ui.main_window.QMessageBox.warning") as warning:
            self.window.start_export(self.path)
            self.wait_for(lambda: self.window._export_worker is None)
            warning.assert_called_once()
            self.assertIn(".csv", warning.call_args.args[2])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertTrue(self.window.export_action.isEnabled())
        target = Path(self.directory.name) / "existing.csv"
        target.write_text("Keep me", encoding="utf-8")
        with patch("ui.main_window.QFileDialog.getSaveFileName", return_value=(str(target.with_suffix("")), "")):
            with patch("ui.main_window.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
                self.window.export_action.trigger()
        self.assertEqual(target.read_text(), "Keep me")
        self.assertIsNone(self.window._export_worker)

    def test_csv_large_export_remains_responsive_with_snapshot_isolation(self):
        self.path.write_bytes(("SF=Large CSV test\n" + PRODUCT * 20000).encode())
        self.open_file()
        target = Path(self.directory.name) / "large.csv"
        heartbeats = []
        timer = QTimer()
        timer.setInterval(1)
        timer.timeout.connect(lambda: heartbeats.append(time.monotonic()))
        timer.start()
        start = time.monotonic()
        self.window.start_export(target)
        self.assertFalse(self.window.export_action.isEnabled())
        self.window.table.set_filter("no matching product")
        self.window.theme_button.click()
        self.wait_for(lambda: self.window._export_worker is None)
        timer.stop()
        with target.open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual(sum(1 for _ in csv.reader(stream)), 20001)
        self.assertGreater(len(heartbeats), 0)
        points = [start] + heartbeats + [time.monotonic()]
        self.assertLess(max(b - a for a, b in zip(points, points[1:])), 1.5)

    def test_details_collapse_reclaims_space_and_enter_reopens_current_item(self):
        self.path.write_bytes((VALID + PRODUCT.replace("CHAIR-01", "SECOND")).encode())
        self.open_file()
        view = self.window.table
        view.splitter.setSizes([800, 350])
        self.app.processEvents()
        before = view.table.width()
        detail_width = view.details.width()
        view.details.hide_button.click()
        self.app.processEvents()
        self.assertFalse(view.details.isVisible())
        self.assertGreater(view.table.width(), before + 200)
        self.assertEqual(self.window.details_action.text(), "Show details")
        column = view.model.columns.index("PN")
        view.table.setCurrentIndex(view.proxy.index(1, column))
        self.assertFalse(view.details.isVisible())
        self.window.raw_action.trigger()
        self.window.table_action.trigger()
        self.assertFalse(view.details.isVisible())
        QTest.keyClick(view.table, Qt.Key.Key_Return)
        self.app.processEvents()
        self.assertTrue(view.details.isVisible())
        self.assertEqual(view.details.record.item, 2)
        self.assertAlmostEqual(view.details.width(), detail_width, delta=3)
        view.table.setFocus()
        QTest.keyClick(view.table, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        self.assertFalse(view.details.isVisible())
        self.open_file()
        self.assertFalse(view.details.isVisible())

    def test_theme_switch_preserves_source_search_selection_and_warning_lines(self):
        self.path.write_bytes((VALID + PRODUCT.replace("MC=ABC", "MC=")).encode())
        original = self.path.read_bytes()
        self.open_file()
        self.window.search.setText("Chair")
        self.window.find_next()
        cursor = self.window.raw.textCursor()
        selection = (cursor.position(), cursor.anchor())
        lines = {s.cursor.blockNumber() for s in self.window.raw.extraSelections()}
        raw_text = self.window.raw.toPlainText()
        for mode in ("dark", "light", "dark"):
            self.window.theme_button.click()
            self.assertEqual(self.window.theme_mode, mode)
            self.assertEqual(self.window.raw.toPlainText(), raw_text)
            self.assertEqual(self.window.search.text(), "Chair")
            cursor = self.window.raw.textCursor()
            self.assertEqual((cursor.position(), cursor.anchor()), selection)
            self.assertEqual({s.cursor.blockNumber() for s in self.window.raw.extraSelections()}, lines)
            selections = self.window.raw.extraSelections()
            color = selections[0].format.background().color()
            self.assertEqual(color.name(), "#463a23" if mode == "dark" else "#fff3cd")
            self.assertEqual(self.window.raw.palette().color(QPalette.ColorRole.Base).name(),
                             "#1c2533" if mode == "dark" else "#ffffff")
            model = self.window.table.model
            self.assertEqual(model.index(1, model.columns.index("MC")).data(), "")
            self.assertEqual(model.index(1, 0).data(Qt.ItemDataRole.ForegroundRole).name(),
                             "#ffda83" if mode == "dark" else "#714d00")
        self.assertEqual(self.path.read_bytes(), original)

    def test_details_and_theme_preferences_survive_restart(self):
        self.open_file()
        self.window.details_action.trigger()
        self.window.theme_button.click()
        self.settings.sync()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        restored = QSettings(self.settings.fileName(), QSettings.Format.IniFormat)
        self.window = MainWindow(settings=restored)
        self.window.show()
        self.open_file()
        self.assertEqual(self.window.theme_mode, "dark")
        self.assertFalse(self.window.table.details.isVisible())
        self.assertFalse(self.window.details_action.isChecked())
        self.window.details_button.click()
        self.assertTrue(self.window.table.details.isVisible())
        self.assertEqual(self.window.table.details.record.item, 1)


if __name__ == "__main__":
    unittest.main()
