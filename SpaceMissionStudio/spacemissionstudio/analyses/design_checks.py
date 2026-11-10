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
"""Design checks: the static checks of the 3D model in one report, and
their findings.

- field-of-view obstruction of every mounted viewing item
  (:mod:`.fov`), deployed and stowed;
- the thrusters' torque arms and authority, with the centre-of-mass drift
  from the beginning to the end of life, and plume impingement as
  geometry (:mod:`.thrusters`);
- the mass budget with maturity margins (:mod:`.mass_budget`);
- launcher compatibility of the stowed configuration (:mod:`.launcher`).

A finding is raised for a part in a field of view or a plume cone (any
sampled ray that meets a part is a real blockage: a sampling error can
only under-read it), for a launch mass over the mass limit, a part outside
the launcher's envelope, and a centre of mass beyond a launcher limit. The
limits are the user's, with their source: no limit is assumed.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

from ..engine.findings import Finding
from . import common
from . import fov as fov_module
from . import launcher as launcher_module
from . import mass_budget as mass_module
from . import thrusters as thruster_module


@dataclass
class DesignReport:
    spacecraft: str
    samples: int = common.DEFAULT_SAMPLES  # rays per cone used
    fov: fov_module.FovReport | None = None
    authority: thruster_module.ThrusterAuthority | None = None
    plumes: list = field(default_factory=list)  # list[PlumeImpingement]
    plume_skipped: list = field(default_factory=list)
    mass: mass_module.MassBudget | None = None
    launcher: launcher_module.LauncherCheck | None = None

    def findings(self) -> list[Finding]:
        """The report's findings, as the Problems panel lists them."""
        found: list[Finding] = []
        name = self.spacecraft
        for o in self.fov.obstructions if self.fov is not None else []:
            if o.blocked_fraction > 0.0:
                parts = ", ".join(f"{p} {100.0 * f:.1f} %" for p, f in o.by_part.items())
                found.append(Finding(f"{name}: {o.item}'s field of view ({o.configuration}) is "
                                     f"{100.0 * o.blocked_fraction:.1f} % blocked by {parts}",
                                     "design.fov_obstructed",
                                     actual=f"{100.0 * o.blocked_fraction:.1f} % +- {100.0 * o.standard_error:.1f} % "
                                            f"of the field of view ({o.samples} rays)", limit="0 %"))
        for p in self.plumes:
            if p.blocked_fraction > 0.0:
                parts = ", ".join(f"{q} {100.0 * f:.1f} %" for q, f in p.by_part.items())
                found.append(Finding(f"{name}: thruster {p.thruster}'s plume cone ({p.half_angle_deg:g} deg "
                                     f"half-angle) meets {parts}", "design.plume_impingement",
                                     actual=f"{100.0 * p.blocked_fraction:.1f} % of the cone ({p.samples} rays)",
                                     limit="0 %"))
        if self.mass is not None and self.mass.headroom_kg is not None and self.mass.headroom_kg < 0.0:
            source = f" ({self.mass.limit_source})" if self.mass.limit_source else ""
            found.append(Finding(f"{name}: launch mass with margins {self.mass.launch_mass_kg:.1f} kg is over the "
                                 f"mass limit {self.mass.mass_limit_kg:g} kg{source}", "design.mass_over_limit",
                                 actual=f"{self.mass.launch_mass_kg:.1f} kg",
                                 limit=f"{self.mass.mass_limit_kg:g} kg"))
        if self.launcher is not None:
            check = self.launcher
            for p in check.protrusions:
                found.append(Finding(f"{name}: {p.part} is {1000.0 * p.distance_m:.0f} mm outside the launcher "
                                     f"envelope ({check.envelope}, {p.where}, {check.configuration})",
                                     "design.envelope_protrusion", actual=f"{1000.0 * p.distance_m:.0f} mm outside",
                                     limit="inside the envelope"))
            for problem in check.limit_problems():
                found.append(Finding(f"{name}: launcher ({check.envelope}): {problem}", "design.launcher_limit",
                                     actual=problem.split(" is over")[0], limit=check.envelope))
        return found


def design_checks(sc, samples: int | None = None, base_dir=None) -> DesignReport:
    """:class:`DesignReport` of spacecraft ``sc``."""
    report = DesignReport(sc.name, common.samples_for(sc, samples))
    report.mass = mass_module.mass_budget(sc)
    authority = thruster_module.thruster_authority(sc)
    report.authority = authority if authority.columns else None
    if sc.model is not None:
        report.fov = fov_module.fov_obstruction(sc, samples=samples, base_dir=base_dir)
        report.plumes, report.plume_skipped = thruster_module.plume_impingement(sc, samples, base_dir)
        report.launcher = launcher_module.launcher_check(sc, base_dir)
    return report


# The findings of each spacecraft as last checked: the editor checks the scenario at every edit
# (engine.scenario_checks), and an edit elsewhere must not cast the rays again.
_FINDINGS: dict = {}  # (spacecraft hash, base_dir) -> list[Finding]
_MAX_FINDINGS = 32


def _spacecraft_key(sc, base_dir) -> tuple:
    text = json.dumps(asdict(sc), sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest(), str(base_dir)


def design_findings(scenario, base_dir=None) -> list[Finding]:
    """Every spacecraft's design findings (none for a spacecraft without a
    3D model, mounts, mass limit or launcher), remembered per spacecraft
    content until it changes."""
    found: list[Finding] = []
    for sc in scenario.spacecraft:
        if sc.model is None:
            continue
        key = _spacecraft_key(sc, base_dir)
        if key not in _FINDINGS:
            if len(_FINDINGS) >= _MAX_FINDINGS:
                _FINDINGS.pop(next(iter(_FINDINGS)))
            _FINDINGS[key] = design_checks(sc, base_dir=base_dir).findings()
        found += _FINDINGS[key]
    return found
