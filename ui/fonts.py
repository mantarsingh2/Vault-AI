from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase


ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
_fonts_loaded = False


def load_application_fonts():
    global _fonts_loaded

    if _fonts_loaded:
        return

    for filename in ("Inter-Variable.ttf", "Roboto-Variable.ttf"):
        QFontDatabase.addApplicationFont(str(ASSETS_DIR / filename))

    _fonts_loaded = True


def figma_font(family, pixel_size, weight):
    font = QFont(family)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font
