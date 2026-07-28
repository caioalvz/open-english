"""Identidade visual da Emily: paleta e o desenho do "orbe" organico.

Pensada para combinar com a persona dela (professora acolhedora, paciente),
em vez do visual frio de HUD/gadget de ficcao cientifica do protótipo
inicial. Cores quentes, formas organicas que "respiram" em vez de aneis
tecnicos rigidos. Este modulo e a unica fonte de verdade de cor/forma -
tanto a janela do app (app/ui.py) quanto o gerador de icone
(scripts/generate_icon.py) desenham a partir daqui, para ficarem
consistentes.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap, QRadialGradient

BG_DEEP = QColor("#150f18")

STATE_COLORS: dict[str, QColor] = {
    "idle": QColor("#9a8aa8"),
    "listening": QColor("#ffb86b"),
    "thinking": QColor("#b48eff"),
    "speaking": QColor("#ff8fa3"),
    "error": QColor("#ff5c5c"),
}

STATE_LABELS: dict[str, str] = {
    "idle": "Ready to chat",
    "listening": "Listening...",
    "thinking": "Thinking...",
    "speaking": "Speaking...",
    "error": "One sec...",
}

TEXT_PRIMARY = QColor("#f2e9e4")

# Cor de marca (nao muda com o estado) - usada no icone/logo da Emily, entre
# o amber de "listening" e o coral de "speaking".
BRAND_COLOR = QColor("#ff9d6c")


def _blob_path(cx: float, cy: float, base_radius: float, wobble: float, phase: float, n_points: int = 10) -> QPainterPath:
    """Contorno organico e suave (nao um circulo perfeito), como uma gota de luz."""
    pts = []
    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        r = base_radius * (
            1.0
            + wobble * 0.5 * math.sin(phase * 1.3 + angle * 3.0)
            + wobble * 0.3 * math.sin(phase * 0.7 + angle * 5.0)
        )
        pts.append(QPointF(cx + r * math.cos(angle), cy + r * math.sin(angle)))

    path = QPainterPath()
    path.moveTo((pts[0] + pts[-1]) / 2)
    for i in range(n_points):
        p0 = pts[i]
        p1 = pts[(i + 1) % n_points]
        mid = (p0 + p1) / 2
        path.quadTo(p0, mid)
    path.closeSubpath()
    return path


def render_glow_pixmap(color: QColor, diameter: int) -> QPixmap:
    """Pre-renderiza o glow externo (gradiente radial grande) UMA vez.

    E a parte mais cara de desenhar (area grande, alpha blend). Gerar isso
    a cada frame e o que causava o atraso entre o audio e a animacao -
    agora e so um blit (bitblt) barato por frame, sem recalcular gradiente.
    """
    pixmap = QPixmap(diameter, diameter)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = diameter / 2
    glow = QRadialGradient(r, r, r)
    c1 = QColor(color)
    c1.setAlpha(70)
    c2 = QColor(color)
    c2.setAlpha(0)
    glow.setColorAt(0.0, c1)
    glow.setColorAt(1.0, c2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(QPointF(r, r), r, r)
    painter.end()
    return pixmap


def render_core_fill_color(color: QColor) -> QColor:
    """Cor solida (sem gradiente) usada para preencher o nucleo ao vivo.

    Preenchimento solido e muito mais barato de rasterizar que um
    QRadialGradient recalculado a cada frame - o "brilho" continua vindo do
    glow cacheado atras (render_glow_pixmap) e do highlight pre-renderizado
    (render_highlight_pixmap), entao visualmente ainda parece uma luz suave.
    """
    return QColor(color).lighter(115)


def render_highlight_pixmap(diameter: int) -> QPixmap:
    """Pequeno brilho (canto superior-esquerdo) pre-renderizado uma vez -
    da profundidade ao nucleo sem custar um gradiente novo por frame."""
    pixmap = QPixmap(diameter, diameter)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = diameter / 2
    grad = QRadialGradient(r, r, r)
    c1 = QColor(255, 255, 255, 130)
    c2 = QColor(255, 255, 255, 0)
    grad.setColorAt(0.0, c1)
    grad.setColorAt(1.0, c2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(grad)
    painter.drawEllipse(QPointF(r, r), r, r)
    painter.end()
    return pixmap


def draw_orb_core(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    pulse: float = 0.4,
    phase: float = 0.0,
    ripple: float = 0.0,
    highlight_pixmap: QPixmap | None = None,
    organic: bool = True,
) -> None:
    """So o nucleo + ondas (leve, area pequena, preenchimento solido) - sem
    o glow externo.

    Feito para ser chamado a cada frame na UI ao vivo; as partes caras
    (glow e highlight) sao pre-renderizadas uma vez e passadas prontas.

    `organic=True` desenha o contorno em "gota" (usado no icone estatico,
    onde o custo so acontece uma vez). `organic=False` desenha um circulo
    perfeito via drawEllipse - o caminho mais barato de preencher que existe
    num motor 2D - usado ao vivo pra garantir que roda leve mesmo sem GPU.
    """
    cx, cy = rect.center().x(), rect.center().y()
    base_radius = min(rect.width(), rect.height()) * 0.22

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if ripple > 0:
        for i in range(3):
            t = (phase * 0.15 + i / 3) % 1.0
            ring_radius = base_radius * (1.0 + t * 2.2)
            alpha = max(0, int(90 * (1 - t) * ripple))
            if alpha <= 0:
                continue
            ring_color = QColor(color)
            ring_color.setAlpha(alpha)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = painter.pen()
            pen.setColor(ring_color)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.drawEllipse(QPointF(cx, cy), ring_radius, ring_radius)

    # nucleo (respira com o pulse) - preenchimento solido, barato
    core_radius = base_radius * (0.75 + pulse * 0.35)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(render_core_fill_color(color))
    if organic:
        blob = _blob_path(cx, cy, core_radius, wobble=0.12 + pulse * 0.10, phase=phase)
        painter.drawPath(blob)
    else:
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

    if highlight_pixmap is not None:
        hd = highlight_pixmap.width()
        painter.drawPixmap(QPointF(cx - hd * 0.65, cy - hd * 0.65), highlight_pixmap)


def draw_emily_rings(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    pulse: float = 0.4,
    phase: float = 0.0,
    bar_count: int = 40,
) -> None:
    """Anel de barras + nucleo simples - quase tudo traco (sem preenchimento
    de area grande), com a paleta e o tom quentes da Emily: barras
    arredondadas e cores acolhedoras.

    E o desenho usado ao vivo (chamado a cada frame) - propositalmente
    barato: linhas e circulos sem preenchimento rasterizam muito mais rapido
    que paths organicos ou gradientes, o que importa em maquinas sem GPU
    dedicada (o Qt desenha tudo isso via CPU).
    """
    cx, cy = rect.center().x(), rect.center().y()
    base_radius = min(rect.width(), rect.height()) * 0.22

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = painter.pen()
    pen.setColor(color)
    pen.setWidthF(2.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    for i in range(bar_count):
        angle = (2 * math.pi * i / bar_count) + phase * 0.15
        wobble = 0.12 * math.sin(phase * 1.6 + i * 0.4) * (0.3 + pulse)
        bar_len = base_radius * (0.16 + pulse * 0.45 + wobble)
        r1 = base_radius
        r2 = base_radius + bar_len
        x1, y1 = cx + r1 * math.cos(angle), cy + r1 * math.sin(angle)
        x2, y2 = cx + r2 * math.cos(angle), cy + r2 * math.sin(angle)
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    # nucleo: dois circulos concentricos so de contorno (barato)
    core_radius = base_radius * (0.55 + pulse * 0.2)
    outline_pen = painter.pen()
    outline_pen.setWidthF(2.0)
    painter.setPen(outline_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)
    inner_radius = core_radius * 0.6
    painter.drawEllipse(QPointF(cx, cy), inner_radius, inner_radius)

    # pontinho central solido e pequeno - da um toque de calor no meio
    dot_radius = inner_radius * 0.35
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(render_core_fill_color(color))
    painter.drawEllipse(QPointF(cx, cy), dot_radius, dot_radius)


def draw_orb(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    pulse: float = 0.4,
    phase: float = 0.0,
    ripple: float = 0.0,
) -> None:
    """Desenho completo (glow + nucleo) num unico frame - usado para gerar o
    icone estatico (scripts/generate_icon.py), onde o custo de recalcular o
    glow nao importa porque so roda uma vez."""
    diameter = int(min(rect.width(), rect.height()) * 0.22 * (2.0 + pulse * 0.6) * 2)
    glow_pixmap = render_glow_pixmap(color, diameter)
    cx, cy = rect.center().x(), rect.center().y()
    painter.drawPixmap(QPointF(cx - diameter / 2, cy - diameter / 2), glow_pixmap)

    core_radius = min(rect.width(), rect.height()) * 0.22 * (0.75 + pulse * 0.35)
    highlight = render_highlight_pixmap(int(core_radius * 1.3))
    draw_orb_core(painter, rect, color, pulse=pulse, phase=phase, ripple=ripple, highlight_pixmap=highlight)
