# Fly a formation with relative orbital elements

How to put a follower in a formation around a chief, set by relative
orbital elements (ROE), make it passively safe, move it from one
formation to another, and hold it with impulsive burns or continuous
thrust.

Template **29** does all of this: a follower starts 2 km behind its
chief and moves to a passively safe helix on day 1.

## The six numbers

A formation is six numbers in metres: the chief's semi-major axis times
each relative orbital element (quasi-nonsingular, after D'Amico).

| Element | What it does |
|---|---|
| a·δa | Relative semi-major axis. Not zero: the follower drifts along-track, about 3π × a·δa (9.4 ×) per orbit, backwards when a·δa is positive. |
| a·δλ | Relative mean longitude: where along the track the follower's centre of motion sits, + ahead of the chief. |
| a·δex, a·δey | Eccentricity vector: the follower circles its centre on an ellipse with this half-size radially and twice it along-track. |
| a·δix, a·δiy | Inclination vector: the cross-track motion, with this half-size. |

The two vectors' angle is their phase. With both vectors at the same
phase (parallel), the follower is never at the chief's radial and
cross-track position at once: the orbits do not cross, and an error in
the along-track spacing cannot bring the two together. That is
**passive safety**; the app shows it as the *closest radial/cross-track
approach*. Perpendicular vectors cross twice an orbit (approach 0 m).

J2 turns the eccentricity vector slowly, and when a·δix is not zero it
drifts the inclination vector and the along-track offset too. A phase of
90 deg (a·δix = 0) is therefore the cheapest to hold: in template 29 a
0 deg phase costs about three times as much.

## The quick way: the generator

1. Under the **Spacecraft** list, click **Generate ROE formation...**.
2. Pick the **Chief (orbit source)** and a **Template (everything else)**.
   The template must have **Station keeping**: the formation fires that
   thruster and draws from its tank.
3. Give a **New follower name** and a **Control law**.
4. Under **Formation**, **Specify as** either:
   * **Passively safe formation**: **Along-track [m]**, **Radial
     half-size [m]**, **Cross-track half-size [m]** and **Phase [deg]**;
   * **Relative orbital elements**: the six numbers above.

   The dialog shows the closest radial/cross-track approach as you type.
5. Click **OK**. The follower is placed at the formation from the start:
   the chief's mean elements plus the ROE, mapped to osculating elements
   with Basilisk's J2 mapping.

From the command line:

```bash
spacemissionstudio generate-roe-formation in.json --out helix.json \
    --chief chief-1 --follower-name follower-1 --safe 0,300,300
spacemissionstudio generate-roe-formation in.json --out roe.json \
    --chief chief-1 --follower-name follower-1 --roe 0,-2000,0,0,0,0 --control-law continuous
```

## By hand, and moving between formations

On the follower's **Power / propulsion / link budget** tab, tick
**ROE formation (relative orbital elements)**, pick the **Chief
spacecraft** and fill **Targets**. Each row is a formation, held from its
**Start [day]** to the next row's; the first starts at day 0. Below the
table, **Passively safe:** adds a helix row one day after the last; the
line under it shows the selected row's closest approach.

The follower's own orbit is where it starts. To start on the first
target, use the generator.

## The two control laws

| Control law | How it works | Template 29, 2 km behind to a 300 m helix |
|---|---|---|
| Impulsive burns (planned with the J2 model), default | When the mean ROE leave their **Tolerances [m]**, along-track burns set a·δa and the eccentricity vector, a cross-track burn the inclination vector, and a drift (a small a·δa, held for about the **Correction window [days]**, no more than **Max drift [m]**) moves the along-track offset. Burns are planned with the J2 state transition matrix and fired only in sunlight; one in eclipse waits an orbit. | On target 1.5 days after the switch, for 0.56 m/s; then 0.026 m/s in 1.5 days to hold it within 13 m. |
| Continuous (Basilisk meanOEFeedback) | Basilisk's mean-element feedback, aimed at the elements the ROE target gives, which are recomputed every **Target refresh [s]**. Fires most of the time. | On target 0.4 days after the switch and within 5 m after, for 1.85 m/s in 4 days. |

Neither fires in eclipse. Both fire the follower's station-keeping
thruster; the follower's station keeping itself never fires, because the
ROE controller already holds the relative semi-major axis, the chief's
reboosts included.

## Read the results

* `{follower}.roe_formation.roe`: the six mean ROE [m] the controller
  measures; `.roe_error`: the same minus the target.
* `.min_rn_separation`: the closest radial/cross-track approach [m].
* `.state`, `.delta_v`, `.target_index`; `.force` for the continuous law.
* **Events**: each burn ("ROE burn (in-plane)", "ROE burn
  (out-of-plane)", "ROE control firing") and each drift.
* **Explain**: the e/i-vector diagram, one colour per target: the two
  vectors and the path around the chief in the radial/cross-track plane.

## Limits

* The chief must be near-circular (eccentricity up to 0.01), not
  equatorial, around Earth with J2 in the gravity model (degree 2 or
  more).
* One run of at most 100 days.
* The guidance has no differential drag: two spacecraft with different
  ballistic coefficients drift apart, and the controller corrects it as
  an error.
* A follower cannot have both an ROE formation and phasing keeping.

**More detail:** User Manual section 6,
[Formations in relative orbital elements](../../USER_MANUAL.md#formations-in-relative-orbital-elements).

---

**Next:** [Orbit keeping and formations](orbit-keeping-and-formations.md) ·
[Read the results](read-the-results.md)
