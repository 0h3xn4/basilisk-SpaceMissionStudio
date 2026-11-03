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
