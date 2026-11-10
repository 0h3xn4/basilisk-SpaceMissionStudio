#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
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
"""Geodetic altitude and latitude for the atmosphere models
(ECSS-E-ST-10-04C 7.2.1.1a; Phase 3 finding F-07, see
``compliance/phase3_log.md``).

**Problem.** NRLMSISE-00 takes geodetic altitude and latitude. Basilisk
2.12's atmosphere models compute them on a sphere (``PCI2LLA`` with the
equatorial radius only, ``atmosphereBase``/``msisAtmosphere``): at
latitude phi the altitude is too low by about 21 km sin^2(phi), so the
density is too high -- in a 400 km, 52.5 deg orbit the decay rate was 10 %
above GMAT's (NRLMSISE-00 on the WGS-84 ellipsoid), 1.6 % with GMAT also on
a sphere.

**Workaround** (no change to Basilisk). The atmosphere model reads a proxy
spacecraft position: the point at the same longitude whose spherical
altitude and latitude, as Basilisk computes them, are the spacecraft's
WGS-84 geodetic altitude and latitude. The drag force still uses the real
state; only the density lookup sees the proxy.
"""

from __future__ import annotations

import numpy as np
from Basilisk.architecture import messaging, sysModel

from .geodesy import atmosphere_proxy_position as proxy_position

#: Task priority: before the atmosphere models (390), which read the proxy.
PRIORITY = 395


class GeodeticProxy(sysModel.SysModel):
    """Writes a copy of a spacecraft state message whose position is
    :func:`geodesy.atmosphere_proxy_position` of the real one."""

    def __init__(self, name: str, sphere_radius_m: float):
        super().__init__()
        self.ModelTag = name
        self.scStateInMsg = messaging.SCStatesMsgReader()
        self.planetInMsg = messaging.SpicePlanetStateMsgReader()
        self.scStateOutMsg = messaging.SCStatesMsg()
        self.sphere_radius_m = sphere_radius_m  # [m]

    def Reset(self, CurrentSimNanos):
        if self.scStateInMsg.isWritten() and self.planetInMsg.isWritten():
            self.UpdateState(CurrentSimNanos)

    def UpdateState(self, CurrentSimNanos):
        state, planet = self.scStateInMsg(), self.planetInMsg()
        r_PN_N = np.array(planet.PositionVector)
        dcm_PN = np.array(planet.J20002Pfix)
        if not dcm_PN.any():
            dcm_PN = np.eye(3)
        payload = messaging.SCStatesMsgPayload()
        payload.r_BN_N = (r_PN_N + proxy_position(np.array(state.r_BN_N) - r_PN_N, dcm_PN,
                                                  self.sphere_radius_m)).tolist()
        payload.v_BN_N = list(state.v_BN_N)
        payload.sigma_BN = list(state.sigma_BN)
        self.scStateOutMsg.write(payload, CurrentSimNanos, self.moduleID)


def attach(sim, task_name: str, name: str, sc_state_out_msg, planet_state_out_msg, sphere_radius_m: float):
    """Insert a :class:`GeodeticProxy` for one spacecraft; returns it (its
    ``scStateOutMsg`` goes to the atmosphere model's ``addSpacecraftToModel``)."""
    proxy = GeodeticProxy(f"geodeticProxy_{name}", sphere_radius_m)
    proxy.scStateInMsg.subscribeTo(sc_state_out_msg)
    proxy.planetInMsg.subscribeTo(planet_state_out_msg)
    sim.AddModelToTask(task_name, proxy, PRIORITY)
    return proxy
