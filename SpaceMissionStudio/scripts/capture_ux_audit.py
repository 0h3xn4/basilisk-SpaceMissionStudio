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

"""Screenshots of every screen and state for the UX audit (docs/ux-audit.md),
taken offscreen along the README's template 22 flow: the start page, the
Scenario Editor, every right-hand tab before and after a run, a run in
progress, stale results, an invalid field, the dialogs and menus, a
comparison of two runs, and the window at 1280 x 720 and 2560 x 1440.
Run it again after a change for the "after" pictures::

    QT_QPA_PLATFORM=offscreen python scripts/capture_ux_audit.py docs/images/ux-audit

Needs Basilisk and the support data (it runs template 22 twice).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

DEFAULT_SIZE = (1440, 900)  # [px] a common laptop screen
SIZES = {"small": (1280, 720), "large": (2560, 1440)}  # [px] the standard's acceptance sizes


def main(out: Path) -> int:
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.theme import apply_theme
    from spacemissionstudio.logging_setup import configure_logging

    apply_theme(app)
    out.mkdir(parents=True, exist_ok=True)
    configure_logging(log_dir=out / "logs")  # as the app does, so the Log tab shows the run's records
    taken = []

    def spin(duration_s: float) -> None:
        end = time.time() + duration_s
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)  # [s]

    def wait(done, limit_s: float, what: str) -> None:
        end = time.time() + limit_s
        while time.time() < end:
            app.processEvents()
            time.sleep(0.05)  # [s]
            if done():
                spin(1.0)  # [s]
                return
        raise SystemExit(f"timed out waiting for {what}")

    def save(widget, name: str) -> None:
        widget.grab().save(str(out / name))
        taken.append(name)
        print(f"wrote {out / name}")

    def dialog_shot(dialog, name: str, size=(1100, 760), settle_s: float = 1.5) -> None:
        dialog.resize(*size)
        dialog.show()
        spin(settle_s)
        save(dialog, name)
        dialog.close()

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    window.resize(*DEFAULT_SIZE)
    window.show()
    spin(2.0)  # [s]
    save(window, "01_start.png")

    def pages():
        """Every page of the workspace: the scenario tree's nodes, the other
        areas' pages (the Run and Results areas' own pages each), then the
        side panel's."""
        for path, page in window.scenario_editor.page_tree.paths():
            yield page, "Scenario_" + path.replace(" > ", "_")
        tabs_of = {"run": window.run_views, "results": window.results_views}
        for area in window.shell.page_areas():
            if area.id == "scenario":
                continue
            inner = tabs_of.get(area.id)
            for sub in range(inner.count() if inner is not None else 1):
                widget = inner.widget(sub) if inner is not None else area.page.content
                yield widget, area.label + ("_" + inner.tabText(sub) if inner is not None else "")
        for index in range(window.side_tabs.count()):
            yield window.side_tabs.widget(index), "side_" + window.side_tabs.tabText(index).split(" (")[0]

    def tab_shots(prefix: str) -> None:
        for index, (widget, label) in enumerate(pages()):
            window.show_view(widget)
            spin(1.5)  # [s]
            save(window, f"{prefix}_{index:02d}_{label.lower().replace(' ', '_')}.png")

    templates = window.load_scenario_widget.list_widget
    row = next(i for i in range(templates.count()) if templates.item(i).text().startswith("22 "))
    templates.setFocus()
    templates.setCurrentRow(row)
    spin(1.0)  # [s]
    save(window, "02_load_scenario_22.png")

    window.open_path(TEMPLATES_DIR / "22_starter_first_leo_satellite.json")
    spin(2.0)  # [s]
    save(window, "03_editor_top.png")
    editor = window.scenario_editor
    from PySide6.QtWidgets import QScrollArea

    areas = [a for a in editor.findChildren(QScrollArea) if a.verticalScrollBar().maximum() > 0]
    if areas:
        bar = areas[0].verticalScrollBar()
        for step, fraction in enumerate((0.5, 1.0), start=1):
            bar.setValue(int(bar.maximum() * fraction))
            spin(0.8)  # [s]
            save(window, f"03_editor_scrolled_{step}.png")
        bar.setValue(0)
    tab_shots("04_before_run")

    # No menu bar since M2a: the run mode's menu is the one left.
    menu = window.run_mode_menu
    menu.popup(window.run_mode_button.mapToGlobal(QPoint(0, window.run_mode_button.height())))
    spin(0.8)  # [s]
    save(menu, "05_menu_run_mode.png")
    menu.close()

    window.show_view(window.results_widget)
    window.on_run()
    spin(3.0)  # [s] the first seconds of the run
    save(window, "06_running.png")
    wait(lambda: not window._busy_progress.isVisible(), 600.0, "the run of template 22")  # [s]
    spin(2.0)  # [s]
    tab_shots("07_after_run")

    # Results stale: change the spacecraft's drag area after the run.
    window.scenario_editor.name_edit.setText("22 - edited after the run")
    spin(1.5)  # [s]
    window.show_view(window.results_widget)
    spin(1.0)  # [s]
    save(window, "08_stale_results.png")

    # An invalid field: an epoch that does not parse.
    window.scenario_editor.epoch_edit.setText("2030-13-45T99:00:00")
    spin(1.5)  # [s]
    save(window, "09_invalid_epoch.png")
    window.scenario_editor.epoch_edit.setText(window._last_run_epoch_utc or "2030-01-01T08:30:00")
    window.scenario_editor.name_edit.setText("22 - Starter: your first LEO satellite")
    spin(1.0)  # [s]

    # A second run, then a comparison of the two.
    window.on_run()
    spin(1.0)  # [s]
    wait(lambda: not window._busy_progress.isVisible(), 600.0, "the second run")  # [s]
    spin(2.0)  # [s]
    combo = window.results_widget.compare_combo
    if combo.count() > 1:
        combo.setCurrentIndex(1)
        spin(2.0)  # [s]
    window.show_view(window.results_widget)
    spin(1.0)  # [s]
    save(window, "10_compare.png")

    for name, size in SIZES.items():
        window.resize(*size)
        spin(2.0)  # [s]
        save(window, f"11_window_{name}_results.png")
        window.show_view(window.event_timeline_widget)
        spin(1.5)  # [s]
        save(window, f"11_window_{name}_events.png")
    window.resize(*DEFAULT_SIZE)
    spin(1.0)  # [s]

    # Dialogs.
    from spacemissionstudio.gui.command_palette import CommandPalette
    from spacemissionstudio.gui.ground_station_editor import GroundStationEditorDialog
    from spacemissionstudio.gui.help_dialog import ManualDialog
    from spacemissionstudio.gui.propagation_setup_dialog import PropagationSetupDialog
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.schema import load_scenario

    scenario = load_scenario(TEMPLATES_DIR / "22_starter_first_leo_satellite.json")
    dialog_shot(PropagationSetupDialog(scenario.gravity, scenario.sim_settings, scenario.space_weather,
                                       parent=window), "12_propagation_setup.png")
    sc_dialog = SpacecraftEditorDialog(config=scenario.spacecraft[0], parent=window)
    from PySide6.QtWidgets import QTabWidget

    sc_tabs = sc_dialog.findChildren(QTabWidget)[0]
    sc_dialog.resize(1100, 760)
    sc_dialog.show()
    for index in range(sc_tabs.count()):
        sc_tabs.setCurrentIndex(index)
        spin(1.0)  # [s]
        label = sc_tabs.tabText(index).lower().replace(" ", "_").replace("/", "").replace("(", "").replace(")", "")
        save(sc_dialog, f"13_spacecraft_{index:02d}_{label}.png")
    sc_dialog.close()
    dialog_shot(GroundStationEditorDialog(scenario.ground_stations[0], parent=window), "14_ground_station.png",
                size=(760, 620))
    dialog_shot(CommandPalette(window.palette_entries(), window), "15_command_palette.png", size=(720, 520))
    window.on_keyboard_shortcuts()  # Settings > Keyboard since M2a
    spin(0.8)  # [s]
    save(window, "16_shortcuts.png")
    dialog_shot(ManualDialog(window), "17_manual.png")

    # Template 23's Mission Sequence in the editor.
    window.open_path(TEMPLATES_DIR / "23_starter_complete_small_satellite.json")
    spin(2.0)  # [s]
    editor = window.scenario_editor
    editor.page_tree.tree.setCurrentItem(editor.mission_sequence_item)
    sequence = editor.mission_sequence_editor
    if sequence.tree.topLevelItemCount():
        sequence.tree.setCurrentItem(sequence.tree.topLevelItem(0))
    spin(1.0)  # [s]
    save(window, "18_mission_sequence.png")
    editor.show_json()
    spin(1.0)  # [s]
    save(window, "19_json.png")

    print(f"{len(taken)} screenshots")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/images/ux-audit")))
