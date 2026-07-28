"""Gera o icone da Emily (assets/emily_icon.ico + .png) a partir do mesmo
desenho usado ao vivo na UI (app/theme.py), pra ficar tudo consistente.

Rodar uma vez (ou quando a identidade visual mudar):
    .venv\\Scripts\\python.exe scripts\\generate_icon.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from app.theme import BG_DEEP, BRAND_COLOR, draw_orb


def render_master_png(size: int = 512) -> bytes:
    app = QApplication.instance() or QApplication([])

    pixmap = QPixmap(size, size)
    pixmap.fill(BG_DEEP)

    painter = QPainter(pixmap)
    draw_orb(painter, QRectF(0, 0, size, size), BRAND_COLOR, pulse=0.75, phase=0.0, ripple=0.0)
    painter.end()

    image = pixmap.toImage()
    tmp_path = ROOT / "assets" / "_emily_icon_master.png"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(tmp_path), "PNG")
    data = tmp_path.read_bytes()
    tmp_path.unlink()
    return data


def main() -> None:
    assets_dir = ROOT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    png_bytes = render_master_png(512)
    master = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

    png_path = assets_dir / "emily_icon.png"
    master.save(png_path, format="PNG")

    ico_path = assets_dir / "emily_icon.ico"
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(ico_path, format="ICO", sizes=sizes)

    print(f"Gerado: {png_path}")
    print(f"Gerado: {ico_path}")


if __name__ == "__main__":
    main()
