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
"""Inline CSS for Qt rich text (labels showing HTML), from the tokens.

Qt's rich text takes a CSS subset in ``style`` attributes. A label built
from it holds the colours of the theme in use when it was built, so a
widget showing one rebuilds its text on ``signals.changed``.
"""

from __future__ import annotations

from .state import TOKENS
from .typography import SIZE, SPACE, WEIGHT


def css(kind: str) -> str:
    """The inline CSS of one rich-text element kind."""
    t = TOKENS
    sm, xs = SPACE["sm"], SPACE["xs"]
    styles = {
        "title": f"font-size:{SIZE['section']}px; font-weight:{WEIGHT['semibold']}; margin:0;",
        "meta": f"color:{t['text.secondary']}; margin:0 0 {xs + 2}px 0;",
        "para": f"margin:0 0 {xs + 2}px 0;",
        "key-cell": f"color:{t['text.secondary']}; padding:2px {sm + 2}px 2px 0; white-space:nowrap;",
        "value-cell": "padding:2px 0;",
        "note": f"color:{t['text.secondary']}; margin-top:{sm}px;",
        "heading-p": f"margin:{sm + 2}px 0 2px 0;",
        "prose-p": f"margin:0 0 {xs}px 0;",
        "list": "margin:0; -qt-list-indent:1;",
        "secondary": f"color:{t['text.secondary']};",
        "subtitle": f"font-size:{SIZE['small']}px; color:{t['text.secondary']};",
    }
    return styles[kind]


def status_css(status: str) -> str:
    """Semibold text in a status colour (``critical`` ... ``off``)."""
    return f"color:{TOKENS[f'status.{status}.text']}; font-weight:{WEIGHT['semibold']};"
