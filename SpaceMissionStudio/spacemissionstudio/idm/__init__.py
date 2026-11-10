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
"""Reading IDM-CIC models (``.idm`` files; IDM-CIC is © CNES).

SpaceMissionStudio reads the model file with its own code, written from
the format's published description and checked against example models;
it uses no CNES software and is not endorsed by CNES. This package knows
nothing about scenarios (``spacemissionstudio.idm_import`` maps a model
into one): ``archive`` opens the file, ``values`` reads its numbers,
``graph`` its objects, ``frames`` and ``shapes`` give poses and
geometry, and ``model`` the typed model and its placement.
"""

from .errors import IdmError
from .model import IdmModel, Placement, load

__all__ = ["IdmError", "IdmModel", "Placement", "load"]
