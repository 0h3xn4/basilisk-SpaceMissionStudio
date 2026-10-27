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
"""The Plotly template and web-page styling, generated from the tokens.

Every Plotly figure in the GUI takes :func:`layout` (or its pieces): Inter,
a transparent background over ``bg.surface``, gridlines in
``border.subtle``, axis text in ``text.secondary`` and the categorical
palette as the colourway. Axis titles carry their units; that is the
caller's text. :func:`page_css` styles the HTML page a ``QWebEngineView``
shows around the figures, with the bundled fonts as ``@font-face`` rules
(local files: nothing is fetched).
"""

from __future__ import annotations


from .fonts import FONTS_DIR
from .typography import SIZE, WEB_FONT_STACK, WEB_MONO_STACK, WEIGHT

TRANSPARENT = "rgba(0,0,0,0)"
_FACES = (
    ("Inter", WEIGHT["regular"], "inter/Inter-Regular.ttf"),
    ("Inter", WEIGHT["medium"], "inter/Inter-Medium.ttf"),
    ("Inter", WEIGHT["semibold"], "inter/Inter-SemiBold.ttf"),
    ("JetBrains Mono", WEIGHT["regular"], "jetbrains-mono/JetBrainsMono-Regular.ttf"),
)


def font_faces() -> str:
    """``@font-face`` rules for the bundled fonts, by local file URL."""
    return " ".join(
        f"@font-face {{ font-family: '{family}'; font-weight: {weight}; "
        f"src: url('{(FONTS_DIR / path).as_uri()}') format('truetype'); }}"
        for family, weight, path in _FACES)


def axis(t: dict[str, str]) -> dict:
    """The style of one cartesian axis."""
    return dict(
        gridcolor=t["border.subtle"], zerolinecolor=t["border.strong"], linecolor=t["border.subtle"],
        tickfont=dict(color=t["text.secondary"], size=SIZE["small"]),
        title_font=dict(color=t["text.secondary"], size=SIZE["small"]),
    )


def title(t: dict[str, str], text: str, subtitle: str = "", size: str = "section") -> dict:
    """A figure or subplot title, with an optional secondary line."""
    full = text if not subtitle else (
        f"{text}<br><span style=\"font-size:{SIZE['small']}px;color:{t['text.secondary']}\">{subtitle}</span>")
    return dict(text=full, font=dict(size=SIZE[size], color=t["text.primary"], family=WEB_FONT_STACK))


def layout(t: dict[str, str], colourway: list[str]) -> dict:
    """The template layout: fonts, colours, hover labels and legend."""
    return dict(
        font=dict(family=WEB_FONT_STACK, color=t["text.primary"], size=SIZE["small"]),
        paper_bgcolor=TRANSPARENT,
        plot_bgcolor=TRANSPARENT,
        colorway=list(colourway),
        hoverlabel=dict(bgcolor=t["bg.raised"], bordercolor=t["border.strong"],
                        font=dict(family=WEB_FONT_STACK, color=t["text.primary"], size=SIZE["small"])),
        legend=dict(font=dict(color=t["text.secondary"], size=SIZE["small"])),
        xaxis=axis(t),
        yaxis=axis(t),
    )


def scene_axis(t: dict[str, str]) -> dict:
    """The style of one axis of a 3D scene."""
    return {"backgroundcolor": t["bg.surface"], "gridcolor": t["border.subtle"],
            "zerolinecolor": t["border.strong"], "color": t["text.secondary"]}


def page_css(t: dict[str, str]) -> str:
    """The CSS of a plot page: the surface, the bundled fonts, the empty
    state's text."""
    return (f"{font_faces()} html, body {{ margin: 0; height: 100%; background: {t['bg.surface']}; "
            f"color: {t['text.primary']}; font-family: {WEB_FONT_STACK}; font-size: {SIZE['body']}px; }} "
            f".empty {{ display: flex; align-items: center; justify-content: center; height: 100%; "
            f"color: {t['text.secondary']}; font-size: {SIZE['body']}px; }} "
            f"code, pre {{ font-family: {WEB_MONO_STACK}; }}")


def grid_css(t: dict[str, str], columns: int, rows: int, many: bool) -> str:
    """The CSS of the plot grid page: cells in a grid with a 4 px gap, the
    focused cell outlined in the accent when there are several."""
    css = (f"html, body {{ margin: 0; height: 100%; overflow: hidden; background: {t['bg.surface']}; }}"
           f".grid {{ display: grid; height: 100%; box-sizing: border-box; padding: 2px; gap: 4px; "
           f"grid-template-columns: repeat({columns}, minmax(0, 1fr)); "
           f"grid-template-rows: repeat({rows}, minmax(0, 1fr)); }}"
           f".cell {{ min-width: 0; min-height: 0; border: 1px solid transparent; border-radius: 6px; }}")
    if many:
        css += (f".grid.many .cell {{ border-color: {t['border.subtle']}; }} "
                f".grid.many .cell.focused {{ border-color: {t['accent']}; }}")
    return css
