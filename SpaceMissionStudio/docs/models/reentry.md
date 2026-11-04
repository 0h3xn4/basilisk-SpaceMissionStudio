# Preliminary re-entry casualty estimate

**A preliminary estimate**, in the manner of NASA's Debris Assessment
Software (DAS), simplified: it is not a substitute for DAS, DRAMA or
SESAM, and the End of Life page says so beside every number. The code is
`analyses/reentry.py`; the choices are decisions D-14 to D-16 in
[the decision log](../developer/model-analyses-decisions.md).

## Method

1. **Break-up.** At `breakup_altitude_km` (78 km) every part of the 3D
   model with mass becomes a fragment: its mass, its whole surface `S`
   (hidden parts too) and its material. DAS 3.0 User's Guide
   (NASA/TP-2019-220300), Sec. 3.8 and 4.1.3: "the outermost structure
   ... is assumed to break apart at an altitude of 78 km".
2. **Descent.** Planar flight over a spherical, non-rotating Earth with
   point-mass gravity:

   ```
   dh/dt     = V sin(gamma)
   dV/dt     = -D / m - g sin(gamma)
   dgamma/dt = (V / r - g / V) cos(gamma)
   ```

   from the circular speed at 78 km and `gamma = 0`, integrated with RK4
   at 0.05 s, in the U.S. Standard Atmosphere 1976 table Basilisk ships
   (`atmosphere_tables`), interpolated in log density.
3. **Drag.** A convex body tumbling at random in Newtonian flow
   (`C_p = 2 cos^2(theta)`) has, averaged over orientations, a drag
   `q S / 4`: `C_d = 1` on its mean projected area `S / 4`, which is
   Cauchy's mean projected area of a convex body. So
   `D = (1/2) rho V^2 S / 4`.
4. **Heating.** Sutton and Graves (NASA TR R-376, 1971) give
   `q_s = K sqrt(p_s / R_n) (h_s - h_w)` with, for air,
   `K = 0.1113 kg / (s m^1.5 atm^0.5)` (their Table II). With
   `p_s = rho V^2` and `h_s - h_w = V^2 / 2` (the simplified form,
   Carroll et al., NTRS 20220018610, Eq. 1):

   `q_s = k sqrt(rho / R_n) V^3`, `k = K / (2 sqrt(101325 Pa)) = 1.748e-4 kg^0.5 / m`

   (decision D-15). `R_n` is the radius of the sphere with the same mean
   projected area, `sqrt(S / (4 pi))`. A windward flux `q_s cos(theta)`
   averaged over a tumbling convex body gives an absorbed heat `q_s S / 4`.
5. **Re-radiation and demise.** A lumped energy balance from 300 K:
   `m c_p dT/dt = q_s S / 4 - eps sigma S T^4` until the melting
   temperature, then the fragment melts as it absorbs `m h_f`. The
   material's melting temperature, heat of fusion and specific heat come
   from DAS 3.0's Table C-4 (`config/materials.py`) or the model's own
   materials. No emissivity at re-entry temperatures could be sourced, so
   every fragment is computed with `eps = 0` (the most heat: demise-prone)
   and `eps = 1` (survival-prone); the survival-prone result is reported
   (decision D-14). A fragment that lands partly melted keeps the unmelted
   mass.
6. **Casualty area.** A fragment landing with more than
   `casualty_energy_j` (15 J, NASA-STD-8719.14B, as the DAS guide's
   Appendix B reproduces it) adds `(0.6 + sqrt(A_i))^2`, `A_i = S / 4`
   (Kelley, IAC-12-A6.2.18, NTRS 20120002794, Eq. 1: 0.6 m is the root of a
   standing person's cross-section seen from above).
7. **Risk.** `E_c = A_c rho_pop`, with the population density the user
   gives (people per km^2; no default, decision D-16), against
   `casualty_risk_limit` (1:10,000, NASA-STD-8719.14B Req. 4.7-1a).

## What it leaves out

- the parent body's own heating before break-up, and fragments of
  fragments;
- hollow and composite objects (DAS's shells, boxes and cylinders of a
  given thickness): each part is one lumped mass;
- oxidation heat, the variation of the specific heat with temperature
  (a range in Table C-4 is entered at its midpoint), and the atmosphere's
  rotation;
- the population's latitude distribution (DAS's population tables).

A part with no material, or a material without the three thermal values,
survives whole here: the estimate says so per part.

## Validation

`tests/test_reentry.py`: the constant `k` from the 1971 table; a fragment
that cannot heat lands at its sea-level terminal speed
`sqrt(2 m g / (rho_0 S/4))` within 1 %; a light aluminium part melts high
and a heavy one survives, with less left at `eps = 0`; the casualty area
and risk follow Kelley's formula and the limit. No published reference
case with fragment-by-fragment results was compared with: none was
accessible from where this was built. `compliance/validation/` records
this.

## Parameters

| Parameter | Default | Unit | Controls | Source |
|---|---|---|---|---|
| `breakup_altitude_km` | 78 | km | Where the spacecraft breaks into its parts | DAS 3.0 User's Guide, Sec. 3.8 |
| `casualty_energy_j` | 15 | J | The impact energy above which a fragment counts | NASA-STD-8719.14B Req. 4.7-1 (via the DAS guide, App. B) |
| `casualty_risk_limit` | 1e-4 | - | The casualty expectation it is compared with | NASA-STD-8719.14B Req. 4.7-1a (via the DAS guide, App. B) |
