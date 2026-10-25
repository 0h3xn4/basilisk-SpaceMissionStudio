# Keep an orbit, fly a formation or a constellation

How to hold a satellite's altitude or GEO slot, keep one spacecraft at a
set distance from another, and build a Walker constellation.

All of these are on the spacecraft's **Power / propulsion / link
budget** page, except the two generators, which are buttons under the
**Spacecraft** list.

## Hold a LEO altitude against drag

1. Open the spacecraft (its node in the scenario tree, or **Edit** in
   the list) and tick **Station keeping (altitude
   maintenance, delta-V + fuel tracking)**.
2. Set **Target altitude [km]** and **Deadband below target [km]**: a
   reboost burn starts when the altitude falls below the target by more
   than the deadband.
3. Set the thruster: **Reboost thrust [N]**, **Reboost thruster Isp [s]**,
   **Propellant available [kg]** and **Minimum thruster on-time [s]**.
4. Make sure drag is on (**Orbit / mass** page). Without drag the deadband
   may never be crossed; **Scenario > Overview** warns you.

Each burn appears on the **Timeline** with its delta-V. Template **18**
does this at 400 km.

## Hold a GEO slot

Tick **GEO station keeping (east-west and north-south boxes)** and set
**Slot longitude (east) [deg]**, **Longitude box half-width [deg]**,
**Inclination limit [deg]** and the thruster. East-west burns hold the
longitude; north-south burns at the nodes hold the inclination. Template
**03** holds 10 deg E within 0.05 deg.

## Keep a distance from another spacecraft (formation)

The quick way: **Generate phasing formation...** under the Spacecraft
list. Pick the **Chief (orbit source)**, a **Template (everything else)**
for the follower, a **New follower name**, the offset (**Along-track (T)
[km]**, and radial and cross-track if you want), and the thruster. It adds
the follower with **Phasing keeping** and its own station keeping already
filled in.

By hand: on the follower, tick **Phasing keeping**, choose the **Chief
spacecraft** and the **Target separation**, and pick a **Control law**:

| Control law | Good for |
|---|---|
| Drift orbit (default) | Long missions; the fewest burns. Template 05 holds 50 km within 5 km for 0.014 m/s in 90 days. |
| Mean orbital elements (Basilisk `meanOEFeedback`) | Holding tens of metres, at much higher delta-V. Template 24. |
| Hill-frame PD (Basilisk `hillFrameRelativeControl`) | Close formations, about 1 km, for short phases |

None of them fires in eclipse. **Scenario > Overview** draws the formation and
warns when a law asks for more thrust than the thruster has.

To hold a whole relative orbit (radial and cross-track motion too, for
example a passively safe helix) rather than one distance, use an ROE
formation instead: [Fly a formation with relative orbital
elements](roe-formation.md), and template **29**.

## Build a constellation

**Generate Walker constellation...** under the Spacecraft list copies one
**Template spacecraft** into a Walker pattern: **Total satellites (T)**,
**Number of planes (P)**, **Phasing factor (F)**, **Altitude [km]**,
**Inclination [deg]** and the **Pattern** (delta: planes spread over
360 deg; star: over 180 deg). Template **04** is a 6-satellite, 2-plane
delta.

From the command line:

```bash
spacemissionstudio generate-constellation in.json --out walker.json \
    --total-satellites 12 --planes 3 --phasing-factor 1 --altitude-km 780 --inclination-deg 86.4
spacemissionstudio generate-phasing-formation in.json --out formation.json \
    --chief chief-1 --follower-name follower-1 --along-track-km 50
```

## Thrust all the time

**Constant thrust (continuous, orbit-frame-relative)** fires a thruster
for the whole run in a fixed direction in the orbit frame, for example a
low-thrust orbit raise.

**More detail:** User Manual section 6,
[Formation control laws](../../USER_MANUAL.md#formation-control-laws).

---

**Next:** [Lifetime and propellant budget](lifetime-and-budget.md) ·
[Attitude and hardware](attitude-and-hardware.md)
