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
#  of every package. Releases up to and including 2.6.0 were published
#  under the ISC licence. Basilisk, which this program uses, keeps its own
#  ISC licence and copyright holders (THIRD_PARTY_NOTICES).
#
#
"""Tests for gui.spacecraft_template_dialog.SpacecraftTemplateDialog."""

import pytest

pytestmark = pytest.mark.requires_gui


def test_description_label_wraps_instead_of_blowing_up_dialog_width(qtbot):
    """Regression guard for the same real bug fixed in
    phasing_formation_dialog.py (found via an actual user screenshot of
    that dialog) -- this dialog copied the identical top-description
    -QLabel shape, missing word-wrap the same way. See that test's own
    docstring for the full explanation.
    """
    from PySide6.QtWidgets import QLabel

    from spacemissionstudio.gui.spacecraft_template_dialog import SpacecraftTemplateDialog

    dialog = SpacecraftTemplateDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(10)

    description_labels = [w for w in dialog.findChildren(QLabel) if len(w.text()) > 100]
    assert description_labels, "expected to find the long top description QLabel"
    assert all(w.wordWrap() for w in description_labels)


def test_dialog_lists_every_template(qtbot):
    """The preset dialog lists every spacecraft preset."""
    from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES
    from spacemissionstudio.gui.spacecraft_template_dialog import SpacecraftTemplateDialog

    dialog = SpacecraftTemplateDialog()
    qtbot.addWidget(dialog)
    assert dialog.list_widget.count() == len(SPACECRAFT_TEMPLATES)


def test_dialog_defaults_to_first_template_selected(qtbot):
    """The first preset is selected, with its description shown."""
    from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES
    from spacemissionstudio.gui.spacecraft_template_dialog import SpacecraftTemplateDialog

    dialog = SpacecraftTemplateDialog()
    qtbot.addWidget(dialog)
    assert dialog.selected_template() is SPACECRAFT_TEMPLATES[0]
    assert dialog.description_label.text() == SPACECRAFT_TEMPLATES[0].description


def test_dialog_selection_changes_description(qtbot):
    """Selecting another preset shows its description."""
    from spacemissionstudio.engine.spacecraft_templates import SPACECRAFT_TEMPLATES
    from spacemissionstudio.gui.spacecraft_template_dialog import SpacecraftTemplateDialog

    dialog = SpacecraftTemplateDialog()
    qtbot.addWidget(dialog)
    dialog.list_widget.setCurrentRow(len(SPACECRAFT_TEMPLATES) - 1)
    assert dialog.selected_template() is SPACECRAFT_TEMPLATES[-1]
    assert dialog.description_label.text() == SPACECRAFT_TEMPLATES[-1].description
