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

r"""
Downlink RF link-margin ESTIMATE: a simplified free-space-path-loss Eb/N0
budget, ported directly from ``../missionAnalysis``'s
``run_constellation_mission.py::_rf_link_margin_db()`` -- EIRP - FSPL
(- an optional antenna-pointing-loss term, see
:func:`link_budget_breakdown`) + G/T against the required Eb/N0 for the
assumed data rate (still no atmosphere/rain/coding-gain terms). See
``schema.scenario.RFLinkConfig``'s docstring for what this does and does
NOT feed into.

This module has NO Basilisk import and is fully unit-testable here with
synthetic data -- it only consumes the already-recorded ``slant_range``/
``has_access``/``pointing_error_deg`` :class:`~engine.results.TimeSeries`
that ``engine.service.SimulationService.run()`` produces from Basilisk's
real, simulated orbit geometry (``groundLocation.GroundLocation``) and
attitude (``engine.fsw.build_comms_pointing``'s arbitrator, when a
spacecraft has ``schema.scenario.CommsPointingConfig`` configured); this
module never computes geometry or attitude itself.

A real, more physically-complete alternative exists in Basilisk itself
(``src/simulation/communication/{simpleAntenna,linkBudget}/`` -- a real
2D-Gaussian-beam antenna pattern + a compiled ``LinkBudget`` module
computing FSPL, atmospheric attenuation, and pointing loss from true
antenna geometry) but is deliberately NOT used here: no example scenario
anywhere in this checkout exercises it yet, so there is no reference
usage to confirm the wiring against the way every other module this
project uses was confirmed first -- see ``SpaceMissionStudio/HISTORY.md``'s
comms_pointing entry for the full reasoning. This module's own simplified,
already-proven approach is used instead, extended (not replaced) below.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .. import constants
from ..schema.scenario import GroundStationConfig, RFLinkConfig
from .results import ResultSet, ResultsError, TimeSeries
from .trace import Quantity, Trace

_C_LIGHT_M_S = constants.SPEED_OF_LIGHT_M_S  # [m/s]
_K_BOLTZMANN_DBW_HZ = -228.6  # [dBW/K/Hz] 10*log10(1.380649e-23)


def rule(name: str, scenario=None):
    """The value of ``link.<name>`` in effect for ``scenario``
    (config.parameters): the required margin and the "fixed" pattern's
    pointing loss."""
    from ..config import registry

    return registry.value(f"link.{name}", scenario)


def link_closes(margin_db: float, scenario=None, required_margin_db: float | None = None) -> bool:
    """True when ``margin_db`` (a NaN: no link) is at least the required
    margin, ``link.required_margin_db`` unless given."""
    required = rule("required_margin_db", scenario) if required_margin_db is None else required_margin_db  # [dB]
    return not math.isnan(margin_db) and margin_db >= required


def needs_link_gate(sc_config) -> bool:
    """True when a spacecraft's downlink is evaluated live, from its
    simulated attitude (``engine.data_handling``'s link gate): an RF link
    with a data-handling chain, or with an antenna pattern."""
    rf_link = sc_config.rf_link
    return rf_link is not None and (sc_config.data_handling is not None or rf_link.antenna_pattern != "fixed")


def cosine_exponent(peak_gain_dbi: float) -> float:
    """The exponent ``n`` of a ``cos^n(theta)`` power pattern with this
    peak gain: such a pattern, confined to the forward hemisphere, has
    directivity ``D0 = 2 (n + 1)`` (Balanis, *Antenna Theory*, ch. 2,
    directivity of ``U = cos^n(theta)``), taken here as the gain. A 6 dBi
    patch gives n = 1.0, a 9 dBi one n = 3.0."""
    return max(0.0, 10.0 ** (peak_gain_dbi / 10.0) / 2.0 - 1.0)


def half_power_beamwidth_deg(rf_link: RFLinkConfig) -> float | None:
    """Full angle [deg] within which the gain stays within 3 dB of the
    peak, for the "cosine" and "table" patterns (None for "fixed")."""
    if rf_link.antenna_pattern == "cosine":
        n = cosine_exponent(rf_link.tx_antenna_gain_dbi)
        return 180.0 if n == 0.0 else 2.0 * math.degrees(math.acos(0.5 ** (1.0 / n)))
    if rf_link.antenna_pattern == "table":
        angles = np.linspace(0.0, 180.0, 3601)  # [deg]
        below = angles[antenna_gain_dbi(rf_link, angles) < peak_gain_dbi(rf_link) - 3.0]
        return 2.0 * float(below[0]) if below.size else 360.0
    return None


def peak_gain_dbi(rf_link: RFLinkConfig) -> float:
    """Boresight gain [dBi]: ``tx_antenna_gain_dbi``, or the table's first row."""
    if rf_link.antenna_pattern == "table":
        return float(rf_link.antenna_gain_table[0][1])
    return rf_link.tx_antenna_gain_dbi


def antenna_gain_dbi(rf_link: RFLinkConfig, off_boresight_deg):
    """Spacecraft antenna gain [dBi] at ``off_boresight_deg`` (a number or
    an array) for the "cosine" and "table" patterns; "fixed" returns the
    peak gain everywhere (its pointing loss is applied separately)."""
    theta = np.abs(np.asarray(off_boresight_deg, dtype=float))  # [deg]
    peak = peak_gain_dbi(rf_link)
    if rf_link.antenna_pattern == "cosine":
        n = cosine_exponent(peak)
        floor = peak - rf_link.antenna_front_to_back_db
        cos_theta = np.cos(np.radians(np.minimum(theta, 90.0)))
        with np.errstate(divide="ignore"):
            front = peak + 10.0 * n * np.log10(cos_theta) if n > 0 else np.full_like(theta, peak)
        gain = np.where(theta < 90.0, np.maximum(front, floor), floor)
    elif rf_link.antenna_pattern == "table":
        angles, gains = np.asarray(rf_link.antenna_gain_table, dtype=float).T
        gain = np.interp(theta, angles, gains)  # holds the last gain beyond the last angle
    else:
        gain = np.full_like(theta, peak)
    return float(gain) if gain.ndim == 0 else gain


@dataclass
class LinkBudgetBreakdown:
    """Every intermediate quantity :func:`link_budget_breakdown` computes
    on the way to the final margin -- for telemetry/display (e.g.
    ``gui.mission_dashboard_widget``), not just the one final number
    :func:`link_margin_db` returns.
    """

    eirp_dbw: float
    fspl_db: float
    pointing_loss_db: float
    received_dbw: float
    n0_dbw_hz: float
    cn0_db_hz: float
    ebno_db: float
    margin_db: float


def link_budget_breakdown(range_m: float, rf_link: RFLinkConfig, ground_station: GroundStationConfig,
                           pointing_error_deg: float = 0.0, scenario=None) -> LinkBudgetBreakdown:
    """The full link budget, every stage broken out -- see
    :class:`LinkBudgetBreakdown`. :func:`link_margin_db` is a thin
    wrapper returning just ``.margin_db``.

    ``pointing_error_deg`` (the ACTUAL achieved angle between the
    spacecraft's antenna boresight and the ground station, e.g. from
    ``{sc}.comms_pointing.pointing_error_deg`` -- see
    ``engine.fsw.build_comms_pointing``) only matters when
    ``rf_link.antenna_beamwidth_deg`` is also set; otherwise
    ``pointing_loss_db`` is always ``0.0``, matching this function's
    exact pre-pointing-loss behavior for every scenario that doesn't set
    that field. When both are given, applies the standard parabolic
    -reflector/Gaussian-main-lobe pointing-loss approximation
    ``12*(pointing_error_deg / antenna_beamwidth_deg)^2`` dB (the 12 is
    ``link.pointing_loss_coeff_db``; clamped to ``link.max_pointing_loss_db``
    -- the approximation itself is only meaningful within a few beamwidths
    of boresight, not an indication the link still "almost" closes far
    off-axis). ``scenario`` gives those parameters' values.
    """
    eirp_dbw = 10.0 * np.log10(rf_link.tx_power_w) + peak_gain_dbi(rf_link) - rf_link.implementation_loss_db
    fspl_db = 20.0 * np.log10(4.0 * np.pi * range_m * rf_link.frequency_hz / _C_LIGHT_M_S)
    pointing_loss = pointing_loss_db(rf_link, pointing_error_deg, scenario)
    received_dbw = eirp_dbw - fspl_db - pointing_loss + ground_station.rx_antenna_gain_dbi
    n0_dbw_hz = _K_BOLTZMANN_DBW_HZ + 10.0 * np.log10(ground_station.system_noise_temp_k)
    cn0_db_hz = received_dbw - n0_dbw_hz
    ebno_db = cn0_db_hz - 10.0 * np.log10(rf_link.data_rate_bps)
    margin_db = ebno_db - rf_link.required_ebno_db
    return LinkBudgetBreakdown(
        eirp_dbw=float(eirp_dbw), fspl_db=float(fspl_db), pointing_loss_db=float(pointing_loss),
        received_dbw=float(received_dbw), n0_dbw_hz=float(n0_dbw_hz), cn0_db_hz=float(cn0_db_hz),
        ebno_db=float(ebno_db), margin_db=float(margin_db),
    )


def margin_at_one_metre_db(rf_link: RFLinkConfig, ground_station: GroundStationConfig) -> float:
    """Every range- and pointing-independent term of the margin [dB]:
    ``link_margin_db(r, ..., angle) == margin_at_one_metre_db(...)
    - 20 log10(r) - pointing loss``. For callers evaluating the margin
    every simulation step (``engine.data_handling``)."""
    return link_budget_breakdown(1.0, rf_link, ground_station, 0.0).margin_db


def pointing_loss_db(rf_link: RFLinkConfig, off_boresight_deg: float, scenario=None) -> float:
    """The gain toward the station below the peak [dB], as
    :func:`link_budget_breakdown` applies it."""
    if rf_link.antenna_pattern != "fixed":
        return peak_gain_dbi(rf_link) - antenna_gain_dbi(rf_link, off_boresight_deg)
    if rf_link.antenna_beamwidth_deg is not None and off_boresight_deg != 0.0:
        coefficient_db = rule("pointing_loss_coeff_db", scenario)  # [dB]
        return min(rule("max_pointing_loss_db", scenario),
                   coefficient_db * (off_boresight_deg / rf_link.antenna_beamwidth_deg) ** 2)
    return 0.0


def link_margin_db(range_m: float, rf_link: RFLinkConfig, ground_station: GroundStationConfig,
                    pointing_error_deg: float = 0.0, scenario=None) -> float:
    """Downlink Eb/N0 margin [dB] at the given slant range: positive means
    the link closes with that much margin to spare; negative means it
    doesn't close at that range with these parameters. See
    :func:`link_budget_breakdown` for every intermediate quantity and
    for what ``pointing_error_deg`` does.
    """
    return link_budget_breakdown(range_m, rf_link, ground_station, pointing_error_deg, scenario).margin_db


_LINK_EQUATION = "the link equation (docs/models/link-data-and-power.md)"


def slant_range_at_elevation_m(semi_major_axis_m: float, ground_station: GroundStationConfig,
                               elevation_deg: float | None = None) -> float:
    """The slant range [m] to a spacecraft on a circular orbit of radius
    ``semi_major_axis_m`` seen at ``elevation_deg`` (the station's minimum
    elevation unless given), from a station at height ``altitude_m`` on a
    sphere of Earth's equatorial radius: the longest range of a pass, where
    a downlink is hardest to close.

        rho = sqrt(r^2 - (R cos(eps))^2) - R sin(eps),  R = R_E + h_gs
    """
    eps = math.radians(ground_station.min_elevation_deg if elevation_deg is None else elevation_deg)
    radius = constants.EARTH_EQUATORIAL_RADIUS_M + ground_station.altitude_m  # [m]
    return math.sqrt(semi_major_axis_m ** 2 - (radius * math.cos(eps)) ** 2) - radius * math.sin(eps)


def link_budget_traces(range_m: float, rf_link: RFLinkConfig, ground_station: GroundStationConfig,
                       pointing_error_deg: float = 0.0, scenario=None, range_source: str = "option: the range asked for",
                       pointing_source: str = "option: the pointing error asked for") -> dict:
    """How each figure of :func:`link_budget_breakdown` was computed
    (``engine.trace``, transparency plan Phase 4a), keyed ``eirp``, ``fspl``,
    ``pointing_loss``, ``received``, ``n0``, ``cn0``, ``ebno``, ``margin`` and
    ``closes``. The values are the breakdown's own; ``range_source`` and
    ``pointing_source`` say where the range and the pointing error came
    from (a run's series, the minimum-elevation geometry, an option)."""
    b = link_budget_breakdown(range_m, rf_link, ground_station, pointing_error_deg, scenario)
    gs, rf = f"scenario: ground_stations[{ground_station.name}]", "scenario: rf_link"
    peak_source = (f"{rf}.antenna_gain_table, first row" if rf_link.antenna_pattern == "table"
                   else f"{rf}.tx_antenna_gain_dbi")
    traces = {"eirp": Trace(
        "EIRP", "EIRP", b.eirp_dbw, "[dBW]", "EIRP = 10 log10(P_tx) + G_tx - L_impl", _LINK_EQUATION,
        inputs=(Quantity("transmitter power", "P_tx", rf_link.tx_power_w, "[W]", f"{rf}.tx_power_w"),
                Quantity("antenna peak gain", "G_tx", peak_gain_dbi(rf_link), "[dBi]", peak_source),
                Quantity("implementation loss", "L_impl", rf_link.implementation_loss_db, "[dB]",
                         f"{rf}.implementation_loss_db")))}
    traces["fspl"] = Trace(
        "Free-space path loss", "FSPL", b.fspl_db, "[dB]", "FSPL = 20 log10(4 pi r f / c)", _LINK_EQUATION,
        inputs=(Quantity("slant range", "r", range_m, "[m]", range_source),
                Quantity("frequency", "f", rf_link.frequency_hz, "[Hz]", f"{rf}.frequency_hz"),
                Quantity("speed of light", "c", _C_LIGHT_M_S, "[m/s]", "constant: SPEED_OF_LIGHT_M_S")))
    angle = Quantity("angle between the boresight and the station", "theta", pointing_error_deg, "[deg]",
                     pointing_source)
    if rf_link.antenna_pattern == "fixed" and rf_link.antenna_beamwidth_deg is not None:
        pointing = Trace("Pointing loss", "L_point", b.pointing_loss_db, "[dB]",
                         "L_point = min(L_max, k (theta / theta_3dB)^2)  (0 at theta = 0)",
                         "the parabolic/Gaussian main-lobe approximation",
                         inputs=(angle, Quantity("half-power beamwidth", "theta_3dB", rf_link.antenna_beamwidth_deg,
                                                 "[deg]", f"{rf}.antenna_beamwidth_deg"),
                                 Quantity("coefficient", "k", rule("pointing_loss_coeff_db", scenario), "[dB]",
                                          "parameter: link.pointing_loss_coeff_db"),
                                 Quantity("largest loss", "L_max", rule("max_pointing_loss_db", scenario), "[dB]",
                                          "parameter: link.max_pointing_loss_db")))
    elif rf_link.antenna_pattern == "fixed":
        pointing = Trace("Pointing loss", "L_point", b.pointing_loss_db, "[dB]", "L_point = 0",
                         "no beamwidth given: the gain is the peak in every direction", inputs=(angle,))
    else:
        pointing = Trace("Pointing loss", "L_point", b.pointing_loss_db, "[dB]", "L_point = G_tx - G(theta)",
                         "the antenna pattern: cos^n(theta), n from the peak gain (Balanis, Antenna Theory, ch. 2)"
                         if rf_link.antenna_pattern == "cosine" else "the antenna pattern: the gain table, interpolated",
                         inputs=(angle, Quantity("antenna peak gain", "G_tx", peak_gain_dbi(rf_link), "[dBi]",
                                                 peak_source)),
                         intermediates=(Quantity("gain toward the station", "G(theta)",
                                                 float(antenna_gain_dbi(rf_link, pointing_error_deg)), "[dBi]",
                                                 f"computed: the {rf_link.antenna_pattern} pattern"),))
    traces["pointing_loss"] = pointing
    traces["received"] = Trace(
        "Received power", "C", b.received_dbw, "[dBW]", "C = EIRP - FSPL - L_point + G_rx", _LINK_EQUATION,
        inputs=(Quantity("EIRP", "EIRP", b.eirp_dbw, "[dBW]", "trace: EIRP"),
                Quantity("free-space path loss", "FSPL", b.fspl_db, "[dB]", "trace: Free-space path loss"),
                Quantity("pointing loss", "L_point", b.pointing_loss_db, "[dB]", "trace: Pointing loss"),
                Quantity("station receive gain", "G_rx", ground_station.rx_antenna_gain_dbi, "[dBi]",
                         f"{gs}.rx_antenna_gain_dbi")))
    traces["n0"] = Trace(
        "Noise density", "N0", b.n0_dbw_hz, "[dBW/Hz]", "N0 = 10 log10(k_B) + 10 log10(T_sys)", _LINK_EQUATION,
        inputs=(Quantity("Boltzmann's constant", "10 log10(k_B)", _K_BOLTZMANN_DBW_HZ, "[dBW/K/Hz]",
                         "constant: 10 log10(1.380649e-23 J/K), rounded to -228.6 as link budgets write it"),
                Quantity("system noise temperature", "T_sys", ground_station.system_noise_temp_k, "[K]",
                         f"{gs}.system_noise_temp_k")))
    traces["cn0"] = Trace(
        "Carrier to noise density", "C/N0", b.cn0_db_hz, "[dB-Hz]", "C/N0 = C - N0", _LINK_EQUATION,
        inputs=(Quantity("received power", "C", b.received_dbw, "[dBW]", "trace: Received power"),
                Quantity("noise density", "N0", b.n0_dbw_hz, "[dBW/Hz]", "trace: Noise density")))
    traces["ebno"] = Trace(
        "Energy per bit to noise density", "Eb/N0", b.ebno_db, "[dB]", "Eb/N0 = C/N0 - 10 log10(R_b)", _LINK_EQUATION,
        inputs=(Quantity("carrier to noise density", "C/N0", b.cn0_db_hz, "[dB-Hz]",
                         "trace: Carrier to noise density"),
                Quantity("data rate", "R_b", rf_link.data_rate_bps, "[bit/s]", f"{rf}.data_rate_bps")))
    traces["margin"] = Trace(
        "Link margin", "M", b.margin_db, "[dB]", "M = Eb/N0 - (Eb/N0)_req", _LINK_EQUATION,
        inputs=(Quantity("energy per bit to noise density", "Eb/N0", b.ebno_db, "[dB]",
                         "trace: Energy per bit to noise density"),
                Quantity("required Eb/N0", "(Eb/N0)_req", rf_link.required_ebno_db, "[dB]",
                         f"{rf}.required_ebno_db")))
    required = rule("required_margin_db", scenario)  # [dB]
    traces["closes"] = Trace(
        "The link closes", "closes", "yes" if link_closes(b.margin_db, scenario) else "no", "[-]",
        "closes: M >= M_req", "SpaceMissionStudio's rule (docs/models/link-data-and-power.md)",
        inputs=(Quantity("link margin", "M", b.margin_db, "[dB]", "trace: Link margin"),
                Quantity("required margin", "M_req", required, "[dB]", "parameter: link.required_margin_db")))
    return traces


def link_margin_series(result: ResultSet, ground_station_name: str, spacecraft_name: str,
                        rf_link: RFLinkConfig, ground_station: GroundStationConfig,
                        comms_pointing_target_ground_station: str | None = None,
                        scenario=None) -> TimeSeries:
    """Builds a ``"<gs>.access_to_<sc>.link_margin_db"`` :class:`TimeSeries`
    from that pair's already-recorded ``slant_range``/``has_access`` series
    (see ``engine.service.SimulationService.run()``'s access-analysis
    wiring). The margin is only defined while ``has_access`` is true --
    there is no link (and so no meaningful margin) outside an access
    window, so those samples are ``NaN`` rather than a misleadingly large
    negative number.

    ``comms_pointing_target_ground_station`` is the spacecraft's own
    ``schema.scenario.CommsPointingConfig.target_ground_station`` (``None``
    if it has no ``comms_pointing`` configured at all -- the pre-existing
    behavior, below, is then unchanged). When it's set and EQUALS
    ``ground_station_name``, this additionally gates on the spacecraft's
    own ``{spacecraft_name}.comms_pointing.active_mode`` series (when
    present) -- real geometric ``has_access`` only means the ground
    station is visible, not that the spacecraft has actually
    (mode-)switched its antenna to point at it yet, so a sample only gets
    a defined margin once BOTH are true -- and feeds its own, real,
    simulated ``{spacecraft_name}.comms_pointing.pointing_error_deg`` into
    :func:`link_margin_db` for that sample, so the margin reflects the
    actually-achieved antenna pointing rather than assuming perfect
    boresight.

    When it's set but does NOT equal ``ground_station_name`` -- i.e. this
    spacecraft's single antenna is committed elsewhere, to a DIFFERENT
    ground station, by ``comms_pointing`` -- the margin is ALWAYS ``NaN``
    for this pair, regardless of this station's own ``has_access``: a
    spacecraft with ``comms_pointing`` configured has exactly one antenna
    under that mode arbitrator's control, so geometric visibility of some
    OTHER, non-targeted station was never a real link attempt (unlike the
    ``comms_pointing_target_ground_station is None`` case, which has no
    single committed antenna to speak of and so keeps the plain, always
    -perfect-pointing ``has_access``-only gate for every station it's
    evaluated against).
    """
    prefix = f"{ground_station_name}.access_to_{spacecraft_name}"
    range_series = result.series.get(f"{prefix}.slant_range")
    access_series = result.series.get(f"{prefix}.has_access")
    if range_series is None or access_series is None:
        raise ResultsError(
            f"no access-analysis series found for ground station {ground_station_name!r} / spacecraft "
            f"{spacecraft_name!r} -- was this pair actually simulated? (expected "
            f"{prefix}.slant_range/{prefix}.has_access in result.series)"
        )

    margin_db = np.full(len(range_series.time_s), np.nan)

    if comms_pointing_target_ground_station is not None \
            and comms_pointing_target_ground_station != ground_station_name:
        # This station was never the antenna's actual target -- no real
        # link attempt here, ever, regardless of its own has_access.
        return TimeSeries(f"{prefix}.link_margin_db", range_series.time_s, ("link_margin_db",),
                           margin_db.reshape(-1, 1), units="dB")

    active_mode_series = result.series.get(f"{spacecraft_name}.comms_pointing.active_mode")
    pointing_error_series = result.series.get(f"{spacecraft_name}.comms_pointing.pointing_error_deg")

    # Defensive, not currently reachable: every recorder in this app
    # shares one time grid today, so these always line up in practice --
    # but range_series/access_series/active_mode_series/pointing_error_series
    # are looked up independently here and then indexed by the SAME
    # integer index i below, with no length check. A future recorder
    # decimated independently of the others would silently misalign
    # rather than raise, same failure shape TimeSeries.__post_init__
    # already guards against for a single series's own time_s/data pair.
    for other in (active_mode_series, pointing_error_series):
        if other is not None and len(other.time_s) != len(range_series.time_s):
            raise ResultsError(
                f"{prefix}: {other.name!r} has {len(other.time_s)} samples but "
                f"{range_series.name!r} has {len(range_series.time_s)} -- these must share one time grid"
            )

    has_access = access_series.data[:, 0] > 0.5
    if active_mode_series is not None:
        has_access = has_access & (active_mode_series.data[:, 0] > 0.5)
    for i in np.nonzero(has_access)[0]:
        pointing_error_deg = float(pointing_error_series.data[i, 0]) if pointing_error_series is not None else 0.0
        margin_db[i] = link_margin_db(float(range_series.data[i, 0]), rf_link, ground_station, pointing_error_deg,
                                      scenario)

    return TimeSeries(f"{prefix}.link_margin_db", range_series.time_s, ("link_margin_db",),
                       margin_db.reshape(-1, 1), units="dB")
