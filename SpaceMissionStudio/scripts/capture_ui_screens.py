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

"""Screenshots of every window, tab, page, menu and dialog of the GUI, for
the UI overhaul (docs/ui/UI_OVERHAUL.md): before it, after each milestone,
and after it. Offscreen, in one theme per process::

    QT_QPA_PLATFORM=offscreen python scripts/capture_ui_screens.py docs/ui/screenshots/before
    QT_QPA_PLATFORM=offscreen python scripts/capture_ui_screens.py OUT --theme dark

``--theme both`` (the default) runs the script once per theme, into
``OUT/light`` and ``OUT/dark``. The example project is template 23 (the
complete small satellite): every scenario page, a run of it (Results,
Events, Log), a second run (Compare), the Monte Carlo template 09 run as a
short batch, an End of Life estimate, every menu, and every dialog, modal ones
included (grabbed while open, then closed). Needs Basilisk and the support
data. The run history goes to a temporary folder, not ~/.spacemissionstudio.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SIZE = (1440, 900)  # [px] a common laptop screen; the window's size for every shot
DIALOG_SIZE = (1100, 760)  # [px]
EXAMPLE = "23_starter_complete_small_satellite.json"
MONTE_CARLO = "09_monte_carlo_dispersion_analysis.json"


def _slug(text: str) -> str:
    keep = "".join(c.lower() if c.isalnum() else "_" for c in text)
    while "__" in keep:
        keep = keep.replace("__", "_")
    return keep.strip("_")


def capture(out: Path, theme: str) -> int:
    from PySide6.QtCore import QPoint, QTimer
    from PySide6.QtWidgets import QApplication, QDialog, QScrollArea, QTabWidget

    app = QApplication(sys.argv[:1])
    from spacemissionstudio.engine import run_store
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.theme import apply_theme
    from spacemissionstudio.logging_setup import configure_logging

    apply_theme(app, theme)
    out.mkdir(parents=True, exist_ok=True)
    configure_logging(log_dir=Path(tempfile.mkdtemp(prefix="sms-ui-logs-")))  # not beside the screenshots
    runs = Path(tempfile.mkdtemp(prefix="sms-ui-runs-"))
    run_store.default_root = lambda: runs  # keep this capture's runs out of the user's history

    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.schema import load_scenario

    taken: list[str] = []
    counter = [0]

    def spin(duration_s: float) -> None:
        end = time.time() + duration_s
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)  # [s]

    def wait(done, limit_s: float, what: str) -> bool:
        end = time.time() + limit_s
        while time.time() < end:
            app.processEvents()
            time.sleep(0.05)  # [s]
            if done():
                spin(1.0)  # [s]
                return True
        print(f"timed out waiting for {what}", file=sys.stderr)
        return False

    def save(widget, name: str) -> None:
        counter[0] += 1
        file = f"{counter[0]:03d}_{_slug(name)}.png"
        widget.grab().save(str(out / file))
        taken.append(file)
        print(f"wrote {out / file}")

    def dialog_shot(dialog, name: str, size=DIALOG_SIZE, settle_s: float = 1.2) -> None:
        dialog.resize(*size)
        dialog.show()
        spin(settle_s)
        save(dialog, name)
        dialog.close()
        dialog.deleteLater()
        spin(0.2)  # [s]

    def modal_shot(trigger, name: str) -> None:
        """Runs ``trigger``, which opens a modal dialog; grabs and closes it."""
        def grab_and_close():
            modal = QApplication.activeModalWidget()
            if modal is None:
                print(f"no modal dialog for {name}", file=sys.stderr)
                return
            spin(0.6)  # [s]
            save(modal, name)
            if isinstance(modal, QDialog):
                modal.reject()
            else:
                modal.close()
        QTimer.singleShot(800, grab_and_close)  # [ms]
        trigger()
        spin(0.3)  # [s]

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    window.resize(*SIZE)
    window.show()
    spin(2.0)  # [s]
    save(window, "start_templates")

    def workspace(prefix: str) -> None:
        """Every scenario-tree node (pages and their sections), the other
        main tabs and the Results tab's own pages, and the side panel's
        tabs."""
        tree = window.scenario_editor.page_tree
        for path, item in tree.paths():
            window.show_view(window.scenario_editor)
            tree.tree.setCurrentItem(item)
            spin(0.8)  # [s]
            save(window, f"{prefix}_scenario_{path}")
        for main in range(1, window.main_tabs.count()):
            page = window.main_tabs.widget(main)
            label = window.main_tabs.tabText(main)
            if page is window.results_views:
                for sub in range(window.results_views.count()):
                    window.show_view(window.results_views.widget(sub))
                    spin(1.5)  # [s]
                    save(window, f"{prefix}_{label}_{window.results_views.tabText(sub)}")
            else:
                window.show_view(page)
                spin(1.2)  # [s]
                save(window, f"{prefix}_{label}")
        for index in range(window.side_tabs.count()):
            window.show_view(window.side_tabs.widget(index))
            spin(0.8)  # [s]
            save(window, f"{prefix}_side_{window.side_tabs.tabText(index).split(' (')[0]}")

    window.open_path(TEMPLATES_DIR / EXAMPLE)
    spin(2.0)  # [s]
    workspace("before_run")

    for action in window.menuBar().actions():
        menu = action.menu()
        if menu is None:
            continue
        menu.popup(window.mapToGlobal(QPoint(40, 30)))
        spin(0.6)  # [s]
        save(menu, f"menu_{action.text().strip('&')}")
        menu.close()

    window.show_view(window.results_widget)
    window.on_run()
    spin(2.5)  # [s]
    save(window, "run_in_progress")
    wait(lambda: window._run_worker is None or not window._busy_progress.isVisible(), 900.0, "the run")  # [s]
    spin(2.0)  # [s]
    workspace("after_run")

    window.scenario_editor.name_edit.setText(window.scenario_editor.name_edit.text() + " (edited)")
    spin(1.2)  # [s]
    window.show_view(window.results_widget)
    spin(1.0)  # [s]
    save(window, "stale_results")
    epoch = window.scenario_editor.epoch_edit.text()
    window.scenario_editor.epoch_edit.setText("2030-13-45T99:00:00")
    spin(1.2)  # [s]
    save(window, "invalid_field")
    window.show_view(window.problems_widget)
    spin(0.6)  # [s]
    save(window, "invalid_field_problems")
    window.scenario_editor.epoch_edit.setText(epoch)
    spin(1.0)  # [s]

    window.on_run()
    spin(1.0)  # [s]
    wait(lambda: not window._busy_progress.isVisible(), 900.0, "the second run")  # [s]
    combo = window.results_widget.compare_combo
    if combo.count() > 1:
        combo.setCurrentIndex(1)
    window.show_view(window.results_widget)
    spin(2.0)  # [s]
    save(window, "results_compared")
    window.show_view(window.compare_widget)
    spin(1.5)  # [s]
    save(window, "compare_two_runs")

    for name, size in {"1280x720": (1280, 720), "2560x1440": (2560, 1440)}.items():
        window.resize(*size)
        spin(1.5)  # [s]
        window.show_view(window.results_widget)
        spin(1.5)  # [s]
        save(window, f"window_{name}_results")
        window.show_view(window.scenario_editor)
        spin(1.0)  # [s]
        save(window, f"window_{name}_scenario")
    window.resize(*SIZE)
    spin(1.0)  # [s]

    window.open_path(TEMPLATES_DIR / "22_starter_first_leo_satellite.json")
    spin(1.5)  # [s]
    window.show_view(window.lifetime_widget)
    window.lifetime_widget.compute()
    wait(lambda: window.lifetime_widget._worker is None, 600.0, "the lifetime estimate")  # [s]
    save(window, "end_of_life_computed")

    # Template 09 as a short batch (3 runs of 0.05 days instead of 20 of a
    # day): the screens are the same, and the full batch takes over 20 min.
    import json

    batch = json.loads((TEMPLATES_DIR / MONTE_CARLO).read_text(encoding="utf-8"))
    batch["monte_carlo"]["num_runs"] = 3
    batch["sim_settings"]["duration_days"] = 0.05  # [day]
    batch_path = Path(tempfile.mkdtemp(prefix="sms-ui-batch-")) / MONTE_CARLO
    batch_path.write_text(json.dumps(batch, indent=2), encoding="utf-8")
    window.open_path(batch_path)
    spin(1.5)  # [s]
    # A batch asks for its archive folder in a modal file dialog: answer it
    # here (the harness only; the app is unchanged), or the capture waits.
    from PySide6.QtWidgets import QFileDialog

    archive = Path(tempfile.mkdtemp(prefix="sms-ui-archive-"))
    QFileDialog.getExistingDirectory = staticmethod(lambda *args, **kwargs: str(archive))
    window.set_run_mode("monte_carlo")
    window.on_run()
    spin(2.0)  # [s]
    save(window, "monte_carlo_running")
    wait(lambda: window._mc_worker is None or not window._busy_progress.isVisible(), 1800.0, "the Monte Carlo batch")
    spin(2.0)  # [s]
    if window.results_views.indexOf(window.monte_carlo_results_widget) >= 0:
        window.show_view(window.monte_carlo_results_widget)
        spin(1.5)  # [s]
        save(window, "monte_carlo_results")
    window.set_run_mode("single")

    window.open_path(TEMPLATES_DIR / EXAMPLE)
    spin(1.5)  # [s]
    editor = window.scenario_editor
    editor.show_json()
    spin(1.0)  # [s]
    save(window, "json_view")

    # Dialogs, each opened on the example project.
    from spacemissionstudio.gui.command_palette import CommandPalette
    from spacemissionstudio.gui.constellation_dialog import WalkerConstellationDialog
    from spacemissionstudio.gui.ground_station_editor import GroundStationEditorDialog
    from spacemissionstudio.gui.help_dialog import ManualDialog, ShortcutsDialog
    from spacemissionstudio.gui.mission_sequence_editor import _CommandEditorDialog
    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog
    from spacemissionstudio.gui.monte_carlo_editor import _DispersionEditorDialog
    from spacemissionstudio.gui.phasing_formation_dialog import PhasingFormationDialog
    from spacemissionstudio.gui.propagation_setup_dialog import PropagationSetupDialog
    from spacemissionstudio.gui.roe_formation_dialog import RoeFormationDialog
    from spacemissionstudio.gui.sensor_actuator_editor import SensorActuatorListWidget, _ItemEditorDialog
    from spacemissionstudio.gui.sil_dialog import SilRunDialog
    from spacemissionstudio.gui.spacecraft_editor import SpacecraftEditorDialog
    from spacemissionstudio.gui.spacecraft_template_dialog import SpacecraftTemplateDialog
    from spacemissionstudio.gui.startup_fetch_dialog import StartupFetchDialog
    from spacemissionstudio.gui.template_wizard import TemplateCustomizeWizard, get_wizard_spec
    from spacemissionstudio.gui.vizard_dialog import VizardDialog

    scenario = load_scenario(TEMPLATES_DIR / EXAMPLE)
    sc = scenario.spacecraft[0]
    names = [s.name for s in scenario.spacecraft]
    dialog_shot(PropagationSetupDialog(scenario.gravity, scenario.sim_settings, scenario.space_weather, parent=window),
                "dialog_propagation_setup")
    sc_dialog = SpacecraftEditorDialog(config=sc, parent=window, simulation_mode=scenario.simulation_mode)
    sc_tabs = sc_dialog.findChildren(QTabWidget)[0]
    sc_dialog.resize(*DIALOG_SIZE)
    sc_dialog.show()
    for index in range(sc_tabs.count()):
        sc_tabs.setCurrentIndex(index)
        spin(0.8)  # [s]
        save(sc_dialog, f"dialog_spacecraft_{sc_tabs.tabText(index)}")
        areas = [a for a in sc_tabs.widget(index).findChildren(QScrollArea) if a.verticalScrollBar().maximum() > 0]
        if isinstance(sc_tabs.widget(index), QScrollArea) and sc_tabs.widget(index).verticalScrollBar().maximum() > 0:
            areas.insert(0, sc_tabs.widget(index))
        if areas:
            bar = areas[0].verticalScrollBar()
            bar.setValue(bar.maximum())
            spin(0.6)  # [s]
            save(sc_dialog, f"dialog_spacecraft_{sc_tabs.tabText(index)}_end")
            bar.setValue(0)
    lists = sc_dialog.findChildren(SensorActuatorListWidget)
    sc_dialog.close()
    for device_list in lists:
        if device_list._items:
            dialog_shot(_ItemEditorDialog(device_list._item_cls, device_list._kind_choices, item=device_list._items[0],
                                          parent=window), f"dialog_device_{device_list._items[0].kind}", size=(900, 700))
    if scenario.ground_stations:
        dialog_shot(GroundStationEditorDialog(scenario.ground_stations[0], parent=window), "dialog_ground_station",
                    size=(760, 620))
    if scenario.mission_sequence:
        dialog_shot(_CommandEditorDialog(command=scenario.mission_sequence[0], parent=window, spacecraft_names=names),
                    "dialog_mission_sequence_step", size=(820, 640))
    dialog_shot(_DispersionEditorDialog(names, parent=window), "dialog_monte_carlo_dispersion", size=(760, 560))
    dialog_shot(ModelEditorDialog(sc.model, spacecraft_name=sc.name), "dialog_3d_model", settle_s=5.0)
    dialog_shot(SpacecraftTemplateDialog(window), "dialog_spacecraft_preset", size=(820, 560))
    dialog_shot(WalkerConstellationDialog([t for t in names], parent=window), "dialog_walker_constellation",
                size=(820, 640))
    dialog_shot(PhasingFormationDialog(names, parent=window, spacecraft=scenario.spacecraft), "dialog_phasing_formation",
                size=(820, 640))
    dialog_shot(RoeFormationDialog(names, parent=window, spacecraft=scenario.spacecraft), "dialog_roe_formation",
                size=(820, 640))
    dialog_shot(SilRunDialog(sc.name, parent=window), "dialog_sil_run", size=(820, 600))
    dialog_shot(VizardDialog(parent=window), "dialog_vizard", size=(760, 560))
    dialog_shot(StartupFetchDialog(window), "dialog_startup_fetch", size=(760, 520))
    dialog_shot(CommandPalette(window.palette_entries(), window), "dialog_command_palette", size=(720, 520))
    actions = [a for m in window.menuBar().actions() if m.menu() is not None for a in m.menu().actions()]
    dialog_shot(ShortcutsDialog(actions, window), "dialog_keyboard_shortcuts", size=(720, 640))
    dialog_shot(ManualDialog(window), "dialog_user_manual")
    window.show_view(window.data_panel_widget)
    spin(1.5)  # [s]
    save(window.data_dialog, "dialog_reference_data")
    window.data_dialog.close()
    spec = get_wizard_spec(EXAMPLE)
    if spec is not None:
        wizard = TemplateCustomizeWizard(scenario, spec, window)
        wizard.resize(1000, 720)
        wizard.show()
        spin(1.2)  # [s]
        save(wizard, "dialog_customize_template")
        wizard.close()
    from spacemissionstudio.gui.facet_editor import BoxFacetDialog
    from spacemissionstudio.gui.model_editor_dialog import _ImportOptionsDialog
    from spacemissionstudio.gui.orbit_ic_widget import OrbitSwitchDialog

    dialog_shot(BoxFacetDialog(window), "dialog_box_facets", size=(640, 420))
    dialog_shot(_ImportOptionsDialog(Path("bus.obj"), True, window), "dialog_obj_import_options", size=(560, 320))
    dialog_shot(OrbitSwitchDialog(window, "Classical elements", "Cartesian state", "a 6928.000 km, e 0.000000",
                                  "r (6928.0, 0.0, 0.0) km, v (0.0, -1.0, 7.5) km/s", "r (7000.0, 0.0, 0.0) km",
                                  ""), "dialog_orbit_type_switch", size=(640, 300))
    modal_shot(window.on_about, "dialog_about")
    window.scenario_editor.name_edit.setText("unsaved edit")
    spin(0.5)  # [s]
    modal_shot(window.on_new, "dialog_confirm_discard")

    print(f"{len(taken)} screenshots in {out}")
    (out / "INDEX.txt").write_text("\n".join(taken) + "\n", encoding="utf-8")
    window._dirty = False
    window.close()
    return 0


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Screenshots of every screen of the GUI, offscreen.")
    parser.add_argument("out", nargs="?", default="docs/ui/screenshots/before")
    parser.add_argument("--theme", choices=("light", "dark", "both"), default="both")
    args = parser.parse_args(argv)
    if args.theme != "both":
        return capture(Path(args.out), args.theme)
    env = dict(os.environ, QT_QPA_PLATFORM=os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    failed = 0
    for theme in ("light", "dark"):
        failed |= subprocess.call([sys.executable, __file__, str(Path(args.out) / theme), "--theme", theme], env=env)
    return failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
