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

"""Home (UI overhaul plan §7, M3): where a mission starts.

Above them, while it asks, the reference-data card: it replaced the
start-up dialog (``gui.startup_fetch_dialog.ReferenceDataCard``). Then
three columns:

* **Start**: "New blank scenario", "Open a scenario file..." and the
  recent scenarios (``gui.recent_files``: the last 10, a missing file
  marked).
* **Templates**: a card per built-in template
  (``spacemissionstudio/scenarios/templates/``) with its mission type,
  orbit summary and one line, all three read from the template file
  itself (:func:`mission_type`, :func:`orbit_summary`,
  :func:`first_sentence`); no metadata is added for them. Text only, no
  thumbnails (plan §9, Q4). A filter narrows the cards.
* **Details**: the selected template's whole description, with Open and
  Customize.

The page only picks: a path (:attr:`path_chosen`), a customized scenario
(:attr:`scenario_customized`) or a blank one (:attr:`blank_requested`);
``MainWindow`` opens it, so one place knows how to open a scenario.

Each card's Customize... acts on THAT card's template, never on the
selection (users missed a single Customize button gated on a selection).
The keyboard: Tab reaches the cards once, the arrow keys move between
them, Enter opens one; the details' Customize... is the next Tab stop.
"""

from __future__ import annotations

import functools
import html
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QTextLayout
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

import spacemissionstudio

from ..engine import small_bodies
from ..engine.scenario_explainer import _BODY_RADIUS_KM, _EARTH_REQUATOR_KM, _is_sun_synchronous, _mode_name
from ..schema import load_scenario
from . import recent_files
from .feedback import report
from .mission_guide import StartFromScratchCard
from .startup_fetch_dialog import ReferenceDataCard
from .template_wizard import TemplateCustomizeWizard, get_wizard_spec
from .theme import SPACE, TOKENS, icon, items, set_role, ui_font
from .theme.richtext import css

_logger = logging.getLogger(__name__)

# Where scripts/_generate_templates.py writes the built-in templates, and
# where setuptools package-data (see pyproject.toml's own comment on
# this) copies them to in an installed wheel -- spacemissionstudio.__file__ is
# <install>/spacemissionstudio/__init__.py either way (a checkout or a real
# install), so this resolves correctly in both.
TEMPLATES_DIR = Path(spacemissionstudio.__file__).resolve().parent / "scenarios" / "templates"

_FILE_FILTER = "SpaceMissionStudio scenario (*.json)"

CARD_MIN_WIDTH_PX = 264  # [px] a card's least width; the columns follow the pane
_CARD_LINES = 4  # the one line wraps to at most this many lines, then elides
_START_WIDTH_PX = 280  # [px] the Start column's width in a new window
_DETAILS_WIDTH_PX = 320  # [px] the details column's width in a new window
_CIRCULAR_BELOW = 0.01  # [-] an eccentricity below this is shown as a circular orbit

# A sentence ends at ".", "!" or "?" before a space; "e.g." and the like do not end one.
_SENTENCE_END = re.compile(r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)(?<=[.!?])\s+")


def description_html(text: str) -> str:
    """A template description as rich text: paragraphs separated by a
    blank line, a paragraph whose first line ends with ":" as a heading,
    and "- " lines as a bullet list (see scripts/_template_descriptions.py).
    A real user called the old plain-text block "just awful UI/UX"."""
    parts = []
    for paragraph in text.strip().split("\n\n"):
        lines = paragraph.splitlines()
        heading = lines[0] if lines and lines[0].endswith(":") and not lines[0].startswith("- ") else None
        body = lines[1:] if heading else lines
        if heading:
            parts.append(f"<p style='{css('heading-p')}'><b>{html.escape(heading[:-1])}</b></p>")
        bullets = [line[2:] for line in body if line.startswith("- ")]
        prose = [line for line in body if not line.startswith("- ")]
        if prose:
            parts.append(f"<p style='{css('prose-p')}'>{html.escape(' '.join(prose))}</p>")
        if bullets:
            parts.append(f"<ul style='{css('list')}'>"
                         + "".join(f"<li>{html.escape(item)}</li>" for item in bullets) + "</ul>")
    return "".join(parts)


# -- what a card says, read from the template ---------------------------------------

def first_sentence(description: str) -> str:
    """The description's first sentence: the card's one line."""
    paragraph = " ".join(description.strip().split("\n\n", 1)[0].split())
    return _SENTENCE_END.split(paragraph, 1)[0] if paragraph else ""


def mission_type(scenario) -> str:
    """The attitude mode (and pointing mode), and how many spacecraft."""
    parts = ["Orbit only" if scenario.simulation_mode == "orbit_only" else "Full attitude"]
    first = scenario.spacecraft[0] if scenario.spacecraft else None
    if scenario.simulation_mode != "orbit_only" and first is not None and first.fsw_mode:
        parts.append(_mode_name(first.fsw_mode))
    count = len(scenario.spacecraft)
    parts.append(f"{count} spacecraft")
    return " · ".join(parts)


def _body_name(central_body: str) -> str:
    return central_body.replace(" barycenter", "").title()


def orbit_summary(scenario) -> str:
    """The central body and the first spacecraft's orbit: altitude (or
    periapsis and apoapsis altitudes), inclination, Sun-synchronous where
    the explainer calls it so."""
    gravity = scenario.gravity
    body = getattr(gravity, "central_body", "earth")
    parts = [_body_name(body)]
    orbit = scenario.spacecraft[0].orbit if scenario.spacecraft else None
    if orbit is None:
        return parts[0]
    if orbit.type == "tle":
        return " · ".join(parts + ["TLE"])
    if orbit.type != "classical_elements" or orbit.semi_major_axis_km is None:
        return " · ".join(parts + ["Cartesian state"])
    sma, ecc, inc = orbit.semi_major_axis_km, orbit.eccentricity or 0.0, orbit.inclination_deg
    if small_bodies.body(body) is not None:  # a small body has no single radius: from its centre
        parts.append(f"{sma:.0f} km from the centre")
    else:
        radius = _BODY_RADIUS_KM.get(body, _EARTH_REQUATOR_KM)  # [km]
        if ecc < _CIRCULAR_BELOW:
            parts.append(f"{sma - radius:.0f} km circular")
        else:
            parts.append(f"{sma * (1.0 - ecc) - radius:.0f} × {sma * (1.0 + ecc) - radius:.0f} km")
    if inc is not None:
        parts.append(f"i {inc:.1f} deg")
    if _is_sun_synchronous(orbit, gravity):
        parts.append("Sun-synchronous")
    return " · ".join(parts)


# -- the cards -------------------------------------------------------------------

class _ClampedLabel(QWidget):
    """Wrapped text cut to ``lines`` lines, the last one elided with "...";
    the whole text is the tooltip."""

    def __init__(self, text: str, lines: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._text = text
        self._lines = lines
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def text(self) -> str:
        return self._text

    def sizeHint(self) -> QSize:
        return QSize(CARD_MIN_WIDTH_PX, self._lines * self.fontMetrics().lineSpacing())

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.sizeHint().height())

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        metrics = self.fontMetrics()
        layout = QTextLayout(self._text, self.font())
        layout.beginLayout()
        y = 0.0
        shown = 0
        while shown < self._lines:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(self.width())
            start, length = line.textStart(), line.textLength()
            if shown == self._lines - 1 and start + length < len(self._text):
                rest = metrics.elidedText(self._text[start:], Qt.TextElideMode.ElideRight, self.width())
                painter.drawText(0, int(y + metrics.ascent()), rest)
            else:
                painter.drawText(0, int(y + metrics.ascent()), self._text[start:start + length].rstrip())
            y += metrics.lineSpacing()
            shown += 1
        layout.endLayout()


class _CardText(QWidget):
    """Wrapped plain text in one colour token, painted directly. A card
    has three of these: as word-wrapped labels (``QLabel``), their
    height-for-width made Home's first show take 108-193 ms
    (``docs/DECISIONS.md``, M3)."""

    def __init__(self, text: str, token: str, font, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._text = text
        self._token = token
        self._heights: Dict[int, int] = {}
        self.setFont(font)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def text(self) -> str:
        return self._text

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        if width not in self._heights:
            bounds = self.fontMetrics().boundingRect(QRect(0, 0, max(width, 1), 1 << 20),
                                                     int(Qt.TextFlag.TextWordWrap), self._text)
            self._heights[width] = bounds.height()
        return self._heights[width]

    def sizeHint(self) -> QSize:
        return QSize(CARD_MIN_WIDTH_PX, self.heightForWidth(CARD_MIN_WIDTH_PX))

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.fontMetrics().lineSpacing())

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.FontChange:
            self._heights.clear()
        super().changeEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setPen(QColor(TOKENS[self._token]))  # read at each paint: a theme switch needs nothing else
        painter.drawText(self.rect(), int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft
                                          | Qt.AlignmentFlag.AlignTop), self._text)


class TemplateCard(QFrame):
    """One template: its title, mission type, orbit and one line, with
    Open and (if it has a wizard) Customize...."""

    selected = Signal(object)  # this card, when clicked or focused
    open_requested = Signal(object)  # Path
    customize_requested = Signal(object)  # Path

    def __init__(self, scenario, path: Path, customizable: bool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("templateCard")
        set_role(self, role="card")
        self.name = scenario.name
        self.path = path
        self.description = scenario.description or ""
        self.setAccessibleName(scenario.name)
        self.setAccessibleDescription(first_sentence(self.description))
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(CARD_MIN_WIDTH_PX)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["md"], SPACE["md"], SPACE["md"], SPACE["md"])
        layout.setSpacing(SPACE["xs"])
        self.title_label = _CardText(scenario.name, "text.primary", ui_font("body", "semibold"))
        self.title_label.setProperty("role", "heading")  # what it is, as a QLabel would say
        self.type_label = _CardText(mission_type(scenario), "text.secondary", ui_font("body"))
        self.orbit_label = _CardText(orbit_summary(scenario), "text.secondary", ui_font("body"))
        self.line_label = _ClampedLabel(first_sentence(self.description), _CARD_LINES)
        layout.addWidget(self.title_label)
        layout.addWidget(self.type_label)
        layout.addWidget(self.orbit_label)
        layout.addSpacing(SPACE["xs"])
        layout.addWidget(self.line_label)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE["xs"])
        # Not Tab stops: the cards are one stop (the arrow keys move between
        # them, Enter opens) and the details hold the same two buttons.
        self.open_button = QPushButton("Open")
        self.open_button.setAccessibleName(f"Open: {scenario.name}")
        self.open_button.setToolTip(f"Open '{scenario.name}' in the Scenario area (Enter)")
        self.open_button.clicked.connect(lambda: self.open_requested.emit(self.path))
        buttons.addWidget(self.open_button)
        self.customize_button: Optional[QPushButton] = None
        if customizable:
            button = QPushButton("Customize...")
            button.setObjectName("rowCustomizeButton")
            button.setAccessibleName(f"Customize: {scenario.name}")
            button.setToolTip(
                f"Customize '{scenario.name}': a short, guided wizard over just this template's own key tunable "
                "parameters, then opens the result in the Scenario Editor -- the original template file "
                "is never modified."
            )
            button.clicked.connect(lambda: self.customize_requested.emit(self.path))
            buttons.addWidget(button)
            self.customize_button = button
        for button in (self.open_button, self.customize_button):
            if button is not None:
                button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                set_role(button, variant="ghost")
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def text_for_filter(self) -> str:
        return " ".join((self.name, self.type_label.text(), self.orbit_label.text(), self.description)).casefold()

    def set_selected(self, selected: bool) -> None:
        set_role(self, selected="true" if selected else None)

    def is_selected(self) -> bool:
        return self.property("selected") == "true"

    def mousePressEvent(self, event) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.selected.emit(self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.open_requested.emit(self.path)
        super().mouseDoubleClickEvent(event)

    def focusInEvent(self, event) -> None:
        self.selected.emit(self)
        super().focusInEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.open_requested.emit(self.path)
            return
        super().keyPressEvent(event)


class TemplateGrid(QWidget):
    """The cards in as many columns as the width holds. One Tab stop: the
    current card; the arrow keys, Home and End move between cards."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._grid = QGridLayout(self)
        # The layout must not hold the grid at its present columns' width
        # (it could never narrow to fewer columns): the width is free, and
        # the height is set from the width (_fit_height).
        self._grid.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(SPACE["md"])
        self.cards: List[TemplateCard] = []
        self._columns = 0
        self._current: Optional[TemplateCard] = None
        self.empty_label = set_role(QLabel("No template matches the filter."), role="empty")
        self.empty_label.setVisible(False)

    def add(self, card: TemplateCard) -> None:
        card.setParent(self)
        card.installEventFilter(self)
        self.cards.append(card)
        if self._current is None:
            self.set_current(card)

    def visible_cards(self) -> List[TemplateCard]:
        return [card for card in self.cards if not card.isHidden()]

    def columns(self) -> int:
        return self._columns

    def set_current(self, card: Optional[TemplateCard]) -> None:
        """The card Tab reaches (roving focus)."""
        for other in self.cards:
            other.setFocusPolicy(Qt.FocusPolicy.StrongFocus if other is card else Qt.FocusPolicy.ClickFocus)
        self._current = card

    def current(self) -> Optional[TemplateCard]:
        return self._current

    def apply_filter(self, text: str) -> None:
        words = text.casefold().split()
        for card in self.cards:
            card.setVisible(all(word in card.text_for_filter() for word in words))
        shown = self.visible_cards()
        if self._current not in shown:
            self.set_current(shown[0] if shown else None)
        self.relayout(force=True)

    def relayout(self, force: bool = False) -> None:
        spacing = self._grid.horizontalSpacing()
        columns = max(1, (self.width() + spacing) // (CARD_MIN_WIDTH_PX + spacing))
        if columns == self._columns and not force:
            return
        self._columns = columns
        while self._grid.count():
            self._grid.takeAt(0)
        shown = self.visible_cards()
        for index, card in enumerate(shown):
            self._grid.addWidget(card, index // columns, index % columns)
        for column in range(self._grid.columnCount()):
            self._grid.setColumnStretch(column, 1 if column < columns else 0)
        if not shown:
            self._grid.addWidget(self.empty_label, 0, 0, 1, columns)
        self.empty_label.setVisible(not shown)
        self._grid.setRowStretch(self._grid.rowCount(), 1)
        self._grid.activate()
        self._fit_height()

    def minimumSizeHint(self) -> QSize:
        return QSize(CARD_MIN_WIDTH_PX, self.minimumHeight())

    def _fit_height(self) -> None:
        """As tall as the cards need at this width, so the scroll area
        scrolls instead of squeezing them."""
        grid = self._grid
        height = grid.totalHeightForWidth(self.width()) if grid.hasHeightForWidth() else grid.totalMinimumSize().height()
        self.setMinimumHeight(max(height, grid.totalMinimumSize().height()))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.relayout()
        self._fit_height()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.relayout()

    def move(self, card: TemplateCard, key: int) -> Optional[TemplateCard]:
        """The card ``key`` (an arrow, Home or End) leads to from ``card``."""
        shown = self.visible_cards()
        if card not in shown:
            return None
        index, columns = shown.index(card), max(1, self._columns)
        target = {Qt.Key.Key_Left: index - 1, Qt.Key.Key_Right: index + 1, Qt.Key.Key_Up: index - columns,
                  Qt.Key.Key_Down: index + columns, Qt.Key.Key_Home: 0, Qt.Key.Key_End: len(shown) - 1}.get(key)
        if target is None or not 0 <= target < len(shown):
            return None
        return shown[target]

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(watched, TemplateCard):
            target = self.move(watched, event.key())
            if target is not None:
                self.set_current(target)
                target.setFocus(Qt.FocusReason.OtherFocusReason)
                return True
        return super().eventFilter(watched, event)


# -- Home ---------------------------------------------------------------------------

class LoadScenarioWidget(QWidget):
    """Home: start, recent scenarios, templates and the selected one's
    details (this module's docstring)."""

    path_chosen = Signal(object)  # pathlib.Path
    scenario_customized = Signal(object)  # schema.scenario.Scenario, built by TemplateCustomizeWizard
    blank_requested = Signal()  # "New blank scenario": MainWindow.on_new

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._template_paths: Dict[str, Path] = {}
        self._specs: Dict[str, object] = {}
        self.cards: List[TemplateCard] = []
        self._selected: Optional[TemplateCard] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # The reference-data question, across the page while it asks: it
        # replaced the start-up dialog (plan §5.2), so it is the first thing
        # seen, and its items keep their whole names.
        self.reference_card = ReferenceDataCard()
        band = QHBoxLayout()
        band.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["lg"], 0)
        band.addWidget(self.reference_card)
        layout.addLayout(band)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self._build_start())
        self.splitter.addWidget(self._build_templates())
        self.splitter.addWidget(self._build_details())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([_START_WIDTH_PX, 2 * CARD_MIN_WIDTH_PX + SPACE["md"], _DETAILS_WIDTH_PX])
        layout.addWidget(self.splitter, 1)  # the columns take the height; the card only what it needs

        self._populate_templates()
        self.refresh_recent()

    # -- Start: reference data, new, open, recent ------------------------------
    def _build_start(self) -> QWidget:
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(SPACE["lg"], SPACE["lg"], SPACE["sm"], SPACE["lg"])
        column.setSpacing(SPACE["md"])
        # The first choice: a mission from scratch (the user: "one of the
        # most important features to have"; it was File > New only).
        self.start_from_scratch = StartFromScratchCard()
        self.start_from_scratch.requested.connect(self.blank_requested)
        column.addWidget(self.start_from_scratch)

        header = QHBoxLayout()
        header.addWidget(set_role(QLabel("Recent scenarios"), role="section-title"), 1)
        self.clear_recent_button = QPushButton("Clear")
        set_role(self.clear_recent_button, variant="ghost")
        self.clear_recent_button.setToolTip("Empty the list; the files stay where they are.")
        self.clear_recent_button.clicked.connect(self._on_clear_recent)
        header.addWidget(self.clear_recent_button)
        column.addLayout(header)
        self.recent_list = QListWidget()
        self.recent_list.setObjectName("recentScenarios")
        self.recent_list.setAccessibleName("Recent scenarios")
        self.recent_list.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.recent_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.recent_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_list.setToolTip("Enter or a double-click opens a scenario; Delete takes it off the list.")
        self.recent_list.itemActivated.connect(self._on_recent_activated)
        self.recent_list.installEventFilter(self)
        column.addWidget(self.recent_list)
        # The empty state; its primary action, Open, is the button under it
        # (CLAUDE.md, "Shell").
        self.recent_empty = set_role(QLabel("No recent scenarios yet. Scenarios you open or save are listed here."),
                                     tone="secondary")
        self.recent_empty.setWordWrap(True)
        column.addWidget(self.recent_empty)
        self.browse_button = QPushButton("Open a scenario file...")
        self.browse_button.setIcon(icon("folder-open", "text.secondary"))
        self.browse_button.setToolTip("Open Scenario (Ctrl+O)")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        column.addWidget(self.browse_button, 0, Qt.AlignmentFlag.AlignLeft)
        column.addStretch(1)

        self.start_scroll = QScrollArea()
        self.start_scroll.setObjectName("homeStart")
        self.start_scroll.setWidgetResizable(True)
        self.start_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # its contents take the focus, not the frame
        self.start_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.start_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.start_scroll.setWidget(body)
        self.start_scroll.setMinimumWidth(220)  # [px]
        return self.start_scroll

    def refresh_recent(self) -> None:
        """The list again from the settings, each file checked for whether
        it is still there."""
        self.recent_list.clear()
        for path in recent_files.recent():
            missing = not path.is_file()
            item = QListWidgetItem(f"{path.name} (missing)" if missing else path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setData(Qt.ItemDataRole.UserRole + 1, missing)
            item.setToolTip(f"{path}\nMissing: it was moved or deleted. Delete takes it off the list."
                            if missing else str(path))
            if missing:
                item.setIcon(icon("triangle-alert", "status.caution"))
                items.tint(item, foreground="text.secondary")
            else:
                item.setIcon(icon("file-text", "text.secondary"))
            self.recent_list.addItem(item)
        count = self.recent_list.count()
        self.recent_list.setVisible(count > 0)
        self.clear_recent_button.setVisible(count > 0)
        self.recent_empty.setVisible(count == 0)
        if count:
            rows = self.recent_list.sizeHintForRow(0) * count + 2 * self.recent_list.frameWidth()
            self.recent_list.setFixedHeight(rows)

    def recent_paths(self) -> List[Path]:
        return [Path(self.recent_list.item(row).data(Qt.ItemDataRole.UserRole))
                for row in range(self.recent_list.count())]

    def _on_recent_activated(self, item: QListWidgetItem) -> None:
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        if not path.is_file():
            self.refresh_recent()
            report(self, f"{path} is missing: it was moved or deleted. Delete takes it off the list.",
                   kind="warning")
            return
        self.path_chosen.emit(path)

    def _on_clear_recent(self) -> None:
        recent_files.clear()
        self.refresh_recent()

    def eventFilter(self, watched, event) -> bool:
        if (watched is self.recent_list and event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)):
            item = self.recent_list.currentItem()
            if item is not None:
                row = self.recent_list.row(item)
                recent_files.forget(Path(item.data(Qt.ItemDataRole.UserRole)))
                self.refresh_recent()
                if self.recent_list.count():
                    self.recent_list.setCurrentRow(min(row, self.recent_list.count() - 1))
                else:
                    self.browse_button.setFocus()
            return True
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh_recent()  # a file may have gone since the list was drawn

    # -- the templates -----------------------------------------------------------
    def _build_templates(self) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(SPACE["sm"], SPACE["lg"], SPACE["sm"], 0)
        column.setSpacing(SPACE["sm"])
        header = QHBoxLayout()
        header.setSpacing(SPACE["sm"])
        self.templates_title = set_role(QLabel("Templates"), role="section-title")
        header.addWidget(self.templates_title)
        self.templates_count = set_role(QLabel(), tone="secondary")
        header.addWidget(self.templates_count, 1)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter templates")
        self.filter_edit.setAccessibleName("Filter templates")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.setMaximumWidth(240)  # [px]
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        header.addWidget(self.filter_edit)
        column.addLayout(header)
        self.grid = TemplateGrid()
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setObjectName("homeTemplates")
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # its contents take the focus, not the frame
        self.grid_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, SPACE["sm"], SPACE["lg"])
        inner_layout.addWidget(self.grid)
        self.grid_scroll.setWidget(inner)
        column.addWidget(self.grid_scroll, 1)
        holder.setMinimumWidth(CARD_MIN_WIDTH_PX + 2 * SPACE["md"])
        return holder

    def _populate_templates(self) -> None:
        if not TEMPLATES_DIR.is_dir():
            self._update_count()
            return
        for path in sorted(TEMPLATES_DIR.glob("*.json")):
            try:
                scenario = load_scenario(path)
            except Exception:  # noqa: BLE001 -- a malformed bundled template must never crash the GUI on open
                _logger.exception("Skipping malformed bundled template %s", path)
                continue
            spec = get_wizard_spec(path.name)
            self._template_paths[scenario.name] = path
            self._specs[scenario.name] = spec
            card = TemplateCard(scenario, path, spec is not None)
            card.selected.connect(self._select_card)
            card.open_requested.connect(self.path_chosen)
            card.customize_requested.connect(
                functools.partial(self._on_customize_card, scenario.name))
            self.grid.add(card)
            self.cards.append(card)
        self._update_count()

    def _update_count(self) -> None:
        shown = len(self.grid.visible_cards())
        total = len(self.cards)
        self.templates_count.setText(f"{total}" if shown == total else f"{shown} of {total}")

    def _on_filter_changed(self, text: str) -> None:
        self.grid.apply_filter(text)
        self._update_count()

    def card(self, name: str) -> TemplateCard:
        """The card of the template named ``name``."""
        return next(card for card in self.cards if card.name == name)

    def select(self, index_or_name) -> TemplateCard:
        """Select a card by its index in file order or its template name."""
        card = self.cards[index_or_name] if isinstance(index_or_name, int) else self.card(index_or_name)
        self._select_card(card)
        return card

    def selected_card(self) -> Optional[TemplateCard]:
        return self._selected

    def _select_card(self, card: TemplateCard) -> None:
        if card is self._selected:
            return
        if self._selected is not None:
            self._selected.set_selected(False)
        self._selected = card
        card.set_selected(True)
        self.grid.set_current(card)
        self.grid_scroll.ensureWidgetVisible(card, 0, SPACE["md"])
        self._show_details(card)

    # -- the details ----------------------------------------------------------
    def _build_details(self) -> QWidget:
        card = QWidget()
        column = QVBoxLayout(card)
        column.setContentsMargins(SPACE["sm"], SPACE["lg"], SPACE["lg"], SPACE["lg"])
        column.setSpacing(SPACE["sm"])
        self.description_title = set_role(QLabel(), role="section-title")
        self.description_title.setWordWrap(True)
        self.description_meta = set_role(QLabel(), tone="secondary")
        self.description_meta.setWordWrap(True)
        self.description_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE["xs"])
        self.open_template_button = QPushButton("Open template")
        self.open_template_button.setProperty("primary", True)
        self.open_template_button.setEnabled(False)
        self.open_template_button.clicked.connect(self._on_open_template_clicked)
        self.customize_template_button = QPushButton("Customize...")
        self.customize_template_button.setEnabled(False)
        self.customize_template_button.setToolTip("A short, guided wizard over this template's key settings; "
                                                  "the template file is never modified.")
        self.customize_template_button.clicked.connect(self._on_customize_selected)
        buttons.addWidget(self.open_template_button)
        buttons.addWidget(self.customize_template_button)
        buttons.addStretch(1)
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setTextFormat(Qt.TextFormat.RichText)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.description_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details_empty = set_role(QLabel("Pick a template to read what it shows. Enter or a double-click "
                                             "opens it."), tone="secondary")
        self.details_empty.setWordWrap(True)
        column.addWidget(self.details_empty)
        column.addWidget(self.description_title)
        column.addWidget(self.description_meta)
        column.addLayout(buttons)
        column.addWidget(self.description_label)
        column.addStretch(1)
        self.description_scroll = QScrollArea()
        self.description_scroll.setObjectName("homeDetails")
        self.description_scroll.setWidgetResizable(True)
        self.description_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # its contents take the focus, not the frame
        self.description_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.description_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.description_scroll.setWidget(card)
        self.description_scroll.setMinimumWidth(240)  # [px]
        return self.description_scroll

    def _show_details(self, card: Optional[TemplateCard]) -> None:
        self.details_empty.setVisible(card is None)
        self.description_title.setText(card.name if card is not None else "")
        self.description_meta.setText(
            f"{card.type_label.text()}\n{card.orbit_label.text()}" if card is not None else "")
        self.description_label.setText(description_html(card.description) if card is not None else "")
        self.open_template_button.setEnabled(card is not None)
        self.customize_template_button.setEnabled(card is not None and card.customize_button is not None)
        if card is not None:
            self.open_template_button.setToolTip(f"Open '{card.name}' (Enter on its card)")

    # -- the commands ------------------------------------------------------------
    def _on_open_template_clicked(self) -> None:
        if self._selected is not None:
            self.path_chosen.emit(self._selected.path)

    def _on_customize_selected(self) -> None:
        if self._selected is not None:
            self._on_customize_card(self._selected.name)

    def _on_customize_card(self, name: str, _path=None) -> None:
        """A card's own Customize...: acts on that card's template, whatever
        is selected."""
        path, spec = self._template_paths[name], self._specs.get(name)
        if spec is None:
            return
        try:
            scenario = load_scenario(path)
        except Exception as exc:  # noqa: BLE001 -- surface ANY failure in a dialog, never crash the GUI
            _logger.exception("Could not load template %s for the customize wizard", path)
            report(self, f"Could not open the template {path.name}: {exc}")
            return
        wizard = TemplateCustomizeWizard(scenario, spec, self)
        if wizard.exec() == TemplateCustomizeWizard.DialogCode.Accepted:
            self.scenario_customized.emit(wizard.result_scenario())

    def _on_browse_clicked(self) -> None:
        path_str, _selected_filter = QFileDialog.getOpenFileName(self, "Open scenario", "", _FILE_FILTER)
        if path_str:
            self.path_chosen.emit(Path(path_str))


HomePage = LoadScenarioWidget  # what the page is since M3; the old name stays for its callers
