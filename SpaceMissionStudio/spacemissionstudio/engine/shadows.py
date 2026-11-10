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
"""Which bodies shadow a spacecraft from the Sun (transparency plan, Phase
6b: ``dynamics.shadowing_bodies``, the models in ``config.models``).

Basilisk's ``eclipse`` module, given several bodies, computes the shadow
of only the one nearest the spacecraft (``eclipse.cpp``,
``UpdateState``): around the Earth that is always the Earth, so the Moon
never shadows. ``central_body`` (the default) keeps that one module with
the bodies it always had. ``tracked_bodies`` gives each other tracked body
its own module, one body each, and :class:`CombinedEclipse` multiplies
the sunlight they leave into the one message every consumer reads.

:func:`occulters` is Basilisk-free; :class:`CombinedEclipse` is a
Basilisk module.
"""

from __future__ import annotations

CHOICE = "dynamics.shadowing_bodies"
# The bodies Basilisk's eclipse knows the radius of by name (eclipse.cpp,
# getPlanetEquatorialRadius); any other needs "custom" and its one rEqCustom.
KNOWN_RADII = ("mercury", "venus", "earth", "moon", "mars barycenter", "mars", "jupiter barycenter", "saturn",
               "uranus", "neptune")


def occulters(model: str, central_body: str, body_names, custom_body: str | None = None):
    """``(shared, own, skipped)``: the bodies of the shared eclipse module
    (the nearest of them shadows), those with a module of their own, and
    the tracked bodies that cannot shadow (no radius by name). ``custom_body``
    is the central small body, whose radius the shared module is given."""
    others = [name for name in body_names if name not in ("sun", central_body)]
    if model == "central_body":
        return (others if central_body == "sun" else [central_body]), [], []
    shared = [] if central_body == "sun" else [central_body]
    own = [name for name in others if name in KNOWN_RADII and name != custom_body]
    skipped = [name for name in others if name not in own]
    if not shared and own:  # a heliocentric run: the first body has the shared module
        shared, own = own[:1], own[1:]
    return shared, own, skipped


def combined_illumination(factors) -> float:
    """[-] The sunlight left by every body's shadow: the product of each
    body's fraction (1 lit, 0 umbra), as if the shadows overlapped
    independently; exact whenever no more than one body shades."""
    result = 1.0
    for factor in factors:
        result *= factor
    return result


def _make_combined():
    from Basilisk.architecture import messaging, sysModel

    from .orbit_maintenance import _eclipse_illumination_fraction

    class CombinedEclipse(sysModel.SysModel):
        """One spacecraft's sunlight from several eclipse messages, one per
        body: their product (:func:`combined_illumination`), written as an
        ``EclipseMsg``."""

        def __init__(self, name: str):
            super().__init__()
            self.ModelTag = name
            self.eclipseInMsgs: list = []
            self.eclipseOutMsg = messaging.EclipseMsg()

        def add(self, eclipse_out_msg) -> None:
            reader = messaging.EclipseMsgReader()
            reader.subscribeTo(eclipse_out_msg)
            self.eclipseInMsgs.append(reader)

        def UpdateState(self, CurrentSimNanos):
            payload = messaging.EclipseMsgPayload()
            value = combined_illumination(_eclipse_illumination_fraction(reader()) for reader in self.eclipseInMsgs)
            if hasattr(payload, "illuminationFactor"):
                payload.illuminationFactor = value
            else:  # an older Basilisk build (orbit_maintenance._eclipse_illumination_fraction)
                payload.shadowFactor = value
            self.eclipseOutMsg.write(payload, CurrentSimNanos, self.moduleID)

    return CombinedEclipse


def CombinedEclipse(name: str):  # noqa: N802 -- a Basilisk module's constructor
    """A :class:`CombinedEclipse` module (built on first use: Basilisk)."""
    global _COMBINED
    if _COMBINED is None:
        _COMBINED = _make_combined()
    return _COMBINED(name)


_COMBINED = None
# Its priority in the dynamics task: after the eclipse modules (370), before every module that reads it.
PRIORITY = 369
