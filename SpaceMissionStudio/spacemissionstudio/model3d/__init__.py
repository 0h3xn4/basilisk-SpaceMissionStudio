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

"""A spacecraft's 3D model: simple shapes and imported ``.obj`` meshes,
their mass properties and the flat plates (facets) their outer surfaces
give for drag and solar radiation pressure.

Pure ``numpy``, Basilisk-free and GUI-free, so every number here is
testable on its own (the precedent of :mod:`engine.constellation` and
:mod:`engine.orbit_design`):

- :mod:`.geometry`: triangle meshes and part placement (rotation, offset).
- :mod:`.mass_properties`: mass, center of mass and inertia; analytic for
  the shapes, exact volume and surface integrals for meshes.
- :mod:`.shapes`: box, n-sided prism (an octagonal bus), cylinder, cone,
  sphere and thin panel.
- :mod:`.obj_io`: reading and writing Wavefront ``.obj`` (+ ``.mtl``).
- :mod:`.surfaces`: facets from outer faces.

Conventions, used throughout: lengths in metres, masses in kilograms,
everything in the spacecraft body frame B unless a name says "local".
Inertia is the tensor with positive diagonal and products of inertia
``Ixy = -integral(x*y dm)``, about the center of mass unless stated.
"""
