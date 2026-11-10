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

"""Flight-software export: packages a spacecraft's Basilisk C flight
software as a standalone C project (User Manual, "Exporting the flight
software"; ``compliance/docs/SRS.md`` SRS-F-18).

* :mod:`.catalog` -- the C modules that can be exported (pure data).
* :mod:`.sources` -- the Basilisk sources, vendored unchanged from the
  pinned revision and checked on every read.
* :mod:`.capture` -- reads the flight software out of a built
  simulation and records a short run (needs Basilisk).
* :mod:`.generate` -- writes the C project from a capture (no Basilisk).
* :mod:`.digest` -- the configuration hash that flags a stale export.
"""
