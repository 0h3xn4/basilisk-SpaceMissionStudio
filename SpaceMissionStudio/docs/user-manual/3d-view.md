# See it in 3D

**Results › 3D View** shows the last run in 3D, or a run while it runs.
It is part of the app: nothing to install, nothing downloaded, nothing
sent anywhere.

- **What it shows:** the Earth (NASA's Blue Marble, turning, lit by the
  Sun, with its atmosphere's rim) under NASA's star map, the Moon, each
  spacecraft (its [3D model](3d-model.md), or a 1 m cube without one)
  turned by the run's attitude, with its path, trail, body axes, arrows
  to the Sun, to nadir and along its velocity, its instruments' fields
  of view and its thrusters' plumes; the ground stations with a line to
  each spacecraft they see; the ground track; labels; and a panel with
  the UTC time, the speed and the followed spacecraft's altitude and
  speed.
- **Play** (Space) plays the run. The speed beside it is simulated time
  per second; it starts at the speed that plays the whole run in about
  30 s.
- **The slider** picks a time. It and the shared time cursor move
  together: click a plot or the Timeline and the view follows; pause or
  drag here and the plots' cursor follows.
- **View** (`[` and `]`): **Whole orbit** (the spacecraft drawn larger
  than they are; the note says by how much), **Follow** a spacecraft (true
  size), **Earth-fixed** (the camera turns with the Earth), or **From** a
  spacecraft along a body axis or an instrument, with its field of view.
- **Show** switches each part on or off, remembered for next time, and
  **Reduced quality** (chosen by itself without a graphics card, or when
  frames are slow; your own choice is kept).
- Drag to turn the view, scroll to zoom, right-drag to pan, double-click
  or Home to reset.

## While it runs

Check **Show in 3D View while running** on the Run area's **Run** page
(remembered). The next single run opens the 3D View and is drawn as it
is computed, with a **LIVE** badge: the spacecraft and their growing
paths, the Earth turning, the Sun moving.

- **Pace** (beside it): **As fast as possible**, or **1×** to **1000×
  real time**, so a run can be watched; it can change during the run.
- **Pause** (Space), the slider or the time cursor go back while the run
  goes on; **Go live** (End) returns to the newest state.
- At the end, or on **Cancel**, the run's result replaces what was drawn
  live, in the same view.
- Ordinary runs, Mission Sequences and runs over 100 days; not SIL.
  Watching does not change the run's results.

A spacecraft without an attitude in the run (a translation-only run) is
drawn aligned with the inertial axes, and the note says so. The Earth's
turning, the Sun and the Moon are drawn from standard formulas (the Earth
rotation angle, the Astronomical Almanac's solar and lunar positions),
close enough to see where things are, not to measure them: the plots and
exports hold the run's numbers.

## Limits

- After a run the 3D View keeps up to 1,500 frames spread over it.
- Live, it shows each spacecraft's state about 200 times an orbit (at
  most every dynamics step); between two states the spacecraft does not
  move.

**More detail:** User Manual section 9,
[3D visualization](../../USER_MANUAL.md#9-3d-visualization).

---

**Next:** [Read the results](read-the-results.md) ·
[Flight software and SIL](flight-software-and-sil.md)
