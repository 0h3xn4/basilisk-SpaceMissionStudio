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
"""Help › Third-Party Licences and the licence lines of the About box (legal milestone M2)."""

from __future__ import annotations

from spacemissionstudio import legal


def test_the_window_shows_one_tab_per_licence_file(qtbot, tmp_path):
    """Each file becomes a read-only tab with its text; the app's licence comes first."""
    from spacemissionstudio.gui.licences_dialog import LicencesDialog

    first, second = tmp_path / "LICENSE", tmp_path / "NOTICES"
    first.write_text("EUROPEAN UNION PUBLIC LICENCE v. 1.2", encoding="utf-8")
    second.write_text("Inter 4.1, OFL-1.1", encoding="utf-8")
    dialog = LicencesDialog(files=[legal.LicenceFile("Licence (English)", first),
                                   legal.LicenceFile("Third-party notices", second)])
    qtbot.addWidget(dialog)
    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == ["Licence (English)", "Third-party notices"]
    view = dialog.tabs.widget(1)
    assert view.isReadOnly() and view.toPlainText() == "Inter 4.1, OFL-1.1"


def test_no_licence_file_found_says_where_they_are(qtbot):
    """A broken install gets one tab that names the files, not an empty window."""
    from spacemissionstudio.gui.licences_dialog import LicencesDialog

    dialog = LicencesDialog(files=[])
    qtbot.addWidget(dialog)
    assert dialog.tabs.count() == 1 and "THIRD_PARTY_NOTICES" in dialog.tabs.widget(0).toPlainText()


def test_the_checkout_files_open_in_the_window(qtbot):
    """From this checkout: the EUPL in English and German and the notices."""
    from spacemissionstudio.gui.licences_dialog import LicencesDialog

    dialog = LicencesDialog()
    qtbot.addWidget(dialog)
    texts = [dialog.tabs.widget(i).toPlainText() for i in range(dialog.tabs.count())]
    assert texts[0].startswith("EUROPEAN UNION PUBLIC LICENCE v. 1.2")
    assert any(text.startswith("THIRD-PARTY NOTICES") for text in texts)
