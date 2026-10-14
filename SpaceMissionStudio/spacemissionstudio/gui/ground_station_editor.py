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

"""Ground station list + per-station editor dialog.

Unlike sensors/actuators/FSW modes (see ``spacecraft_editor.py``'s scope
note), ground stations are pure scenario DATA with no implication of an
immediate simulated effect -- access-window computation is Phase 3, but
defining where the stations are is core mission setup (this project's own
spec draws exactly this distinction), so this editor exists now even
though nothing reads ``scenario.ground_stations`` yet.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..schema.scenario import GroundStationConfig, ScenarioValidationError
from .feedback import (ProblemBanner, bring_into_view, clear_field_error, clear_invalid, clear_on_edit,
                       mark_invalid, report, show_field_error, show_toast)
from .problem_location import GROUND_STATION, locate
from .widgets import PreciseDoubleSpinBox


def _spin(minimum: float, maximum: float, decimals: int = 4, step: float = 1.0, value: float = 0.0) -> QDoubleSpinBox:
    box = PreciseDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    return box


class GroundStationEditorDialog(QDialog):
    def __init__(self, config: GroundStationConfig | None = None, parent: QWidget | None = None,
                 other_names: list[str] | None = None):
        super().__init__(parent)
        self._other_names = other_names or []
        self.setWindowTitle("Ground station" if config is None else f"Ground station: {config.name}")

        layout = QVBoxLayout(self)
        # What is wrong, when the dialog is opened at a problem or OK finds one (U-12).
        self.problem_banner = ProblemBanner()
        layout.addWidget(self.problem_banner)
        self._problem_field = None
        form = QFormLayout()
        self.name_edit = QLineEdit(config.name if config else "gs-1")
        self.name_edit.textChanged.connect(self._on_name_changed)
        form.addRow("Name", self.name_edit)
        self.lat_deg = _spin(-90.0, 90.0, decimals=6, step=1.0, value=config.latitude_deg if config else 0.0)
        self.lat_deg.setToolTip("Geodetic latitude on the WGS-84 ellipsoid, north positive.\n"
                                "Other central bodies: planetocentric, on a sphere.")
        form.addRow("Geodetic latitude [deg] (WGS-84)", self.lat_deg)
        self.lon_deg = _spin(-180.0, 180.0, decimals=6, step=1.0, value=config.longitude_deg if config else 0.0)
        self.lon_deg.setToolTip("Longitude, east positive from the prime meridian of the body-fixed frame.")
        form.addRow("Longitude [deg] (WGS-84, east positive)", self.lon_deg)
        self.alt_m = _spin(-500.0, 9000.0, decimals=1, step=10.0, value=config.altitude_m if config else 0.0)
        self.alt_m.setToolTip("Height above the WGS-84 ellipsoid (not above sea level: they differ by up to ~100 m).")
        form.addRow("Height [m] (above the WGS-84 ellipsoid)", self.alt_m)
        self.min_elev_deg = _spin(0.0, 89.9, decimals=2, step=1.0,
                                   value=config.min_elevation_deg if config else 10.0)
        self.min_elev_deg.setToolTip(
            "The lowest elevation angle above the local horizon counted as real, usable "
            "access -- real terrain/buildings/RF-noise near the horizon mean a satellite just "
            "above the geometric horizon usually isn't actually usable. Lower = longer, more "
            "frequent access windows but at progressively worse link quality near the edges; "
            "higher = shorter, higher-quality windows only. 5-10 deg is a common real-world "
            "default."
        )
        form.addRow("Minimum elevation mask [deg]", self.min_elev_deg)
        # Only meaningful for a spacecraft that also has an RF link budget
        # configured (see spacecraft_editor.py's "Power / link budget" tab
        # and schema.scenario.RFLinkConfig) -- harmless, unused otherwise.
        self.rx_antenna_gain_dbi = _spin(-50.0, 100.0, decimals=2, step=1.0,
                                          value=config.rx_antenna_gain_dbi if config else 45.0)
        self.rx_antenna_gain_dbi.setToolTip(
            "This ground station's receive antenna gain -- only used if a spacecraft also has "
            "an RF link budget configured (Spacecraft editor's Power tab). Higher gain "
            "improves the reported link margin for any spacecraft downlinking to this station."
        )
        form.addRow("RX antenna gain [dBi] (for a link budget)", self.rx_antenna_gain_dbi)
        self.system_noise_temp_k = _spin(0.1, 1.0e5, decimals=2, step=10.0,
                                          value=config.system_noise_temp_k if config else 290.0)
        self.system_noise_temp_k.setToolTip(
            "This ground station's receiver system noise temperature -- same link-budget-only "
            "scope as the antenna gain above. Lower (a quieter, better receiver) improves the "
            "reported link margin."
        )
        form.addRow("System noise temperature [K] (for a link budget)", self.system_noise_temp_k)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # See constellation_dialog.py's identical fix for why this is
        # needed: Qt can size a freshly-constructed QDialog smaller than
        # its own sizeHint() on first show() on a real desktop, a gap
        # this project's own offscreen test rendering doesn't reproduce.
        self.resize(self.sizeHint())

    def _on_name_changed(self, text: str) -> None:
        name = text.strip()
        if not name:
            mark_invalid(self.name_edit, "Name must not be empty")
        elif name in self._other_names:
            mark_invalid(self.name_edit, f"A ground station named {name!r} already exists")
        else:
            clear_invalid(self.name_edit)

    def _on_accept(self) -> None:
        # Same data-loss bug/fix as SpacecraftEditorDialog._on_accept --
        # see that method's own docstring. Checked here, before
        # to_dataclass()/accept(), so a duplicate/empty name keeps this
        # dialog open instead of discarding the user's edits.
        name = self.name_edit.text().strip()
        if not name:
            mark_invalid(self.name_edit, "Name must not be empty")
            self.name_edit.setFocus()
            return
        if name in self._other_names:
            mark_invalid(self.name_edit, f"A ground station named {name!r} already exists")
            self.name_edit.setFocus()
            return
        try:
            self.to_dataclass()
        except ScenarioValidationError as exc:
            location = locate(str(exc), station_names=[self.name_edit.text().strip()])
            self.show_problem(location.path if location is not None and location.area == GROUND_STATION else "",
                              str(exc))
            return
        self.accept()

    def to_dataclass(self) -> GroundStationConfig:
        config = GroundStationConfig(
            name=self.name_edit.text().strip(),
            latitude_deg=self.lat_deg.value(),
            longitude_deg=self.lon_deg.value(),
            altitude_m=self.alt_m.value(),
            min_elevation_deg=self.min_elev_deg.value(),
            rx_antenna_gain_dbi=self.rx_antenna_gain_dbi.value(),
            system_noise_temp_k=self.system_noise_temp_k.value(),
        )
        config.validate()
        return config


    # Where a ground station field's widget is (docs/ux-audit.md U-12).
    _FIELD_WIDGETS = {"name": "name_edit", "latitude_deg": "lat_deg", "longitude_deg": "lon_deg",
                      "altitude_m": "alt_m", "min_elevation_deg": "min_elev_deg",
                      "rx_antenna_gain_dbi": "rx_antenna_gain_dbi", "system_noise_temp_k": "system_noise_temp_k"}

    def field_widget(self, path: str):
        """The widget for the station field ``path``, or None."""
        name = self._FIELD_WIDGETS.get(path)
        return getattr(self, name, None) if name else None

    def clear_problem(self) -> None:
        """Hide the banner and unmark the field :meth:`show_problem` marked."""
        if self._problem_field is not None:
            clear_field_error(self._problem_field)
            self._problem_field = None
        self.problem_banner.hide()

    def show_problem(self, path: str, message: str, focus: bool = True) -> None:
        """Opens at a problem: the banner says what is wrong, and the field
        at ``path`` (when there is one) is marked, and shown and focused
        when ``focus`` (not while the user types in the form: a live form
        in the Scenario Editor marks a problem where it is, U-01)."""
        if self._problem_field is not None:
            clear_field_error(self._problem_field)
            self._problem_field = None
        self.problem_banner.show_problem(message)
        widget = self.field_widget(path)
        if widget is not None:
            show_field_error(widget, message)
            if focus:
                clear_on_edit(widget)
            self._problem_field = widget
            if focus:
                bring_into_view(widget)


class GroundStationListWidget(QWidget):
    changed = Signal()
    reloaded = Signal()  # from_list() replaced every entry (a load, an undo): not an edit

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._configs: list[GroundStationConfig] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        button_row = QHBoxLayout()
        self.add_button = QPushButton("Add...")
        self.edit_button = QPushButton("Edit...")
        self.remove_button = QPushButton("Remove")
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.edit_button)
        button_row.addWidget(self.remove_button)
        layout.addLayout(button_row)

        self.add_button.clicked.connect(self._on_add)
        self.edit_button.clicked.connect(self._on_edit)
        self.remove_button.clicked.connect(self._on_remove)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._on_edit())

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        for config in self._configs:
            self.list_widget.addItem(QListWidgetItem(f"{config.name} ({config.latitude_deg:.2f}, {config.longitude_deg:.2f})"))

    def _on_add(self) -> None:
        existing_names = {c.name for c in self._configs}
        dialog = GroundStationEditorDialog(parent=self, other_names=sorted(existing_names))
        base_name = dialog.name_edit.text()
        candidate, n = base_name, 1
        while candidate in existing_names:
            n += 1
            candidate = f"{base_name}-{n}"
        dialog.name_edit.setText(candidate)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.to_dataclass()
            if config.name in existing_names:
                report(self, f"Not added: a ground station named {config.name!r} already exists", kind="warning")
                return
            self._configs.append(config)
            self._refresh_list()
            self.list_widget.setCurrentRow(len(self._configs) - 1)
            show_toast(self.window(), f"Added ground station {config.name!r}")
            self.changed.emit()

    def set_edit_handler(self, handler) -> None:
        """``handler(row)`` replaces the editor dialog that Edit... and a
        double-click open: the Scenario Editor shows the ground station's page
        in its tree instead (docs/ux-audit.md U-01, U-11)."""
        self._edit_handler = handler

    def replace_config(self, row: int, config) -> None:
        """Put ``config`` in ``row``, as an edit in the ground station's page
        does: the list's text follows, and :attr:`changed` is emitted."""
        self._configs[row] = config
        self.list_widget.item(row).setText(config.name)
        self.changed.emit()

    def _on_edit(self) -> None:
        row = self.list_widget.currentRow()
        if row >= 0 and getattr(self, "_edit_handler", None) is not None:
            self._edit_handler(row)
        elif row >= 0:
            self.edit_station(row)

    def edit_station_named(self, name: str, path: str = "", message: str = "") -> None:
        """Open the editor for the ground station ``name``, at the problem
        ``message`` about its field ``path`` when given (Problems, U-12)."""
        names = [config.name for config in self._configs]
        if name in names:
            self.list_widget.setCurrentRow(names.index(name))
            self.edit_station(names.index(name), path, message)

    def edit_station(self, row: int, path: str = "", message: str = "") -> None:
        other_names = sorted(c.name for i, c in enumerate(self._configs) if i != row)
        dialog = GroundStationEditorDialog(config=self._configs[row], parent=self, other_names=other_names)
        if message:
            dialog.show_problem(path, message)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_config = dialog.to_dataclass()
            if new_config.name in set(other_names):
                report(self, f"Not saved: a ground station named {new_config.name!r} already exists",
                       kind="warning")
                return
            self._configs[row] = new_config
            self._refresh_list()
            self.list_widget.setCurrentRow(row)
            show_toast(self.window(), f"Updated ground station {new_config.name!r}")
            self.changed.emit()

    def _on_remove(self) -> None:
        row = self.list_widget.currentRow()
        if row < 0:
            return
        name = self._configs[row].name
        del self._configs[row]
        self._refresh_list()
        show_toast(self.window(), f"Removed ground station {name!r}", kind="info")
        self.changed.emit()

    def to_list(self) -> list[GroundStationConfig]:
        return list(self._configs)

    def from_list(self, configs: list[GroundStationConfig]) -> None:
        self._configs = list(configs)
        self._refresh_list()
        self.reloaded.emit()
