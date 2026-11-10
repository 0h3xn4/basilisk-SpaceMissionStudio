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


"""Software-in-the-loop: runs a spacecraft's flight software as an
external program against the Basilisk dynamics (User Manual, "Running
the flight software in the loop"; ``compliance/docs/SRS.md`` SRS-F-19).

* :mod:`.contract` -- the SIL transport contract, version 1: frames and
  payloads (``fsw_export/templates/SIL_CONTRACT.md``).
* :mod:`.transport` -- the byte stream: Unix-domain socket or TCP on
  127.0.0.1, swappable.
* :mod:`.session` -- the simulation side of a session: handshake,
  lock-step steps, deadlines and timeouts.
* :mod:`.report` -- residuals, timing and dropped steps.
* :mod:`.runner` -- starts the program and runs the scenario with the
  bridge in the task (needs Basilisk).
"""
