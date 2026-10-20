"""Main window; file I/O and parsing run outside the GUI thread."""

from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton,
                               QSizePolicy, QStackedWidget, QStyle, QToolButton, QVBoxLayout, QWidget)

from core.file_reader import FileReadError, read_file
from core.csv_exporter import ExportCancelled, export_csv
from core.sif_parser import parse_sif
from core.sif_csv import export_reversible_csv, import_reversible_csv
from core.windows_defaults import is_default_sif_app
from ui.raw_view import RawView
from ui.table_view import TableView
from ui.theme import palette_for, stylesheet_for
from ui.plain_text import plain_tooltip
from core.resource_limits import ProcessingCancelled
from core.updates import RELEASES_URL
from ui.update_checker import UpdateChecker
from ui.disco import DiscoOverlay


class LoadWorker(QThread):
    succeeded = Signal(object, object)
    failed = Signal(str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        try:
            document = read_file(self.path, cancelled=self.isInterruptionRequested)
            if self.isInterruptionRequested():
                return
            parsed = parse_sif(document.text, self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.succeeded.emit(document, parsed)
        except ProcessingCancelled:
            pass
        except FileReadError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f"Could not load this file ({type(exc).__name__}: {exc}).")


class ConversionWorker(QThread):
    succeeded = Signal(object, int)
    failed = Signal(str)

    def __init__(self, path, document, source=None, parent=None):
        super().__init__(parent)
        self.path, self.document, self.source = Path(path), document, source
        self.result_path = None

    def run(self):
        try:
            if self.source is None:
                count = export_reversible_csv(self.path, self.document, self.isInterruptionRequested)
            else:
                count = import_reversible_csv(self.source, self.path,
                                              self.document.path if self.document else None,
                                              self.isInterruptionRequested)
            self.result_path = self.path
            self.succeeded.emit(self.path, count)
        except ExportCancelled:
            pass
        except Exception as exc:
            self.failed.emit(str(exc))


class ExportWorker(QThread):
    succeeded = Signal(object, int)
    failed = Signal(str)

    def __init__(self, path, snapshot, source_path, parent=None):
        super().__init__(parent)
        self.path, self.snapshot, self.source_path = path, snapshot, source_path

    def run(self):
        try:
            count = export_csv(self.path, *self.snapshot, self.source_path,
                               cancelled=self.isInterruptionRequested)
            self.succeeded.emit(self.path, count)
        except ExportCancelled:
            pass
        except Exception as exc:
            self.failed.emit(str(exc))


def format_size(size):
    if size < 1024:
        return f"{size:,} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB ({size:,} bytes)"
    return f"{size / (1024 * 1024):.1f} MiB ({size:,} bytes)"


class MainWindow(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings if settings is not None else QSettings("ORI", "SIF Viewer")
        self.setWindowTitle("SIF Viewer")
        self.resize(1280, 820)
        self.setMinimumSize(1000, 600)
        self.setAcceptDrops(True)
        self.current_file = None
        self.parse_result = None
        self._worker = None
        self._export_worker = None
        self._busy = False
        self._closing = False
        self._manual_update_check = False
        self.update_checker = UpdateChecker(QApplication.applicationVersion(), self)
        self.update_checker.completed.connect(self._update_checked)
        self._build_ui()
        self.disco = DiscoOverlay(self)
        self._disco_clicks = 0
        self._disco_click_timer = QTimer(self)
        self._disco_click_timer.setSingleShot(True)
        self._disco_click_timer.setInterval(1800)
        self._disco_click_timer.timeout.connect(self._reset_disco_clicks)
        self._disco_escape = QShortcut(QKeySequence("Escape"), self)
        self._disco_escape.activated.connect(self.disco.stop)
        self.table.set_details_visible(self.settings.value("view/detailsVisible", True, type=bool))
        self.dark_action.setChecked(self.settings.value("view/theme", "light") == "dark")
        self._apply_theme()
        self._refresh_default_app_button()

    def check_for_updates(self, manual=False):
        self._manual_update_check = self._manual_update_check or manual
        self.update_button.setEnabled(False)
        self.update_checker.check()

    def _update_checked(self, version, error):
        self.update_button.setEnabled(True)
        manual, self._manual_update_check = self._manual_update_check, False
        if self._closing:
            return
        if version:
            dialog = QMessageBox(self)
            dialog.setWindowTitle("Update available")
            dialog.setTextFormat(Qt.TextFormat.PlainText)
            dialog.setText(f"SIF Viewer {version} is available.\nInstalled version: {self.update_checker.installed}")
            download = dialog.addButton("Open download page", QMessageBox.ButtonRole.AcceptRole)
            dialog.addButton("Later", QMessageBox.ButtonRole.RejectRole)
            dialog.exec()
            if dialog.clickedButton() == download:
                QDesktopServices.openUrl(QUrl(RELEASES_URL))
        elif manual:
            QMessageBox.information(self, "Check for updates", error or
                                    f"SIF Viewer {self.update_checker.installed} is up to date.")

    def _refresh_default_app_button(self):
        self.default_app_button.setVisible(not is_default_sif_app())

    def changeEvent(self, event):
        super().changeEvent(event)
        if (event.type() == QEvent.Type.ActivationChange and self.isActiveWindow()
                and hasattr(self, "default_app_button")):
            self._refresh_default_app_button()

    def _build_ui(self):
        self.open_action = QAction("Open file…", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.choose_file)
        self.addAction(self.open_action)
        self.export_action = QAction("Export CSV…", self)
        self.export_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.export_action.setToolTip("Export filtered rows and visible columns, with original item numbers")
        self.export_action.triggered.connect(self.choose_export)
        self.addAction(self.export_action)
        self.reversible_action = QAction("Export reversible CSV…", self)
        self.reversible_action.setToolTip("Preserve the entire SIF, including original field order, blanks and uninterpreted fields")
        self.reversible_action.triggered.connect(self.choose_reversible_export)
        self.convert_sif_action = QAction("Convert CSV to SIF…", self)
        self.convert_sif_action.triggered.connect(self.choose_sif_conversion)
        self.addAction(self.reversible_action)
        self.addAction(self.convert_sif_action)
        self.details_action = QAction("Hide details", self, checkable=True, checked=True)
        self.details_action.setShortcut(QKeySequence("Ctrl+D"))
        self.addAction(self.details_action)
        self.dark_action = QAction("Dark mode", self, checkable=True)
        self.dark_action.setToolTip("Switch between light and dark mode")
        self.dark_action.toggled.connect(self._apply_theme)
        group = QActionGroup(self)
        self.raw_action = QAction("Raw text", self, checkable=True)
        self.table_action = QAction("Table", self, checkable=True, checked=True)
        for action in (self.raw_action, self.table_action):
            group.addAction(action)
            self.addAction(action)
        self.raw_action.triggered.connect(lambda: self.set_view(0))
        self.table_action.triggered.connect(lambda: self.set_view(1))
        self.wrap_action = QAction("Word wrap", self, checkable=True)
        self.find_action = QAction("Find", self)
        self.find_action.setShortcut(QKeySequence.StandardKey.Find)
        self.find_action.triggered.connect(self.focus_search)
        self.addAction(self.find_action)
        self.next_shortcut = QShortcut(QKeySequence("F3"), self)
        self.next_shortcut.activated.connect(self.find_next)
        self.previous_shortcut = QShortcut(QKeySequence("Shift+F3"), self)
        self.previous_shortcut.activated.connect(lambda: self.find_next(True))
        central = QWidget()
        central.setObjectName("workspace")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("fileHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 14, 22, 14)
        header_layout.setSpacing(12)
        badge = QLabel("SIF")
        self.file_badge = badge
        badge.installEventFilter(self)
        badge.setObjectName("fileBadge")
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QApplication.windowIcon().pixmap(34, 34)
        if not pixmap.isNull():
            badge.setPixmap(pixmap)
        header_layout.addWidget(badge)
        file_info = QVBoxLayout()
        file_info.setSpacing(3)
        title_row = QHBoxLayout()
        title_row.setSpacing(9)
        self.file_name = QLabel("SIF Viewer")
        self.file_name.setObjectName("fileName")
        self.file_name.setTextFormat(Qt.TextFormat.PlainText)
        self.file_name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_row.addWidget(self.file_name)
        read_only = QLabel("Read-only")
        read_only.setObjectName("readOnly")
        title_row.addWidget(read_only)
        title_row.addStretch(1)
        file_info.addLayout(title_row)
        path_row = QHBoxLayout()
        path_row.setSpacing(3)
        self.file_path = QLabel("Open or drop a .sif file to get started")
        self.file_path.setObjectName("filePath")
        self.file_path.setTextFormat(Qt.TextFormat.PlainText)
        self.file_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_path.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        path_row.addWidget(self.file_path, 1)
        self.copy_path = QPushButton("Copy path")
        self.copy_path.setObjectName("iconButton")
        self.copy_path.setToolTip("Copy the full file path")
        self.copy_path.clicked.connect(lambda: QApplication.clipboard().setText(str(self.current_file.path)) if self.current_file else None)
        path_row.addWidget(self.copy_path)
        self.folder_button = QPushButton()
        self.folder_button.setObjectName("iconButton")
        self.folder_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.folder_button.setToolTip("Open containing folder")
        self.folder_button.setAccessibleName("Open containing folder")
        self.folder_button.clicked.connect(self.open_folder)
        path_row.addWidget(self.folder_button)
        self.default_app_button = QPushButton("Set default .sif app…")
        self.default_app_button.setObjectName("iconButton")
        self.default_app_button.setToolTip("Choose SIF Viewer for .sif files in Windows Default apps")
        self.default_app_button.clicked.connect(self.choose_default_app)
        path_row.addWidget(self.default_app_button)
        file_info.addLayout(path_row)
        header_layout.addLayout(file_info, 1)
        self.update_button = QPushButton("Check for updates…")
        self.update_button.clicked.connect(lambda: self.check_for_updates(manual=True))
        header_layout.addWidget(self.update_button)
        self.theme_button = QToolButton()
        self.theme_button.setDefaultAction(self.dark_action)
        self.theme_button.setAccessibleName("Dark mode")
        header_layout.addWidget(self.theme_button)
        self.export_button = QToolButton()
        self.export_button.setDefaultAction(self.export_action)
        header_layout.addWidget(self.export_button)
        self.conversion_button = QToolButton()
        self.conversion_button.setText("Convert…")
        self.conversion_button.setAccessibleName("SIF and reversible CSV conversion")
        conversion_menu = QMenu(self.conversion_button)
        conversion_menu.addAction(self.reversible_action)
        conversion_menu.addAction(self.convert_sif_action)
        self.conversion_button.setMenu(conversion_menu)
        self.conversion_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        header_layout.addWidget(self.conversion_button)
        open_button = QPushButton("Open file…")
        open_button.setObjectName("primaryButton")
        open_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        open_button.clicked.connect(self.open_action.trigger)
        self.open_action.changed.connect(lambda: open_button.setEnabled(self.open_action.isEnabled()))
        header_layout.addWidget(open_button)
        layout.addWidget(header)
        view_bar = QFrame()
        view_bar.setObjectName("viewBar")
        bar = QHBoxLayout(view_bar)
        bar.setContentsMargins(22, 10, 22, 10)
        bar.setSpacing(12)
        switch = QFrame()
        switch.setObjectName("viewSwitch")
        switch_layout = QHBoxLayout(switch)
        switch_layout.setContentsMargins(2, 2, 2, 2)
        switch_layout.setSpacing(0)
        for action in (self.table_action, self.raw_action):
            button = QToolButton()
            button.setObjectName("viewTab")
            button.setDefaultAction(action)
            switch_layout.addWidget(button)
        bar.addWidget(switch)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(180)
        self.search.setMaximumWidth(480)
        self.search.setAccessibleName("Filter products or search raw text")
        self.search.textChanged.connect(self._query_changed)
        self.search.returnPressed.connect(self._search_enter)
        bar.addWidget(self.search, 1)
        self.match_case = QCheckBox("Aa")
        self.match_case.setObjectName("caseToggle")
        self.match_case.setToolTip("Match case")
        self.match_case.setAccessibleName("Match case")
        self.match_case.toggled.connect(self._query_changed)
        bar.addWidget(self.match_case)
        self.previous = QPushButton("Previous")
        self.next = QPushButton("Next")
        self.previous.clicked.connect(lambda: self.find_next(True))
        self.next.clicked.connect(lambda: self.find_next(False))
        bar.addWidget(self.previous)
        bar.addWidget(self.next)
        self.wrap_button = QToolButton()
        self.wrap_button.setDefaultAction(self.wrap_action)
        bar.addWidget(self.wrap_button)
        bar.addStretch(1)
        layout.addWidget(view_bar)
        self.notice = QLabel()
        self.notice.setObjectName("notice")
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        self.notice.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.notice.hide()
        layout.addWidget(self.notice)
        self.stack = QStackedWidget()
        self.raw = RawView()
        self.raw.loaded.connect(self._raw_ready)
        self.raw.progress.connect(lambda value: self.statusBar().showMessage(f"Displaying text… {value}%"))
        self.wrap_action.toggled.connect(self.raw.set_wrap)
        raw_container = QWidget()
        raw_layout = QVBoxLayout(raw_container)
        raw_layout.setContentsMargins(22, 12, 22, 14)
        raw_layout.addWidget(self.raw)
        self.table = TableView()
        self.table.show_raw.connect(self.show_raw_line)
        self.table.clear_filter.connect(self.search.clear)
        bar.addWidget(self.table.columns_button)
        self.details_button = QToolButton()
        self.details_button.setDefaultAction(self.details_action)
        bar.addWidget(self.details_button)
        self.details_action.toggled.connect(self.table.set_details_visible)
        self.table.details_visibility_changed.connect(self._details_visibility_changed)
        self.stack.addWidget(raw_container)
        self.stack.addWidget(self.table)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.metadata = QLabel("No file open")
        self.metadata.setTextFormat(Qt.TextFormat.PlainText)
        self.statusBar().addWidget(self.metadata, 1)
        self.help_text = QLabel("Ctrl+F filter  ·  ↑ ↓ move between items  ·  Enter for details")
        self.statusBar().addPermanentWidget(self.help_text)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(150)
        self._filter_timer.timeout.connect(self._apply_filter)
        self.set_view(1)
        self._enable_search(False)

    def _apply_theme(self, *_):
        self.theme_mode = "dark" if self.dark_action.isChecked() else "light"
        palette = palette_for(self.theme_mode)
        QApplication.instance().setPalette(palette)
        self.setPalette(palette)
        self.setStyleSheet(stylesheet_for(self.theme_mode))
        self.raw.set_theme(self.theme_mode)
        self.table.set_theme(self.theme_mode)
        self.theme_button.setText("Light mode" if self.theme_mode == "dark" else "Dark mode")
        self.theme_button.setAccessibleName(self.theme_button.text())
        self.settings.setValue("view/theme", self.theme_mode)

    def _details_visibility_changed(self, visible):
        self.details_action.setChecked(visible)
        self.details_action.setText("Hide details" if visible else "Show details")
        self.details_action.setToolTip("Hide or show item details (Ctrl+D)")
        self.settings.setValue("view/detailsVisible", visible)

    def _enable_search(self, enabled):
        for widget in (self.search, self.next, self.previous, self.match_case):
            widget.setEnabled(enabled)
        self.find_action.setEnabled(enabled)
        self.wrap_action.setEnabled(enabled and self.stack.currentIndex() == 0)
        self.copy_path.setEnabled(enabled)
        self.folder_button.setEnabled(enabled)
        self._update_export_action()

    def _update_export_action(self):
        self.export_action.setEnabled(bool(self.current_file and self.parse_result and self.parse_result.available
                                          and self.stack.currentIndex() == 1 and not self._busy
                                          and self._export_worker is None and not self._closing))
        ready = not self._busy and self._export_worker is None and not self._closing
        self.reversible_action.setEnabled(bool(ready and self.current_file))
        self.convert_sif_action.setEnabled(ready)
        self.conversion_button.setEnabled(ready)
        self.open_action.setEnabled(not self._busy and not self._closing
                                    and not isinstance(self._export_worker, ConversionWorker))

    def set_view(self, index):
        self.stack.setCurrentIndex(index)
        (self.raw_action if index == 0 else self.table_action).setChecked(True)
        is_raw = index == 0
        self.previous.setVisible(is_raw)
        self.next.setVisible(is_raw)
        self.wrap_button.setVisible(is_raw)
        self.table.columns_button.setVisible(not is_raw)
        self.details_button.setVisible(not is_raw)
        self.details_action.setEnabled(not is_raw and self.table.model.result.available)
        self._update_export_action()
        self.search.setPlaceholderText("Search original text…" if is_raw else "Filter by product, description or option…")
        self.wrap_action.setEnabled(is_raw and self.current_file is not None and not self._busy)
        self.help_text.setText("Ctrl+F search  ·  F3 next  ·  Shift+F3 previous" if is_raw else "Ctrl+F filter  ·  ↑ ↓ move between items  ·  Enter for details")
        if is_raw:
            self._filter_timer.stop()
        elif self.current_file is not None and not self._busy:
            self._apply_filter()

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _query_changed(self, *_):
        if not self._busy and self.current_file and self.stack.currentIndex() == 1:
            self._filter_timer.start()

    def _apply_filter(self):
        self._filter_timer.stop()
        if self.current_file and self.stack.currentIndex() == 1:
            self.table.set_filter(self.search.text(), self.match_case.isChecked())

    def _search_enter(self):
        if self.stack.currentIndex() == 1:
            self._apply_filter()
            self.table.table.setFocus()
        else:
            self.find_next()

    def find_next(self, backward=False):
        if self._busy or self.current_file is None:
            return
        self.set_view(0)
        query = self.search.text()
        if not query:
            self.search.setFocus()
            self.statusBar().showMessage("Enter text to search.", 5000)
            return
        found, wrapped = self.raw.find_text(query, backward, self.match_case.isChecked())
        self.statusBar().showMessage(
            ("Match found · wrapped to " + ("end" if backward else "start")) if found and wrapped
            else "Match found" if found else "No matches", 6000)

    def show_raw_line(self, line):
        self.set_view(0)
        block = self.raw.document().findBlockByNumber(line - 1)
        if block.isValid():
            self.raw.setTextCursor(QTextCursor(block))
            self.raw.centerCursor()
            self.raw.setFocus()

    def open_folder(self):
        if self.current_file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_file.path.parent)))

    def choose_default_app(self):
        QMessageBox.information(
            self, "Open .sif Files with SIF Viewer",
            "In Windows Default apps, search for .sif and select SIF Viewer. "
            "On Windows 10, choose 'Choose default apps by file type' first.\n\n"
            "If SIF Viewer is not listed, install it using the latest SIF Viewer Setup, "
            "then try again. Windows will ask you to confirm your choice.")
        if not QDesktopServices.openUrl(QUrl("ms-settings:defaultapps")):
            QMessageBox.warning(self, "Cannot Open Windows Settings",
                                "Open Windows Settings → Apps → Default apps, then choose "
                                "SIF Viewer for .sif files.")

    def choose_file(self):
        start = str(self.current_file.path.parent) if self.current_file else ""
        path, _ = QFileDialog.getOpenFileName(self, "Open SIF File", start,
                                             "SIF files (*.sif *.SIF);;All files (*)")
        if path:
            self.open_path(path)

    def choose_export(self):
        if not self.export_action.isEnabled():
            return
        # Flush the debounce timer so a just-typed filter is included.
        self._apply_filter()
        if self.table.proxy.rowCount() == 0:
            self.statusBar().showMessage("No products match the filter. Clear or change it before exporting.", 8000)
            return
        if all(self.table.table.isColumnHidden(i) for i in range(self.table.model.columnCount())):
            self.statusBar().showMessage("Show at least one column before exporting.", 8000)
            return
        initial = self.current_file.path.with_suffix(".csv")
        path, _ = QFileDialog.getSaveFileName(self, "Export Table as CSV", str(initial), "CSV files (*.csv)")
        if path:
            target = Path(path)
            if not target.suffix:
                target = target.with_suffix(".csv")
                if target.exists() and QMessageBox.question(
                        self, "Replace CSV?", plain_tooltip(f"{target.name} already exists. Replace it?"),
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                    return
            self.start_export(target)

    def _conversion_destination(self, title, initial, suffix):
        path, _ = QFileDialog.getSaveFileName(self, title, str(initial),
                                             f"{suffix[1:].upper()} files (*{suffix})")
        if not path:
            return None
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(suffix)
            if target.exists() and QMessageBox.question(
                    self, "Replace destination?", plain_tooltip(f"{target.name} already exists. Replace it?"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return None
        return target

    def choose_reversible_export(self):
        if not self.reversible_action.isEnabled():
            return
        target = self._conversion_destination("Export Reversible SIF CSV",
                                               str(self.current_file.path) + ".csv", ".csv")
        if target:
            self.start_conversion(target)

    def choose_sif_conversion(self):
        if not self.convert_sif_action.isEnabled():
            return
        source, _ = QFileDialog.getOpenFileName(self, "Choose Reversible SIF CSV", "", "CSV files (*.csv)")
        if not source:
            return
        # Never suggest the original .sif as the output destination.
        stem = Path(source).stem
        if stem.lower().endswith(".sif"):
            stem = stem[:-4]
        initial = Path(source).with_name(stem + "-converted.sif")
        target = self._conversion_destination("Save Converted SIF", initial, ".sif")
        if target:
            self.start_conversion(target, Path(source))

    def start_conversion(self, path, source=None):
        action = self.convert_sif_action if source is not None else self.reversible_action
        if not action.isEnabled():
            return
        worker = ConversionWorker(path, self.current_file, source, self)
        self._export_worker = worker
        self._update_export_action()
        self.statusBar().showMessage("Converting the complete document…")
        worker.succeeded.connect(lambda target, count: self.statusBar().showMessage(
            f"Saved {count:,} SIF lines to {target}", 12000) if not self._closing else None)
        worker.failed.connect(self._conversion_failed)
        worker.finished.connect(lambda: self._export_finished(worker))
        worker.start()

    def _conversion_failed(self, message):
        if not self._closing:
            self.statusBar().showMessage("Conversion failed", 8000)
            QMessageBox.warning(self, "Cannot Convert File", plain_tooltip(message))

    def start_export(self, path):
        if not self.export_action.isEnabled():
            return
        snapshot = self.table.export_snapshot()
        worker = ExportWorker(Path(path), snapshot, self.current_file.path, self)
        self._export_worker = worker
        self._update_export_action()
        self.statusBar().showMessage(f"Exporting {len(snapshot[2]):,} products to CSV…")
        worker.succeeded.connect(self._export_succeeded)
        worker.failed.connect(self._export_failed)
        worker.finished.connect(lambda: self._export_finished(worker))
        worker.start()

    def _export_succeeded(self, path, count):
        if not self._closing:
            self.statusBar().showMessage(f"Exported {count:,} products to {path}", 12000)

    def _export_failed(self, message):
        if not self._closing:
            self.statusBar().showMessage("CSV export failed", 8000)
            QMessageBox.warning(self, "Cannot Export CSV", plain_tooltip(message))

    def _export_finished(self, worker):
        converted = (worker.result_path if isinstance(worker, ConversionWorker)
                     and worker.source is not None else None)
        if self._export_worker is worker:
            self._export_worker = None
        worker.deleteLater()
        self._update_export_action()
        if self._closing:
            QTimer.singleShot(0, self.close)
        elif converted is not None:
            self.open_path(converted)

    def open_path(self, path):
        if self._busy or isinstance(self._export_worker, ConversionWorker):
            self.statusBar().showMessage("Please wait for the current file to finish loading.")
            return
        self._filter_timer.stop()
        self._busy = True
        self.open_action.setEnabled(False)
        self.raw_action.setEnabled(False)
        self.table_action.setEnabled(False)
        self._enable_search(False)
        self.statusBar().showMessage(f"Reading {Path(path).name}…")
        worker = LoadWorker(path, self)
        self._worker = worker
        worker.succeeded.connect(self._file_ready)
        worker.failed.connect(self._load_failed)
        worker.finished.connect(lambda: self._worker_finished(worker))
        worker.start()

    def _file_ready(self, document, parsed):
        if self._closing:
            return
        self.current_file = document
        self.parse_result = parsed
        self.file_name.setText(document.path.name)
        self.file_path.setText(str(document.path))
        self.file_path.setToolTip(plain_tooltip(str(document.path)))
        self.setWindowTitle(f"{document.path.name} — SIF Viewer")
        records = f"{len(parsed.records):,} products" if parsed.available else "table unavailable"
        self.metadata.setText(f"{document.path.name}  |  {format_size(document.size)}  |  "
                              f"{document.line_count:,} lines  |  {records}  |  {document.encoding}")
        self.metadata.setToolTip(plain_tooltip(f"{document.path}\nLine endings: {document.newline_style}"))
        note = "Read-only · Original files are never changed."
        if document.encoding_note:
            note += " " + document.encoding_note
        if not parsed.available:
            note += " " + parsed.reason
        elif parsed.unknown_codes:
            note += " Table View retains uninterpreted fields: " + ", ".join(parsed.unknown_codes) + "."
        if parsed.warnings:
            note += " Table View is available with warnings. "
            note += " ".join(warning.text for warning in parsed.warnings[:3])
            if len(parsed.warnings) > 3:
                note += " More warnings are shown in the table."
        self.notice.setText(note)
        self.notice.setVisible(not parsed.available or bool(document.encoding_note))
        self.table.set_result(parsed)
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.set_view(1 if parsed.available else 0)
        self.raw.load_text(document.text)

    def _raw_ready(self):
        lines = {warning.line for warning in self.parse_result.warnings}
        lines.update(record.line for record in self.parse_result.records if record.warnings)
        self.raw.highlight_lines(lines)
        self._set_idle()
        self.statusBar().clearMessage()

    def _set_idle(self):
        self._busy = False
        self.open_action.setEnabled(True)
        self.raw_action.setEnabled(True)
        self.table_action.setEnabled(True)
        self._enable_search(self.current_file is not None)

    def _load_failed(self, message):
        self._set_idle()
        self.statusBar().showMessage("File could not be opened", 8000)
        if not self._closing:
            QMessageBox.warning(self, "Cannot Open File", plain_tooltip(message))

    def _worker_finished(self, worker):
        if self._worker is worker:
            self._worker = None
        worker.deleteLater()
        if self._closing:
            QTimer.singleShot(0, self.close)

    @staticmethod
    def _drop_path(mime):
        urls = mime.urls() if mime.hasUrls() else []
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if path.suffix.lower() == ".sif" and path.is_file():
                return path
        return None

    def dragEnterEvent(self, event):
        if not self._busy and self._drop_path(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()
            self.statusBar().showMessage("Drop one local .sif file to open it.", 5000)

    def dropEvent(self, event):
        path = self._drop_path(event.mimeData())
        if path and not self._busy:
            event.acceptProposedAction()
            self.open_path(path)
        else:
            event.ignore()

    def _reset_disco_clicks(self):
        self._disco_clicks = 0

    def eventFilter(self, watched, event):
        if (watched is getattr(self, "file_badge", None)
                and event.type() == QEvent.Type.MouseButtonRelease
                and event.button() == Qt.MouseButton.LeftButton):
            self._disco_clicks += 1
            self._disco_click_timer.start()
            if self._disco_clicks == 5:
                self._reset_disco_clicks()
                self._disco_click_timer.stop()
                self.disco.start()
        return super().eventFilter(watched, event)

    def closeEvent(self, event):
        self._closing = True
        self.update_checker.cancel()
        running = [worker for worker in (self._worker, self._export_worker)
                   if worker is not None and worker.isRunning()]
        if running:
            self._closing = True
            for worker in running:
                worker.requestInterruption()
            self.hide()
            event.ignore()  # Let the worker finish safely before Qt is destroyed.
        else:
            self.raw._timer.stop()
            event.accept()
