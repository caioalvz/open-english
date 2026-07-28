"""Interface da Emily: aba de conversa (orbe) + aba de progresso, na mesma
janela - sem popups nem janelas externas."""
from __future__ import annotations

import math
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import (
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QLabel,
    QApplication,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
)

from app import curriculum
from app.audio_io import AmplitudeMonitor
from app.memory import Memory
from app.theme import (
    BG_DEEP,
    STATE_COLORS,
    STATE_LABELS,
    TEXT_PRIMARY,
    draw_emily_rings,
    render_glow_pixmap,
)

PANEL_BG = QColor("#1c1420")
LOCKED_COLOR = QColor("#6b5f73")


class TutorBridge(QObject):
    """Sinais Qt para atualizar a UI a partir da thread de audio/LLM em background."""

    user_text_changed = pyqtSignal(str)
    reply_text_changed = pyqtSignal(str)
    correction_added = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    error_changed = pyqtSignal(str)
    progress_changed = pyqtSignal()


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


class ConversationTab(QWidget):
    """A aba original: orbe + legendas da conversa em andamento."""

    def __init__(self, amp_monitor: AmplitudeMonitor, bridge: TutorBridge, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
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

        bridge.user_text_changed.connect(lambda t: self.user_label.setText(f"You: {t}"))
        bridge.user_text_changed.connect(lambda _t: self.error_label.setText(""))
        bridge.reply_text_changed.connect(lambda t: self.reply_label.setText(f"Emily: {t}"))
        bridge.correction_added.connect(self.correction_label.setText)
        bridge.error_changed.connect(self.error_label.setText)


class ProgressTab(QWidget):
    """Painel de progresso: nivel/sequencia/vocabulario, plano da aula atual
    e a trilha completa A1->C2 - tudo lido do banco local (data/tutor.db)."""

    def __init__(self, memory: Memory, parent=None):
        super().__init__(parent)
        self.memory = memory

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header_style = f"color: {TEXT_PRIMARY.name()}; font-family: 'Segoe UI'; font-size: 15px; font-weight: 700;"
        body_style = f"color: {TEXT_PRIMARY.name()}; font-family: 'Segoe UI'; font-size: 13px;"

        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        self.stats_label.setStyleSheet(header_style)
        layout.addWidget(self.stats_label)

        plan_title = QLabel("Current lesson")
        plan_title.setStyleSheet(f"color: {STATE_COLORS['listening'].name()}; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;")
        layout.addWidget(plan_title)

        self.plan_label = QLabel()
        self.plan_label.setWordWrap(True)
        self.plan_label.setStyleSheet(body_style)
        layout.addWidget(self.plan_label)

        path_title = QLabel("Learning path (A1 -> C2)")
        path_title.setStyleSheet(f"color: {STATE_COLORS['listening'].name()}; font-family: 'Segoe UI'; font-size: 12px; font-weight: 700;")
        layout.addWidget(path_title)

        self.path_list = QListWidget()
        self.path_list.setStyleSheet(
            f"QListWidget {{ background-color: {PANEL_BG.name()}; border: none; "
            f"color: {TEXT_PRIMARY.name()}; font-family: 'Segoe UI'; font-size: 12px; }}"
            "QListWidget::item { padding: 4px 6px; }"
        )
        layout.addWidget(self.path_list, stretch=1)

        self.refresh()

    def refresh(self) -> None:
        profile = self.memory.build_profile()
        completed_ids = self.memory.get_completed_lesson_ids()
        streak = self.memory.get_streak_days()
        current_id = self.memory.get_current_lesson_id()
        current_lesson = curriculum.get_lesson(current_id)

        total = len(curriculum.LESSONS)
        done = len(completed_ids)

        self.stats_label.setText(
            f"Level {profile.cefr_level}  -  {done}/{total} lessons  -  "
            f"{profile.known_vocab_count} words  -  {streak}-day streak"
        )

        vocab_preview = ", ".join(current_lesson.focus_vocab[:5])
        self.plan_label.setText(
            f"{current_lesson.title}\n"
            f"Goal: {current_lesson.can_do_objective}\n"
            f"Key phrases: {vocab_preview}"
        )

        self.path_list.clear()
        last_level = None
        for lesson in curriculum.LESSONS:
            if lesson.level != last_level:
                header = QListWidgetItem(f"— {lesson.level} —")
                header.setForeground(QColor(TEXT_PRIMARY))
                font = header.font()
                font.setBold(True)
                header.setFont(font)
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                self.path_list.addItem(header)
                last_level = lesson.level

            if lesson.id in completed_ids:
                marker, color = "[x]", STATE_COLORS["speaking"]
            elif lesson.id == current_id:
                marker, color = "[>]", STATE_COLORS["listening"]
            else:
                marker, color = "[ ]", LOCKED_COLOR

            item = QListWidgetItem(f"  {marker} {lesson.title}")
            item.setForeground(color)
            self.path_list.addItem(item)


class MainWindow(QMainWindow):
    def __init__(self, amp_monitor: AmplitudeMonitor, bridge: TutorBridge, title: str, memory: Memory):
        super().__init__()
        self.setWindowTitle(title)
        self.setStyleSheet(f"background-color: {BG_DEEP.name()};")
        self.resize(580, 780)

        tabs = QTabWidget()
        tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background-color: {BG_DEEP.name()}; }}"
            f"QTabBar::tab {{ background: {PANEL_BG.name()}; color: {TEXT_PRIMARY.name()}; "
            "padding: 8px 20px; font-family: 'Segoe UI'; }"
            f"QTabBar::tab:selected {{ background: {BG_DEEP.name()}; "
            f"border-bottom: 2px solid {STATE_COLORS['listening'].name()}; }}"
        )

        self.conversation_tab = ConversationTab(amp_monitor, bridge)
        self.progress_tab = ProgressTab(memory)
        tabs.addTab(self.conversation_tab, "Conversation")
        tabs.addTab(self.progress_tab, "Progress")

        self.setCentralWidget(tabs)

        bridge.progress_changed.connect(self.progress_tab.refresh)


def run_ui(amp_monitor: AmplitudeMonitor, bridge: TutorBridge, title: str, memory: Memory) -> int:
    app = QApplication.instance() or QApplication([])

    icon_path = Path(__file__).resolve().parent.parent / "assets" / "emily_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow(amp_monitor, bridge, title, memory)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec()
