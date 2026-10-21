# Run many variations at once (Monte Carlo)

How to run a scenario many times with small random changes, and see how
far apart the results end up.

## Set up a batch

1. In the scenario tree, open the **Monte Carlo** page and tick
   **Enabled**.
2. Set how many runs, and how many run in parallel.
3. Add one or more **dispersions**: which quantity varies, for which
   spacecraft, and by how much.
4. Set the mode beside **Run** to **Monte Carlo**, press **Run**, and
   choose a folder. Every run is saved there; the progress strip counts
   the cases done. A batch runs to the end: it cannot be cancelled.

What can vary:

| Quantity | Varies | Kinds |
|---|---|---|
| `dry_mass_kg` | Dry mass [kg] | uniform, normal |
| `attitude_sigma_bn` | Starting attitude | uniform |
| `orbit_elements` | Each orbital element of the starting orbit | normal, uniform |
| `inertia_kg_m2` | The inertia [kg m^2] | normal |
| `angular_rate_bn_b` | Starting body rate [deg/s] | normal, uniform |
| `drag_coeff`, `srp_coeff` | The drag or solar-pressure coefficient | uniform, normal |

Inertia and body rate need *Full attitude*; the coefficients need drag or
solar pressure on.

## Read the batch

The **Monte Carlo** view of Results opens on the batch:

- **Tiles:** how many runs succeeded, and the 1-sigma spread at the end
  along track, radially and across track.
- **Plots:** every run's altitude and its offset from the mean, and the
  spread over time.
- **Runs:** what each run drew and where it ended. Sort a column to see
  which drawn value goes with the largest offset. **Export table CSV...**
  saves it.

**Open Monte Carlo Results...** (the Run area) opens a batch you ran earlier.

## From the command line or Python

```bash
spacemissionstudio monte-carlo spacemissionstudio/scenarios/templates/25_monte_carlo_orbit_and_drag_dispersions.json --archive-dir mc
python3 examples/monte_carlo_spread.py --runs 20 --archive mc_out
```

The example prints the spread day by day and ends with a line like
`day 3.00: 1-sigma 448.0 km along track`. Its 20 runs took 2 to 3
minutes in our clean-install tests.

## Templates

**09** varies the mass of a drag-free orbit (and shows that it changes
nothing). **25** varies the orbit and the drag coefficient: the runs
spread about 150 km per day along track.

**More detail:** User Manual section 10,
[Monte Carlo](../../USER_MANUAL.md#10-monte-carlo-running-many-variations-at-once).

---

**Next:** [Lifetime and propellant budget](lifetime-and-budget.md) ·
[Read the results](read-the-results.md)
