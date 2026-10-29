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
"""Lucide icons (ISC licence), bundled in ``gui/assets/icons/lucide/`` and
tinted from the tokens when they are drawn.

:func:`icon` returns a ``QIcon`` whose engine looks the colour up each
time it paints, so an icon follows a live theme change without being set
again; a disabled icon takes ``text.disabled``. :func:`icon_file` writes a
tinted copy for the style sheet's ``url()`` glyphs (combo and spin arrows,
the tick of a check box). Only the icons the GUI uses are bundled; the
names below are the app's, mapped to Lucide's.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QObject, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from shiboken6 import isValid

from ... import temp_folders
from . import state
from .fonts import ASSETS_DIR

ICONS_DIR = ASSETS_DIR / "icons" / "lucide"

# The app's action and step names -> Lucide icon names.
ACTION_ICONS = {
    "new": "file-plus",
    "open": "folder-open",
    "save": "save",
    "run": "play",
    "monte-carlo": "dices",
    "abort": "circle-stop",
    "live-plot": "activity",
    "check-kernels": "file-check",
    "vizard-config": "sliders-horizontal",
    "vizard-launch": "monitor-play",
    "model-3d": "box",
    "open-monte-carlo": "folder-open",
    "clear-cursor": "x",
}
STEP_ICONS = {
    "assignment": "variable",
    "if": "git-branch",
    "lambert_transfer": "route",
    "maneuver": "rocket",
    "propagate": "orbit",
    "report": "file-text",
    "script_block": "code",
    "while": "repeat",
}
# The token each action's icon is drawn in: Run in the accent, Cancel in
# critical, the rest in text.secondary.
ACTION_TOKENS = {"run": "accent", "abort": "status.critical"}

_svg_cache: dict[str, bytes] = {}
_renderers: dict[tuple[str, str], QSvgRenderer] = {}
_pixmaps: dict[tuple[str, str, int, int, float], QPixmap] = {}
_files_dir: Path | None = None


def available(name: str) -> bool:
    """Whether the Lucide icon ``name`` is bundled."""
    return (ICONS_DIR / f"{name}.svg").is_file()


def _svg(name: str) -> bytes:
    if name not in _svg_cache:
        _svg_cache[name] = (ICONS_DIR / f"{name}.svg").read_bytes()
    return _svg_cache[name]


def tinted_svg(name: str, colour: str, stroke_width: float | None = None) -> bytes:
    """The SVG of ``name`` drawn in ``colour`` (``#RRGGBB``)."""
    data = _svg(name).replace(b"currentColor", colour.encode("ascii"))
    if stroke_width is not None:
        data = data.replace(b'stroke-width="2"', f'stroke-width="{stroke_width:g}"'.encode("ascii"))
    return data


def _renderer(name: str, colour: str) -> QSvgRenderer:
    key = (name, colour)
    if key not in _renderers:
        _renderers[key] = QSvgRenderer(QByteArray(tinted_svg(name, colour)))
    return _renderers[key]


class _TokenIconEngine(QIconEngine):
    """Draws a Lucide icon in the current colour of a token."""

    def __init__(self, name: str, token: str) -> None:
        super().__init__()
        self._name = name
        self._token = token

    def _colour(self, mode: QIcon.Mode) -> str:
        return state.TOKENS["text.disabled" if mode == QIcon.Mode.Disabled else self._token]

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, icon_state: QIcon.State) -> None:
        _renderer(self._name, self._colour(mode)).render(painter, QRectF(rect))

    def pixmap(self, size: QSize, mode: QIcon.Mode, icon_state: QIcon.State) -> QPixmap:
        return self.scaledPixmap(size, mode, icon_state, 1.0)

    def scaledPixmap(self, size: QSize, mode: QIcon.Mode, icon_state: QIcon.State,  # noqa: N802 -- Qt API
                     scale: float) -> QPixmap:
        colour = self._colour(mode)
        key = (self._name, colour, size.width(), size.height(), scale)
        pixmap = _pixmaps.get(key)
        if pixmap is None:
            pixmap = QPixmap(round(size.width() * scale), round(size.height() * scale))
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            _renderer(self._name, colour).render(painter)
            painter.end()
            pixmap.setDevicePixelRatio(scale)
            _pixmaps[key] = pixmap
        return pixmap

    def clone(self) -> QIconEngine:
        return _TokenIconEngine(self._name, self._token)

    def key(self) -> str:
        return "spacemissionstudio-lucide"


def icon(name: str, ink: str = "text.secondary") -> QIcon:
    """The Lucide icon ``name`` in the colour of the token ``ink``, following the
    theme. An empty icon if ``name`` is not bundled."""
    if not available(name):
        return QIcon()
    return QIcon(_TokenIconEngine(name, ink))


def action_icon(name: str) -> QIcon:
    """The icon of one of the app's actions (``ACTION_ICONS``)."""
    return icon(ACTION_ICONS[name], ACTION_TOKENS.get(name, "text.secondary"))


def step_icon(kind: str) -> QIcon:
    """The icon of a Mission Sequence step kind; empty for an unknown kind."""
    return icon(STEP_ICONS[kind]) if kind in STEP_ICONS else QIcon()


def icon_file(name: str, colour: str, stroke_width: float | None = None) -> Path:
    """A tinted copy of ``name`` on disk, for a style sheet's ``url()``:
    written once per process to a temporary folder."""
    global _files_dir
    if _files_dir is None:
        _files_dir = temp_folders.folder_removed_at_exit(temp_folders.ICONS)
    suffix = "" if stroke_width is None else f"-w{stroke_width:g}"
    target = _files_dir / f"{name}-{colour.lstrip('#').upper()}{suffix}.svg"
    if not target.exists():
        target.write_bytes(tinted_svg(name, colour, stroke_width))
    return target


class _KeepIcon(QObject):
    """Sets an icon on a tool button again after its action changes (Qt
    copies the action's icon onto the button on every change)."""

    def __init__(self, button, qicon: QIcon) -> None:
        super().__init__(button)
        self._button = button
        self._icon = qicon
        button.setIcon(qicon)
        button.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 -- Qt API name
        if event.type() == QEvent.Type.ActionChanged:
            # This filter as the context: the call is dropped with the button.
            QTimer.singleShot(0, self, self._apply)
        return False

    def _apply(self) -> None:
        if isValid(self._button):
            self._button.setIcon(self._icon)


def keep_icon(button, qicon: QIcon) -> None:
    """Show ``qicon`` on a tool button that shows an action, whatever the
    action's own icon: the primary Run button draws its icon on the accent
    fill, in ``text.on_accent``, where the action's accent icon would vanish."""
    _KeepIcon(button, qicon)
