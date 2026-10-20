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

"""The 3D model editor: build a spacecraft's model from simple shapes or
imported ``.obj`` groups, and see the mass properties and facets it gives.

Left, the parts; in the middle, the selected part's form; right, the 3D
view (:mod:`.model_view_widget`). Below, three tabs: **Mass properties**
(computed from the parts, typed in, or imported from a file), **Surfaces**
(the facets drag and solar pressure will act on) and **Use** (what the
model is applied to, and an ``.obj`` export). Every change recomputes the
model (``model3d.model.derive``) a moment later.

The dialog edits a copy of the model; :meth:`ModelEditorDialog.model`
returns it after OK. Applying it to the spacecraft's fields is the
spacecraft editor's job.
"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QColorDialog, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QMenu, QMessageBox, QPushButton, QRadioButton, QScrollArea, QSplitter, QToolButton,
                               QVBoxLayout, QWidget)

from ..model3d import mass_import, obj_io
from ..model3d import model as model3d
from ..schema.scenario import (MESH_UNITS, MODEL_SHAPE_DIMENSIONS, MODEL_SHAPE_FACES, ModelMassPropertiesConfig,
                               ModelMeshConfig, ModelPartConfig, ScenarioValidationError, SpacecraftModelConfig,
                               name_error)
from .feedback import report, show_dialog_error
from .model_view_widget import ModelViewWidget
from .theme import set_role
from .theme.palettes import swatch_style
from .widgets import ComboBox, PreciseDoubleSpinBox, SpinBox, TabWidget

_RECOMPUTE_DELAY_MS = 150  # [ms] after the last edit

# What "Add" puts in: a sensible size and mass to start from.
_NEW_PARTS = {
    "box": ({"x": 0.5, "y": 0.5, "z": 0.5}, 10.0, "solid"),  # [m], [kg]
    "prism": ({"width_across_flats": 1.0, "height": 1.0}, 80.0, "solid"),  # [m], [kg]
    "cylinder": ({"diameter": 0.3, "height": 0.5}, 5.0, "solid"),  # [m], [kg]
    "cone": ({"base_diameter": 0.6, "height": 0.25}, 2.0, "shell"),  # [m], [kg]
    "sphere": ({"diameter": 0.3}, 5.0, "solid"),  # [m], [kg]
    "panel": ({"width": 1.0, "length": 2.0, "thickness": 0.03}, 6.0, "shell"),  # [m], [kg]
}
_ADD_LABELS = {"box": "Box", "prism": "Prism (octagon; any number of sides)", "cylinder": "Cylinder",
               "cone": "Cone", "sphere": "Sphere", "panel": "Panel (flat plate)"}
_DIMENSION_LABELS = {"x": "Length x", "y": "Length y", "z": "Length z", "width_across_flats": "Width across flats",
                     "height": "Height", "diameter": "Diameter", "base_diameter": "Base diameter", "width": "Width (x)",
                     "length": "Length (y)", "thickness": "Thickness (z)"}
_UP_AXIS_LABELS = {"z": "Z up (as the body frame)", "y": "Y up (most modelling tools)"}


def _spin(minimum: float, maximum: float, value: float, decimals: int = 3, step: float = 0.1,
          suffix: str = "") -> PreciseDoubleSpinBox:
    box = PreciseDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(value)
    if suffix:
        box.setSuffix(suffix)
    return box


def _row(*widgets) -> QWidget:
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        if isinstance(widget, PreciseDoubleSpinBox):
            widget.setMinimumWidth(70)  # [px] three to a row must fit the form column
            widget.setButtonSymbols(PreciseDoubleSpinBox.ButtonSymbols.NoButtons)
        layout.addWidget(widget, 1)
    return holder


def unique_name(base: str, taken: List[str]) -> str:
    """``base``, or ``base 2``, ``base 3``... -- the first not in ``taken``.
    Characters a part name cannot hold become ``_``."""
    cleaned = "".join("_" if (c in '/\\:*?"<>|.' or ord(c) < 32) else c for c in base).strip() or "part"
    if name_error("part", cleaned) is not None:
        cleaned = f"{cleaned}_"
    if cleaned not in taken:
        return cleaned
    k = 2
    while f"{cleaned} {k}" in taken:
        k += 1
    return f"{cleaned} {k}"


class _ImportOptionsDialog(QDialog):
    """Units, up axis and whether to copy an ``.obj`` beside the scenario."""

    def __init__(self, path: Path, can_copy: bool, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(f"Import {path.name}")
        layout = QVBoxLayout(self)
        note = QLabel(".obj files store neither a unit nor which way is up: say what this one uses.")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.units = ComboBox()
        for unit in MESH_UNITS:
            self.units.addItem({"m": "metres", "mm": "millimetres", "cm": "centimetres", "in": "inches"}[unit], unit)
        form.addRow("Units", self.units)
        self.up_axis = ComboBox()
        for axis, label in _UP_AXIS_LABELS.items():
            self.up_axis.addItem(label, axis)
        form.addRow("Up axis", self.up_axis)
        layout.addLayout(form)
        self.copy_check = QCheckBox("Copy the file into the scenario's folder (models/)")
        self.copy_check.setEnabled(can_copy)
        self.copy_check.setChecked(can_copy)
        self.copy_check.setToolTip("Keeps the scenario and its model together when you move or share them."
                                   if can_copy else "Save the scenario first to copy models beside it.")
        layout.addWidget(self.copy_check)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def uses_note(simulation_mode: Optional[str]) -> str:
    """What the next run takes from an applied model in a scenario of this
    simulation mode; empty when the mode is not known."""
    if simulation_mode == "orbit_only":
        return ("This scenario runs orbit only (Scenario Editor > Simulation mode): the next run uses the "
                "dry mass, for drag and solar pressure. The center of mass, inertia and facets take effect "
                "in a full-attitude run.")
    if simulation_mode:
        return ("The next run uses the mass, center of mass and inertia in the attitude dynamics, and the "
                "facets for the drag and solar pressure forces and torques (when drag or solar pressure is "
                "on).")
    return ""


class ModelEditorDialog(QDialog):
    """Edits a copy of a :class:`SpacecraftModelConfig` (see the module
    docstring). ``base_dir`` is the scenario file's folder: mesh paths are
    stored relative to it, and imports can be copied into it."""

    def __init__(self, model: Optional[SpacecraftModelConfig], spacecraft_name: str = "sat-1",
                 base_dir=None, parent: Optional[QWidget] = None, simulation_mode: Optional[str] = None):
        super().__init__(parent)
        self._simulation_mode = simulation_mode
        self.setWindowTitle(f"3D model: {spacecraft_name}")
        self.resize(1280, 820)
        self._spacecraft_name = spacecraft_name
        self._base_dir = Path(base_dir) if base_dir else None
        self._model = copy.deepcopy(model) if model is not None else SpacecraftModelConfig(parts=[])
        self._cache = model3d.MeshCache()
        self.derived: model3d.DerivedModel = model3d.DerivedModel()
        self._loading_form = False
        self._recompute_timer = QTimer(self)
        self._recompute_timer.setSingleShot(True)
        self._recompute_timer.setInterval(_RECOMPUTE_DELAY_MS)
        self._recompute_timer.timeout.connect(self.recompute_now)

        outer = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_parts_panel())
        self._form_area = QScrollArea()
        self._form_area.setWidgetResizable(True)
        self._form_area.setMinimumWidth(460)
        splitter.addWidget(self._form_area)
        self.view = ModelViewWidget()
        splitter.addWidget(self.view)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([230, 480, 570])

        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(splitter)
        vertical.addWidget(self._build_bottom_tabs())
        vertical.setSizes([560, 240])
        outer.addWidget(vertical)

        self.messages = QLabel()
        self.messages.setWordWrap(True)
        set_role(self.messages, tone="caution")
        outer.addWidget(self.messages)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._refresh_parts_list()
        self._load_use_tab()
        self._load_mass_tab()
        if self._model.parts:
            self.parts_list.setCurrentRow(0)
        else:
            self._show_part_form(None)
        self.recompute_now()

    # -- parts list -------------------------------------------------------------------------------------------

    def _build_parts_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Parts"))
        self.parts_list = QListWidget()
        self.parts_list.currentRowChanged.connect(self._on_part_selected)
        layout.addWidget(self.parts_list)
        self.add_button = QToolButton()
        self.add_button.setText("Add")
        self.add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.add_button)
        for shape, label in _ADD_LABELS.items():
            menu.addAction(label, lambda s=shape: self.add_part(s))
        self.add_button.setMenu(menu)
        self.import_button = QPushButton("Import .obj...")
        self.import_button.clicked.connect(self._on_import_obj)
        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.clicked.connect(self.duplicate_part)
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_part)
        grid = QGridLayout()
        grid.addWidget(self.add_button, 0, 0)
        grid.addWidget(self.import_button, 0, 1)
        grid.addWidget(self.duplicate_button, 1, 0)
        grid.addWidget(self.delete_button, 1, 1)
        layout.addLayout(grid)
        return panel

    def _refresh_parts_list(self) -> None:
        row = self.parts_list.currentRow()
        self.parts_list.blockSignals(True)
        self.parts_list.clear()
        for part in self._model.parts:
            label = f"{part.name}  ({part.shape})"
            if not part.visible:
                label += "  hidden"
            self.parts_list.addItem(label)
        self.parts_list.blockSignals(False)
        if self._model.parts:
            self.parts_list.setCurrentRow(min(max(row, 0), len(self._model.parts) - 1))

    def selected_part(self) -> Optional[ModelPartConfig]:
        row = self.parts_list.currentRow()
        return self._model.parts[row] if 0 <= row < len(self._model.parts) else None

    def add_part(self, shape: str) -> ModelPartConfig:
        """Add a new part of ``shape`` (a simple shape) and select it."""
        dims, mass, distribution = _NEW_PARTS[shape]
        part = ModelPartConfig(name=unique_name(shape, [p.name for p in self._model.parts]), shape=shape,
                               dimensions_m=dict(dims), mass_kg=mass, distribution=distribution)
        self._model.parts.append(part)
        self._refresh_parts_list()
        self.parts_list.setCurrentRow(len(self._model.parts) - 1)
        self._schedule()
        return part

    def duplicate_part(self) -> None:
        part = self.selected_part()
        if part is None:
            return
        twin = copy.deepcopy(part)
        twin.name = unique_name(part.name, [p.name for p in self._model.parts])
        self._model.parts.insert(self.parts_list.currentRow() + 1, twin)
        row = self.parts_list.currentRow() + 1
        self._refresh_parts_list()
        self.parts_list.setCurrentRow(row)
        self._schedule()

    def delete_part(self) -> None:
        row = self.parts_list.currentRow()
        if not 0 <= row < len(self._model.parts):
            return
        del self._model.parts[row]
        self._drop_unused_meshes()
        self._refresh_parts_list()
        if not self._model.parts:
            self._show_part_form(None)
        self._schedule()

    def _drop_unused_meshes(self) -> None:
        used = sorted({p.mesh_index for p in self._model.parts if p.shape == "mesh"})
        remap = {old: new for new, old in enumerate(used)}
        self._model.meshes = [self._model.meshes[k] for k in used]
        for part in self._model.parts:
            if part.shape == "mesh":
                part.mesh_index = remap[part.mesh_index]

    def _on_part_selected(self, row: int) -> None:
        self._show_part_form(self.selected_part())
        self._redraw()

    # -- importing ---------------------------------------------------------------------------------------------

    def _on_import_obj(self) -> None:
        start = str(self._base_dir) if self._base_dir else str(Path.home())
        name, _ = QFileDialog.getOpenFileName(self, "Import a 3D model", start, "Wavefront OBJ (*.obj *.OBJ)")
        if not name:
            return
        options = _ImportOptionsDialog(Path(name), self._base_dir is not None, self)
        if options.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.import_obj(name, units=options.units.currentData(), up_axis=options.up_axis.currentData(),
                            copy_to_scenario=options.copy_check.isChecked())
        except (OSError, obj_io.ObjError) as exc:
            report(self, f"Could not import {name}: {exc}")

    def import_obj(self, path, units: str = "m", up_axis: str = "z", copy_to_scenario: bool = False) -> List[str]:
        """Add every group of the ``.obj`` at ``path`` as a mesh part (mass
        0 until set); returns their names. Raises ObjError or OSError."""
        source = Path(path)
        obj = obj_io.read_obj(source, units=units, up_axis=up_axis)  # check before anything is copied
        if copy_to_scenario and self._base_dir is not None:
            target_dir = self._base_dir / "models"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / source.name
            if target.resolve() != source.resolve():
                shutil.copy2(source, target)
                for mtl in self._mtl_files(source):
                    shutil.copy2(mtl, target_dir / mtl.name)
            source = target
        stored = self._stored_path(source)
        self._model.meshes.append(ModelMeshConfig(path=stored, sha256=model3d.file_sha256(source), units=units,
                                                  up_axis=up_axis))
        index = len(self._model.meshes) - 1
        names = []
        for group in obj.groups:
            name = unique_name(group.name, [p.name for p in self._model.parts])
            color = list(group.color) if group.color is not None else [0.7, 0.7, 0.7]
            self._model.parts.append(ModelPartConfig(name=name, shape="mesh", mesh_index=index,
                                                     mesh_group=group.name, color=color, mass_kg=0.0))
            names.append(name)
        self._refresh_parts_list()
        self.parts_list.setCurrentRow(len(self._model.parts) - len(names))
        self._schedule()
        return names

    @staticmethod
    def _mtl_files(obj_path: Path) -> List[Path]:
        files = []
        for line in obj_path.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split("#", 1)[0].split()
            if parts[:1] == ["mtllib"]:
                name = " ".join(parts[1:])
                candidate = obj_path.parent / name
                if Path(name).name == name and candidate.is_file():
                    files.append(candidate)
        return files

    def _stored_path(self, path: Path) -> str:
        """Relative to the scenario's folder when inside it, else absolute."""
        path = path.resolve()
        if self._base_dir is not None:
            try:
                return path.relative_to(self._base_dir.resolve()).as_posix()
            except ValueError:
                pass
        return str(path)

    # -- part form ---------------------------------------------------------------------------------------------

    def _show_part_form(self, part: Optional[ModelPartConfig]) -> None:
        self._loading_form = True
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self.part_widgets = {}
        if part is None:
            hint = QLabel("Add a shape, or import an .obj file. Each part gets a size, a place, a mass and the "
                          "surface properties drag and sunlight act on.")
            hint.setWordWrap(True)
            form.addRow(hint)
            self._form_area.setWidget(form_widget)
            self._loading_form = False
            return
        w = self.part_widgets
        w["name"] = QLineEdit(part.name)
        w["name"].editingFinished.connect(self._on_name_edited)
        form.addRow("Name", w["name"])
        if part.shape == "mesh":
            mesh = self._model.meshes[part.mesh_index] if part.mesh_index is not None and part.mesh_index < len(
                self._model.meshes) else None
            source = QLabel(f"group '{part.mesh_group}' of {mesh.path if mesh else '?'}"
                            + (f" ({mesh.units}, {mesh.up_axis} up)" if mesh else ""))
            source.setWordWrap(True)
            form.addRow("From", source)
        else:
            form.addRow("Shape", QLabel(part.shape))
            for key in MODEL_SHAPE_DIMENSIONS[part.shape]:
                box = _spin(0.001, 1000.0, float(part.dimensions_m.get(key, 1.0)), suffix=" m")
                box.valueChanged.connect(lambda value, k=key: self._set_dimension(k, value))
                w[f"dim:{key}"] = box
                form.addRow(_DIMENSION_LABELS.get(key, key), box)
        if part.shape == "prism":
            w["sides"] = SpinBox()
            w["sides"].setRange(3, 64)
            w["sides"].setValue(part.sides)
            w["sides"].valueChanged.connect(lambda v: self._set("sides", int(v)))
            form.addRow("Sides", w["sides"])
        if part.shape in ("cylinder", "cone", "sphere"):
            w["segments"] = SpinBox()
            w["segments"].setRange(8, 256)
            w["segments"].setValue(part.segments)
            w["segments"].setToolTip("Flat sides it is drawn and faceted with; its mass properties are exact.")
            w["segments"].valueChanged.connect(lambda v: self._set("segments", int(v)))
            form.addRow("Segments", w["segments"])
        self._vector_row(form, "Position [m]", "position_b_m", part.position_b_m, -100.0, 100.0)
        w["position_b_m"][0].parentWidget().setToolTip("x, y, z of the part's centre, from body point B.")
        self._vector_row(form, "Rotation [deg]", "rotation_deg", part.rotation_deg, -360.0, 360.0, step=5.0)
        w["rotation_deg"][0].parentWidget().setToolTip(
            "Roll, pitch, yaw: the part's axes turned from the body axes by yaw about z, then pitch about the new "
            "y, then roll about the new x.")
        if part.shape == "mesh":
            self._vector_row(form, "Scale [-]", "scale", part.scale, -1000.0, 1000.0, decimals=4)
        w["color"] = QPushButton()
        w["color"].clicked.connect(self._on_pick_color)
        self._paint_color_button(part.color)
        w["visible"] = QCheckBox("Shown")
        w["visible"].setToolTip("Drawn in the 3D view and in Vizard. A hidden part keeps its mass and facets.")
        w["visible"].setChecked(part.visible)
        w["visible"].toggled.connect(self._on_visible_toggled)
        form.addRow("Colour", _row(w["color"], w["visible"]))

        mass_group = QGroupBox("Mass")
        mass_form = QFormLayout(mass_group)
        w["mass_kg"] = _spin(0.0, 1.0e6, float(part.mass_kg), step=1.0, suffix=" kg")
        w["mass_kg"].valueChanged.connect(lambda v: self._set("mass_kg", float(v)))
        mass_form.addRow("Mass", w["mass_kg"])
        w["distribution"] = ComboBox()
        w["distribution"].addItem("Solid (through the volume)", "solid")
        w["distribution"].addItem("Shell (over the surface)", "shell")
        w["distribution"].setCurrentIndex(0 if part.distribution == "solid" else 1)
        w["distribution"].currentIndexChanged.connect(
            lambda _i: self._set("distribution", w["distribution"].currentData()))
        mass_form.addRow("Spread", w["distribution"])
        w["counts_toward_mass"] = QCheckBox("Counts toward the spacecraft's mass")
        w["counts_toward_mass"].setToolTip("Untick for a part whose mass is modelled elsewhere, such as a flexible "
                                           "solar array (its mass is in the array's own settings).")
        w["counts_toward_mass"].setChecked(part.counts_toward_mass)
        w["counts_toward_mass"].toggled.connect(lambda v: self._set("counts_toward_mass", bool(v)))
        mass_form.addRow(w["counts_toward_mass"])
        form.addRow(mass_group)

        surface_group = QGroupBox("Surface (drag and solar pressure)")
        surface_form = QFormLayout(surface_group)
        w["in_surface_model"] = QCheckBox("Its outer faces are facets")
        w["in_surface_model"].setChecked(part.in_surface_model)
        w["in_surface_model"].toggled.connect(lambda v: self._set("in_surface_model", bool(v)))
        surface_form.addRow(w["in_surface_model"])
        faces = MODEL_SHAPE_FACES[part.shape]
        if faces:
            face_boxes = []
            for face in faces:
                box = QCheckBox(face)
                box.setChecked(face not in part.excluded_faces)
                box.toggled.connect(self._on_faces_toggled)
                w[f"face:{face}"] = box
                face_boxes.append(box)
            holder = _row(*face_boxes)
            holder.setToolTip("Untick a face that touches another part, so it is not counted as exposed.")
            surface_form.addRow("Faces", holder)
        for key, label in (("drag_coeff", "Drag coefficient"), ("specular_coeff", "Specular reflection"),
                           ("diffuse_coeff", "Diffuse reflection")):
            box = _spin(0.0, 10.0 if key == "drag_coeff" else 1.0, float(getattr(part, key)), step=0.05)
            box.valueChanged.connect(lambda v, k=key: self._set(k, float(v)))
            w[key] = box
            surface_form.addRow(label, box)
        form.addRow(surface_group)
        self._form_area.setWidget(form_widget)
        self._loading_form = False

    def _vector_row(self, form, label: str, field: str, values, low: float, high: float, step: float = 0.05,
                    decimals: int = 3) -> None:
        boxes = []
        for k in range(3):
            box = _spin(low, high, float(values[k]), decimals=decimals, step=step)
            box.valueChanged.connect(lambda _v, f=field: self._set_vector(f))
            boxes.append(box)
        self.part_widgets[field] = boxes
        form.addRow(label, _row(*boxes))

    def _set(self, field: str, value) -> None:
        part = self.selected_part()
        if part is None or self._loading_form:
            return
        setattr(part, field, value)
        self._schedule()

    def _set_dimension(self, key: str, value: float) -> None:
        part = self.selected_part()
        if part is None or self._loading_form:
            return
        part.dimensions_m[key] = float(value)
        self._schedule()

    def _set_vector(self, field: str) -> None:
        self._set(field, [float(b.value()) for b in self.part_widgets[field]])

    def _on_faces_toggled(self) -> None:
        part = self.selected_part()
        if part is None or self._loading_form:
            return
        part.excluded_faces = [face for face in MODEL_SHAPE_FACES[part.shape]
                               if not self.part_widgets[f"face:{face}"].isChecked()]
        self._schedule()

    def _on_visible_toggled(self, visible: bool) -> None:
        self._set("visible", bool(visible))
        self._refresh_parts_list()

    def _on_name_edited(self) -> None:
        part = self.selected_part()
        if part is None:
            return
        name = self.part_widgets["name"].text().strip()
        others = [p.name for p in self._model.parts if p is not part]
        problem = name_error("part", name) or (f"another part is called {name!r}" if name in others else None)
        if problem:
            self.part_widgets["name"].setText(part.name)
            self.messages.setText(problem)
            return
        part.name = name
        self._refresh_parts_list()
        self._schedule()

    def _on_pick_color(self) -> None:
        part = self.selected_part()
        if part is None:
            return
        chosen = QColorDialog.getColor(QColor.fromRgbF(*part.color), self, f"Colour of {part.name}")
        if chosen.isValid():
            part.color = [round(chosen.redF(), 4), round(chosen.greenF(), 4), round(chosen.blueF(), 4)]
            self._paint_color_button(part.color)
            self._schedule()

    def _paint_color_button(self, color) -> None:
        r, g, b = (int(round(255 * c)) for c in color)
        button = self.part_widgets["color"]
        button.setText(f"#{r:02X}{g:02X}{b:02X}")
        button.setStyleSheet(swatch_style(f"#{r:02X}{g:02X}{b:02X}"))

    # -- bottom tabs -------------------------------------------------------------------------------------------

    def _build_bottom_tabs(self) -> QWidget:
        tabs = TabWidget()
        tabs.addTab(self._build_mass_tab(), "Mass properties")
        surfaces = QWidget()
        surfaces_layout = QVBoxLayout(surfaces)
        self.surfaces_label = QLabel()
        self.surfaces_label.setWordWrap(True)
        self.surfaces_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        surfaces_layout.addWidget(self.surfaces_label)
        surfaces_layout.addStretch(1)
        tabs.addTab(surfaces, "Surfaces")
        tabs.addTab(self._build_use_tab(), "Use")
        self.bottom_tabs = tabs
        return tabs

    def _build_mass_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        left = QVBoxLayout()
        self.source_group = QButtonGroup(self)
        self.source_buttons = {}
        for source, label in (("computed", "Computed from the parts"), ("typed", "Typed in"),
                              ("imported", "Imported from a file")):
            button = QRadioButton(label)
            self.source_group.addButton(button)
            self.source_buttons[source] = button
            button.toggled.connect(self._on_source_toggled)
            left.addWidget(button)
        self.import_mass_button = QPushButton("Import file...")
        self.import_mass_button.setToolTip("JSON or CSV with mass, center of mass and inertia (format: User Manual).")
        self.import_mass_button.clicked.connect(self._on_import_mass)
        self.copy_computed_button = QPushButton("Start from the computed values")
        self.copy_computed_button.clicked.connect(self._copy_computed_to_typed)
        left.addWidget(self.import_mass_button)
        left.addWidget(self.copy_computed_button)
        self.mass_source_label = QLabel()
        self.mass_source_label.setWordWrap(True)
        left.addWidget(self.mass_source_label)
        left.addStretch(1)
        layout.addLayout(left)

        typed_group = QGroupBox("Typed values (about the center of mass, body axes)")
        typed_form = QFormLayout(typed_group)
        self.typed_mass = _spin(0.001, 1.0e6, 100.0, step=1.0, suffix=" kg")
        typed_form.addRow("Mass", self.typed_mass)
        self.typed_com = [_spin(-100.0, 100.0, 0.0, decimals=4, step=0.01) for _ in range(3)]
        typed_form.addRow("Center of mass [m] from B", _row(*self.typed_com))
        self.typed_inertia = {key: _spin(-1.0e8 if key[1] != key[2] else 0.0, 1.0e8, 0.0, decimals=4, step=1.0)
                              for key in ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")}
        typed_form.addRow("Ixx, Iyy, Izz [kg m^2]",
                          _row(self.typed_inertia["Ixx"], self.typed_inertia["Iyy"], self.typed_inertia["Izz"]))
        typed_form.addRow("Ixy, Ixz, Iyz [kg m^2]",
                          _row(self.typed_inertia["Ixy"], self.typed_inertia["Ixz"], self.typed_inertia["Iyz"]))
        products_note = QLabel("Products of inertia in tensor form: Ixy = -integral(x y dm).")
        set_role(products_note, tone="secondary")
        typed_form.addRow(products_note)
        for box in [self.typed_mass, *self.typed_com, *self.typed_inertia.values()]:
            box.valueChanged.connect(self._on_typed_changed)
        self.typed_group = typed_group
        layout.addWidget(typed_group, 1)

        self.mass_summary = QLabel()
        self.mass_summary.setWordWrap(True)
        self.mass_summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary_group = QGroupBox("Result")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.addWidget(self.mass_summary)
        layout.addWidget(summary_group, 1)
        return tab

    def _load_mass_tab(self) -> None:
        self._loading_form = True
        self.source_buttons[self._model.mass_properties_source].setChecked(True)
        typed = self._model.mass_properties
        if typed is not None:
            self._show_typed(typed)
        self._loading_form = False
        self._update_mass_controls()

    def _show_typed(self, typed: ModelMassPropertiesConfig) -> None:
        loading = self._loading_form
        self._loading_form = True
        self.typed_mass.setValue(typed.mass_kg)
        for box, value in zip(self.typed_com, typed.center_of_mass_b_m):
            box.setValue(value)
        i = typed.inertia_kg_m2
        for key, index in (("Ixx", 0), ("Iyy", 4), ("Izz", 8), ("Ixy", 1), ("Ixz", 2), ("Iyz", 5)):
            self.typed_inertia[key].setValue(i[index])
        self._loading_form = loading

    def _typed_from_form(self) -> ModelMassPropertiesConfig:
        t = {k: float(b.value()) for k, b in self.typed_inertia.items()}
        previous = self._model.mass_properties
        return ModelMassPropertiesConfig(
            mass_kg=float(self.typed_mass.value()), center_of_mass_b_m=[float(b.value()) for b in self.typed_com],
            inertia_kg_m2=[t["Ixx"], t["Ixy"], t["Ixz"], t["Ixy"], t["Iyy"], t["Iyz"], t["Ixz"], t["Iyz"], t["Izz"]],
            source_file=previous.source_file if previous is not None and self._source() == "imported" else "",
            source_sha256=previous.source_sha256 if previous is not None and self._source() == "imported" else "")

    def _source(self) -> str:
        return next(s for s, b in self.source_buttons.items() if b.isChecked())

    def _on_source_toggled(self, checked: bool) -> None:
        if not checked or self._loading_form:
            return
        source = self._source()
        self._model.mass_properties_source = source
        if source != "computed" and self._model.mass_properties is None:
            self._copy_computed_to_typed()
        self._update_mass_controls()
        self._schedule()

    def _update_mass_controls(self) -> None:
        source = self._model.mass_properties_source
        self.typed_group.setEnabled(source == "typed")
        self.copy_computed_button.setEnabled(source == "typed")
        typed = self._model.mass_properties
        if source == "imported" and typed is not None and typed.source_file:
            self.mass_source_label.setText(f"From {typed.source_file} (SHA-256 {typed.source_sha256[:12]}...)")
        else:
            self.mass_source_label.setText("")

    def _on_typed_changed(self) -> None:
        if self._loading_form or self._source() != "typed":
            return
        self._model.mass_properties = self._typed_from_form()
        self._schedule()

    def _copy_computed_to_typed(self) -> None:
        computed = model3d.tidy(self.derived.computed) if self.derived.computed.mass_kg > 0.0 else None
        typed = ModelMassPropertiesConfig(
            mass_kg=computed.mass_kg if computed else 100.0,
            center_of_mass_b_m=[float(v) for v in computed.center_of_mass_m] if computed else [0.0, 0.0, 0.0],
            inertia_kg_m2=[float(v) for v in computed.inertia_kg_m2.reshape(9)] if computed else
            [10.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 10.0])
        self._model.mass_properties = typed
        self._show_typed(typed)
        self._schedule()

    def _on_import_mass(self) -> None:
        start = str(self._base_dir) if self._base_dir else str(Path.home())
        name, _ = QFileDialog.getOpenFileName(self, "Import mass properties", start,
                                              "Mass properties (*.json *.csv)")
        if name:
            try:
                notes = self.import_mass_properties(name)
            except mass_import.MassImportError as exc:
                report(self, f"Could not import the mass properties from {name}: {exc}")
                return
            if notes:
                self.messages.setText("; ".join(notes))

    def import_mass_properties(self, path) -> List[str]:
        """Read a mass-properties file and use it (source "imported")."""
        config, notes = mass_import.read_mass_properties(path)
        self._model.mass_properties = config
        self._model.mass_properties_source = "imported"
        self._loading_form = True
        self.source_buttons["imported"].setChecked(True)
        self._loading_form = False
        self._show_typed(config)
        self._update_mass_controls()
        self._schedule()
        return notes

    def _build_use_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.use_note = QLabel(uses_note(self._simulation_mode))
        self.use_note.setWordWrap(True)
        self.use_note.setVisible(bool(self.use_note.text()))
        layout.addWidget(self.use_note)
        self.apply_mass_check = QCheckBox("Apply the mass properties to the spacecraft (mass, center of mass, inertia)")
        self.apply_facets_check = QCheckBox("Apply the facets (drag and solar pressure; full-attitude runs only)")
        self.use_for_vizard_check = QCheckBox("Show this model in Vizard")
        for box, field in ((self.apply_mass_check, "apply_mass_properties"), (self.apply_facets_check, "apply_facets"),
                           (self.use_for_vizard_check, "use_for_vizard")):
            box.toggled.connect(lambda v, f=field: self._set_model_flag(f, v))
            layout.addWidget(box)
        self.export_button = QPushButton("Export .obj...")
        self.export_button.setToolTip("Writes the visible parts as a Wavefront .obj and .mtl: body frame, metres, +z up.")
        self.export_button.clicked.connect(self._on_export)
        layout.addWidget(self.export_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return tab

    def _load_use_tab(self) -> None:
        self._loading_form = True
        self.apply_mass_check.setChecked(self._model.apply_mass_properties)
        self.apply_facets_check.setChecked(self._model.apply_facets)
        self.use_for_vizard_check.setChecked(self._model.use_for_vizard)
        self._loading_form = False

    def _set_model_flag(self, field: str, value: bool) -> None:
        if not self._loading_form:
            setattr(self._model, field, bool(value))

    def _on_export(self) -> None:
        groups = model3d.obj_groups(self.derived)
        if not groups:
            report(self, "Nothing to export: the model has no part that can be drawn", kind="info")
            return
        start = str((self._base_dir or Path.home()) / f"{self._spacecraft_name}.obj")
        name, _ = QFileDialog.getSaveFileName(self, "Export the 3D model", start, "Wavefront OBJ (*.obj)")
        if name:
            try:
                obj_io.write_obj(name, groups)
            except OSError as exc:
                report(self, f"Could not export the model to {name}: {exc}")
                return
            report(self, f"Exported the model to {name}", kind="success")

    # -- recomputing -------------------------------------------------------------------------------------------

    def _schedule(self) -> None:
        self._recompute_timer.start()

    def recompute_now(self) -> None:
        """Derive the model now and update the view, the tabs and messages."""
        self._recompute_timer.stop()
        self.derived = model3d.derive(self._model, self._base_dir, cache=self._cache)
        props = self.derived.mass_properties
        computed = self.derived.computed
        lines = []
        if props is not None:
            lines += model3d.principal_summary(props)
        else:
            lines.append("No mass yet: give the parts a mass.")
        if self._model.mass_properties_source != "computed" and computed.mass_kg > 0.0:
            lines.append(f"(the parts give {computed.mass_kg:.6g} kg)")
        self.mass_summary.setText("\n".join(lines))
        if self.derived.faces:
            areas = self.derived.projected_areas_m2()
            total = sum(f.area_m2 for f in self.derived.faces)
            seen = "\n".join(f"  seen from {axis}: {area:.4g} m^2" for axis, area in areas.items())
            self.surfaces_label.setText(f"{len(self.derived.faces)} facets, {total:.4g} m^2 in all\n{seen}\n"
                                        "Each facet takes its part's drag and reflection coefficients. Parts do not "
                                        "shade each other in the simulation.")
        else:
            self.surfaces_label.setText("No facets: no part is in the surface model.")
        problems = self.derived.errors + self.derived.warnings
        self.messages.setText("\n".join(problems))
        self._redraw()

    def _redraw(self) -> None:
        part = self.selected_part()
        self.view.show_model(self.derived, part.name if part is not None else None)

    # -- result ------------------------------------------------------------------------------------------------

    def model(self) -> SpacecraftModelConfig:
        """The edited model (a copy; the one passed in is untouched)."""
        return copy.deepcopy(self._model)

    def _on_ok(self) -> None:
        if self._model.mass_properties_source == "typed":
            self._model.mass_properties = self._typed_from_form()
        try:
            self._model.validate(self._spacecraft_name)
        except ScenarioValidationError as exc:
            show_dialog_error(self, f"The model is not complete: {exc}")
            return
        self.recompute_now()
        if self.derived.errors:
            answer = QMessageBox.question(
                self, "Parts that cannot be built",
                "These parts cannot be built and are left out of the model, its mass and its facets:\n\n"
                + "\n".join(self.derived.errors) + "\n\nKeep the model without them?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.accept()
