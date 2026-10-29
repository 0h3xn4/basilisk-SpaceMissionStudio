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

"""The default MRP feedback gains (``mrpFeedback`` K and P) and how they are
scaled to a spacecraft, without Basilisk, so that the GUI shows the gains
the engine applies (transparency audit 3.4: it showed the unscaled 3.5 and
30, about 90 times the gains applied to the default 10 kg*m^2 spacecraft).

``DEFAULT_MRP_GAINS`` is lifted directly from Basilisk's own examples/BskSim
reference (BSK_Fsw.py's mrpFeedbackRWs), tuned for THAT example's
900 kg*m^2 spacecraft (BSK_Dynamics.py's I_sc) at its fswRate=0.1.
Applied unscaled to a much smaller spacecraft (this app's own schema
default inertia is 10 kg*m^2 -- 90x smaller), the resulting discrete-time
control update is wildly over-aggressive for the body's actual rotational
inertia and reliably reaches NaN within seconds (root-caused and fixed,
by hand, per-template, in HISTORY.md's "attitude determination pipeline"
entry -- the scaling here generalizes that same fix to every spacecraft by
default, not just the templates it was manually applied to).
"""

from __future__ import annotations

DEFAULT_MRP_GAINS: dict[str, float] = {"K": 3.5, "P": 30.0}
MRP_GAIN_REFERENCE_INERTIA_KG_M2 = 900.0  # [kg*m^2] BskSim's I_sc, for which DEFAULT_MRP_GAINS were tuned


def mean_inertia(inertia_kg_m2: list[float] | None) -> float | None:
    """trace/3 [kg*m^2] of the row-major 3x3 hub inertia, or None without
    one (or with a trace that is not positive)."""
    if not inertia_kg_m2:
        return None
    mean = (inertia_kg_m2[0] + inertia_kg_m2[4] + inertia_kg_m2[8]) / 3.0  # [kg*m^2]
    return mean if mean > 0.0 else None


def default_mrp_gains_for_inertia(inertia_kg_m2: list[float] | None) -> dict[str, float]:
    """``DEFAULT_MRP_GAINS`` scaled by a spacecraft's own (isotropic-
    equivalent) inertia relative to the 900 kg*m^2 reference it was tuned
    for -- confirmed in HISTORY.md to converge cleanly where the unscaled
    gains diverge to NaN, for both RW- and thruster-actuated spacecraft.
    ``inertia_kg_m2`` is the row-major 3x3 hub inertia
    (``SpacecraftConfig.inertia_kg_m2``); its trace/3 is used as the
    scaling quantity so an anisotropic inertia still gets a sensible
    scalar gain pair (``mrpFeedback``'s K/P are themselves scalars, not
    per-axis). Falls back to the unscaled reference gains if no inertia is
    given (callers that have no spacecraft inertia in scope).
    """
    mean = mean_inertia(inertia_kg_m2)
    if mean is None:  # no inertia, or one Scenario.validate() would refuse
        return dict(DEFAULT_MRP_GAINS)
    scale = mean / MRP_GAIN_REFERENCE_INERTIA_KG_M2  # [-]
    return {"K": DEFAULT_MRP_GAINS["K"] * scale, "P": DEFAULT_MRP_GAINS["P"] * scale}


def describe_default_gains(inertia_kg_m2: list[float] | None) -> str:
    """One sentence: the gains applied when K and P are not given, and
    where they come from."""
    gains = default_mrp_gains_for_inertia(inertia_kg_m2)
    mean = mean_inertia(inertia_kg_m2)
    if mean is None:
        return f"Unticked: K {gains['K']:.4g}, P {gains['P']:.4g}, integral off."
    return (f"Unticked: K {gains['K']:.4g}, P {gains['P']:.4g}, integral off. That is K {DEFAULT_MRP_GAINS['K']:g}, "
            f"P {DEFAULT_MRP_GAINS['P']:g} (tuned for {MRP_GAIN_REFERENCE_INERTIA_KG_M2:g} kg*m^2) times mean "
            f"inertia {mean:.4g} kg*m^2 / {MRP_GAIN_REFERENCE_INERTIA_KG_M2:g}.")
