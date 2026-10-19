"""Virtual table model: source strings stay intact, numbers sort as decimals."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFrame, QHeaderView,
                               QHBoxLayout, QLabel, QMenu, QSplitter, QStyledItemDelegate,
                               QStyle, QStyleOptionViewItem, QTableView, QToolButton, QVBoxLayout, QWidget)

from core.sif_parser import FIELD_DEFINITIONS, ParseResult, extended_list_price, numeric_value
from core.table_summary import summarize
from core.table_data import record_value
from ui.details_panel import DetailsPanel, money, quantity_text
from ui.theme import colors_for


BASE_CODES = ("MC", "PN", "PD", "options_count", "QT", "PL", "extended_list", "S-", "P%",
              "GC", "TG", "option_codes", "option_descriptions", "attribute_codes",
              "attribute_descriptions", "S%", "B%", "PV")
LABELS = {
    "options_count": "Option count",
    "warnings": "Missing / blank fields",
    "option_codes": "Option codes (ON)",
    "option_descriptions": "Option descriptions (OD)",
    "attribute_codes": "Attribute codes / notes (AN)",
    "attribute_descriptions": "Attribute descriptions (AD)",
    "extended_list": "Extended list price (calculated)",
    "options": "Options combined (ON / OD)",
    "attributes": "Attributes combined (AN / AD)",
    "unknown": "Uninterpreted fields combined",
}
COMPACT_LABELS = {"MC": "Mfr", "PN": "Product #", "PD": "Description", "options_count": "Options",
                  "QT": "Qty", "PL": "List", "extended_list": "Ext. list", "S-": "Sell\ndisc.", "P%": "Buy"}


def column_label(code):
    if code.startswith("raw:"):
        return f"{code[4:]} (uninterpreted)"
    return LABELS[code] if code in LABELS else f"{FIELD_DEFINITIONS[code].label} ({code})"


def numeric_column(code):
    return code in ("extended_list", "options_count") or (code in FIELD_DEFINITIONS and FIELD_DEFINITIONS[code].numeric)


class SifTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.result = ParseResult()
        self.columns = list(BASE_CODES) + ["options", "attributes", "unknown"]
        self.default_visible = set()
        self.search_strings = []
        self.active_item = None
        self.colors = colors_for("light")

    def set_result(self, result):
        self.beginResetModel()
        self.result = result
        optional = [code for code in FIELD_DEFINITIONS if code not in BASE_CODES]
        raw = [f"raw:{code}" for code in result.unknown_codes]
        self.columns = (["warnings"] if result.warnings else []) + list(BASE_CODES) + optional + raw + ["options", "attributes", "unknown"]
        self.default_visible = set(COMPACT_LABELS)
        self.search_strings = ["\n".join(list(row.fields.values()) + list(row.tags)
                               + [value for pairs in (row.options, row.attributes, row.unknown)
                                  for pair in pairs for value in pair]) for row in result.records]
        self.active_item = None
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.result.records)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.result.records[index.row()]
        code = self.columns[index.column()]
        if role == Qt.ItemDataRole.BackgroundRole and row.item == self.active_item:
            return QColor(self.colors["active"])
        if role == Qt.ItemDataRole.BackgroundRole and row.warnings:
            return QColor(self.colors["warning"])
        if role == Qt.ItemDataRole.ForegroundRole and row.warnings:
            return QColor(self.colors["warning_text"])
        if role == Qt.ItemDataRole.ForegroundRole and code in ("PN", "options_count"):
            return QColor(self.colors["link"])
        if role == Qt.ItemDataRole.TextAlignmentRole:
            numeric = numeric_column(code)
            return int((Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft)
                       | Qt.AlignmentFlag.AlignVCenter)
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return None
        value = record_value(row, code)
        if role == Qt.ItemDataRole.ToolTipRole:
            details = "\n".join(f"Raw text line {warning.line}: {warning.message}" for warning in row.warnings)
            if code == "extended_list":
                details += "\nCalculated: quantity (QT) × list price (PL), without rounding. Blank if either value is missing."
            elif code.startswith("raw:"):
                details += "\nSource values in occurrence order. This field's meaning is not interpreted."
            elif code in ("option_codes", "option_descriptions", "attribute_codes", "attribute_descriptions"):
                details += "\nRepeated values are separated by | in source order; paired codes/descriptions use the same order."
            return (f"Item {row.item} in original file order\nRaw text starts at line {row.line}\n{value}"
                    + (f"\n{details}" if details else ""))
        return value

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.ToolTipRole and orientation == Qt.Orientation.Horizontal:
            code = self.columns[section]
            if code == "extended_list":
                return "Calculated: QT × PL. Exact decimal multiplication; no assumed currency or rounding."
            if code.startswith("raw:"):
                return f"Literal {code[4:]} source field. No semantic definition is assumed."
            return column_label(code)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Vertical:
            return self.result.records[section].item
        code = self.columns[section]
        return COMPACT_LABELS.get(code, column_label(code))


class NumericSortProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.accepted = None

    def set_query(self, query, case_sensitive=False):
        self.beginFilterChange()
        if query:
            needle = query if case_sensitive else query.casefold()
            self.accepted = {i for i, text in enumerate(self.sourceModel().search_strings)
                             if needle in (text if case_sensitive else text.casefold())}
        else:
            self.accepted = None
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row, parent):
        return self.accepted is None or source_row in self.accepted

    def visible_records(self):
        rows = self.sourceModel().result.records
        return rows if self.accepted is None else tuple(rows[i] for i in sorted(self.accepted))

    def lessThan(self, left, right):
        code = self.sourceModel().columns[left.column()]
        a, b = left.data(), right.data()
        if numeric_column(code):
            number_a, number_b = numeric_value(a), numeric_value(b)
            if number_a is not None and number_b is not None:
                return number_a < number_b
            if (number_a is None) != (number_b is None):
                return number_a is None
        return a.casefold() < b.casefold()


class CopyableTable(QTableView):
    details_requested = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.details_requested.emit()
        elif event.matches(QKeySequence.StandardKey.Copy):
            indexes = [index for index in self.selectionModel().selectedIndexes()
                       if not self.isColumnHidden(index.column())]
            if indexes:
                cells = {(index.row(), index.column()): index.data() for index in indexes}
                rows = sorted({row for row, _ in cells})
                columns = sorted({column for _, column in cells}, key=self.horizontalHeader().visualIndex)
                text = "\n".join("\t".join(cells.get((row, column), "") for column in columns) for row in rows)
                QApplication.clipboard().setText(text)
            event.accept()
        else:
            super().keyPressEvent(event)


class NumberDelegate(QStyledItemDelegate):
    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        code = self.view.model.columns[index.column()]
        value = index.data()
        if code in ("PL", "extended_list") and value:
            option.text = money(value, self.view.currency.currentData())
        elif code == "QT" and value:
            option.text = quantity_text(value)
        elif code in ("S-", "S%", "P%", "B%") and value:
            option.text = quantity_text(value) + "%"
        elif code == "options_count" and value:
            option.text = f"{value} options" if value != "1" else "1 option"

    def paint(self, painter, option, index):
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        source = self.view.proxy.mapToSource(index)
        record = self.view.model.result.records[source.row()] if source.isValid() else None
        active = record is not None and record.item == self.view.model.active_item
        colors = self.view.model.colors
        tint = QColor(colors["active_tint"]) if active else QColor(colors["warning_tint"]) if record and record.warnings else None
        if self.view.model.columns[index.column()] != "options_count":
            self.view.table.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, self.view.table)
            if tint is not None:
                painter.fillRect(option.rect, tint)
            if active and self.view.table.columnViewportPosition(index.column()) == 0:
                painter.fillRect(option.rect.x(), option.rect.y(), 2, option.rect.height(), QColor(colors["accent"]))
            return
        text = styled.text
        styled.text = ""
        self.view.table.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, self.view.table)
        if tint is not None:
            painter.fillRect(option.rect, tint)
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        width = min(option.rect.width() - 8, option.fontMetrics.horizontalAdvance(text) + 14)
        pill = QRectF(option.rect.x() + 5, option.rect.center().y() - 9, width, 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colors["pill"]))
        painter.drawRoundedRect(pill, 8, 8)
        painter.setPen(QColor(colors["pill_text"]))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class TotalsModel(QAbstractTableModel):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.summary = summarize(())
        self.label_column = 0

    def refresh(self, records):
        self.beginResetModel()
        self.summary = summarize(records)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 1

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.view.model.columnCount()

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        return "" if role == Qt.ItemDataRole.DisplayRole else None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        code = self.view.model.columns[index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return (f"Totals for {self.summary.count} visible items. "
                    f"Missing quantities: {self.summary.quantity_missing}; "
                    f"missing extended prices: {self.summary.extended_missing}. "
                    "Only supplied values are summed. Displayed prices use two decimal places; source values are unchanged.")
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int((Qt.AlignmentFlag.AlignRight if code in ("QT", "extended_list") else Qt.AlignmentFlag.AlignLeft)
                       | Qt.AlignmentFlag.AlignVCenter)
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if code == "QT":
            text = quantity_text(self.summary.quantity)
            return text + (" *" if self.summary.quantity_missing else "")
        if code == "extended_list":
            text = money(self.summary.extended, self.view.currency.currentData())
            return text + (" *" if self.summary.extended_missing else "")
        if index.column() == self.label_column:
            return f"Total · {self.summary.count:,} {'item' if self.summary.count == 1 else 'items'}"
        return ""


class TableView(QWidget):
    show_raw = Signal(int)
    clear_filter = Signal()
    details_visibility_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._visibility = {}
        self._column_actions = {}
        self._loading = False
        self.details_visible = True
        self._details_sizes = [900, 285]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 0, 22, 14)
        layout.setSpacing(10)
        info = QHBoxLayout()
        info.setSpacing(12)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setTextFormat(Qt.TextFormat.PlainText)
        self.source = QLabel()
        self.source.setObjectName("muted")
        info.addWidget(self.note)
        info.addWidget(self.source)
        currency_layout = QHBoxLayout()
        currency_layout.setSpacing(6)
        caption = QLabel("Currency")
        caption.setObjectName("muted")
        currency_layout.addWidget(caption)
        self.currency = QComboBox()
        for caption, code in (("Not set", ""), ("USD", "USD"), ("CAD", "CAD"), ("EUR", "EUR"), ("GBP", "GBP")):
            self.currency.addItem(caption, code)
        self.currency.setToolTip("Display preference only. Currency is not supplied by this SIF. No conversion is performed.")
        currency_layout.addWidget(self.currency)
        info.addLayout(currency_layout)
        self.unknown_button = QToolButton()
        self.unknown_button.setMaximumWidth(320)
        self.unknown_button.setObjectName("infoChip")
        self.unknown_button.clicked.connect(self.show_uninterpreted)
        info.addWidget(self.unknown_button)
        self.warning_button = QToolButton()
        self.warning_button.setObjectName("warningChip")
        self.warning_button.clicked.connect(self.select_warning)
        info.addWidget(self.warning_button)
        info.addStretch(1)
        layout.addLayout(info)
        self.columns_button = QToolButton()
        self.columns_button.setText("Columns")
        self.columns_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.columns_menu = QMenu(self.columns_button)
        self.columns_button.setMenu(self.columns_menu)
        self.model = SifTableModel(self)
        self.proxy = NumericSortProxy(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setDynamicSortFilter(False)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(12)
        card = QFrame()
        card.setObjectName("tableCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(1, 1, 1, 1)
        card_layout.setSpacing(0)
        self.table = CopyableTable()
        self.table.setModel(self.proxy)
        self.table.setItemDelegate(NumberDelegate(self))
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
        self.table.setShowGrid(False)
        self.table.setWordWrap(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setMinimumSectionSize(38)
        self.table.horizontalHeader().setFixedHeight(45)
        self.table.verticalHeader().setDefaultSectionSize(51)
        self.table.verticalHeader().setFixedWidth(36)
        self.table.setMinimumHeight(96)
        card_layout.addWidget(self.table, 1)
        self.totals = QTableView()
        self.totals.setObjectName("totals")
        self.totals_model = TotalsModel(self)
        self.totals.setModel(self.totals_model)
        self.totals.setFixedHeight(36)
        self.totals.horizontalHeader().hide()
        self.totals.verticalHeader().setFixedWidth(36)
        self.totals.verticalHeader().setDefaultSectionSize(35)
        self.totals.setShowGrid(False)
        self.totals.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.totals.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.totals.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.totals.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.totals.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        card_layout.addWidget(self.totals)
        card_layout.addStretch(0)
        self.splitter.addWidget(card)
        self.details = DetailsPanel()
        self.details.show_raw.connect(self.show_raw)
        self.details.hide_requested.connect(lambda: self.set_details_visible(False))
        self.splitter.addWidget(self.details)
        self.splitter.setSizes([900, 285])
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 1)
        layout.addWidget(self.splitter, 1)
        self.table.selectionModel().currentChanged.connect(self._selection_changed)
        self.table.details_requested.connect(self.show_details)
        self.table.horizontalHeader().sectionResized.connect(lambda *_: self._sync_footer())
        self.table.horizontalHeader().sectionMoved.connect(lambda *_: self._sync_footer())
        self.table.horizontalScrollBar().valueChanged.connect(self.totals.horizontalScrollBar().setValue)
        self.proxy.layoutChanged.connect(self._refresh_details)
        self.currency.currentIndexChanged.connect(self._currency_changed)
        self.set_result(ParseResult(reason="Open a file to view its products."))

    def set_result(self, result):
        self._loading = True
        self.proxy.set_query("")
        self.table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
        self.model.set_result(result)
        self.currency.setCurrentIndex(0)
        self.table.setVisible(result.available)
        self.totals.setVisible(result.available)
        self.details.setVisible(result.available and self.details_visible)
        self.columns_button.setEnabled(result.available)
        self.currency.setEnabled(result.available)
        self._rebuild_columns_menu()
        widths = {"warnings": 270, "MC": 48, "PN": 96, "PD": 300, "options_count": 80,
                  "QT": 46, "PL": 82, "extended_list": 92, "S-": 55, "P%": 50,
                  "option_codes": 210, "option_descriptions": 320, "attribute_codes": 180,
                  "attribute_descriptions": 250, "options": 360, "unknown": 260}
        for column, code in enumerate(self.model.columns):
            self.table.setColumnWidth(column, widths.get(code, 160))
        headers = dict(result.headers)
        source_text = headers.get("SF", headers.get("ST", ""))
        self.source.setText("Source file  " + self.source.fontMetrics().elidedText(source_text, Qt.TextElideMode.ElideMiddle, 145) if source_text else "")
        self.source.setToolTip("\n".join(f"{key}={value}" for key, value in result.headers))
        warnings = [row for row in result.records if row.warnings]
        self.warning_button.setText(f"{len(warnings)} items need attention")
        self.warning_button.setToolTip("\n".join(w.text for w in result.warnings))
        self.warning_button.setVisible(bool(warnings))
        self.unknown_button.setVisible(bool(result.unknown_codes))
        self._loading = False
        self._refresh_visible()
        if not result.available:
            self.note.setText(result.reason)

    def set_filter(self, text, case_sensitive=False):
        self.proxy.set_query(text, case_sensitive)
        self._refresh_visible()

    def export_snapshot(self):
        header = self.table.horizontalHeader()
        visible = sorted((i for i in range(self.model.columnCount()) if not self.table.isColumnHidden(i)),
                         key=header.visualIndex)
        columns = tuple(self.model.columns[i] for i in visible)
        headings = tuple(column_label(code) for code in columns)
        records = tuple(self.model.result.records[self.proxy.mapToSource(self.proxy.index(row, 0)).row()]
                        for row in range(self.proxy.rowCount()))
        return headings, columns, records

    def set_details_visible(self, visible):
        visible = bool(visible)
        if visible == self.details_visible:
            return
        if not visible:
            sizes = self.splitter.sizes()
            if sizes[1] > 0:
                self._details_sizes = sizes
            if self.details.isAncestorOf(QApplication.focusWidget()) or self.details.hasFocus():
                self.table.setFocus()
        self.details_visible = visible
        self.details.setVisible(visible and self.model.result.available)
        if visible:
            self.splitter.setSizes(self._details_sizes)
        self.details_visibility_changed.emit(visible)

    def show_details(self):
        if self.model.result.available:
            self.set_details_visible(True)
            self.details.setFocus()

    def set_theme(self, mode):
        self.model.colors = colors_for(mode)
        self.table.viewport().update()

    def _refresh_visible(self):
        rows = self.proxy.visible_records()
        total = len(self.model.result.records)
        self.note.setText(f"{len(rows):,} products" if len(rows) == total else f"{len(rows):,} of {total:,} products")
        self.totals_model.refresh(rows)
        self.table.setMaximumHeight(max(96, 47 + len(rows) * 51 + 12))
        self._sync_footer()
        if self.proxy.rowCount() and not self.table.currentIndex().isValid():
            first = next((i for i in range(self.model.columnCount()) if not self.table.isColumnHidden(i)), 0)
            self.table.setCurrentIndex(self.proxy.index(0, first))
        self._refresh_details()

    def _selection_changed(self, current, previous):
        if self._loading:
            return
        self._refresh_details()

    def _refresh_details(self, *_):
        index = self.table.currentIndex()
        row = self.proxy.mapToSource(index).row() if index.isValid() else -1
        record = self.model.result.records[row] if 0 <= row < len(self.model.result.records) else None
        self.model.active_item = record.item if record else None
        self.table.viewport().update()
        self.details.set_record(record, len(self.model.result.records), self.currency.currentData())

    def _currency_changed(self, *_):
        if not self._loading:
            self.table.viewport().update()
            self.totals.viewport().update()
            self._refresh_details()

    def _rebuild_columns_menu(self):
        self.columns_menu.clear()
        self._column_actions = {}
        self.columns_menu.addAction("Show all columns", self.show_all_columns)
        self.columns_menu.addAction("Reset columns", self.reset_columns)
        self.columns_menu.addSeparator()
        for column, code in enumerate(self.model.columns):
            action = self.columns_menu.addAction(column_label(code))
            action.setCheckable(True)
            visible = self._visibility.get(code, code in self.model.default_visible)
            action.setChecked(visible)
            self.table.setColumnHidden(column, not visible)
            action.toggled.connect(lambda checked, key=code: self.set_column_visible(key, checked))
            self._column_actions[code] = action
        self._sync_footer()
        self._update_column_status()

    def set_column_visible(self, code, visible):
        self._visibility[code] = visible
        column = self.model.columns.index(code)
        self.table.setColumnHidden(column, not visible)
        action = self._column_actions[code]
        action.blockSignals(True)
        action.setChecked(visible)
        action.blockSignals(False)
        self._sync_footer()
        self._update_column_status()

    def _update_column_status(self):
        shown = sum(not self.table.isColumnHidden(i) for i in range(self.model.columnCount()))
        self.columns_button.setText(f"Columns  {shown} of {self.model.columnCount()}")
        hidden = [code for code in self.model.result.unknown_codes
                  if self.table.isColumnHidden(self.model.columns.index(f"raw:{code}"))]
        if hidden:
            names = f" ({', '.join(hidden)})" if len(hidden) <= 3 else ""
            self.unknown_button.setText(f"{len(hidden)} uninterpreted fields hidden{names}")
        else:
            self.unknown_button.setText("Uninterpreted fields shown")
        self.unknown_button.setToolTip("Source values with unverified meanings are retained. Click to show their columns.\n"
                                      + ", ".join(self.model.result.unknown_codes))

    def _sync_footer(self):
        if not hasattr(self, "totals") or self._loading:
            return
        header = self.table.horizontalHeader()
        footer = self.totals.horizontalHeader()
        self.totals.clearSpans()
        visible = sorted((i for i in range(self.model.columnCount()) if not self.table.isColumnHidden(i)), key=header.visualIndex)
        self.totals_model.label_column = next((i for i in visible if self.model.columns[i] not in ("QT", "extended_list")), -1)
        prefix = []
        for i in visible:
            if self.model.columns[i] in ("QT", "PL", "extended_list"):
                break
            prefix.append(i)
        if len(prefix) > 1 and prefix == list(range(prefix[0], prefix[-1] + 1)):
            self.totals.setSpan(0, prefix[0], 1, len(prefix))
        for i in range(self.model.columnCount()):
            self.totals.setColumnHidden(i, self.table.isColumnHidden(i))
            self.totals.setColumnWidth(i, self.table.columnWidth(i))
            desired = header.visualIndex(i)
            if footer.visualIndex(i) != desired:
                footer.moveSection(footer.visualIndex(i), desired)
        self.totals.horizontalScrollBar().setValue(self.table.horizontalScrollBar().value())
        self.totals.viewport().update()

    def show_all_columns(self):
        for code in self.model.columns:
            self.set_column_visible(code, True)

    def show_uninterpreted(self):
        for code in self.model.result.unknown_codes:
            self.set_column_visible(f"raw:{code}", True)

    def select_warning(self):
        if self.proxy.accepted is not None:
            self.set_filter("")
            self.clear_filter.emit()
        for row in range(self.proxy.rowCount()):
            source = self.proxy.mapToSource(self.proxy.index(row, 0)).row()
            if self.model.result.records[source].warnings:
                column = self.model.columns.index("PN")
                self.table.setCurrentIndex(self.proxy.index(row, column))
                self.table.scrollTo(self.table.currentIndex())
                return

    def reset_columns(self):
        self._visibility.clear()
        header = self.table.horizontalHeader()
        for column, code in enumerate(self.model.columns):
            header.moveSection(header.visualIndex(column), column)
            self.set_column_visible(code, code in self.model.default_visible)
        self._visibility.clear()
