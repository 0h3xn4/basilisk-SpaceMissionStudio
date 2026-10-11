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
"""Capture the screenshots in ``docs/images/`` from the real GUI, offscreen.

Run from the ``SpaceMissionStudio`` folder, in an environment with
Basilisk 2.12.0, the ``gui`` extra and the reference data installed::

    QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py docs/images

It opens templates 22, 18 and 07, runs template 22, estimates its lifetime
and template 18's propellant budget, and saves each view at 1600 x 900
pixels. ``monte_carlo_tab.png`` needs a Monte Carlo batch and is not
captured here.
"""

import sys
import time
from pathlib import Path

WINDOW_SIZE = (1600, 900)  # [px]
WIZARD_SIZE = (960, 640)  # [px]
TOAST_S = 5.0  # [s] long enough for the "Opened ..." notice to fade


def main(out: Path) -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv[:1])
    from spacemissionstudio.gui.load_scenario_widget import TEMPLATES_DIR
    from spacemissionstudio.gui.main_window import MainWindow
    from spacemissionstudio.gui.template_wizard import TemplateCustomizeWizard, get_wizard_spec
    from spacemissionstudio.gui.theme import apply_theme
    from spacemissionstudio.schema import load_scenario

    apply_theme(app)
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
    window.resize(*WINDOW_SIZE)
    window.show()
    spin(1.5)  # [s]

    templates = window.load_scenario_widget.list_widget
    row = next(i for i in range(templates.count()) if templates.item(i).text().startswith("22 "))
    window.activateWindow()
    templates.setFocus()
    templates.setCurrentRow(row)
    templates.scrollToItem(templates.item(row))
    spin(1.0)  # [s]
    save("load_scenario_tab.png")

    open_template("22_starter_first_leo_satellite.json")
    window.right_tabs.setCurrentWidget(window.scenario_explainer_widget)
    spin(4.0)  # [s]
    save("scenario_editor_tab.png")

    window.on_run()
    wait(lambda: window.event_timeline_widget.table.rowCount() > 0, 300.0, "the run of template 22")  # [s]
    window.right_tabs.setCurrentWidget(window.event_timeline_widget)
    spin(2.0)  # [s]
    save("events_tab.png")

    window.right_tabs.setCurrentWidget(window.lifetime_widget)
    window.lifetime_widget.compute()
    wait(lambda: window.lifetime_widget._worker is None, 300.0, "the lifetime estimate")  # [s]
    save("end_of_life_tab.png")

    open_template("18_leo_station_keeping.json")
    budget_page = window.budget_widget.parentWidget().parentWidget()  # the tab's scroll area
    window.right_tabs.setCurrentIndex(window.right_tabs.indexOf(budget_page))
    window.budget_widget.compute()
    wait(lambda: window.budget_widget._worker is None, 600.0, "the budget")  # [s]
    save("budget_tab.png")

    open_template("07_attitude_pointing_with_adcs_hardware.json")
    window.right_tabs.setCurrentWidget(window.flight_software_widget)
    spin(1.5)  # [s]
    save("flight_software_tab.png")

    name = "22_starter_first_leo_satellite.json"
    wizard = TemplateCustomizeWizard(load_scenario(TEMPLATES_DIR / name), get_wizard_spec(name))
    wizard.resize(*WIZARD_SIZE)
    wizard.show()
    spin(1.5)  # [s]
    wizard.grab().save(str(out / "customize_wizard.png"))
    print(f"wrote {out / 'customize_wizard.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "docs/images")))
