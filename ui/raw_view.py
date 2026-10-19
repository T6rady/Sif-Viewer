"""Read-only text widget with a line gutter and incremental loading."""

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QTextCursor, QTextDocument, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from ui.theme import colors_for


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class RawView(QPlainTextEdit):
    loaded = Signal()
    progress = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setAcceptDrops(False)  # The main window handles file drops.
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setPlaceholderText("Open or drop a .sif file to read its contents.")
        self.gutter = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_gutter_width)
        self.updateRequest.connect(self.update_gutter)
        self.update_gutter_width()
        self._text = ""
        self._position = 0
        self.colors = colors_for("light")
        self._highlighted_lines = ()
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._insert_chunk)

    def gutter_width(self):
        digits = len(str(max(1, self.blockCount())))
        return 22 + self.fontMetrics().horizontalAdvance("9") * digits

    def update_gutter_width(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def update_gutter(self, rect, dy):
        if dy:
            self.gutter.scroll(0, dy)
        else:
            self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        rect = self.contentsRect()
        self.gutter.setGeometry(QRect(rect.left(), rect.top(), self.gutter_width(), rect.height()))

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor(self.colors["gutter"]))
        painter.setPen(QColor(self.colors["muted"]))
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                painter.drawText(0, top, self.gutter.width() - 10, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(block.blockNumber() + 1))
            block = block.next()
            top += height

    def set_wrap(self, enabled):
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if enabled
                             else QPlainTextEdit.LineWrapMode.NoWrap)

    def load_text(self, text):
        self._timer.stop()
        self._highlighted_lines = ()
        self.setExtraSelections([])
        self.clear()
        self._text = text
        self._position = 0
        self._timer.start()

    def _insert_chunk(self):
        # Limit each GUI turn; never truncate the document or split CRLF pairs.
        end = min(self._position + 32_768, len(self._text))
        if end < len(self._text) and self._text[end - 1:end] == "\r":
            end += 1
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(self._text[self._position:end])
        self._position = end
        self.progress.emit(round(100 * end / max(1, len(self._text))))
        if end >= len(self._text):
            self._timer.stop()
            self._text = ""
            self.moveCursor(QTextCursor.MoveOperation.Start)
            self.loaded.emit()

    def highlight_lines(self, lines):
        self._highlighted_lines = tuple(sorted(set(lines)))
        selections = []
        for line in self._highlighted_lines:
            block = self.document().findBlockByNumber(line - 1)
            if block.isValid():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = QTextCursor(block)
                selection.format.setBackground(QColor(self.colors["warning"]))
                selection.format.setForeground(QColor(self.colors["warning_text"]))
                selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
                selections.append(selection)
        self.setExtraSelections(selections)

    def set_theme(self, mode):
        self.colors = colors_for(mode)
        self.highlight_lines(self._highlighted_lines)
        self.gutter.update()

    def find_text(self, query, backward=False, case_sensitive=False):
        """Find literal text, wrapping once. Return (found, wrapped)."""
        if not query:
            return False, False
        flags = QTextDocument.FindFlag(0)
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        original = self.textCursor()
        if self.find(query, flags):
            return True, False
        self.moveCursor(QTextCursor.MoveOperation.End if backward else QTextCursor.MoveOperation.Start)
        if self.find(query, flags):
            return True, True
        self.setTextCursor(original)
        return False, False
