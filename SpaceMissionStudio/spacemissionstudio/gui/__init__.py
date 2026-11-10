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
"""SpaceMissionStudio's PySide6 GUI shell (Phase 1).

Deliberately thin: every widget here reads/writes plain
``spacemissionstudio.schema`` dataclasses and calls
``spacemissionstudio.engine.service.SimulationService`` for anything that
needs Basilisk -- there is no GUI-only copy of scenario state or
simulation logic. See ``main_window.MainWindow`` for how the pieces fit
together, and ``../README.md``'s Phase 1 section for what is and isn't
in scope.
"""
