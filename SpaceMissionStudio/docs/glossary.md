# Glossary

Every term and abbreviation the SpaceMissionStudio documentation uses,
explained in plain words, in alphabetical order. The app's built-in manual
(**Help > User Manual**, section 12) has a shorter version of this list.

[A](#a) · [B](#b) · [C](#c) · [D](#d) · [E](#e) · [F](#f) · [G](#g) ·
[H](#h) · [I](#i) · [J](#j) · [K](#k) · [L](#l) · [M](#m) · [N](#n) ·
[O](#o) · [P](#p) · [R](#r) · [S](#s) · [T](#t) · [U](#u) · [V](#v) ·
[W](#w)

## A

**AD10** -- ESA's guideline for delta-V and propellant budgets (document
EOP-FM/2024-07-177). The **Budget** tab follows its structure: margins,
residual propellant, and solar activity at a high (95th) percentile for
operations.

**ADCS** -- Attitude Determination and Control System: the sensors,
actuators and software that work out which way a spacecraft points and
turn it.

**Ap** -- a daily index of how disturbed Earth's magnetic field is. With
[F10.7](#f), it sets how dense the upper atmosphere is, and so how much
[drag](#d) a low satellite feels.

**Attitude** -- which way a spacecraft points, as opposed to where it is.
"Attitude control" keeps it pointed at a target: the ground, the Sun, a
ground station or a planet.

## B

**Basilisk** -- the open-source spacecraft simulation framework from the
AVS Lab at the University of Colorado Boulder. It computes every number in
SpaceMissionStudio. This repository is a fork of it.

**Boresight** -- the direction an antenna or sensor looks straight out
of; its gain or field of view is centred on it.

## C

**CCSDS** -- the Consultative Committee for Space Data Systems, which
publishes the standard file formats space agencies exchange. SpaceMissionStudio
reads and writes three of its orbit messages: [OPM, OMM and OEM](#o).

**Cd (drag coefficient)** -- how strongly the thin upper atmosphere drags
on a spacecraft for its size. ESA's [AD10](#a) uses 3.0 for operations (a
higher, conservative value) and 2.2 for end of life.

**Classical orbit elements** -- six numbers that describe an orbit:
semi-major axis (roughly its average size), eccentricity (how stretched
it is), inclination (its tilt to the equator), [RAAN](#r) and argument of
periapsis (its orientation), and an anomaly (where the spacecraft starts
along it).

**CSS (coarse sun sensor)** -- a small, simple light sensor. Several of
them, facing different ways, give a rough direction to the Sun.

## D

**Delta-V** -- how much a manoeuvre changes a spacecraft's velocity, in
m/s. The usual way to say how much propellant something costs,
independent of the spacecraft.

**Drag** -- the push of the thin upper atmosphere against a low-orbiting
spacecraft. It slowly lowers the orbit until the spacecraft re-enters.

## E

**ECSS** -- the European Cooperation for Space Standardization, whose
standards European space projects follow. The `compliance/` folder records
how SpaceMissionStudio measures up to four of them (and one CCSDS standard).

**EME2000** -- an inertial reference frame (axes fixed relative to distant
stars) defined by Earth's equator and equinox on 1 January 2000. The
inertial frame of CCSDS files SpaceMissionStudio writes.

**Epoch** -- the calendar date and time a simulation starts at, in
[UTC](#u), for example `2030-01-01T00:00:00`. Sun and Moon positions,
atmospheric density and where the ground is all depend on it.

**Events** -- things that happen at a time during a run: ground-station
passes, eclipses, burns and attitude-mode changes. The **Events** tab
lists and draws them.

## F

**F10.7** -- the Sun's radio brightness at 10.7 cm wavelength, a daily
measure of solar activity. A more active Sun heats and expands the upper
atmosphere, so low satellites feel more [drag](#d).

**Facet model** -- the spacecraft described as flat plates, each with its
own area, facing direction and centre of pressure. Drag and solar
pressure push on each plate that faces the flow or the Sun, so both
depend on the attitude and can twist the spacecraft.

**Flexible appendage** -- a large, light part, such as a solar-array
wing, that bends and swings when the spacecraft turns. Its first mode is
its lowest bending frequency; its damping ratio says how quickly the
swinging dies away.

**FSW (flight software)** -- the software that runs on the spacecraft. In
SpaceMissionStudio it means the attitude software: navigation, guidance
and control, built from Basilisk's own modules.

**FSW mode** -- which built-in pointing behaviour a spacecraft uses: for
example pointing straight down (nadir), at the Sun, or at a ground
station.

## G

**GCRF, ICRF** -- modern inertial reference frames, practically the same
as [EME2000](#e) for most purposes. SpaceMissionStudio accepts both in
imported [OPM](#o) files.

**GEO (geostationary orbit)** -- a circular orbit about 35,786 km above
the equator, where a satellite goes round once a day and so stays over
the same spot on the ground.

**Ground station** -- an antenna at a fixed point on Earth. SpaceMissionStudio
computes when each spacecraft can see each station (a **pass**) and how
far and how high it is.

## H

**Hill frame (R/T/N)** -- axes that move with a reference spacecraft (the
chief): **R**adial (away from Earth), **T**ransverse (along the direction
of travel) and **N**ormal (out of the orbit plane). Formation offsets are
given in it.

## I

**ICD (interface control document)** -- a document that lists every
message a piece of software reads and writes: its fields, units, who
writes it and who reads it. Each flight-software export has one.

**IERS** -- the International Earth Rotation and Reference Systems
Service, which measures exactly how Earth turns. Its data make the
[ITRF93](#i) frame accurate.

**IMU (inertial measurement unit)** -- a sensor that measures how fast
the spacecraft is turning (and, in some, how it accelerates).

**ITRF93, IAU_EARTH** -- two models of how Earth is oriented in space,
used to place ground stations and compute the ground track. ITRF93 uses
measured Earth rotation ([IERS](#i) data, downloaded with
`spacemissionstudio earth-orientation --fetch`); IAU_EARTH is a simpler
formula, about 10 km off at the surface in 2026. Runs say which one they
used.

## J

**J2** -- the largest effect of Earth's equatorial bulge on an orbit. It
slowly turns the orbit plane; [Sun-synchronous](#s) orbits use exactly
that.

## K

**KVN (keyword = value notation)** -- the plain-text form of [CCSDS](#c)
files: one `KEYWORD = value` per line. SpaceMissionStudio reads and
writes KVN, not the XML form.

## L

**Lambert transfer** -- the burn that takes a spacecraft from where it
is to a chosen position in a chosen time. The `lambert_transfer` command
in a [Mission Sequence](#m) computes it.

**LEO (low Earth orbit)** -- orbits below about 2000 km. Most satellites
fly there, low enough to feel [drag](#d).

**Link margin** -- how much stronger the received radio signal is than
the receiver needs, in dB. At 0 dB or more the link closes and data can
be sent; below 0 dB it cannot.

**LTAN (local time of the ascending node)** -- for a [Sun-synchronous
orbit](#s), the local solar time when the satellite crosses the equator
going north, for example 10:30. It sets the lighting the satellite sees.

## M

**Mean elements** -- orbit elements with the short, regular wobbles
averaged out, so slow trends (such as the orbit plane turning under
[J2](#j)) are easy to see. The opposite of osculating elements.

**Mission Sequence** -- a list of commands a run carries out in order:
propagate (fly) until something happens, burn, compute a Lambert
transfer, report a value, branch with `if`/`while`, or run a script
block. Like GMAT's or FreeFlyer's mission sequence.

**Monte Carlo** -- running the same scenario many times with small random
changes (mass, attitude, orbit, drag, ...), to see the range of outcomes
instead of one answer.

**MRP (modified Rodrigues parameters)** -- three numbers that describe an
[attitude](#a). Basilisk uses them for attitudes and attitude errors.

**MSFC** -- NASA's Marshall Space Flight Center, which publishes the
monthly solar-activity prediction ([F10.7](#f) and [Ap](#a)) that
SpaceMissionStudio uses beyond the measured record.

## N

**NAIF** -- NASA's Navigation and Ancillary Information Facility, which
publishes the [SPICE kernels](#s) and Earth orientation files.

**Navigation error** -- a deliberate error added to what the flight
software is told about the spacecraft (attitude, rate, position, ...),
so a run shows how the software copes with imperfect sensors.

**NRLMSISE-00** -- the model of the upper atmosphere's density that
drag uses, driven by [F10.7](#f) and [Ap](#a).

## O

**OEM, OMM, OPM** -- three [CCSDS](#c) orbit files. An **OPM** (Orbit
Parameter Message) gives one state at one time; an **OMM** (Orbit
Mean-Elements Message) gives mean elements, such as a [TLE](#t); an
**OEM** (Orbit Ephemeris Message) lists positions and velocities over
time.

**Orbital lifetime** -- how long [drag](#d) takes to bring an orbit down
to re-entry (here: the perigee reaching 120 km). Disposal rules cap it
after the mission ends: 5 years under ESA's Zero Debris approach and the
FCC, 25 years under the older IADC guideline.

**Osculating elements** -- the [classical elements](#c) of the orbit the
spacecraft would follow if every force but the central gravity stopped
at that instant. They wobble along the orbit; see mean elements.

## P

**Pass** -- one period when a spacecraft is above a ground station's
horizon (and above its minimum elevation).

**Patch antenna** -- a flat antenna on one face of the spacecraft. Its
gain is highest straight out of the face and falls off to the sides, so
the link depends on where the spacecraft points.

**Phasing (along-track separation)** -- how far ahead of or behind
another spacecraft (the chief) a satellite sits along the same orbit.
"Phasing-keeping" holds that separation, the way station-keeping holds
altitude.

**Provenance** -- `provenance.json`, written with every run's results: the
Basilisk version, whether it is the verified one, the other software
versions, and checksums of the scenario and every reference file used.

## R

**RAAN (right ascension of the ascending node)** -- the direction, in
space, where the orbit crosses the equator going north. It sets which way
the orbit plane faces.

**Reaction wheel (RW)** -- a spinning wheel inside the spacecraft.
Speeding it up or slowing it down turns the spacecraft the other way,
without propellant.

**Reference data** -- the data files runs need: [SPICE kernels](#s), the
gravity field, the magnetic field model, Earth orientation files and
space weather. The **Data** tab lists them.

**RF** -- radio frequency: the radio link between spacecraft and ground.

**RTN, VNB** -- two sets of axes for a burn's direction. **RTN**: Radial,
Transverse (along-track), Normal. **VNB**: Velocity, Normal (orbit
normal), Binormal. Both move with the spacecraft.

## S

**Scenario** -- one mission set-up saved as a JSON file: spacecraft,
orbits, ground stations, environment, run settings and an optional
Mission Sequence. A **template** is a ready-made scenario.

**SIL (software in the loop)** -- running the flight software as its own
program against the simulated spacecraft, step by step: the simulation
sends it the sensor readings and flies the spacecraft with its commands.

**Space weather** -- solar activity ([F10.7](#f)) and geomagnetic
activity ([Ap](#a)) over time. SpaceMissionStudio uses only real data:
measured values, and NASA [MSFC](#m)'s prediction for the future.

**SPICE kernels** -- reference files from [NAIF](#n) with planet
positions, leap seconds and planet shapes, which Basilisk needs for
real-world time and position.

**Spherical-harmonics gravity** -- a gravity model that includes a
planet's real, slightly lumpy shape, not just a point mass. A higher
degree means more detail and more computing time.

**SRP (solar radiation pressure)** -- the tiny push of sunlight on a
spacecraft. It matters most for high orbits and large, light spacecraft.

**Station-keeping** -- small, regular burns that put a satellite back
where it should be as drag and gravity make it drift.

**Sun-synchronous orbit (SSO)** -- a near-polar orbit whose plane turns
once a year, in step with the Sun, so the satellite passes over each
latitude at the same local solar time every day. Common for Earth
observation.

## T

**TAI, TDB, TT, UT1** -- time scales. **TAI**: atomic time. **TT**:
TAI plus 32.184 s. **TDB**: the time scale of planet positions, within
2 ms of TT. **UT1**: time by Earth's actual rotation. [UTC](#u) follows
TAI with leap seconds and stays within 0.9 s of UT1.

**Template** -- one of the 27 ready-made scenarios that come with the
app, each showing one idea or a complete mission. See the
[template catalog](../spacemissionstudio/scenarios/templates/README.md).

**Third-body perturbation** -- the small extra pull of a body other than
the one being orbited, such as the Sun or Moon on a satellite of Earth.

**TLE (two-line element set)** -- the compact text format in which
tracked satellites' orbits are published (for example by CelesTrak). A
way to give a starting orbit if you have one.

**Torque rod (magnetic torquer, MTB)** -- an electromagnet that pushes
against Earth's magnetic field to turn the spacecraft. Used here to
unload reaction wheels.

## U

**UTC** -- Coordinated Universal Time, the civil time standard. Every
epoch and time in SpaceMissionStudio is in UTC unless it says otherwise.

## V

**Vizard** -- Basilisk's separate 3D visualisation program. SpaceMissionStudio
can stream a run to it live or save a file to play back.

**VNB** -- see [RTN, VNB](#r).

## W

**Walker constellation** -- a constellation of satellites spread evenly
over several orbit planes, given as total satellites / planes / phasing
factor. **Generate Walker constellation** builds one.

---

**Next:** [Documentation index](README.md) ·
[Getting started](getting-started.md) · [FAQ](faq.md)
