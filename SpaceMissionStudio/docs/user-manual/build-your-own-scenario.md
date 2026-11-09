# Build your own scenario

How to make a mission of your own: either start from a starter template,
or build one up from an empty scenario.

## The quick way: start from a starter

1. On **Home**, open **22 - Starter: your first LEO satellite**
   (one satellite, orbit only) or **23 - Starter: complete
   small-satellite mission** (sensors, wheels, power and a radio link).
2. **Save As...** (Ctrl+Shift+S) and give it your own name.
3. Change what you need in the **Scenario** area. Each template's
   description says what to change first.

## From an empty scenario

1. **New Scenario** (Ctrl+N). Type a **Name** and set the **Epoch (UTC)**.
   The epoch matters: it decides where the Sun and Moon are, how dense the
   upper atmosphere is, and when ground stations see you. Leave
   **Simulation mode** on *Orbit only* for now.
2. **Environment** (in the scenario tree): for a satellite around Earth,
   - tick **Enable spherical-harmonics gravity**, **Degree/order** 10;
   - add **sun** and **moon** as third-body perturbers;
   - set **Duration** to 1 day;
   - leave the atmosphere on the bundled, real space-weather data.
3. **Spacecraft**: **Add** (or **New from template...** for a 100 to
   500 kg preset). On **Orbit / mass**:
   - semi-major axis = 6378 km + altitude, so 6928 km for 550 km;
   - for an Earth-observation orbit, press **Compute Sun-sync inclination
     for this altitude** and **Compute RAAN for LTAN...** (10:30 is usual).
     The note under the field marks the value computed; if you change it,
     **Give a reason...** records why, and the value is then marked
     overridden ([Computed and overridden values](../models/value-marks.md));
   - or choose the TLE orbit type and paste a real satellite's TLE
     (switching the orbit type asks whether to convert the orbit you
     have or use the new page's values);
   - or take the orbit from another tool's CCSDS OPM or OMM with
     **Import CCSDS OPM/OMM...**
     ([Exchange orbits with other tools](orbit-files.md#in-the-app));
   - set **Dry mass**, and tick **Enable atmospheric drag** with its area
     (and **Enable solar radiation pressure**).
4. **Ground stations > Add**: a name, latitude, longitude and the lowest
   usable elevation (10 deg is common).
5. Check the bottom of the Scenario area. **✓ valid** means you can run; otherwise
   the message names the field to fix, and the **Problems** panel
   takes you to it with a double-click. **Scenario > Overview** already shows
   the orbit type and the predicted ground passes.
6. **Save As...** (Ctrl+Shift+S), then **Run** (`Ctrl+R`).

## Then grow it, one step at a time

Run after each step, so that when a result changes you know why.

1. Switch **Simulation mode** to *Full attitude* and pick a pointing mode
   ([Attitude and hardware](attitude-and-hardware.md)).
2. Add sensors and actuators.
3. Add station keeping ([Orbit keeping and formations](orbit-keeping-and-formations.md)).
4. Add power, a radio link or data handling
   ([Power, link and data](power-link-and-data.md)).
5. Add a [Mission Sequence](mission-sequence.md).

Template 23 is this process, finished.

## As text instead

**Form · JSON**, at the top of the Scenario area, shows the scenario as
the file it is saved as, and edits it. Press `Ctrl+Space` for the fields
an object can still have, each with its default, and the choices or names
a field takes; the key under the cursor is described under the text.
Every problem is underlined where it is, `Ctrl+.` offers a fix, and `F2`
renames a spacecraft, ground station or part everywhere
([the JSON page](../../USER_MANUAL.md#6-a-tour-of-the-scenario-editor)).

## From Python instead

[`examples/build_a_scenario.py`](../../examples/build_a_scenario.py)
builds the same kind of scenario in code and prints the summary that **Scenario > Overview** shows.

**More detail:** User Manual section 6,
[Building your own scenario, step by step](../../USER_MANUAL.md#building-your-own-scenario-step-by-step).

---

**Next:** [Read the results](read-the-results.md) ·
[Attitude and hardware](attitude-and-hardware.md)
