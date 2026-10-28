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
"""The application style sheet, generated from the tokens.

One sheet, set on the ``QApplication``: no widget styles itself. A widget
picks its look through dynamic properties, the documented way to add a
custom selector to Qt Style Sheets (set them with :func:`theme.set_role`,
which re-polishes a widget already shown):

* ``role``: what a label or frame is. ``caption``, ``heading``,
  ``section-title``, ``page-title``, ``display``, ``strong``, ``mono``,
  ``empty`` (an empty state), ``hint`` (a note box), ``card`` (a raised
  tile), ``toast``, ``banner``, ``chip``.
* ``tone``: the colour of its text. ``secondary``, ``muted``, ``link`` or a
  status: ``critical``, ``serious``, ``caution``, ``normal``, ``standby``,
  ``off``.
* ``badge``: a status pill, one of the statuses.
* ``variant``: a button's kind, ``primary``, ``secondary`` (the default),
  ``ghost`` or ``danger``.

Qt Style Sheets are a limited CSS dialect (Qt docs, "Qt Style Sheets
Reference"): no shadows, no outline outside the border, no transitions.
A focused field draws its 2 px ring as its border, with the padding
reduced by 1 px so the text does not move.
"""

from __future__ import annotations

from collections.abc import Sequence

from . import icons
from .typography import BORDER, CONTROL_HEIGHT, FOCUS_RING, MONO_FONT_FAMILY, RADIUS, SIZE, SPACE, WEIGHT

_STATUSES = ("critical", "serious", "caution", "normal", "standby", "off")


def _url(name: str, colour: str, stroke_width: float | None = None) -> str:
    # Qt's url() wants forward slashes on every platform, Windows included.
    return icons.icon_file(name, colour, stroke_width).as_posix()


def stylesheet(t: dict[str, str], series: Sequence[str] = ()) -> str:
    """The style sheet for the tokens ``t`` (one theme's tokens) and its
    categorical palette ``series``."""
    px = lambda value: f"{value}px"  # noqa: E731 -- a short local formatter
    control_h = CONTROL_HEIGHT["default"]
    compact_h = CONTROL_HEIGHT["compact"]
    pad_y = (control_h - 2 * BORDER - SIZE["body"] - 4) // 2  # 4: the line's leading
    pad_x = SPACE["sm"]
    ring = FOCUS_RING - BORDER
    r_ctl, r_panel = px(RADIUS["control"]), px(RADIUS["panel"])
    semibold, medium = WEIGHT["semibold"], WEIGHT["medium"]
    chevron_down = _url("chevron-down", t["text.secondary"])
    chevron_up = _url("chevron-up", t["text.secondary"])
    chevron_down_off = _url("chevron-down", t["text.disabled"])
    chevron_up_off = _url("chevron-up", t["text.disabled"])
    chevron_right = _url("chevron-right", t["text.secondary"])
    tick = _url("check", t["text.on_accent"], 3)
    tick_off = _url("check", t["text.disabled"], 3)

    tones = "\n".join(
        f'QLabel[tone="{name}"], QCheckBox[tone="{name}"] {{ color: {t[f"status.{name}.text"]}; }}'
        for name in _STATUSES)
    badges = "\n".join(
        f'QLabel[badge="{name}"], QPushButton[badge="{name}"] {{ background-color: {t[f"status.{name}.soft"]}; '
        f'color: {t[f"status.{name}.text"] if name != "off" else t["text.secondary"]}; }}'
        for name in _STATUSES)
    toasts = "\n".join(
        f'QLabel[role="toast"][tone="{name}"] {{ background-color: {t[f"status.{name}.soft"]}; '
        f'border-color: {t[f"status.{name}"]}; color: {t["text.primary"]}; }}'
        for name in _STATUSES)
    swatches = "\n".join(
        f'QCheckBox[series="{index}"] {{ border-left: {px(SPACE["md"] - 2)} solid {colour}; '
        f'padding-left: {px(SPACE["xs"])}; }}' for index, colour in enumerate(series))
    chips = "\n".join(
        f'QLabel#statusChip[state="{state}"] {{ background-color: {t[f"status.{name}.soft"]}; '
        f'color: {t[f"status.{name}.text"] if name != "off" else t["text.secondary"]}; }}'
        for state, name in (("idle", "off"), ("running", "standby"), ("done", "normal"), ("failed", "critical"),
                            ("cancelled", "caution")))

    return f"""
/* ---- base: text colour, selection and the font come from the
   application palette and font (theme/apply.py); no QWidget rule, which
   would make Qt restyle every widget on a theme switch for nothing. ---- */
QMainWindow, QDialog, QWizard {{
    background-color: {t['bg.canvas']};
}}
QLabel, QCheckBox, QRadioButton, QStackedWidget, QStackedWidget > QWidget {{
    background: transparent;
}}
QToolTip {{
    background-color: {t['bg.raised']};
    color: {t['text.primary']};
    border: {px(BORDER)} solid {t['border.strong']};
    border-radius: {r_ctl};
    padding: {px(SPACE['xs'])} {px(SPACE['sm'])};
}}

/* ---- text roles and tones ------------------------------------------- */
QLabel[role="caption"] {{ font-size: {px(SIZE['caption'])}; color: {t['text.secondary']}; }}
QLabel[role="small"] {{ font-size: {px(SIZE['small'])}; }}
QLabel[role="heading"], QLabel[role="strong"] {{ font-weight: {semibold}; }}
QLabel[role="section-title"], QLabel#sectionTitle {{
    font-size: {px(SIZE['section'])}; font-weight: {semibold}; padding: {px(SPACE['xs'])} 0px;
}}
QLabel[role="page-title"] {{ font-size: {px(SIZE['page'])}; font-weight: {semibold}; }}
QLabel[role="display"] {{ font-size: {px(SIZE['display'])}; font-weight: {semibold}; }}
QLabel[role="value"] {{ font-size: {px(SIZE['section'])}; font-weight: {semibold}; }}
QLabel[role="mono"] {{ font-family: "{MONO_FONT_FAMILY}"; font-size: {px(SIZE['small'])}; }}
QLabel[role="empty"], QLabel#emptyState {{ color: {t['text.secondary']}; padding: {px(SPACE['xl'])}; }}
QLabel[role="hint"] {{
    background-color: {t['status.standby.soft']};
    color: {t['text.primary']};
    border-radius: {r_ctl};
    padding: {px(SPACE['sm'])} {px(SPACE['md'])};
}}
QLabel[tone="secondary"], QCheckBox[tone="secondary"] {{ color: {t['text.secondary']}; }}
QLabel[tone="muted"] {{ color: {t['text.muted']}; }}
QLabel[tone="link"] {{ color: {t['text.link']}; }}
{tones}
{swatches}

/* ---- status badges --------------------------------------------------- */
QLabel[badge], QPushButton[badge] {{
    border: none;
    border-radius: {px(SPACE['md'] - 2)};
    padding: 1px {px(SPACE['sm'])};
    font-size: {px(SIZE['small'])};
    font-weight: {medium};
}}
{badges}
QLabel#statusChip {{
    border-radius: {px(SPACE['md'] - 2)};
    padding: 1px {px(SPACE['sm'] + 2)};
    font-size: {px(SIZE['small'])};
    font-weight: {medium};
}}
{chips}
QLabel#statusItem[state="warning"], QToolButton#statusDataButton[state="warning"] {{
    color: {t['status.caution.text']};
}}

/* ---- toasts and banners ----------------------------------------------- */
QLabel[role="toast"] {{
    border: {px(BORDER)} solid {t['border.strong']};
    border-radius: {r_panel};
    padding: {px(SPACE['sm'] + 2)} {px(SPACE['lg'])};
    font-weight: {medium};
}}
{toasts}
QFrame#problemBanner, QFrame[role="banner"][tone="critical"] {{
    background-color: {t['status.critical.soft']};
    border: none;
    border-radius: {r_panel};
}}
QFrame#problemBanner QLabel {{ color: {t['status.critical.text']}; }}
QFrame#staleResultsBanner, QFrame[role="banner"][tone="caution"] {{
    background-color: {t['status.caution.soft']};
    border: none;
    border-radius: {r_panel};
}}
QFrame#staleResultsBanner QLabel {{ color: {t['text.primary']}; }}

/* ---- surfaces: cards, panels ----------------------------------------- */
QFrame[role="card"] {{
    background-color: {t['bg.surface']};
    border: {px(BORDER)} solid {t['border.subtle']};
    border-radius: {r_panel};
}}
QFrame[role="card"] QLabel {{ border: none; }}
/* A template card on Home: hover, selected (the accent edge) and focus
   (the 2 px ring; the 1 px margin keeps its content from moving). */
QFrame#templateCard {{ margin: {px(FOCUS_RING - BORDER)}; }}
QFrame#templateCard:hover {{ background-color: {t['bg.hover']}; }}
QFrame#templateCard[selected="true"] {{ background-color: {t['bg.selected']}; border-color: {t['accent']}; }}
QFrame#templateCard:focus {{ border: {px(FOCUS_RING)} solid {t['border.focus']}; margin: 0px; }}
QFrame#templateCard[selected="true"] QPushButton[variant="ghost"] {{ color: {t['text.primary']}; }}
QFrame[role="recessed"], QScrollArea#paramReference {{
    background-color: {t['bg.canvas']};
    border: {px(BORDER)} solid {t['border.subtle']};
    border-radius: {r_panel};
}}
QScrollArea#paramReference > QWidget > QWidget {{ background-color: {t['bg.canvas']}; }}

/* ---- group boxes: a heading, not a frame (no boxes in boxes) ---------- */
QGroupBox {{
    background: transparent;
    border: none;
    margin-top: {px(SPACE['xl'])};
    padding-top: {px(SPACE['xs'])};
    font-weight: {semibold};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 0px;
    padding: 0px 0px {px(SPACE['xs'])} 0px;
    color: {t['text.primary']};
}}

/* ---- buttons --------------------------------------------------------- */
QPushButton {{
    background-color: {t['bg.surface']};
    color: {t['text.primary']};
    border: {px(BORDER)} solid {t['border.strong']};
    border-radius: {r_ctl};
    padding: {px(pad_y)} {px(SPACE['md'])};
    min-height: {px(SIZE['body'] + 4)};
    font-weight: {medium};
}}
QPushButton:hover {{ background-color: {t['bg.hover']}; }}
QPushButton:pressed {{ background-color: {t['bg.selected']}; }}
QPushButton:focus {{
    border: {px(FOCUS_RING)} solid {t['border.focus']};
    padding: {px(pad_y - ring)} {px(SPACE['md'] - ring)};
}}
QPushButton:disabled {{
    color: {t['text.disabled']};
    background-color: {t['bg.surface']};
    border-color: {t['border.subtle']};
}}
QPushButton:default, QPushButton[primary="true"], QPushButton[variant="primary"] {{
    background-color: {t['accent']};
    border: {px(BORDER)} solid {t['accent']};
    color: {t['text.on_accent']};
}}
QPushButton:default:hover, QPushButton[primary="true"]:hover, QPushButton[variant="primary"]:hover {{
    background-color: {t['accent.hover']};
    border-color: {t['accent.hover']};
}}
QPushButton:default:pressed, QPushButton[primary="true"]:pressed, QPushButton[variant="primary"]:pressed {{
    background-color: {t['accent.pressed']};
    border-color: {t['accent.pressed']};
}}
QPushButton:default:focus, QPushButton[primary="true"]:focus, QPushButton[variant="primary"]:focus {{
    border: {px(FOCUS_RING)} solid {t['text.primary']};
}}
QPushButton:default:disabled, QPushButton[primary="true"]:disabled, QPushButton[variant="primary"]:disabled {{
    background-color: {t['bg.hover']};
    border-color: {t['bg.hover']};
    color: {t['text.disabled']};
}}
QPushButton[variant="ghost"], QPushButton#rowCustomizeButton {{
    background-color: transparent;
    border: {px(BORDER)} solid transparent;
    color: {t['text.link']};
    padding: 1px {px(SPACE['sm'])};
    min-height: 0px;
}}
QPushButton[variant="ghost"]:hover, QPushButton#rowCustomizeButton:hover {{ background-color: {t['bg.hover']}; }}
QPushButton[variant="danger"] {{
    color: {t['status.critical.text']};
    border-color: {t['status.critical']};
}}
QPushButton[variant="danger"]:hover {{ background-color: {t['status.critical.soft']}; }}
QPushButton[role="chip"], QPushButton#suggestionChip {{
    background-color: {t['bg.surface']};
    border: {px(BORDER)} solid {t['border.subtle']};
    border-radius: {px(SPACE['md'] - 2)};
    padding: 1px {px(SPACE['sm'] + 2)};
    min-height: 0px;
    font-weight: {WEIGHT['regular']};
}}
QPushButton[role="chip"]:hover, QPushButton#suggestionChip:hover {{ border-color: {t['accent']}; }}
QPushButton[role="chip"]:checked, QPushButton#suggestionChip:checked {{
    background-color: {t['bg.selected']};
    border-color: {t['accent']};
}}
QPushButton[badge] {{ text-decoration: underline; }}
QPushButton[badge]:hover {{ border: none; }}

/* ---- segmented control ------------------------------------------------ */
QFrame#segmentedControl {{
    background-color: {t['bg.hover']};
    border-radius: {r_ctl};
}}
QFrame#segmentedControl QPushButton#segmentButton {{
    background-color: transparent;
    color: {t['text.secondary']};
    border: {px(BORDER)} solid transparent;
    border-radius: {px(RADIUS['control'] - 2)};
    padding: {px(pad_y - 2)} {px(SPACE['md'])};
    margin: 2px;
    min-height: 0px;
}}
QFrame#segmentedControl QPushButton#segmentButton:hover {{ color: {t['text.primary']}; }}
QFrame#segmentedControl QPushButton#segmentButton:checked {{
    background-color: {t['bg.surface']};
    color: {t['text.primary']};
    border-color: {t['border.subtle']};
}}

/* ---- fields ------------------------------------------------------------ */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateTimeEdit {{
    background-color: {t['bg.field']};
    border: {px(BORDER)} solid {t['border.control']};
    border-radius: {r_ctl};
    padding: {px(pad_y)} {px(pad_x)};
}}
QComboBox, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QLineEdit {{ min-height: {px(SIZE['body'] + 4)}; }}
QLineEdit:hover, QPlainTextEdit:hover, QTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover,
QComboBox:hover, QDateTimeEdit:hover {{
    border-color: {t['text.muted']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QDateTimeEdit:focus {{
    border: {px(FOCUS_RING)} solid {t['border.focus']};
    padding: {px(pad_y - ring)} {px(pad_x - ring)};
}}
QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled, QSpinBox:disabled,
QDoubleSpinBox:disabled, QComboBox:disabled, QDateTimeEdit:disabled {{
    color: {t['text.disabled']};
    background-color: {t['bg.canvas']};
    border-color: {t['border.subtle']};
}}
QLineEdit:read-only {{
    background-color: {t['bg.canvas']};
    border-color: {t['border.subtle']};
}}
QLineEdit[state="error"], QDoubleSpinBox[state="error"], QSpinBox[state="error"], QComboBox[state="error"],
QLineEdit[state="error"]:focus, QDoubleSpinBox[state="error"]:focus, QSpinBox[state="error"]:focus,
QComboBox[state="error"]:focus {{
    border: {px(FOCUS_RING)} solid {t['status.critical']};
    padding: {px(pad_y - ring)} {px(pad_x - ring)};
}}
QPlainTextEdit[state="error"], QListWidget[state="error"], QTableWidget[state="error"] {{
    border: {px(FOCUS_RING)} solid {t['status.critical']};
}}
QLineEdit[state="warning"], QDoubleSpinBox[state="warning"], QSpinBox[state="warning"],
QComboBox[state="warning"], QLineEdit[state="warning"]:focus, QDoubleSpinBox[state="warning"]:focus,
QSpinBox[state="warning"]:focus, QComboBox[state="warning"]:focus {{
    border: {px(FOCUS_RING)} solid {t['status.caution']};
    padding: {px(pad_y - ring)} {px(pad_x - ring)};
}}
QLabel#fieldError {{ color: {t['status.critical.text']}; font-size: {px(SIZE['small'])}; }}
QLabel#fieldWarning {{ color: {t['status.caution.text']}; font-size: {px(SIZE['small'])}; }}
QPlainTextEdit#logText, QPlainTextEdit#jsonEdit, QPlainTextEdit[role="mono"], QTextEdit[role="mono"] {{
    font-family: "{MONO_FONT_FAMILY}";
    font-size: {px(SIZE['small'])};
}}
QComboBox::drop-down {{
    border: none;
    width: {px(control_h - SPACE['xs'])};
}}
QComboBox::down-arrow {{
    image: url({chevron_down});
    width: {px(SIZE['body'] + 1)};
    height: {px(SIZE['body'] + 1)};
}}
QComboBox::down-arrow:disabled {{ image: url({chevron_down_off}); }}
QComboBox QAbstractItemView {{
    background-color: {t['bg.raised']};
    border: {px(BORDER)} solid {t['border.subtle']};
    selection-background-color: {t['bg.hover']};
    selection-color: {t['text.primary']};
    outline: none;
    padding: {px(SPACE['xs'])};
}}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
    width: {px(SPACE['lg'] + 2)};
    border: none;
    background: transparent;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QDateTimeEdit::up-arrow {{
    image: url({chevron_up}); width: {px(SPACE['md'])}; height: {px(SPACE['md'])};
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QDateTimeEdit::down-arrow {{
    image: url({chevron_down}); width: {px(SPACE['md'])}; height: {px(SPACE['md'])};
}}
QSpinBox::up-arrow:disabled, QDoubleSpinBox::up-arrow:disabled, QSpinBox::up-arrow:off,
QDoubleSpinBox::up-arrow:off {{ image: url({chevron_up_off}); }}
QSpinBox::down-arrow:disabled, QDoubleSpinBox::down-arrow:disabled, QSpinBox::down-arrow:off,
QDoubleSpinBox::down-arrow:off {{ image: url({chevron_down_off}); }}

/* ---- lists, trees, tables ------------------------------------------------ */
QListWidget, QTreeWidget, QListView, QTreeView, QTableWidget, QTableView {{
    background-color: {t['bg.surface']};
    alternate-background-color: {t['bg.surface']};
    border: {px(BORDER)} solid {t['border.subtle']};
    border-radius: {r_panel};
    outline: none;
    gridline-color: {t['border.subtle']};
    selection-background-color: {t['bg.selected']};
    selection-color: {t['text.primary']};
}}
QListWidget::item, QTreeWidget::item, QListView::item, QTreeView::item {{
    padding: {px(SPACE['xs'])} {px(SPACE['xs'] + 2)};
    border: none;
}}
QListWidget::item:selected, QTreeWidget::item:selected, QListView::item:selected, QTreeView::item:selected,
QTableView::item:selected {{
    background-color: {t['bg.selected']};
    color: {t['text.primary']};
}}
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected, QListView::item:hover:!selected,
QTreeView::item:hover:!selected, QTableView::item:hover:!selected {{
    background-color: {t['bg.hover']};
}}
QTreeView::branch {{ background: transparent; }}
QTreeView::branch:has-children:!has-siblings:closed, QTreeView::branch:closed:has-children:has-siblings {{
    image: url({chevron_right});
}}
QTreeView::branch:open:has-children:!has-siblings, QTreeView::branch:open:has-children:has-siblings {{
    image: url({chevron_down});
}}
QHeaderView {{ background-color: transparent; border: none; }}
QHeaderView::section {{
    background-color: {t['bg.surface']};
    color: {t['text.secondary']};
    font-size: {px(SIZE['small'])};
    font-weight: {semibold};
    border: none;
    border-bottom: {px(BORDER)} solid {t['border.subtle']};
    padding: {px(SPACE['xs'] + 2)} {px(SPACE['sm'])};
}}
QTableCornerButton::section {{
    background-color: {t['bg.surface']};
    border: none;
    border-bottom: {px(BORDER)} solid {t['border.subtle']};
}}

/* ---- tabs: line tabs ------------------------------------------------------ */
QTabWidget::pane {{
    background-color: transparent;
    border: none;
    border-top: {px(BORDER)} solid {t['border.subtle']};
    top: -{px(BORDER)};
}}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background-color: transparent;
    color: {t['text.secondary']};
    padding: {px(SPACE['sm'])} {px(SPACE['md'])};
    border: none;
    border-bottom: {px(FOCUS_RING)} solid transparent;
    font-weight: {medium};
}}
QTabBar::tab:selected {{
    color: {t['text.primary']};
    border-bottom: {px(FOCUS_RING)} solid {t['accent']};
}}
QTabBar::tab:hover:!selected {{ color: {t['text.primary']}; }}
QTabBar::tab:disabled {{ color: {t['text.disabled']}; }}

/* ---- scroll areas and scroll bars ---------------------------------------- */
QScrollArea {{ border: none; background-color: transparent; }}
QScrollArea > QWidget > QWidget {{ background-color: transparent; }}
QScrollBar:vertical {{ background: transparent; width: {px(SPACE['md'] - 2)}; margin: 0px; }}
QScrollBar:horizontal {{ background: transparent; height: {px(SPACE['md'] - 2)}; margin: 0px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {t['border.strong']};
    border-radius: {px(SPACE['xs'])};
    margin: 2px;
}}
QScrollBar::handle:vertical {{ min-height: {px(SPACE['xl'])}; }}
QScrollBar::handle:horizontal {{ min-width: {px(SPACE['xl'])}; }}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{ background: {t['text.muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- menus, toolbars, status bar, splitters -------------------------------- */
QMenuBar {{
    background-color: {t['bg.surface']};
    border-bottom: {px(BORDER)} solid {t['border.subtle']};
}}
QMenuBar::item {{
    padding: {px(SPACE['xs'] + 2)} {px(SPACE['sm'] + 2)};
    background: transparent;
    border-radius: {px(SPACE['xs'])};
}}
QMenuBar::item:selected {{ background-color: {t['bg.hover']}; }}
QMenu {{
    background-color: {t['bg.raised']};
    border: {px(BORDER)} solid {t['border.subtle']};
    border-radius: {r_panel};
    padding: {px(SPACE['xs'])};
}}
QMenu::item {{
    padding: {px(SPACE['xs'] + 2)} {px(SPACE['xl'])} {px(SPACE['xs'] + 2)} {px(SPACE['sm'])};
    border-radius: {px(SPACE['xs'])};
    background: transparent;
}}
QMenu::item:selected {{ background-color: {t['bg.hover']}; color: {t['text.primary']}; }}
QMenu::item:disabled {{ color: {t['text.disabled']}; }}
QMenu::separator {{ height: {px(BORDER)}; background: {t['border.subtle']}; margin: {px(SPACE['xs'])} 0px; }}
QMenu::icon {{ padding-left: {px(SPACE['xs'])}; }}
QToolBar {{
    background-color: {t['bg.surface']};
    border: none;
    border-bottom: {px(BORDER)} solid {t['border.subtle']};
    padding: {px(SPACE['xs'])};
    spacing: {px(SPACE['xs'])};
}}
QToolBar::separator {{ background: {t['border.subtle']}; width: {px(BORDER)}; margin: {px(SPACE['xs'])}; }}
QToolButton {{
    background-color: transparent;
    border: {px(BORDER)} solid transparent;
    border-radius: {r_ctl};
    padding: {px(SPACE['xs'])} {px(SPACE['sm'])};
    min-height: {px(compact_h - 2 * SPACE['xs'] - 2 * BORDER)};
}}
QToolButton:hover {{ background-color: {t['bg.hover']}; }}
QToolButton:pressed {{ background-color: {t['bg.selected']}; }}
QToolButton:focus {{ border-color: {t['border.focus']}; }}
QToolButton:disabled {{ color: {t['text.disabled']}; }}
QToolButton:checked {{ background-color: {t['bg.selected']}; color: {t['text.primary']}; }}
QToolButton[tertiary="true"] {{
    background-color: {t['bg.surface']};
    border: {px(BORDER)} solid {t['border.strong']};
    padding: {px(pad_y)} {px(SPACE['xl'])} {px(pad_y)} {px(SPACE['md'])};
    font-weight: {medium};
}}
QToolButton[tertiary="true"]:hover {{ background-color: {t['bg.hover']}; }}
QToolButton[tertiary="true"]:disabled {{ border-color: {t['border.subtle']}; }}
QToolButton::menu-indicator {{
    image: url({chevron_down});
    subcontrol-position: right center;
    subcontrol-origin: padding;
    right: {px(SPACE['xs'])};
    width: {px(SPACE['md'])};
    height: {px(SPACE['md'])};
}}
QToolButton#primaryToolButton {{
    background-color: {t['accent']};
    color: {t['text.on_accent']};
    font-weight: {semibold};
}}
QToolButton#primaryToolButton:hover {{ background-color: {t['accent.hover']}; }}
QToolButton#primaryToolButton:pressed {{ background-color: {t['accent.pressed']}; }}
QToolButton#primaryToolButton:disabled {{ background-color: {t['bg.hover']}; color: {t['text.disabled']}; }}
QStatusBar {{
    background-color: {t['bg.surface']};
    border-top: {px(BORDER)} solid {t['border.subtle']};
    color: {t['text.secondary']};
    font-size: {px(SIZE['small'])};
}}
QStatusBar QLabel {{ color: {t['text.secondary']}; }}
QStatusBar::item {{ border: none; }}
QFrame#statusSeparator {{
    border: none;
    border-left: {px(BORDER)} solid {t['border.subtle']};
    margin: {px(SPACE['xs'] + 2)} {px(SPACE['xs'])};
}}
QSplitter::handle {{ background-color: {t['border.subtle']}; }}
QSplitter::handle:horizontal {{ width: {px(BORDER)}; }}
QSplitter::handle:vertical {{ height: {px(BORDER)}; }}
QSplitter::handle:hover {{ background-color: {t['accent']}; }}
QDockWidget::title {{
    background-color: {t['bg.surface']};
    padding: {px(SPACE['xs'] + 2)} {px(SPACE['sm'])};
    border-bottom: {px(BORDER)} solid {t['border.subtle']};
}}

/* ---- app shell ---------------------------------------------------------------- */
QWidget#topBar {{
    background-color: {t['bg.surface']};
    border-bottom: {px(BORDER)} solid {t['border.subtle']};
}}
QLabel#topBarName {{ font-size: {px(SIZE['section'])}; font-weight: {semibold}; }}
QLabel#topBarDetail, QLabel#runTime {{ color: {t['text.secondary']}; }}
QLabel#topBarBreadcrumbs {{ color: {t['text.secondary']}; font-size: {px(SIZE['small'])}; }}
QToolButton#topBarSearch {{
    background-color: {t['bg.field']};
    border: {px(BORDER)} solid {t['border.subtle']};
    color: {t['text.secondary']};
    padding: {px(SPACE['xs'])} {px(SPACE['md'])} {px(SPACE['xs'])} {px(SPACE['sm'])};
    min-width: {px(SPACE['xxl'] * 5)};
}}
QToolButton#topBarSearch:hover {{ border-color: {t['border.strong']}; }}
QFrame#navRail {{
    background-color: {t['bg.surface']};
    border: none;
    border-right: {px(BORDER)} solid {t['border.subtle']};
}}
QToolButton#railButton {{
    color: {t['text.secondary']};
    padding: {px(SPACE['xs'] + 2)} {px(SPACE['xs'])};
    font-size: {px(SIZE['caption'])};
}}
QToolButton#railButton:checked {{
    background-color: {t['bg.selected']};
    color: {t['text.primary']};
    font-weight: {medium};
}}
QFrame#areaHeader {{
    background-color: {t['bg.canvas']};
    border: none;
}}
QFrame#runProgressStrip {{
    background-color: {t['bg.selected']};
    border-bottom: {px(BORDER)} solid {t['border.subtle']};
}}
QLabel#inspectorName {{ font-size: {px(SIZE['section'])}; font-weight: {semibold}; }}

/* ---- progress -------------------------------------------------------------- */
QProgressBar {{
    background-color: {t['bg.hover']};
    border: none;
    border-radius: 3px;
    text-align: center;
    color: {t['text.secondary']};
    max-height: {px(SPACE['xs'] + 2)};
    font-size: {px(SIZE['caption'])};
}}
QProgressBar::chunk {{ background-color: {t['accent']}; border-radius: 3px; }}

/* ---- check boxes and radio buttons ----------------------------------------- */
QCheckBox, QRadioButton {{ spacing: {px(SPACE['sm'])}; }}
QCheckBox::indicator, QGroupBox::indicator, QRadioButton::indicator, QListWidget::indicator,
QTreeWidget::indicator, QListView::indicator, QTreeView::indicator, QTableView::indicator {{
    width: {px(SIZE['body'] + 1)};
    height: {px(SIZE['body'] + 1)};
    border: {px(BORDER)} solid {t['border.control']};
    border-radius: {px(SPACE['xs'])};
    background-color: {t['bg.field']};
}}
QRadioButton::indicator {{ border-radius: {px((SIZE['body'] + 3) // 2)}; }}
QCheckBox::indicator:hover, QGroupBox::indicator:hover, QRadioButton::indicator:hover,
QListWidget::indicator:hover, QTreeWidget::indicator:hover {{
    border-color: {t['accent']};
}}
QCheckBox::indicator:focus, QRadioButton::indicator:focus {{ border: {px(FOCUS_RING)} solid {t['border.focus']}; }}
QCheckBox::indicator:checked, QGroupBox::indicator:checked, QListWidget::indicator:checked,
QTreeWidget::indicator:checked, QListView::indicator:checked, QTreeView::indicator:checked,
QTableView::indicator:checked {{
    background-color: {t['accent']};
    border-color: {t['accent']};
    image: url({tick});
}}
QCheckBox::indicator:indeterminate, QTreeWidget::indicator:indeterminate {{
    background-color: {t['accent']};
    border-color: {t['accent']};
}}
QRadioButton::indicator:checked {{
    border-color: {t['accent']};
    background-color: qradialgradient(cx: 0.5, cy: 0.5, radius: 0.5, fx: 0.5, fy: 0.5,
        stop: 0 {t['accent']}, stop: 0.42 {t['accent']}, stop: 0.5 {t['bg.field']}, stop: 1 {t['bg.field']});
}}
QCheckBox::indicator:disabled, QGroupBox::indicator:disabled, QRadioButton::indicator:disabled,
QListWidget::indicator:disabled, QTreeWidget::indicator:disabled {{
    background-color: {t['bg.canvas']};
    border-color: {t['border.subtle']};
}}
QCheckBox::indicator:checked:disabled, QGroupBox::indicator:checked:disabled,
QListWidget::indicator:checked:disabled, QTreeWidget::indicator:checked:disabled {{
    background-color: {t['bg.hover']};
    border-color: {t['border.subtle']};
    image: url({tick_off});
}}
QCheckBox:disabled, QRadioButton:disabled {{ color: {t['text.disabled']}; }}
"""
