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
"""Analyses built on a spacecraft's 3D model, its mounted equipment and,
where they need one, a finished run (``docs/developer/model-analyses-design.md``).

Each module computes one analysis and returns a dataclass of tables,
series and findings, with no GUI:

- static design checks, from the scenario alone: :mod:`.fov` (field-of-view
  obstruction), :mod:`.thrusters` (authority and plume impingement),
  :mod:`.mass_budget`, :mod:`.launcher`; :mod:`.design_checks` runs them all;
- run analyses: :mod:`.blinding` (Sun, Earth and Moon in the sensors'
  exclusion cones; antenna obstruction during passes),
  :mod:`.disturbances`, :mod:`.shading`, :mod:`.exposure`,
  :mod:`.brightness`; :mod:`.run_analyses` adds their series to a run;
- :mod:`.reentry`: the re-entry casualty risk on the End of Life page.

Nothing here changes Basilisk or what it computes: drag and SRP stay as
Basilisk computes them, and shadowing applies to these analyses only.
"""
