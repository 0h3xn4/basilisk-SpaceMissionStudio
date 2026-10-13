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
