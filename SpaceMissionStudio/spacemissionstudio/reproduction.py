#
#  ISC License
#
#  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
"""Reproduction bundles: a run's folder that can run itself again, and the
check that it does (transparency audit, Phase 2h; ICD-03).

A bundle is a ``run --out-dir`` folder (the series CSVs, ``events.csv``,
``provenance.json`` and ``scenario_as_run.json``) with, in addition:

- ``inputs/``: a copy of every file the scenario refers to (model meshes,
  a Vizard model, the user's space-weather and MSFC files) and of the
  space-weather files the run read, which for the ``"bundled"`` source
  depend on the computer;
- ``bundle.json`` (:data:`MANIFEST`): each copy, with the reference it
  stands for and its SHA-256.

The installed reference data (SPICE kernels, gravity fields, Earth
orientation) is not copied: ``de430.bsp`` alone is 114 MB. Its SHA-256 is
in ``provenance.json``, and :func:`reproduce` compares it with this
computer's copy.

:func:`reproduce` checks the bundle, runs its scenario with the references
pointed at the copies, and compares every series with the bundle's,
column by column, within ``rtol`` of the column's largest value. It says
what differed: versions, platform, data files, and which series, by how
much.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path

MANIFEST = "bundle.json"
SCENARIO_AS_RUN = "scenario_as_run.json"
INPUTS = "inputs"
FORMAT = 1
# Files of a run folder that are not series.
NOT_SERIES = {"events.csv", "command_summary.csv"}
# The default comparison: a column agrees when every value is within this
# fraction of the column's largest magnitude. The CSVs hold 9 significant
# digits, and the regression baseline found well-conditioned outputs to
# agree within 3.8e-7 of their scale across computers (DECISIONS,
# "The regression baseline").
DEFAULT_RTOL = 1e-6  # [-]
_SHAPES = ("CUBE", "CYLINDER", "SPHERE")  # vizard_model_path values that are not files


class BundleError(Exception):
    """A folder that is not a bundle, or one whose files do not match it."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _references(scenario):
    """(role, owner, attribute, path given, relative to the scenario's
    folder) of each file ``scenario`` refers to; ``owner.attribute`` holds
    the path. A model's meshes and Vizard model are read relative to the
    scenario file's folder; the space-weather files relative to the
    working folder, as ``engine.spaceweather`` opens them."""
    for sc in scenario.spacecraft:
        if sc.model is not None:
            for index, mesh in enumerate(sc.model.meshes):
                yield f"spacecraft[{sc.name}].model.meshes[{index}]", mesh, "path", mesh.path, True
        if sc.vizard_model_path and sc.vizard_model_path.upper() not in _SHAPES:
            yield f"spacecraft[{sc.name}].vizard_model_path", sc, "vizard_model_path", sc.vizard_model_path, True
    weather = scenario.space_weather
    if weather.source == "local_file" and weather.local_file_path:
        yield "space_weather.local_file_path", weather, "local_file_path", weather.local_file_path, False
    if weather.msfc_file_path:
        yield "space_weather.msfc_file_path", weather, "msfc_file_path", weather.msfc_file_path, False


def _resolve(given: str, base_dir: Path | None) -> Path:
    path = Path(given).expanduser()
    return path if path.is_absolute() or base_dir is None else base_dir / path


def write_bundle(out_dir, scenario, result, base_dir=None) -> Path:
    """Make the run folder ``out_dir`` a bundle: copy into ``inputs/`` the
    files ``scenario`` refers to (relative paths resolved from
    ``base_dir``, the scenario file's folder) and the space-weather files
    the run read (``result.provenance.data_files``), and write
    :data:`MANIFEST`. A file referred to that does not exist is listed as
    missing. Returns the manifest's path."""
    from . import __version__

    out_dir = Path(out_dir)
    inputs = out_dir / INPUTS
    entries, copied = [], {}

    def copy(source: Path) -> str | None:
        source = source.resolve()
        if source in copied:
            return copied[source]
        if not source.is_file():
            return None
        inputs.mkdir(exist_ok=True)
        name, count = source.name, 1
        while (inputs / name).exists():  # two files of one name from different folders
            count += 1
            name = f"{source.stem}_{count}{source.suffix}"
        shutil.copy2(source, inputs / name)
        copied[source] = f"{INPUTS}/{name}"
        return copied[source]

    for role, _owner, _attribute, given, from_scenario in _references(scenario):
        stored = copy(_resolve(given, base_dir if from_scenario else None))
        entries.append({"role": role, "reference": given, "file": stored,
                        "sha256": _sha256(out_dir / stored) if stored else None,
                        **({} if stored else {"missing": True})})
    data_files = result.provenance.data_files if result.provenance is not None else {}
    for key in ("space_weather", "space_weather_forecast"):
        record = data_files.get(key)
        if record and record.get("path"):
            stored = copy(Path(record["path"]))
            if stored:
                entries.append({"role": f"data_files.{key}", "reference": record["path"], "file": stored,
                                "sha256": _sha256(out_dir / stored)})
    provenance = result.provenance
    manifest = {"format": FORMAT, "scenario": SCENARIO_AS_RUN,
                "scenario_sha256": provenance.scenario_sha256 if provenance is not None else "",
                "inputs": entries, "spacemissionstudio_version": __version__,
                "created_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    path = out_dir / MANIFEST
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def export_bundle(out_dir, scenario, result, base_dir=None, epoch_utc: str | None = None, progress=None) -> Path:
    """A bundle written from a run held in memory (the GUI's): the series
    CSVs and ``provenance.json`` (``ResultSet.export_csv``, with
    ``progress``), ``events.csv``, the scenario as run, then
    :func:`write_bundle`. ``out_dir`` should be empty: a file an earlier
    export left there would be compared too. Returns the manifest's path."""
    from .engine import events
    from .engine.results import output_path
    from .schema.scenario import scenario_text

    out_dir = Path(out_dir)
    result.export_csv(out_dir, progress=progress)
    found = events.extract_events(result)
    if found:
        events.write_csv(found, out_dir / "events.csv", epoch_utc or scenario.epoch_utc)
    output_path(out_dir, SCENARIO_AS_RUN).write_text(scenario_text(scenario), encoding="utf-8")
    return write_bundle(out_dir, scenario, result, base_dir)


def missing_inputs(manifest_path) -> list[str]:
    """The references a bundle could not copy (their files were not found)."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    return [entry["reference"] for entry in manifest.get("inputs", []) if entry.get("missing")]


@dataclass
class SeriesDifference:
    """The largest difference in one series between the bundle and the new
    run, as a fraction of the column's largest magnitude."""

    series: str
    column: str
    relative: float  # [-] max |new - old| / max |old| over the column (inf when the shapes differ)
    absolute: float  # in the series' unit
    note: str = ""


@dataclass
class Reproduction:
    """What :func:`reproduce` found."""

    bundle: Path
    out_dir: Path
    rtol: float
    series_compared: int = 0
    worst: list[SeriesDifference] = field(default_factory=list)  # largest first
    failed: list[SeriesDifference] = field(default_factory=list)  # over rtol, or missing
    substitutions: list[str] = field(default_factory=list)  # references pointed at the bundle's copies
    differences: list[str] = field(default_factory=list)  # versions, platform, data files, events
    run_warnings: list[str] = field(default_factory=list)

    @property
    def reproduced(self) -> bool:
        return not self.failed

    def lines(self) -> list[str]:
        """The report, one line each."""
        verdict = (f"REPRODUCED: {self.series_compared} series within {self.rtol:g} of their scale"
                   if self.reproduced else
                   f"NOT REPRODUCED: {len(self.failed)} of {self.series_compared} series differ by more "
                   f"than {self.rtol:g} of their scale")
        out = [verdict]
        shown = self.failed[:10] if self.failed else self.worst[:1]  # the differences, or the largest agreement
        out += [f"  {'largest difference: ' if not self.failed else ''}{d.series} [{d.column}]: "
                f"{d.relative:.3g} of scale ({d.absolute:.6g})" + (f", {d.note}" if d.note else "") for d in shown]
        out += [f"USED: {s}" for s in self.substitutions]
        out += [f"DIFFERS: {d}" for d in self.differences]
        return out


def read_manifest(bundle) -> dict:
    """The bundle's :data:`MANIFEST`; :class:`BundleError` if there is none,
    or if a copy's SHA-256 is not the one recorded."""
    bundle = Path(bundle)
    try:
        manifest = json.loads((bundle / MANIFEST).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise BundleError(f"{bundle} is not a reproduction bundle: no {MANIFEST} (write one with "
                          "'run --bundle')") from None
    except (OSError, ValueError) as exc:
        raise BundleError(f"{bundle / MANIFEST}: could not be read ({exc})") from None
    if manifest.get("format") != FORMAT:
        raise BundleError(f"{bundle / MANIFEST}: bundle format {manifest.get('format')!r}, this version reads "
                          f"{FORMAT}")
    for entry in manifest.get("inputs", []):
        if entry.get("file") and _sha256(bundle / entry["file"]) != entry.get("sha256"):
            raise BundleError(f"{bundle / entry['file']} is not the file the bundle was made with (its SHA-256 "
                              "changed)")
    return manifest


def bundled_scenario(bundle, manifest: dict):
    """(the bundle's scenario with its file references pointed at the
    bundle's copies, the substitutions made). The scenario's canonical
    hash before the substitutions must be the one recorded."""
    from . import output_provenance
    from .schema import load_scenario

    bundle = Path(bundle)
    scenario = load_scenario(bundle / manifest.get("scenario", SCENARIO_AS_RUN))
    if manifest.get("scenario_sha256") and output_provenance.scenario_sha256(scenario) != manifest["scenario_sha256"]:
        raise BundleError(f"{bundle / SCENARIO_AS_RUN} is not the scenario the bundle was made from (its SHA-256 "
                          "differs from the one recorded)")
    by_role = {entry["role"]: entry for entry in manifest.get("inputs", [])}
    substitutions = []
    for role, owner, attribute, given, _from_scenario in _references(scenario):
        entry = by_role.get(role)
        if entry and entry.get("file"):
            setattr(owner, attribute, str((bundle / entry["file"]).resolve()))
            substitutions.append(f"{role}: the bundle's {entry['file']} for {given}")
    return scenario, substitutions


def _use_bundled_space_weather(scenario, bundle: Path, manifest: dict, recorded: dict, substitutions: list):
    """For the ``"bundled"`` source, the space-weather files the run read
    depend on the computer (the shipped file or a newer download). When
    this computer's differs from the one recorded and the bundle has a
    copy, the copy is used, and said so."""
    from .engine import spaceweather

    weather = scenario.space_weather
    by_role = {entry["role"]: entry for entry in manifest.get("inputs", [])}
    if weather.source == "bundled":
        entry = by_role.get("data_files.space_weather")
        here = spaceweather.real_data_path("bundled", None, weather.cache_dir)
        if entry and here.is_file() and _sha256(here) != recorded.get("space_weather", {}).get("sha256"):
            weather.source, weather.local_file_path = "local_file", str((bundle / entry["file"]).resolve())
            substitutions.append(f"space weather: the bundle's {entry['file']}, as this computer's {here.name} "
                                 "differs from the one the run read")
    entry = by_role.get("data_files.space_weather_forecast")
    if entry and not weather.msfc_file_path and spaceweather.MSFC_BUNDLED_PATH.is_file() and \
            _sha256(spaceweather.MSFC_BUNDLED_PATH) != recorded.get("space_weather_forecast", {}).get("sha256"):
        weather.msfc_file_path = str((bundle / entry["file"]).resolve())
        substitutions.append(f"MSFC prediction: the bundle's {entry['file']}, as this computer's differs")


def _read_series(path: Path) -> tuple[list[str], list[list[float]]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.reader(stream))
    header, body = rows[0], rows[1:]
    return header, [[float(v) for v in row] for row in body]


def compare_series(old: Path, new: Path, name: str) -> list[SeriesDifference]:
    """One :class:`SeriesDifference` per column of series ``name``,
    between its CSV in the bundle (``old``) and in the new run (``new``)."""
    old_header, old_rows = _read_series(old)
    new_header, new_rows = _read_series(new)
    if old_header != new_header or len(old_rows) != len(new_rows):
        return [SeriesDifference(name, "*", math.inf, math.inf,
                                 f"{len(old_rows)} rows of {old_header} against {len(new_rows)} of {new_header}")]
    out = []
    for index, column in enumerate(old_header):
        old_values = [row[index] for row in old_rows]
        new_values = [row[index] for row in new_rows]
        scale = max((abs(v) for v in old_values if math.isfinite(v)), default=0.0)
        worst = max((abs(a - b) for a, b in zip(new_values, old_values) if math.isfinite(a - b)), default=0.0)
        if any(math.isfinite(a) != math.isfinite(b) for a, b in zip(new_values, old_values)):
            out.append(SeriesDifference(name, column, math.inf, math.inf, "a value is finite in one run only"))
            continue
        out.append(SeriesDifference(name, column, worst / scale if scale > 0.0 else (0.0 if worst == 0.0 else
                                                                                       math.inf), worst))
    return out


def _environment_differences(recorded: dict, new: dict) -> list[str]:
    out = []
    for key in ("spacemissionstudio_version", "basilisk_version"):
        if recorded.get(key) != new.get(key):
            out.append(f"{key}: {recorded.get(key)} in the bundle, {new.get(key)} here")
    old_deps, new_deps = recorded.get("dependency_versions", {}), new.get("dependency_versions", {})
    for key in sorted(set(old_deps) | set(new_deps)):
        if old_deps.get(key) != new_deps.get(key):
            note = (" (Basilisk's sensor noise differs between C++ standard libraries, so noisy sensor outputs "
                    "are expected to differ)" if key == "platform" else "")
            out.append(f"{key}: {old_deps.get(key)} in the bundle, {new_deps.get(key)} here{note}")
    old_files, new_files = recorded.get("data_files", {}), new.get("data_files", {})
    for key in sorted(set(old_files) | set(new_files)):
        old_sha, new_sha = old_files.get(key, {}).get("sha256"), new_files.get(key, {}).get("sha256")
        if old_sha != new_sha:
            out.append(f"data file {key}: SHA-256 {str(old_sha)[:12]}... in the bundle, {str(new_sha)[:12]}... here")
    return out


def reproduce(bundle, out_dir, rtol: float = DEFAULT_RTOL, allow_scripts: bool = False) -> Reproduction:
    """Run the bundle's scenario again into ``out_dir`` and compare. Raises
    :class:`BundleError` for a bundle that does not check out, and lets a
    failed run's exception through."""
    from .engine.events import extract_events
    from .engine.results import output_path
    from .engine.service import SimulationService
    from .schema.command import runs_sequence
    from .schema.scenario import scenario_text

    bundle, out_dir = Path(bundle), Path(out_dir)
    if out_dir.resolve() == bundle.resolve():
        raise BundleError("--out-dir must not be the bundle itself: the new run would overwrite what it is "
                          "compared with")
    manifest = read_manifest(bundle)
    try:
        recorded = json.loads((bundle / "provenance.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BundleError(f"{bundle / 'provenance.json'}: could not be read ({exc})") from None
    scenario, substitutions = bundled_scenario(bundle, manifest)
    _use_bundled_space_weather(scenario, bundle, manifest, recorded.get("data_files", {}), substitutions)

    service = SimulationService(scenario)
    if runs_sequence(scenario.mission_sequence):
        from .engine.mission_engine import MissionEngine

        result, _summary = MissionEngine(scenario, service=service, allow_scripts=allow_scripts).run()
    else:
        result = service.run()
    out_dir.mkdir(parents=True, exist_ok=True)
    result.export_csv(out_dir)
    output_path(out_dir, SCENARIO_AS_RUN).write_text(scenario_text(scenario), encoding="utf-8")

    report = Reproduction(bundle, out_dir, rtol, substitutions=substitutions, run_warnings=list(result.warnings))
    found = []
    for old in sorted(bundle.glob("*.csv")):
        if old.name in NOT_SERIES:
            continue
        new = out_dir / old.name
        if not new.is_file():
            report.failed.append(SeriesDifference(old.stem, "*", math.inf, math.inf, "not in the new run"))
            continue
        found += compare_series(old, new, old.stem)
        report.series_compared += 1
    extra = sorted({p.stem for p in out_dir.glob("*.csv")} - {p.stem for p in bundle.glob("*.csv")})
    report.failed += [SeriesDifference(name, "*", math.inf, math.inf, "not in the bundle") for name in extra]
    found.sort(key=lambda d: -d.relative)
    report.worst = found[:10]
    report.failed = [d for d in found if d.relative > rtol] + report.failed
    old_events = bundle / "events.csv"
    new_count = len(extract_events(result))
    old_count = max(0, sum(1 for _ in old_events.open(encoding="utf-8")) - 1) if old_events.is_file() else 0
    if old_count != new_count:
        report.differences.append(f"events: {old_count} in the bundle, {new_count} in the new run")
    new_record = result.provenance_record() if result.provenance is not None else {}
    report.differences += _environment_differences(recorded, new_record)
    return report
