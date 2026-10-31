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

"""MissionDashboardWidget: a live, at-a-glance telemetry readout for a
``schema.scenario.CommsPointingConfig`` spacecraft -- the GUI counterpart
to template '19' (``19_sun_pointing_comms_link.json``). Takes a plain
``engine.results.ResultSet`` (no Basilisk import in this module, same
"testable with synthetic data" convention as ``results_widget.py``) plus
an optional ``schema.scenario.Scenario`` (for the RF/power config needed
to recompute a live link-budget breakdown and a battery SOC percentage --
see :meth:`set_result`'s docstring for exactly what each unlocks).

Follows ``ResultsWidget``'s own ``set_result()``/``set_live_result()``
calling convention exactly, so ``gui/main_window.py`` can feed it from
the same ``RunWorker.progress``/``finished_ok``/``cancelled`` signals
with one more call alongside each existing ``results_widget`` one --
``engine.service.SimulationService.run_live()`` already re-derives the
FULL ``ResultSet`` (including this feature's own
``{sc}.comms_pointing.*`` series) on every progress chunk, so this widget
is "live" for free, the same way ``ResultsWidget`` already is.

Single-spacecraft assumption: this dashboard shows ONE spacecraft -- the
first one found carrying a ``{sc}.comms_pointing.active_mode`` series in
the given ``ResultSet`` (see :func:`_find_comms_pointing_spacecraft`).
Matches ``gui/template_wizard.py``'s own ``_sc()`` helper's documented
"every current wizard spec is single-spacecraft" precedent -- a future
multi-spacecraft version would need one panel per spacecraft, not a
change to this module's own per-spacecraft logic.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import registry
from ..engine import link_budget, power_state
from ..engine.results import ResultSet
from ..schema.scenario import Scenario
from .badges import ACCENT as _ACCENT_BADGE, DANGER as _DANGER_BADGE, MUTED as _MUTED_BADGE
from .badges import SUCCESS as _SUCCESS_BADGE, set_badge
from .calculation_panel import Explanation
from .theme import set_role


def _find_comms_pointing_spacecraft(result: ResultSet | None) -> str | None:
    """The first spacecraft name with a recorded
    ``{name}.comms_pointing.active_mode`` series, or ``None`` if the
    given result has none (e.g. no run yet, or a scenario with no
    ``comms_pointing`` spacecraft at all).
    """
    if result is None:
        return None
    suffix = ".comms_pointing.active_mode"
    for series_name in result.series:
        if series_name.endswith(suffix):
            return series_name[: -len(suffix)]
    return None


def _find_ground_station(result: ResultSet, spacecraft_name: str,
                          comms_pointing_target_ground_station: str | None = None) -> str | None:
    """The ground station this panel should show for ``spacecraft_name``.

    When ``comms_pointing_target_ground_station`` is given (the
    spacecraft's own ``schema.scenario.CommsPointingConfig.
    target_ground_station``, when a ``Scenario`` is available -- see
    :meth:`MissionDashboardWidget._refresh`) and that pair was actually
    recorded, it's used directly: a ``comms_pointing`` spacecraft has
    exactly one antenna under that mode arbitrator's control, so it is
    the ONLY ground station whose access/link-margin series mean
    anything for this panel, even if another station happens to be
    simultaneously, geometrically visible too (see
    ``engine.link_budget.link_margin_series``'s own docstring for the
    same reasoning on the engine side). Otherwise falls back to the
    FIRST ``{gs}.access_to_{sc}.has_access`` pairing found in
    ``result.series`` (e.g. no ``Scenario`` was given alongside this
    ``ResultSet``) -- matching this module's own single-spacecraft-panel
    scope (a spacecraft tracked by more than one ground station would
    need more than one RF panel, not handled here).
    """
    if comms_pointing_target_ground_station is not None:
        if f"{comms_pointing_target_ground_station}.access_to_{spacecraft_name}.has_access" in result.series:
            return comms_pointing_target_ground_station
        return None
    suffix = f".access_to_{spacecraft_name}.has_access"
    for series_name in result.series:
        if series_name.endswith(suffix):
            return series_name[: -len(suffix)]
    return None


_sample_index = power_state.sample_index  # the last sample at or before the time cursor, else the last one


def _latest(result: ResultSet, series_name: str, at_s: float | None = None) -> float | None:
    series = result.series.get(series_name)
    if series is None or series.data.shape[0] == 0:
        return None
    return float(series.data[_sample_index(series, at_s), 0])


def _card_form(box: QGroupBox) -> QFormLayout:
    """A card's form: values (and badges) at their natural width, not
    stretched into full-width bars."""
    form = QFormLayout(box)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    form.setHorizontalSpacing(14)
    form.setVerticalSpacing(6)
    return form


class MissionDashboardWidget(QWidget):
    """``calculation_requested(Explanation)``: Show calculation was chosen
    for the link budget at the time cursor."""

    calculation_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._link_inputs = None  # (range, rf_link, station, angle, the sources) of the budget shown
        self._power_inputs = None  # (spacecraft, battery capacity [W*h] or None, the cursor [s] or None)
        self._result: ResultSet | None = None
        self._scenario: Scenario | None = None
        self._cursor_s: float | None = None  # [s] the shared time cursor, or None (the latest sample)

        layout = QVBoxLayout(self)

        self._placeholder = QLabel(
            "No live telemetry yet. Run a scenario with Comms pointing (e.g. template 19) to see it here."
        )
        self._placeholder.setWordWrap(True)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)  # same centered empty state as the Results tab
        set_role(self._placeholder, tone="secondary")
        layout.addWidget(self._placeholder)

        # Cards sized to their content, in two columns (one when the pane
        # is narrow -- see resizeEvent), with spare height left below them
        # (real user feedback on clutter: the cards used to stretch to the
        # full tab height, ~85% empty).
        self._panels_grid = QGridLayout()
        self._panels_grid.setHorizontalSpacing(12)
        self._panels_grid.setVerticalSpacing(12)
        layout.addLayout(self._panels_grid)
        layout.addStretch(1)
        self._columns = 0

        # -- Operating state --------------------------------------------
        self._state_box = QGroupBox("Operating state")
        state_form = _card_form(self._state_box)
        self.sim_time_label = QLabel("--")
        self.mode_badge = QLabel("--")
        self.visibility_badge = QLabel("--")
        state_form.addRow("Sim time:", self.sim_time_label)
        state_form.addRow("Mode:", self.mode_badge)
        state_form.addRow("Ground station:", self.visibility_badge)

        # -- Attitude -----------------------------------------------------
        self._attitude_box = QGroupBox("Attitude")
        attitude_form = _card_form(self._attitude_box)
        self.pointing_error_label = QLabel("--")
        self.tracking_badge = QLabel("--")
        attitude_form.addRow("Pointing error:", self.pointing_error_label)
        attitude_form.addRow("Tracking:", self.tracking_badge)

        # -- Power ----------------------------------------------------------
        self._power_box = QGroupBox("Power")
        power_form = _card_form(self._power_box)
        self.battery_charge_label = QLabel("--")
        # A slim gauge with the percentage beside it: the old "67% SOC"
        # text drawn across the bar was grey on blue and hard to read.
        self.battery_soc_bar = QProgressBar()
        self.battery_soc_bar.setRange(0, 100)
        self.battery_soc_bar.setTextVisible(False)
        self.battery_soc_bar.setFixedSize(140, 10)  # [px]
        self.battery_soc_label = QLabel("--")
        soc_row = QWidget()
        soc_layout = QHBoxLayout(soc_row)
        soc_layout.setContentsMargins(0, 0, 0, 0)
        soc_layout.addWidget(self.battery_soc_bar)
        soc_layout.addWidget(self.battery_soc_label)
        self.net_power_label = QLabel("--")
        power_form.addRow("Battery charge:", self.battery_charge_label)
        power_form.addRow("State of charge:", soc_row)
        power_form.addRow("Net power:", self.net_power_label)
        self.power_calculation_button = QPushButton("Show calculation")
        self.power_calculation_button.setToolTip("How the battery charge, state of charge and net power at the "
                                                 "time cursor were read: each series and sample, and the capacity")
        self.power_calculation_button.setEnabled(False)
        self.power_calculation_button.clicked.connect(self.show_power_calculation)
        power_form.addRow(self.power_calculation_button)

        # -- RF link --------------------------------------------------------
        self._rf_box = QGroupBox("RF link")
        rf_form = _card_form(self._rf_box)
        self.link_status_badge = QLabel("--")
        self.slant_range_label = QLabel("--")
        self.eirp_label = QLabel("--")
        self.fspl_label = QLabel("--")
        self.pointing_loss_label = QLabel("--")
        self.received_power_label = QLabel("--")
        self.noise_label = QLabel("--")
        self.cn0_label = QLabel("--")
        self.ebno_label = QLabel("--")
        self.margin_label = QLabel("--")
        # The answer first (status, margin, range), then the link budget as
        # a muted breakdown: ten equally weighted rows hid the margin.
        set_role(self.margin_label, role="strong")
        rf_form.addRow("Link status:", self.link_status_badge)
        rf_form.addRow("Link margin:", self.margin_label)
        rf_form.addRow("Slant range:", self.slant_range_label)
        budget_heading = QLabel("Link budget")
        set_role(budget_heading, role="heading", tone="secondary")
        rf_form.addRow(budget_heading)
        for text, value_label in (("EIRP", self.eirp_label), ("Free-space path loss", self.fspl_label),
                                  ("Antenna pointing loss", self.pointing_loss_label),
                                  ("Received power", self.received_power_label), ("Noise (N0)", self.noise_label),
                                  ("C/N0", self.cn0_label), ("Eb/N0", self.ebno_label)):
            row_label = QLabel(f"{text}:")
            set_role(row_label, tone="secondary")
            set_role(value_label, tone="secondary")
            rf_form.addRow(row_label, value_label)
        self.calculation_button = QPushButton("Show calculation")
        self.calculation_button.setToolTip("How the link budget at the time cursor was computed: each figure's "
                                           "equation, its inputs and their sources")
        self.calculation_button.setEnabled(False)
        self.calculation_button.clicked.connect(self.show_calculation)
        rf_form.addRow(self.calculation_button)
        self._arrange_cards(2)

        self._set_panels_visible(False)

    _ONE_COLUMN_BELOW_PX = 760  # [px] narrower than this, cards stack in one column

    def _arrange_cards(self, columns: int) -> None:
        """Place the cards in ``columns`` independent stacks (1 or 2): each
        card keeps its own height instead of matching its row neighbour."""
        if columns == self._columns:
            return
        self._columns = columns
        while self._panels_grid.count():
            old_stack = self._panels_grid.takeAt(0).widget()
            for card in (self._state_box, self._attitude_box, self._power_box, self._rf_box):
                card.setParent(self)  # keep the cards; only the empty stack goes
            if old_stack is not None:
                old_stack.deleteLater()
        stacks = ([[self._state_box, self._attitude_box, self._power_box, self._rf_box]] if columns == 1
                  else [[self._state_box, self._attitude_box], [self._power_box, self._rf_box]])
        for column, cards in enumerate(stacks):
            stack = QWidget()
            stack_layout = QVBoxLayout(stack)
            stack_layout.setContentsMargins(0, 0, 0, 0)
            stack_layout.setSpacing(12)
            for card in cards:
                stack_layout.addWidget(card)
            stack_layout.addStretch(1)
            self._panels_grid.addWidget(stack, 0, column)
        for column in range(2):
            self._panels_grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event):  # noqa: N802 -- Qt API name
        super().resizeEvent(event)
        self._arrange_cards(1 if event.size().width() < self._ONE_COLUMN_BELOW_PX else 2)

    def _set_panels_visible(self, visible: bool) -> None:
        self._state_box.setVisible(visible)
        self._attitude_box.setVisible(visible)
        self._power_box.setVisible(visible)
        self._rf_box.setVisible(visible)
        self._placeholder.setVisible(not visible)

    def explanation(self) -> Explanation | None:
        """The link margin's calculation at the time cursor; the budget's
        other figures are reached from it."""
        if self._link_inputs is None:
            return None
        range_m, rf_link, station, angle, range_source, angle_source, title = self._link_inputs
        traces = link_budget.link_budget_traces(range_m, rf_link, station, angle, self._scenario, range_source,
                                                angle_source)
        first = traces.pop("margin")
        return Explanation(title, [first, *traces.values()])

    def show_calculation(self) -> None:
        explanation = self.explanation()
        if explanation is not None:
            self.calculation_requested.emit(explanation)

    def power_explanation(self) -> Explanation | None:
        """How the Power card's figures were read at the time cursor: the
        state of charge first when there is one, then the net power and the
        charge."""
        if self._power_inputs is None or self._result is None:
            return None
        spacecraft, capacity_wh, at_s = self._power_inputs
        traces = power_state.battery_traces(self._result, spacecraft, capacity_wh, at_s)
        if not traces:
            return None
        order = [traces[key] for key in ("state_of_charge", "net_power", "charge") if key in traces]
        return Explanation(f"Power: {spacecraft}", order)

    def show_power_calculation(self) -> None:
        explanation = self.power_explanation()
        if explanation is not None:
            self.calculation_requested.emit(explanation)

    def set_time_cursor(self, cursor) -> None:
        """Show the values at ``cursor`` (a :class:`gui.time_cursor.TimeCursor`) instead of the latest."""
        cursor.changed.connect(self._on_cursor_changed)
        self._on_cursor_changed(cursor.time_s)

    def _on_cursor_changed(self, time_s: float | None) -> None:
        self._cursor_s = time_s
        self._refresh()

    def set_result(self, result: ResultSet | None, scenario: Scenario | None = None) -> None:
        self._result = result
        self._scenario = scenario
        self._refresh()

    def set_live_result(self, result: ResultSet, scenario: Scenario | None = None) -> None:
        """Updates the dashboard with one chunk's worth of a still
        -running simulation -- see ``ResultsWidget.set_live_result()``'s
        own docstring for the live-update story this mirrors. Unlike that
        method, this widget holds no per-series UI state to avoid
        rebuilding (there is no series picker here), so this is simply an
        alias for :meth:`set_result`.
        """
        self.set_result(result, scenario)

    def _refresh(self) -> None:
        sc_name = _find_comms_pointing_spacecraft(self._result)
        if sc_name is None:
            self._set_panels_visible(False)
            self._link_inputs = self._power_inputs = None
            return
        self._set_panels_visible(True)
        result = self._result
        assert result is not None  # noqa: S101 -- type narrowing; _result is set when sc_name is

        sc_config = None
        if self._scenario is not None:
            sc_config = next((sc for sc in self._scenario.spacecraft if sc.name == sc_name), None)

        # -- Operating state --------------------------------------------
        active_mode_series = result.series.get(f"{sc_name}.comms_pointing.active_mode")
        at_s = self._cursor_s  # the shared time cursor; None: the end of the run
        sim_time_s = float(active_mode_series.time_s[_sample_index(active_mode_series, at_s)]) \
            if active_mode_series is not None and active_mode_series.time_s.shape[0] > 0 else None
        self.sim_time_label.setText((f"{sim_time_s:,.1f} s" + (" (time cursor)" if at_s is not None else ""))
                                    if sim_time_s is not None else "--")

        active_mode = _latest(result, f"{sc_name}.comms_pointing.active_mode", at_s)
        is_comms_mode = bool(active_mode is not None and active_mode > 0.5)
        if active_mode is None:
            self.mode_badge.setText("Unknown")
            set_badge(self.mode_badge, _MUTED_BADGE)
        elif is_comms_mode:
            self.mode_badge.setText("Ground-station-pointing")
            set_badge(self.mode_badge, _ACCENT_BADGE)
        else:
            self.mode_badge.setText("Sun-pointing")
            set_badge(self.mode_badge, _SUCCESS_BADGE)

        comms_target = sc_config.comms_pointing.target_ground_station \
            if sc_config is not None and sc_config.comms_pointing is not None else None
        gs_name = _find_ground_station(result, sc_name, comms_target)
        has_access = None
        slant_range_m = None
        if gs_name is not None:
            has_access_val = _latest(result, f"{gs_name}.access_to_{sc_name}.has_access", at_s)
            has_access = bool(has_access_val is not None and has_access_val > 0.5)
            slant_range_m = _latest(result, f"{gs_name}.access_to_{sc_name}.slant_range", at_s)
        if has_access is None:
            self.visibility_badge.setText("Unknown")
            set_badge(self.visibility_badge, _MUTED_BADGE)
        elif has_access:
            self.visibility_badge.setText(f"In view of {gs_name}")
            set_badge(self.visibility_badge, _ACCENT_BADGE)
        else:
            self.visibility_badge.setText("No ground station in view")
            set_badge(self.visibility_badge, _MUTED_BADGE)

        # -- Attitude -----------------------------------------------------
        pointing_error_deg = _latest(result, f"{sc_name}.comms_pointing.pointing_error_deg", at_s)
        self.pointing_error_label.setText(
            f"{pointing_error_deg:.2f} deg" if pointing_error_deg is not None else "--"
        )
        if pointing_error_deg is None:
            self.tracking_badge.setText("Unknown")
            set_badge(self.tracking_badge, _MUTED_BADGE)
        elif pointing_error_deg < registry.value("results.pointing_converged_deg", self._scenario):  # [deg]
            self.tracking_badge.setText("Converged")
            set_badge(self.tracking_badge, _SUCCESS_BADGE)
        else:
            self.tracking_badge.setText("Slewing")
            set_badge(self.tracking_badge, _ACCENT_BADGE)

        # -- Power ----------------------------------------------------------
        battery_charge_wh = _latest(result, f"{sc_name}.battery_charge", at_s)
        net_power_w = _latest(result, f"{sc_name}.battery_net_power", at_s)
        self.battery_charge_label.setText(f"{battery_charge_wh:.2f} W*hr" if battery_charge_wh is not None else "--")
        battery_capacity_wh = sc_config.power.battery_capacity_wh if sc_config is not None and \
            sc_config.power is not None else None
        self._power_inputs = (sc_name, battery_capacity_wh, at_s) \
            if battery_charge_wh is not None or net_power_w is not None else None
        self.power_calculation_button.setEnabled(self._power_inputs is not None)
        if battery_charge_wh is not None and battery_capacity_wh is not None and battery_capacity_wh > 0:
            soc_pct = power_state.state_of_charge_pct(battery_charge_wh, battery_capacity_wh)
            self.battery_soc_bar.setValue(int(round(soc_pct)))
            self.battery_soc_bar.setEnabled(True)
            self.battery_soc_label.setText(f"{soc_pct:.0f}%")
        else:
            self.battery_soc_bar.setValue(0)
            self.battery_soc_bar.setEnabled(False)
            self.battery_soc_label.setText("--")
        if net_power_w is not None:
            sign = "+" if net_power_w >= 0 else ""
            self.net_power_label.setText(f"{sign}{net_power_w:.2f} W")
            set_role(self.net_power_label, tone="normal" if net_power_w >= 0 else "critical")
        else:
            self.net_power_label.setText("--")
            set_role(self.net_power_label, tone=None)

        # -- RF link --------------------------------------------------------
        self._refresh_rf_link(sc_config, gs_name, has_access, is_comms_mode, slant_range_m, pointing_error_deg)

    def _refresh_rf_link(self, sc_config, gs_name: str | None, has_access: bool | None,
                          is_comms_mode: bool, slant_range_m: float | None,
                          pointing_error_deg: float | None) -> None:
        self.slant_range_label.setText(f"{slant_range_m / 1000.0:,.1f} km" if slant_range_m is not None else "--")

        rf_link = sc_config.rf_link if sc_config is not None else None
        gs_config = None
        if self._scenario is not None and gs_name is not None:
            gs_config = next((gs for gs in self._scenario.ground_stations if gs.name == gs_name), None)

        # Gated on has_access AND is_comms_mode -- matching
        # engine.link_budget.link_margin_series()'s own gating exactly
        # (see that function's docstring): real geometric access alone
        # does not mean the spacecraft has actually switched into
        # ground-station-pointing mode yet, so no link attempt -- and so
        # no breakdown -- should be shown while it's still Sun-pointing,
        # even if the ground station happens to already be visible.
        breakdown = None
        self._link_inputs = None
        self.calculation_button.setEnabled(False)
        if rf_link is not None and gs_config is not None and slant_range_m is not None \
                and has_access and is_comms_mode:
            breakdown = link_budget.link_budget_breakdown(
                slant_range_m, rf_link, gs_config, pointing_error_deg or 0.0, self._scenario
            )
            sc_name = sc_config.name
            at = "the time cursor" if self._cursor_s is not None else "the end of the run"
            range_source = f"last run: {gs_name}.access_to_{sc_name}.slant_range, at {at}"
            angle_source = (f"last run: {sc_name}.comms_pointing.pointing_error_deg, at {at}"
                            if pointing_error_deg is not None else "computed: no pointing series, taken as 0")
            self._link_inputs = (slant_range_m, rf_link, gs_config, pointing_error_deg or 0.0, range_source,
                                 angle_source, f"Link: {sc_name} to {gs_name}")
            self.calculation_button.setEnabled(True)

        if breakdown is None:
            for label in (self.eirp_label, self.fspl_label, self.pointing_loss_label,
                          self.received_power_label, self.noise_label, self.cn0_label,
                          self.ebno_label, self.margin_label):
                label.setText("--")
            if has_access is None:
                self.link_status_badge.setText("Unknown")
                set_badge(self.link_status_badge, _MUTED_BADGE)
            elif not has_access:
                self.link_status_badge.setText("No access")
                set_badge(self.link_status_badge, _MUTED_BADGE)
            elif not is_comms_mode:
                # Real access exists, but the spacecraft hasn't
                # (mode-)switched its antenna to point at it yet -- the
                # "geometric visibility vs. actual RF link availability"
                # distinction this feature is built around.
                self.link_status_badge.setText("Not yet comms-pointing")
                set_badge(self.link_status_badge, _MUTED_BADGE)
            else:
                self.link_status_badge.setText("Link status unknown (no rf_link configured)")
                set_badge(self.link_status_badge, _MUTED_BADGE)
            return

        self.eirp_label.setText(f"{breakdown.eirp_dbw:.2f} dBW")
        self.fspl_label.setText(f"{breakdown.fspl_db:.2f} dB")
        self.pointing_loss_label.setText(f"{breakdown.pointing_loss_db:.2f} dB")
        self.received_power_label.setText(f"{breakdown.received_dbw:.2f} dBW")
        self.noise_label.setText(f"{breakdown.n0_dbw_hz:.2f} dBW/Hz")
        self.cn0_label.setText(f"{breakdown.cn0_db_hz:.2f} dB-Hz")
        self.ebno_label.setText(f"{breakdown.ebno_db:.2f} dB")
        self.margin_label.setText(f"{breakdown.margin_db:.2f} dB")
        if not link_budget.link_closes(breakdown.margin_db, self._scenario):
            self.link_status_badge.setText("Link degraded")
            set_badge(self.link_status_badge, _DANGER_BADGE)
        else:
            self.link_status_badge.setText("Link OK")
            set_badge(self.link_status_badge, _SUCCESS_BADGE)
