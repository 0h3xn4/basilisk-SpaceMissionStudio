#
#  ISC License
#
#  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
"""The bundled fonts: Inter (400, 500, 600) and JetBrains Mono (400, 500),
registered with ``QFontDatabase`` from the package so the GUI never
depends on a system font. Both are under the SIL Open Font License 1.1;
the licence text sits next to each family's files
(``gui/assets/fonts/<family>/OFL.txt``).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

from .typography import MONO_FONT_FAMILY, SIZE, UI_FONT_FAMILY, WEIGHT

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
_loaded_families: list[str] = []

_QT_WEIGHT = {400: QFont.Weight.Normal, 500: QFont.Weight.Medium, 600: QFont.Weight.DemiBold}


def load_fonts() -> list[str]:
    """Register the bundled faces with Qt (once); the families that loaded.
    A face Qt cannot read is skipped, not fatal."""
    if not _loaded_families:
        for path in sorted(FONTS_DIR.glob("*/*.ttf")):
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id >= 0:
                _loaded_families.extend(f for f in QFontDatabase.applicationFontFamilies(font_id)
                                        if f not in _loaded_families)
    return list(_loaded_families)


def tabular_figures_supported() -> bool:
    """Whether this Qt can switch on OpenType features (Qt 6.7 and later)."""
    return hasattr(QFont, "setFeature") and hasattr(QFont, "Tag")


def ui_font(size: str = "body", weight: str = "regular") -> QFont:
    """Inter at a size of the type scale (``"caption"`` ... ``"display"``)
    and a weight (``"regular"``, ``"medium"``, ``"semibold"``)."""
    font = QFont(UI_FONT_FAMILY)
    font.setPixelSize(SIZE[size])
    font.setWeight(_QT_WEIGHT[WEIGHT[weight]])
    return font


def mono_font(size: str = "small", weight: str = "regular") -> QFont:
    """JetBrains Mono, for values, IDs, code and logs."""
    font = QFont(MONO_FONT_FAMILY)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPixelSize(SIZE[size])
    font.setWeight(_QT_WEIGHT[WEIGHT[weight]])
    return font


def numeric_font(size: str = "small") -> QFont:
    """The font of numbers in tables: Inter with tabular figures where Qt
    supports font features, JetBrains Mono otherwise (the brief's rule)."""
    if not tabular_figures_supported():
        return mono_font(size)
    font = ui_font(size)
    font.setFeature(QFont.Tag("tnum"), 1)
    return font
