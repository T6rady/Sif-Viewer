"""Read-only record details; option/attribute values are never truncated in the model."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QFrame, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QScrollArea, QTableView, QVBoxLayout, QWidget)

from core.sif_parser import extended_list_price, numeric_value
from core.resource_limits import MAX_CALCULATED_CHARACTERS


def money(value, currency=""):
    number = numeric_value(str(value), MAX_CALCULATED_CHARACTERS) if value is not None else None
    return ((currency + " ") if currency else "") + format(number, ",.2f") if number is not None else "—"


def quantity_text(value):
    number = numeric_value(str(value), MAX_CALCULATED_CHARACTERS) if value is not None else None
    return format(number, ",f").rstrip("0").rstrip(".") if number is not None and number.as_tuple().exponent < 0 else format(number, ",f") if number is not None else "—"


def label(text="", name="", wrap=False):
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


class PairModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pairs = ()

    def set_pairs(self, pairs):
        self.beginResetModel()
        self.pairs = pairs
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.pairs)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 2

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return self.pairs[index.row()][index.column()]
        return None


class DetailsPanel(QScrollArea):
    show_raw = Signal(int)
    hide_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("detailsPanel")
        self.setWidgetResizable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(260)
        self.setMaximumWidth(470)
        self.record = None
        self.body = QWidget()
        self.body.setObjectName("detailsBody")
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        self.position = label("Select an item", "muted")
        self.product = label("Item details", "detailTitle", True)
        self.description = label("Select a table row to inspect its full description and options.", wrap=True)
        position_row = QHBoxLayout()
        position_row.addWidget(self.position, 1)
        self.hide_button = QPushButton("Hide")
        self.hide_button.setObjectName("linkButton")
        self.hide_button.setAccessibleName("Hide item details")
        self.hide_button.setToolTip("Hide details and give the table more room (Ctrl+D)")
        self.hide_button.clicked.connect(self.hide_requested)
        position_row.addWidget(self.hide_button)
        layout.addLayout(position_row)
        layout.addWidget(self.product)
        layout.addWidget(self.description)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)
        grid = QGridLayout()
        self.values = {}
        for i, (key, caption) in enumerate((("MC", "Manufacturer"), ("QT", "Quantity"),
                                           ("PL", "List (each)"), ("extended", "Extended list"))):
            row, col = divmod(i, 2)
            grid.addWidget(label(caption, "muted"), row * 2, col)
            value = label("—", "detailValue", True)
            grid.addWidget(value, row * 2 + 1, col)
            self.values[key] = value
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(7)
        layout.addLayout(grid)
        self.warnings = label("", "warning", True)
        layout.addWidget(self.warnings)
        self.sections = {}
        for key, title in (("options", "Options"), ("attributes", "Attributes"), ("unknown", "Uninterpreted fields")):
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(9)
            heading = QHBoxLayout()
            caption = label(title, "sectionTitle")
            heading.addWidget(caption, 1)
            copy = QPushButton("Copy all")
            copy.setObjectName("linkButton")
            copy.clicked.connect(lambda _, name=key: self.copy_pairs(name))
            heading.addWidget(copy)
            section_layout.addLayout(heading)
            table = QTableView()
            model = PairModel(table)
            table.setModel(model)
            table.setWordWrap(True)
            table.setShowGrid(False)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
            table.verticalHeader().hide()
            table.horizontalHeader().hide()
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.verticalHeader().setDefaultSectionSize(46)
            table.setMinimumHeight(40)
            section_layout.addWidget(table)
            layout.addWidget(section)
            self.sections[key] = (section, caption, table, model)
        self.raw_button = QPushButton("View raw text")
        self.raw_button.clicked.connect(lambda: self.show_raw.emit(self.record.line) if self.record else None)
        layout.addWidget(self.raw_button)
        layout.addStretch(1)
        self.setWidget(self.body)
        self.set_record(None, 0)

    def set_record(self, record, count, currency=""):
        self.record = record
        self.position.setText(f"Item {record.item} of {count}" if record else "No item selected")
        self.product.setText(record.fields.get("PN", "") if record else "Item details")
        self.description.setText(record.fields.get("PD", "") if record else "Select a row to see its details.")
        self.values["MC"].setText(record.fields.get("MC", "") if record else "—")
        self.values["QT"].setText(quantity_text(record.fields.get("QT", "")) if record else "—")
        self.values["PL"].setText(money(record.fields.get("PL", ""), currency) if record else "—")
        self.values["extended"].setText(money(extended_list_price(record), currency) if record else "—")
        warning = "\n".join(w.text for w in record.warnings) if record else ""
        self.warnings.setText(warning)
        self.warnings.setVisible(bool(warning))
        for key, (section, caption, table, model) in self.sections.items():
            pairs = getattr(record, key) if record else ()
            model.set_pairs(pairs)
            caption.setText(f"{key.capitalize() if key != 'unknown' else 'Uninterpreted fields'} ({len(pairs)})")
            section.setVisible(bool(pairs))
            table.setFixedHeight(min(240, len(pairs) * 46 + 4))
        self.raw_button.setEnabled(record is not None)

    def copy_pairs(self, key):
        if self.record:
            pairs = getattr(self.record, key)
            QApplication.clipboard().setText("\n".join(f"{code}\t{description}" for code, description in pairs))
