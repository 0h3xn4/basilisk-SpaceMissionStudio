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
