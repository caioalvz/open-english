"""Interface da Emily: orbe organico que respira/reage ao audio + legendas."""
from __future__ import annotations

import math
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import QWidget, QMainWindow, QVBoxLayout, QLabel, QApplication

from app.audio_io import AmplitudeMonitor
from app.theme import (
    BG_DEEP,
    STATE_COLORS,
    STATE_LABELS,
    TEXT_PRIMARY,
    draw_emily_rings,
    render_glow_pixmap,
)


class TutorBridge(QObject):
    """Sinais Qt para atualizar a UI a partir da thread de audio/LLM em background."""

    user_text_changed = pyqtSignal(str)
    reply_text_changed = pyqtSignal(str)
    correction_added = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    error_changed = pyqtSignal(str)


class OrbWidget(QWidget):
    """Anel de barras + nucleo, desenhado quase todo com tracos simples (sem
    preenchimento de area grande), com a paleta e o tom quentes da Emily.
    Roda bem mesmo sem GPU dedicada, ja que o Qt desenha tudo isso via CPU
    (raster software)."""

    def __init__(self, amp_monitor: AmplitudeMonitor, parent=None):
        super().__init__(parent)
        self.amp_monitor = amp_monitor
        self._display_level = 0.0
        self._phase = 0.0

        self._glow_cache: dict[str, object] = {}
        self._cached_size: tuple[int, int] | None = None

        self.setMinimumSize(360, 360)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60fps - o desenho agora e barato o suficiente pra isso

    def _rebuild_cache(self) -> None:
        base_radius = min(self.width(), self.height()) * 0.22
        glow_diameter = int(base_radius * 2.3 * 2)
        self._glow_cache = {name: render_glow_pixmap(color, glow_diameter) for name, color in STATE_COLORS.items()}
        self._cached_size = (self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_cache()

    def _tick(self):
        # ganho de suavizacao e incremento de fase recalibrados pro timer de
        # 60fps (16ms) - mesma velocidade de animacao "real" que antes a 15fps
        target = min(1.0, self.amp_monitor.get_level() * 6.0)
        self._display_level += (target - self._display_level) * 0.10
        self._phase += 0.0145
        self.update()

    def paintEvent(self, event):
        if self._cached_size != (self.width(), self.height()) or not self._glow_cache:
            self._rebuild_cache()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), BG_DEEP)

        state = self.amp_monitor.get_state()
        color = STATE_COLORS.get(state, STATE_COLORS["idle"])

        # respiracao suave mesmo parada, mais forte com o audio real
        breath = 0.5 + 0.5 * math.sin(self._phase * 0.5)
        pulse = min(1.0, breath * 0.25 + self._display_level * 0.9)

        glow_pixmap = self._glow_cache.get(state, self._glow_cache.get("idle"))
        if glow_pixmap is not None:
            cx, cy = self.width() / 2, self.height() / 2
            gd = glow_pixmap.width()
            painter.drawPixmap(QPointF(cx - gd / 2, cy - gd / 2), glow_pixmap)

        draw_emily_rings(painter, QRectF(self.rect()), color, pulse=pulse, phase=self._phase)

        painter.setFont(QFont("Segoe UI", 12))
        painter.setPen(QColor(TEXT_PRIMARY))
        label = STATE_LABELS.get(state, STATE_LABELS["idle"])
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, label)


class MainWindow(QMainWindow):
    def __init__(self, amp_monitor: AmplitudeMonitor, bridge: TutorBridge, title: str):
        super().__init__()
        self.setWindowTitle(title)
        self.setStyleSheet(f"background-color: {BG_DEEP.name()};")
        self.resize(560, 720)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self.orb = OrbWidget(amp_monitor)
        layout.addWidget(self.orb, stretch=1)

        text_style = f"color: {TEXT_PRIMARY.name()}; font-family: 'Segoe UI'; font-size: 13px;"

        self.user_label = QLabel("You: ...")
        self.user_label.setWordWrap(True)
        self.user_label.setStyleSheet(text_style)

        self.reply_label = QLabel("Emily: ...")
        self.reply_label.setWordWrap(True)
        self.reply_label.setStyleSheet(text_style + "font-weight: 600;")

        self.correction_label = QLabel("")
        self.correction_label.setWordWrap(True)
        self.correction_label.setStyleSheet(
            f"color: {STATE_COLORS['listening'].name()}; font-family: 'Segoe UI'; font-size: 12px;"
        )

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(
            f"color: {STATE_COLORS['error'].name()}; font-family: 'Segoe UI'; font-size: 12px; font-weight: 600;"
        )

        layout.addWidget(self.user_label)
        layout.addWidget(self.reply_label)
        layout.addWidget(self.correction_label)
        layout.addWidget(self.error_label)

        self.setCentralWidget(central)

        bridge.user_text_changed.connect(lambda t: self.user_label.setText(f"You: {t}"))
        bridge.user_text_changed.connect(lambda _t: self.error_label.setText(""))
        bridge.reply_text_changed.connect(lambda t: self.reply_label.setText(f"Emily: {t}"))
        bridge.correction_added.connect(self.correction_label.setText)
        bridge.error_changed.connect(self.error_label.setText)


def run_ui(amp_monitor: AmplitudeMonitor, bridge: TutorBridge, title: str) -> int:
    app = QApplication.instance() or QApplication([])

    icon_path = Path(__file__).resolve().parent.parent / "assets" / "emily_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow(amp_monitor, bridge, title)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec()
