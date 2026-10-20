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

"""The Results plot grid as one web page (docs/ux-audit.md U-24, U-28,
decision 4: keep Plotly, several figures in one page).

:func:`build_page` lays the figures out in a CSS grid, one ``div`` each
(:func:`div_id`; the first keeps the id the single plot always had). The
page script:

- links the x axes: zooming or panning one plot (or a double-click
  reset) does the same to every other linked plot (the access timeline,
  always in elapsed hours, is not linked);
- reports clicks, hovers and focus changes to Qt through the page title
  (:func:`parse_message`; the app has no QWebChannel), hovers at most
  every 80 ms;
- marks the selected plot (:func:`focus_script`) and draws the shared
  time cursor on every plot (:func:`cursor_script`) without a reload.
"""

from __future__ import annotations

import json
import math
from typing import List, Optional, Tuple

from .theme import TOKENS
from .theme.plotly_template import grid_css

# name: (rows, columns), in the order the Layout box offers them
LAYOUTS = {"1x1": (1, 1), "2x1": (2, 1), "1x2": (1, 2), "3x1": (3, 1), "1x3": (1, 3), "2x2": (2, 2), "3x2": (3, 2),
           "2x3": (2, 3)}
MAX_PLOTS = max(rows * columns for rows, columns in LAYOUTS.values())

PLOT_DIV_ID = "spacemissionstudio-plot"
CLICK_MESSAGE = "spacemissionstudio-cursor:"
HOVER_MESSAGE = "spacemissionstudio-hover:"
FOCUS_MESSAGE = "spacemissionstudio-focus:"
CURSOR_SHAPE = "spacemissionstudio-cursor"
_HOVER_INTERVAL_MS = 80  # [ms] at most one hover report this often


def layout_label(name: str) -> str:
    """ "2x2" -> "2 × 2"."""
    rows, columns = LAYOUTS[name]
    return f"{rows} × {columns}"


def smallest_layout(count: int) -> str:
    """The layout with the fewest cells that holds ``count`` plots, tall
    before wide: time plots stacked share their x axis best, and a narrow
    window keeps them readable."""
    count = max(1, count)
    fitting = [name for name, (rows, columns) in LAYOUTS.items() if rows * columns >= count]
    return min(fitting, key=lambda name: (LAYOUTS[name][0] * LAYOUTS[name][1], -LAYOUTS[name][0])) if fitting \
        else "3x2"


_PREFERRED_CELL_ASPECT = 2.0  # [-] width / height: time plots read best about twice as wide as tall
_SPARE_CELL_COST = 0.4  # [-] an empty cell costs as much as cells ~1.5 times too wide or too tall


def best_layout(count: int, width: float, height: float) -> str:
    """The layout for ``count`` plots in a ``width`` x ``height`` [px] area:
    of those that hold them with at most one cell to spare, the one whose
    cells are closest to twice as wide as tall, an empty cell counting
    against it (fewest cells on a tie). So three plots in a wide, short
    pane share a 2 x 2 grid rather than three thin strips, and two in a
    tall pane stack. Without a size, :func:`smallest_layout`."""
    count = max(1, min(count, MAX_PLOTS))
    if width <= 0 or height <= 0:
        return smallest_layout(count)
    fitting = [name for name, (rows, columns) in LAYOUTS.items() if count <= rows * columns <= count + 1]

    def score(name: str):
        rows, columns = LAYOUTS[name]
        aspect = (width / columns) / (height / rows)
        return (abs(math.log(aspect / _PREFERRED_CELL_ASPECT)) + _SPARE_CELL_COST * (rows * columns - count),
                rows * columns)

    return min(fitting, key=score) if fitting else smallest_layout(count)


def capacity(name: str) -> int:
    rows, columns = LAYOUTS[name]
    return rows * columns


def div_id(index: int) -> str:
    return PLOT_DIV_ID if index == 0 else f"{PLOT_DIV_ID}-{index}"


def parse_message(title: str) -> Optional[Tuple[str, int, Optional[str]]]:
    """``(kind, plot index, x)`` from a page title the script set, kind
    "click", "hover" or "focus" (``x`` None for a focus, and for a hover
    that left the plot), or None for any other title."""
    for kind, prefix in (("click", CLICK_MESSAGE), ("hover", HOVER_MESSAGE), ("focus", FOCUS_MESSAGE)):
        if title.startswith(prefix):
            body = title[len(prefix):].rsplit("|", 1)[0]
            index_text, _, x = body.partition("@")
            try:
                index = int(index_text)
            except ValueError:
                return None
            return kind, index, (x if x else None)
    return None


def build_page(figure_json: List[str], layout: str, focused: int, linked: List[bool], plotly_src: str,
               style: str) -> str:
    """The page for ``figure_json`` (``go.Figure.to_json()`` of each plot,
    in grid order); ``linked[i]`` links plot ``i``'s x axis with the
    others; ``plotly_src`` the local plotly.js URL; ``style`` extra CSS
    (fonts, margins)."""
    rows, columns = LAYOUTS.get(layout, (1, 1))
    cells = "".join(f'<div id="{div_id(i)}" class="cell{" focused" if i == focused else ""}"></div>'
                    for i in range(len(figure_json)))
    css = f"<style>{grid_css(TOKENS, columns, rows, len(figure_json) > 1)}</style>"
    script = f"""<script>
var FIGS = [{", ".join(figure_json)}];
var LINKED = {json.dumps(list(linked))};
var IDS = {json.dumps([div_id(i) for i in range(len(figure_json))])};
var CONFIG = {{displaylogo: false, responsive: true}};
var sent = 0, lastHover = 0, pointClicked = false, syncing = false;
function send(message) {{ sent += 1; document.title = message + '|' + sent; }}
function others(gd) {{
    return IDS.map(function(id) {{ return document.getElementById(id); }})
              .filter(function(o, i) {{ return o !== gd && LINKED[i]; }});
}}
function linkAxes(gd, i) {{
    gd.on('plotly_relayout', function(ev) {{
        if (syncing || !LINKED[i] || !ev) {{ return; }}
        var update = null;
        if (ev['xaxis.range[0]'] !== undefined) {{
            update = {{'xaxis.range': [ev['xaxis.range[0]'], ev['xaxis.range[1]']]}};
        }} else if (ev['xaxis.range']) {{
            update = {{'xaxis.range': ev['xaxis.range']}};
        }} else if (ev['xaxis.autorange']) {{
            update = {{'xaxis.autorange': true}};
        }}
        if (!update) {{ return; }}
        syncing = true;
        Promise.all(others(gd).map(function(o) {{ return Plotly.relayout(o, update); }}))
            .then(function() {{ syncing = false; }}, function() {{ syncing = false; }});
    }});
}}
IDS.forEach(function(id, i) {{
    var fig = FIGS[i];
    Plotly.newPlot(id, fig.data, fig.layout, CONFIG).then(function(gd) {{
        gd.on('plotly_click', function(ev) {{
            if (ev && ev.points && ev.points.length) {{
                pointClicked = true;
                send({CLICK_MESSAGE!r} + i + '@' + ev.points[0].x);
            }}
        }});
        gd.on('plotly_hover', function(ev) {{
            var now = Date.now();
            if (now - lastHover < {_HOVER_INTERVAL_MS} || !ev || !ev.points || !ev.points.length) {{ return; }}
            lastHover = now;
            send({HOVER_MESSAGE!r} + i + '@' + ev.points[0].x);
        }});
        gd.on('plotly_unhover', function() {{ send({HOVER_MESSAGE!r} + i + '@'); }});
        gd.addEventListener('click', function() {{
            setTimeout(function() {{
                if (!pointClicked) {{ send({FOCUS_MESSAGE!r} + i); }}
                pointClicked = false;
            }}, 30);
        }});
        linkAxes(gd, i);
    }});
}});
</script>"""
    grid_class = "grid many" if len(figure_json) > 1 else "grid"
    return (f'<!doctype html><html><head><meta charset="utf-8"><script src="{plotly_src}"></script>{style}{css}'
            f'</head><body><div class="{grid_class}">{cells}</div>{script}</body></html>')


def focus_script(focused: int) -> str:
    """Mark plot ``focused`` as the selected one."""
    return f"""(function() {{
    document.querySelectorAll('.cell').forEach(function(cell, i) {{
        cell.classList.toggle('focused', i === {int(focused)});
    }});
}})();"""


def cursor_script(x_literals: List[str], color: str) -> str:
    """Draw the cursor line at ``x_literals[i]`` (a JavaScript value, or
    ``null`` for none) on plot ``i``, without a reload."""
    return f"""(function() {{
    var xs = [{", ".join(x_literals)}];
    if (typeof Plotly === 'undefined') {{ return; }}
    xs.forEach(function(x, i) {{
        var gd = document.getElementById({json.dumps(PLOT_DIV_ID)} + (i === 0 ? '' : '-' + i));
        if (!gd || !gd.layout) {{ return; }}
        var shapes = (gd.layout.shapes || []).filter(function(s) {{ return s.name !== {CURSOR_SHAPE!r}; }});
        if (x !== null) {{
            shapes.push({{type: 'line', name: {CURSOR_SHAPE!r}, xref: 'x', yref: 'paper', x0: x, x1: x,
                          y0: 0, y1: 1, line: {{color: {color!r}, width: 2}}}});
        }}
        Plotly.relayout(gd, {{shapes: shapes}});
    }});
}})();"""
