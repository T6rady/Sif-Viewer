"""A short, self-contained Kentucky celebration overlay."""

import math
from pathlib import Path
import random

from PySide6.QtCore import QElapsedTimer, QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap, QRadialGradient
from PySide6.QtWidgets import QWidget


class DiscoOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.logo = QPixmap(str(Path(__file__).resolve().parent.parent / "assets" / "kentucky-logo.png"))
        self.particles = [(random.random(), random.random(), random.uniform(55, 100),
                           random.uniform(0.035, 0.085), random.uniform(0, math.tau))
                          for _ in range(22)]
        self.elapsed = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        parent.installEventFilter(self)
        self.hide()

    def start(self):
        self.setGeometry(self.parentWidget().rect())
        self.elapsed.start()
        self.show()
        self.raise_()
        self.timer.start()
        self.update()

    def stop(self):
        self.timer.stop()
        self.hide()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def _tick(self):
        if self.elapsed.elapsed() >= 10000:
            self.stop()
        else:
            self.update()

    def paintEvent(self, event):
        t = self.elapsed.elapsed() / 1000
        fade = min(1.0, t / 0.6, max(0.0, (10 - t) / 0.8))
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(fade)
        painter.fillRect(self.rect(), QColor(0, 12, 45, 150))
        for i, color in enumerate(("#0033a0", "#8455ed", "#16bce0")):
            x = self.width() * (0.5 + 0.45 * math.sin(t * 0.65 + i * 2.1))
            y = self.height() * (0.5 + 0.45 * math.cos(t * 0.5 + i * 2.1))
            gradient = QRadialGradient(x, y, max(self.width(), self.height()) * 0.6)
            center = QColor(color)
            center.setAlpha(135)
            gradient.setColorAt(0, center)
            gradient.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(self.rect(), gradient)
        for x, y, size, speed, phase in self.particles:
            px = x * self.width() + 20 * math.sin(t + phase)
            py = ((y + t * speed) % 1.25) * (self.height() + 100) - 100
            painter.save()
            painter.translate(px, py)
            painter.rotate(12 * math.sin(t * 1.3 + phase))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("white"))
            painter.drawRoundedRect(QRectF(-size / 2 - 5, -size * 0.39 - 5,
                                           size + 10, size * 0.78 + 10), 10, 10)
            painter.drawPixmap(QRectF(-size / 2, -size * 0.39, size, size * 0.78),
                               self.logo, QRectF(140, 220, 705, 550))
            painter.restore()
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "GO BIG BLUE!")
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(self.rect().adjusted(0, 0, 0, -22),
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                         "Disco mode · Esc to exit")
