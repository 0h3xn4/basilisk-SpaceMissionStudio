# Space weather data

`SW-All.txt` is CelesTrak's space-weather file (CSSI format, version 1.2),
unmodified except for line endings (stored with LF):

* source: <https://celestrak.org/SpaceData/SW-All.txt>
  (format: <https://celestrak.org/SpaceData/SpaceWx-format.php>);
* updated 2026-10-19 20:34 UTC;
* observed daily Kp/Ap and F10.7 from 1957-10-01 to 2026-10-18, CelesTrak's
  45-day daily forecast to 2026-12-02, and NOAA's monthly F10.7 forecast
  from 2027-01 to 2041-10;
* downloaded from the source above on 2026-10-19. The copies before it
  were downloaded on 2026-10-12 (updated 2026-10-12) and, before that
  (updated 2025-07-21), came from the `spaceweather` Python package
  (version 0.4.2), which redistributes it with CelesTrak's permission.

CelesTrak asks only that the URL above is given so others can find the
data and its documentation; there are no other licensing requirements
(Dr. T.S. Kelso, CelesTrak).

A newer copy downloaded from the app's reference-data card on Home or
the Reference data dialog (with your consent)
replaces this one automatically; see `engine/spaceweather.py`.

`oct2026f10-prd.txt` is NASA Marshall Space Flight Center's solar-cycle
prediction of October 2026 ("Table 3: estimates of 13-month smoothed solar
activity for the balance of cycle 25, with a mean cycle for cycle 26"),
unmodified except for line endings (stored with LF): monthly F10.7 and Ap
at the 95th, 50th and 5th percentiles
from 2026-04 to 2041-10.

* source: <https://www.nasa.gov/solar-cycle-progression-and-forecast/>
  (this issue: `wp-content/uploads/2026/10/oct2026f10-prd.txt`);
* a NASA work, so not subject to copyright in the US.

ESA's guideline EOP-FM/2024-07-177 (AD10) Sec. 5.9 prescribes MSFC's
prediction for future solar activity: the 95th percentile for operations
budgets, the 50th for end of life, NRLMSISE-00, and the last 132 months
repeated past the file's end. A study's own MSFC file can be set in
**MSFC prediction** on the Scenario area's **Environment** page instead.

The two files differ from the published originals only in whitespace that
this repository's pre-commit hooks remove: trailing spaces at the end of
two header lines (`SW-All.txt`: one comment line; `oct2026f10-prd.txt`: the
percentile header), and LF instead of CRLF line endings. No value changed.
A run records the SHA-256 of the file it used in its provenance.
