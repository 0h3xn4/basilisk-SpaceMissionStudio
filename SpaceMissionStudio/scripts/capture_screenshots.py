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
"""Capture the screenshots in ``docs/images/`` from the real GUI, offscreen.

Run from the ``SpaceMissionStudio`` folder, in an environment with
Basilisk 2.12.0, the ``gui`` extra and the reference data installed::

    QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py docs/images

It opens templates 22, 18 and 07 (22 also on its JSON page, a key
misspelt), runs template 22 for one day and then
two (Compare), runs template 25's Monte Carlo batch into a temporary
folder, estimates template 22's lifetime and template 18's propellant
budget, and saves each view at 1600 x 900 pixels, and the 3D model editor
with an octagonal bus. The batch takes the longest (20 runs of 3 days).

``--theme light|dark`` captures in that theme (default: light, as the
documentation shows) and ``--size WxH`` at another window size, e.g. for
the dark-theme and 2560 x 1440 checks, into another folder::

    QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py /tmp/dark --theme dark --size 1280x720

Offscreen, the 3D view (Qt WebEngine) needs Chromium's software WebGL,
or it shows "WebGL is not supported"; run as root, also without its
sandbox::

    QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --use-angle=swiftshader --enable-unsafe-swiftshader" \
        QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py docs/images
"""

import argparse
import sys
import time
from pathlib import Path

WINDOW_SIZE = (1600, 900)  # [px]
WIZARD_SIZE = (960, 640)  # [px]
TOAST_S = 5.0  # [s] long enough for the "Opened ..." notice to fade


def _octagonal_bus_model():
    """The model shown in ``model_editor.png``: an octagonal bus, two
    deployed panels and a dish."""
    from spacemissionstudio.schema.scenario import ModelPartConfig, SpacecraftModelConfig

    panel = {"width": 1.0, "length": 2.2, "thickness": 0.03}  # [m]
    return SpacecraftModelConfig(parts=[
        ModelPartConfig(name="bus", shape="prism", dimensions_m={"width_across_flats": 1.1, "height": 1.2},
                        mass_kg=180.0, color=[0.78, 0.78, 0.8]),  # [m], [kg]
        ModelPartConfig(name="wing +y", shape="panel", dimensions_m=dict(panel), position_b_m=[0.0, 1.75, 0.1],
                        mass_kg=8.0, distribution="shell", color=[0.1, 0.2, 0.55]),  # [m], [kg]
        ModelPartConfig(name="wing -y", shape="panel", dimensions_m=dict(panel), position_b_m=[0.0, -1.75, 0.1],
                        mass_kg=8.0, distribution="shell", color=[0.1, 0.2, 0.55]),  # [m], [kg]
        ModelPartConfig(name="dish", shape="cone", dimensions_m={"base_diameter": 0.6, "height": 0.18},
                        position_b_m=[0.0, 0.0, 0.69], mass_kg=3.0, distribution="shell",
                        color=[0.9, 0.9, 0.85]),  # [m], [kg]
    ])


def main(out: Path, theme: str = "light", size: tuple = WINDOW_SIZE) -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.template_wizard import TemplateCustomizeWizard, get_wizard_spec
    from spacemissionstudio.gui.theme import apply_theme
    from spacemissionstudio.schema import load_scenario

    apply_theme(app, theme)
    out.mkdir(parents=True, exist_ok=True)

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

    def open_template(name: str) -> None:
        window.open_path(TEMPLATES_DIR / name)
        spin(TOAST_S)

    def save(name: str) -> None:
        window.grab().save(str(out / name))
        print(f"wrote {out / name}")

    window = MainWindow(prompt_startup_fetch=False, check_autosave_recovery=False)
    window.resize(*size)
    window.show()
    spin(1.5)  # [s]

    home = window.load_scenario_widget
    card = next(card for card in home.cards if card.name.startswith("22 "))
    window.activateWindow()
    home.select(card.name)
    card.setFocus()
    spin(1.0)  # [s]
    save("load_scenario_tab.png")

    open_template("22_starter_first_leo_satellite.json")
    window.show_view(window.scenario_editor.scenario_page)  # its Scenario page (Explain is the tree's Overview, M4b)
    spin(4.0)  # [s]
    save("scenario_editor_tab.png")
    capture_json_page(window, out, spin)

    window.on_run()
    wait(lambda: window.event_timeline_widget.table.row_count() > 0, 300.0, "the run of template 22")  # [s]
    window.show_view(window.event_timeline_widget)
    spin(2.0)  # [s]
    save("events_tab.png")

    # Compare: the same template again, two days long (the manual's caption).
    scenario = window.scenario_editor.to_scenario()
    scenario.sim_settings.duration_days = 2.0  # [day]
    window.scenario_editor.from_scenario(scenario)
    runs_before = len(window.run_history.runs)
    window.on_run()
    wait(lambda: len(window.run_history.runs) > runs_before and not window._run_worker.isRunning(), 300.0,
         "the two-day run of template 22")  # [s]
    window.show_view(window.compare_widget)
    spin(4.0)  # [s] the overlaid plot loads
    save("compare_tab.png")

    window.show_view(window.lifetime_widget)
    window.lifetime_widget.compute()
    wait(lambda: window.lifetime_widget._worker is None, 300.0, "the lifetime estimate")  # [s]
    save("end_of_life_tab.png")

    open_template("18_leo_station_keeping.json")
    window.show_view(window.budget_widget)
    window.budget_widget.compute()
    wait(lambda: window.budget_widget._worker is None, 600.0, "the budget")  # [s]
    save("budget_tab.png")

    # Monte Carlo: template 25's batch, in a temporary folder.
    import tempfile

    from PySide6.QtWidgets import QFileDialog

    batch_dir = Path(tempfile.mkdtemp(prefix="sms_monte_carlo_"))
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: str(batch_dir))
    from PySide6.QtWidgets import QMessageBox

    # A batch an earlier capture left in that folder is replaced, not asked about.
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    open_template("25_monte_carlo_orbit_and_drag_dispersions.json")
    window.on_run_monte_carlo()
    wait(lambda: window.monte_carlo_results_widget.batch is not None and not window._mc_worker.isRunning(),
         3600.0, "the Monte Carlo batch of template 25")  # [s]
    window.show_view(window.monte_carlo_results_widget)
    spin(4.0)  # [s]
    save("monte_carlo_tab.png")

    open_template("07_attitude_pointing_with_adcs_hardware.json")
    window.show_view(window.flight_software_widget)
    spin(1.5)  # [s]
    save("flight_software_tab.png")

    from spacemissionstudio.gui.model_editor_dialog import ModelEditorDialog

    editor = ModelEditorDialog(_octagonal_bus_model(), spacecraft_name="sat-1")
    editor.resize(*size)
    editor.show()
    spin(6.0)  # [s] the 3D view loads plotly.js and draws
    editor.grab().save(str(out / "model_editor.png"))
    print(f"wrote {out / 'model_editor.png'}")
    editor.close()

    capture_idm_import(out, spin)

    name = "22_starter_first_leo_satellite.json"
    wizard = TemplateCustomizeWizard(load_scenario(TEMPLATES_DIR / name), get_wizard_spec(name))
    wizard.resize(*WIZARD_SIZE)
    wizard.show()
    spin(1.5)  # [s]
    wizard.grab().save(str(out / "customize_wizard.png"))
    print(f"wrote {out / 'customize_wizard.png'}")
    return 0


def capture_json_page(window, out: Path, spin) -> None:
    """``json_page.png``: template 22 on its JSON page, "dry_mass_kg"
    misspelt "dry_mas_kg": the key underlined where it is, and the cursor
    on it giving its message under the text. The form is shown again
    after, with the template's own text."""
    from PySide6.QtGui import QTextCursor

    editor = window.scenario_editor
    editor.show_json()
    spin(1.0)  # [s]
    edit = editor.json_view.edit
    text = edit.toPlainText()
    start = text.index('"dry_mass_kg"')
    cursor = edit.textCursor()
    cursor.setPosition(start + 1)
    cursor.setPosition(start + len('"dry_mass_kg'), QTextCursor.MoveMode.KeepAnchor)
    edit.setTextCursor(cursor)
    edit.insertPlainText("dry_mas_kg")
    editor.json_view.flush()
    cursor = edit.textCursor()
    cursor.setPosition(start + 4)
    edit.setTextCursor(cursor)
    edit.centerCursor()
    edit.setFocus()
    spin(2.0)  # [s]
    window.statusBar().clearMessage()  # "Opened <the template's path on this computer>"
    spin(0.2)  # [s]
    window.grab().save(str(out / "json_page.png"))
    print(f"wrote {out / 'json_page.png'}")
    edit.undo()
    editor.json_view.flush()
    spin(1.0)  # [s]


def capture_idm_import(out: Path, spin) -> None:
    """``idm_import.png``: the IDM-CIC import dialog on a synthetic test
    model (``tests/data/idm/axessat``, made up; never a real model), its
    devices listed with the axes their shapes show, scrolled to the
    thruster added to the 3D model from its plume cone."""
    import tempfile

    from spacemissionstudio.gui.idm_import_dialog import IdmImportDialog

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
    from idm_fixtures import model_xml, write_idm

    with tempfile.TemporaryDirectory() as folder:
        dialog = IdmImportDialog(write_idm(Path(folder) / "axessat.idm", model_xml("axessat")))
        dialog.resize(900, 720)  # [px] its own default size: the tabs and the origin row fit
        dialog.show()
        end = time.time() + 30.0  # [s] the file read and the import planned in the worker
        while (dialog.busy() or dialog.plan() is None) and time.time() < end:
            spin(0.1)  # [s]
        dialog.devices_table.scrollToBottom()
        spin(1.0)  # [s]
        dialog.grab().save(str(out / "idm_import.png"))
        print(f"wrote {out / 'idm_import.png'}")
        dialog.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture the GUI's screenshots, offscreen.")
    parser.add_argument("out", nargs="?", default="docs/images", help="the folder to write them to")
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument("--size", default=f"{WINDOW_SIZE[0]}x{WINDOW_SIZE[1]}", help="the window size, WxH [px]")
    args = parser.parse_args()
    width, height = (int(v) for v in args.size.lower().split("x"))
    sys.exit(main(Path(args.out), args.theme, (width, height)))
