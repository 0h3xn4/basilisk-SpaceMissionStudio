#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#

"""Help text in every dialog stays short and readable.

Real user feedback: long help paragraphs squeezed beside or under fields
were "cramped", and several named code fields (``phasing_keeping``,
``hs_max``, docstrings). This renders every dialog (each tab, every
optional group on) and checks each visible plain-text label: at most 160
characters and no code names. Rich-text cards (device card, template
description) are structured, scrollable content and are not checked here.
"""

import re

import pytest
import shiboken6

from test_input_borders import _CASES, _expand_everything

pytestmark = pytest.mark.requires_gui

_MAX_LABEL_CHARS = 160
_CODE_NAME = re.compile(r"\b[a-z]+_[a-z_]+\b|docstring|\w+\(\)|\bengine\.|\bschema\.")
# Where code syntax IS the content: the if/while condition is typed as a
# Python expression, so its hint has to show the names it can use.
_SYNTAX_HINTS = ("A condition, e.g.", "Available: t_s")


@pytest.fixture
def themed(qapp):
    from spacemissionstudio.gui.theme import apply_theme

    previous = qapp.styleSheet()
    apply_theme(qapp)
    yield
    qapp.setStyleSheet(previous)


def _problems(root):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    found = []
    for label in root.findChildren(QLabel):
        text = label.text().strip()
        if not label.isVisible() or not text or label.textFormat() == Qt.TextFormat.RichText or "<" in text:
            continue
        if len(text) > _MAX_LABEL_CHARS:
            found.append(f"{len(text)} chars: {text[:80]!r}")
        match = _CODE_NAME.search(text)
        if match and not text.startswith(_SYNTAX_HINTS):
            found.append(f"code name {match.group(0)!r}: {text[:80]!r}")
    return found


@pytest.mark.parametrize("factory", [factory for _, factory in _CASES], ids=[name for name, _ in _CASES])
def test_help_text_is_short_and_plain(qtbot, qapp, themed, factory):
    """Every visible help label of a dialog, on every tab, is at most 160
    characters and names no code."""
    dialog = factory()
    qtbot.addWidget(dialog)
    dialog.resize(max(dialog.width(), 1000), max(dialog.height(), 800))  # [px]
    dialog.show()
    qtbot.waitExposed(dialog)
    problems = _problems(dialog)
    for tabs in _expand_everything(dialog, qapp):
        if not shiboken6.isValid(tabs):  # the main window's hidden label form, deleted once read
            continue
        for index in range(tabs.count()):
            tabs.setCurrentIndex(index)
            qapp.processEvents()
            problems += [f"[{tabs.tabText(index)}] {p}" for p in _problems(dialog)]
    assert not sorted(set(problems)), "\n".join(sorted(set(problems)))
