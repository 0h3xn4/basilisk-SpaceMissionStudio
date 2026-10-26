# Data, standards and the offline policy

Which Basilisk version the app is qualified against, which standards its
orbit files and Earth model follow, where its reference data comes from,
and when it uses the network.

## Contents

- [Qualified Basilisk version](#qualified-basilisk-version)
- [Installing Basilisk: wheel or source](#installing-basilisk-wheel-or-source)
- [CCSDS orbit data messages](#ccsds-orbit-data-messages)
- [Earth orientation](#earth-orientation)
- [Space weather](#space-weather)
- [The offline policy](#the-offline-policy)

## Qualified Basilisk version

SpaceMissionStudio is verified against **Basilisk 2.12.0**
(`spacemissionstudio.dependencies.QUALIFIED_BASILISK_VERSION`; ECSS
compliance decision D5). The `.deb`, the install scripts and the Windows
setup script install `bsk[all]==2.12.0`. Another version still runs, but the GUI status bar and
`spacemissionstudio run` say so, and every run's `provenance.json` records
the Basilisk version, whether it is the qualified one, the other dependency
versions, a SHA-256 of the scenario and the reference data files used
(SPICE kernels, gravity field, magnetic model, space weather). The Basilisk
sources in this repository (the root `src/`, currently 2.13.0b0) are not
the qualified version, and the app does not use them.

## Installing Basilisk: wheel or source

Building from source in an automated/CI/sandboxed context is fragile --
this project hit exactly that failure mode early on (see
[`HISTORY.md`](../../HISTORY.md) for the full story). The plan flagged from the start was to
**vendor a prebuilt wheel pinned to a specific Basilisk release/commit**
as the default install path for end users, keeping "build from source" a
documented, opt-in developer path only.

That plan turned out to be simpler to satisfy than expected: Basilisk
itself now publishes prebuilt wheels to PyPI (`pip install "bsk[all]"`),
so there is usually no separate wheel to hunt down or vendor at all --
[Getting started](../getting-started.md) IS the vendoring story for most users.
`packaging/install.sh --basilisk-wheel` still exists and still works (it
was run end-to-end against `"bsk[all]"` for real -- see
[`packaging/README.md`](../../packaging/README.md)) for the cases that DO need something other than
the published PyPI package: a specific pinned/older release for
reproducibility, a locally-built wheel with custom modules, or an offline
install from a wheel file already on disk. `--basilisk-wheel` accepts any
string `pip install` would (a path, a URL, or a plain requirement
specifier like `"bsk[all]==2.12.0"`), not literally only a `.whl` file.

## CCSDS orbit data messages

SpaceMissionStudio reads, validates and writes CCSDS 502.0-B-3 (April 2023)
Orbit Parameter, Mean-Elements and Ephemeris Messages in KVN
(`spacemissionstudio/engine/ccsds_odm.py`; the OCM and the XML form are not
supported):

* `spacemissionstudio ccsds-validate FILE...` checks files against the
  standard; every breach of a "shall" is an error and of a "should" a
  warning, each with its clause.
* `spacemissionstudio run SCENARIO --oem` also writes each spacecraft's
  ephemeris as an OEM (EME2000, UTC; `--oem-stride N` thins it).
* `spacemissionstudio ccsds-export SCENARIO --out DIR` writes each
  spacecraft's initial state as an OPM (with osculating elements and GM for
  Earth), or a TLE spacecraft's elements as an OMM.
* `spacemissionstudio ccsds-import FILE SCENARIO --spacecraft NAME` sets a
  spacecraft's orbit from an OPM (EME2000, ICRF or GCRF; UTC, TAI, TT or
  TDB; `--set-epoch` moves the scenario epoch to the OPM's) or from a
  TLE-based OMM (converted to the TLE it represents).

[`compliance/ics_ccsds_502.csv`](../../compliance/ics_ccsds_502.csv) is the Implementation Conformance Statement
(Annex A) for the three messages.

How to use them: [Orbit files](../user-manual/orbit-files.md).

## Earth orientation

With NAIF's IERS-based Earth PCKs installed, the Earth-fixed frame of a run
is **ITRF93** (precession, nutation with IERS corrections, UT1, polar
motion); without them it is SPICE's `IAU_EARTH` rotation model (about
1.5 mrad, roughly 10 km at the surface, away from ITRF93 in 2026) and every
Earth run says so. The files (about 36 MB from naif.jpl.nasa.gov) are
fetched by the installers, by the reference-data card on Home when you agree, or with
`spacemissionstudio earth-orientation --fetch`; `--import FILE` installs
them from disk and `--rollback` restores the previous set. After the files'
last measured data plus about ten weeks the orientation is NAIF's
long-term prediction, which Explain (**Scenario › Overview**) notes.

## Space weather

`engine.spaceweather.resolve()` itself -- the function actually called
while a scenario runs -- never touches the network. Space weather is real
data only: `source` is `"bundled"` (the default: CelesTrak's SW-All file
shipped in `spacemissionstudio/data/spaceweather/`, or a newer copy the
reference-data card on Home downloaded) or `"local_file"` (your own CelesTrak file).
The shipped file (updated 2026-10-25; <https://celestrak.org/SpaceData/>)
holds observed daily F10.7 and Ap from 1957-10-01 and CelesTrak's 45-day
forecast. Beyond that, solar activity comes from NASA MSFC's October 2026
prediction (also shipped; F10.7 and Ap at the 95th/50th/5th percentiles,
2026-04 to 2041-10, the last 132 months repeated after that), as ESA's
AD10 guideline (EOP-FM/2024-07-177, Sec. 5.9) prescribes. "Solar
activity" picks the column: Nominal (50th) by default, Conservative
(95th) as AD10 asks for operations budgets, the 50th for end of life. Months before MSFC's
first use NOAA's monthly F10.7 with Ap at the observed mean (12.8). Runs
say which data they used in their warnings. The earlier `"synthetic"` profile was
removed; older scenario files are migrated to `"bundled"`. So was the
old "conservative" margin (a constant percentile of the observed
record): schema v4 turns it into the 95th percentile.

## The offline policy

SpaceMissionStudio makes **no network calls implicitly**: nothing is
fetched without asking, and a run never downloads anything. Network
access happens only in these places, each started by you:

| Where | What it fetches | How it asks |
|---|---|---|
| Installation | Basilisk and the Python packages (PyPI), then the support data once | You run the installer or `pip` |
| The **Fetch or update reference data?** card on Home at each GUI start (`gui.startup_fetch_dialog.ReferenceDataCard`) | Support data, CelesTrak space weather, Earth orientation files: what you tick | Shown every time; **Not now** touches no network; no "don't ask again" |
| The **Reference data** dialog's **Download...** (**Settings > Reference data**, or the status bar) | Support data, space weather or Earth orientation | Names the source, the files and the size; default No |
| **Download Vizard** in the "Vizard not found" dialog | AVS's pre-built Vizard | Only on that click; **Browse...** is the alternative |
| Commands you type | `kernels-status` (missing support data), `earth-orientation --fetch` | Running the command is the request |

Everything fetched is stored locally, and every file can also be
installed from disk (**Import file...** in the **Reference data** dialog,
`earth-orientation --import`), so a machine can stay offline for good. The installers'
part is described in [`packaging/README.md`](../../packaging/README.md);
`tests/test_offline.py` runs with all network access blocked in CI.

---

**Next:** [Reference data](../user-manual/reference-data.md) ·
[Known limitations](limitations.md) ·
[Documentation index](../README.md)
