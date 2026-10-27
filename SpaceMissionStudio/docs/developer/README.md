# Developer guide

How to set up SpaceMissionStudio for development, run its tests and
checks, and keep its generated files current.

**Contents**

1. [Set up](#1-set-up)
2. [Run the tests](#2-run-the-tests)
3. [Lint](#3-lint)
4. [Generated files: regenerate, never edit](#4-generated-files-regenerate-never-edit)
5. [Conventions](#5-conventions)
6. [What CI runs](#6-what-ci-runs)
7. [More developer pages](#7-more-developer-pages)

## 1. Set up

You need Python 3.14 (CI uses 3.14), git, and on Linux glibc 2.28
or newer. From a terminal:

```bash
git clone https://github.com/0h3xn4/basilisk-SpaceMissionStudio.git
cd basilisk-SpaceMissionStudio/SpaceMissionStudio
python3 -m venv .venv
source .venv/bin/activate              # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install "bsk[all]==2.12.0"         # Basilisk, the version the tool is verified against
pip install -e ".[dev,gui]"            # the tool, its GUI, and pytest, pytest-qt, pytest-xdist, ruff
spacemissionstudio kernels-status      # downloads the reference data once (about 116 MB)
spacemissionstudio earth-orientation --fetch
```

On a minimal Debian or Ubuntu system, Qt needs a few system libraries:

```bash
sudo apt-get install libegl1 libopengl0 libxcb-cursor0 libgl1 libxkbcommon0 libnss3 libatk-bridge2.0-0 libgbm1
```

**Basilisk comes from PyPI, not from this repository.** The tool imports
the `bsk` wheel installed above. The Basilisk sources in `../src` (the
upstream fork, currently `2.13.0b0`) are not built or used by the tool.
The verified version is set in
`spacemissionstudio/dependencies.py` (`QUALIFIED_BASILISK_VERSION`).

## 2. Run the tests

From the `SpaceMissionStudio` folder, with the environment active:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests -q -n auto
```

- `-n auto` runs on every CPU core (pytest-xdist). A full run takes about
  7 minutes on 4 cores.
- `QT_QPA_PLATFORM=offscreen` runs the GUI tests without a display. On
  Windows PowerShell: `$env:QT_QPA_PLATFORM = "offscreen"`.
- Markers (`tests/conftest.py`) skip what your machine cannot run:
  - `requires_basilisk`: needs Basilisk;
  - `requires_gui`: needs PySide6 (the `gui` extra);
  - `requires_c_toolchain`: builds the exported C code; needs CMake and a
    C compiler.
- Tests whose data is not installed skip: the Eros files, the IERS Earth
  orientation files, the GMAT references, a German locale. The tests of
  what happens without Basilisk run with Basilisk hidden (the
  `basilisk_unavailable` fixture in `tests/conftest.py`).
- `slow` marks the tests that take about a minute or more (each a full
  Basilisk run). CI runs them; `-m "not slow"` leaves them out of a quick
  local run.
- One file at a time: `python -m pytest tests/test_cli.py -q`.

**Offline tests.** `tests/test_offline.py` checks that nothing touches the
network. CI runs it inside a network namespace with no network at all:

```bash
unshare -rn python -m pytest tests/test_offline.py -q -p no:cacheprovider
```

**Coverage**, as CI measures it:

```bash
python -m pytest tests -q -n auto --cov=spacemissionstudio --cov-branch --cov-report=json:coverage.json
python compliance/tools/metrics.py --coverage coverage.json --fail-under 90 --fail-under-branch 80
```

## 3. Lint

```bash
python -m ruff check spacemissionstudio tests scripts compliance/tools
```

The rules are in `pyproject.toml` (`[tool.ruff]`). The repository root's
pre-commit hooks also check trailing whitespace and end-of-file newlines
on every changed file, Markdown included:

```bash
pip install pre-commit
pre-commit run trailing-whitespace --files <files>
pre-commit run end-of-file-fixer --files <files>
```

## 4. Generated files: regenerate, never edit

Several files are written by scripts. Edit the source, then run the
script; CI fails when a generated file is out of date.

| You changed | Run | It rewrites |
|---|---|---|
| `USER_MANUAL.md` or its images in `docs/images/` | `python scripts/sync_help.py` | `spacemissionstudio/help/` (the copy the app shows; `tests/gui/test_help.py` checks it) |
| A template, the schema, or `scripts/_template_descriptions.py` | `python scripts/_generate_templates.py` | `spacemissionstudio/scenarios/templates/*.json` |
| Code, tests or the schema | the five commands below | `compliance/docs/` (ICD schema, component map, test specifications, traceability) |
| A compliance assessment | `python compliance/tools/build_matrix.py` | `compliance/compliance_matrix.csv` |
| What a screen looks like | `QT_QPA_PLATFORM=offscreen python scripts/capture_screenshots.py docs/images` (needs Basilisk and the reference data; the Monte Carlo batch takes the longest), then `python scripts/sync_help.py` | The screenshots in `docs/images/` |

The compliance documents, as CI checks them:

```bash
for t in check_drds build_icd_schema build_sdd_components build_test_specs build_traceability; do
  python compliance/tools/$t.py
done
git diff --exit-code -- compliance/docs
```

**The bundled manual's links.** `spacemissionstudio/help/USER_MANUAL.md`
is a copy that lives inside the package, so its relative links to other
files (`GETTING_STARTED.md` and so on) do not resolve on GitHub. The app
shows such links as "Not found in the manual". Leave the copy out of link
checks; check `USER_MANUAL.md` itself.

## 5. Conventions

- **Code:** `compliance/docs/coding_standard.md`, and the repository-wide
  rules in `../AGENTS.md` (unit comments on physical values, an ISC
  licence header on new files, a docstring on every test).
- **Basilisk is not modified.** No edits to `../src`, no patches, no
  monkey-patching of its internals. Where Basilisk falls short, the tool
  works around it in its own code and says so.
- **Reference data is real.** Space weather, Earth orientation and the
  other reference data come from their publishers; nothing is made up.
- **Nothing touches the network without asking.** See the
  [FAQ](../faq.md#does-it-need-the-internet).
- **Commits:** one logical change each. Code commits name the requirement
  they address (for example `SRS-F-19: ...`, from
  `compliance/docs/SRS.md`); documentation commits start with `docs:`.
  The root `.pre-commit-config.yaml` also has Basilisk's `[#1234]`
  commit-message hook; it is upstream's convention and applies only if
  you install the commit-msg hook.
- **Records:** a change worth explaining gets an entry in
  [`HISTORY.md`](../../HISTORY.md) (the development log) and, when it
  changes what users see, in [`CHANGELOG.md`](../../CHANGELOG.md).

## 6. What CI runs

`.github/workflows/spacemissionstudio.yml`, on every push and pull
request that touches `SpaceMissionStudio/`:

| Job | Runs on | What |
|---|---|---|
| `docs` | Ubuntu, when only documentation changed | Whitespace hooks, the compliance-document checks, `tests/gui/test_help.py` |
| `test` | Ubuntu, Python 3.14 | Lint; compliance-document checks; reference data download; the full suite with coverage; the offline tests; metrics (statement coverage at least 90 %, branch at least 80 %); traceability and compliance matrix |
| `platforms` | `windows-latest` | Reference data download and the full suite |

If a process in the `test` job crashes in native code (Qt, numpy,
Basilisk), Python's faulthandler shows only `<no Python frame>` for the
crashed thread. The job therefore keeps core dumps in `/tmp/cores`, and
the step **Native stacks of crashed processes, if any** runs
[`scripts/print_core_backtraces.sh`](../../scripts/print_core_backtraces.sh)
on them: `gdb` prints the crashed thread's C/C++ stack, every thread and
the loaded libraries. The output is in that step's log and in the
`native-stacks` artifact; the step finds nothing on a run without a
crash. Before the tests, the job crashes one Python process on purpose
to check that cores are written and readable, and warns if not.

Basilisk's own workflows (in `.github/workflows/`, from upstream) also
run; they build and test Basilisk itself, on Linux and Windows only
(their macOS jobs were removed: `docs/DECISIONS.md`, macOS removed).

## 7. More developer pages

- [Architecture](architecture.md): how the code is organised.
- [Releasing](releasing.md): cutting a release.
- [Syncing with upstream Basilisk](upstream-sync.md): taking a new
  Basilisk, and refreshing the upstream part of the root README.
- [`compliance/`](../../compliance/README.md): the ECSS and CCSDS
  compliance work, requirements, design and verification documents.

---

**Next:** [Architecture](architecture.md) ·
[Contributing](../../CONTRIBUTING.md) · [Documentation index](../README.md)
