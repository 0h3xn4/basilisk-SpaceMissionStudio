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
"""Project configuration files (transparency audit, Phase 3b): YAML, with
the parameters a project changes under ``parameters``::

    format: 1
    parameters:
      propellant_budget.cam_count_factor: 3.0   # [-] our own CAM statistics

A scenario names its file in ``config_file`` (relative to the scenario
file's folder); no file is read that a scenario does not name.
:data:`DEFAULTS_FILE` lists every parameter with its default, unit, source
and limits, each line commented out: a copy of it changes nothing until a
line is uncommented.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .registry import ConfigError, Configuration, checked_overrides, parameters

FORMAT = 1
DEFAULTS_FILE = Path(__file__).resolve().parent / "defaults.yaml"
MAX_FILE_BYTES = 1_000_000  # a configuration is a few kilobytes; a larger file is not one


def read(path) -> Configuration:
    """The configuration in ``path``, every value checked against the
    registry; :class:`ConfigError` naming the file and what is wrong."""
    import yaml

    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"configuration {path}: could not be read ({exc.strerror or exc})") from None
    if len(data) > MAX_FILE_BYTES:
        raise ConfigError(f"configuration {path}: larger than {MAX_FILE_BYTES // 1000} kB: not a configuration file")
    try:
        content = yaml.safe_load(data.decode("utf-8")) or {}
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"configuration {path}: not valid YAML ({exc})") from None
    if not isinstance(content, dict):
        raise ConfigError(f"configuration {path}: a mapping with 'format' and 'parameters' is expected")
    unknown = sorted(set(content) - {"format", "parameters"})
    if unknown:
        raise ConfigError(f"configuration {path}: unknown key(s) {', '.join(map(str, unknown))} (only 'format' and "
                          "'parameters')")
    if content.get("format", FORMAT) != FORMAT:
        raise ConfigError(f"configuration {path}: format {content.get('format')!r}, this version reads {FORMAT}")
    values = content.get("parameters") or {}
    if not isinstance(values, dict):
        raise ConfigError(f"configuration {path}: 'parameters' must map parameter names to values")
    return Configuration(checked_overrides(values, f"configuration {path}"),
                         {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest()})


def resolve_path(config_file: str, base_dir) -> Path:
    path = Path(config_file).expanduser()
    return path if path.is_absolute() or base_dir is None else Path(base_dir) / path


def attach(scenario, base_dir) -> None:
    """Set ``scenario.configuration`` from the file its ``config_file``
    names (relative to ``base_dir``, the scenario file's folder), or to
    None when it names none. A file that cannot be used sets the
    configuration's ``error``: the scenario then does not validate, and
    nothing is run with a configuration other than the one named."""
    if not scenario.config_file:
        scenario.configuration = None
        return
    if base_dir is None and not Path(scenario.config_file).expanduser().is_absolute():
        scenario.configuration = Configuration(error=f"{scenario.config_file} is relative to the scenario file's "
                                                     "folder: save the scenario first, or give an absolute path")
        return
    try:
        scenario.configuration = read(resolve_path(scenario.config_file, base_dir))
    except ConfigError as exc:
        scenario.configuration = Configuration(error=str(exc))


def format_value(value) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(format_value(v) for v in value) + "]"
    return repr(value) if isinstance(value, float) else str(value)


def defaults_yaml() -> str:
    """The text of :data:`DEFAULTS_FILE`: every parameter, commented out,
    by area, with what it controls, its source and its limits."""
    lines = ["# SpaceMissionStudio parameters and their defaults (generated by",
             "# scripts/build_config_defaults.py from spacemissionstudio/config/parameters.py).",
             "#",
             "# To change a parameter for a project: copy this file next to the scenario,",
             "# uncomment the lines to change and set the values, and name the file in the",
             "# scenario's \"config_file\". Each value is checked against the limits given.",
             "# 'spacemissionstudio assumptions scenario.json' lists the values in effect.",
             "",
             f"format: {FORMAT}",
             "parameters:"]
    area = None
    for parameter in parameters():
        if parameter.area != area:
            area = parameter.area
            lines += ["", f"  # -- {area} " + "-" * max(0, 70 - len(area))]
        limits = " to ".join(f"{bound:g}" for bound in (parameter.minimum, parameter.maximum) if bound is not None)
        if parameter.minimum is not None and parameter.maximum is None:
            limits = f"at least {parameter.minimum:g}"
        elif parameter.minimum is None and parameter.maximum is not None:
            limits = f"at most {parameter.maximum:g}"
        lines.append("")
        lines.append(f"  # {parameter.controls}")
        lines.append(f"  # Source: {parameter.source}." + (f" {parameter.rationale}" if parameter.rationale else ""))
        if parameter.choices is not None:
            lines.append(f"  # One of: {', '.join(f'{c:g}' for c in parameter.choices)} {parameter.unit}")
        elif limits:
            lines.append(f"  # Limits: {limits} {parameter.unit}" + (f", {parameter.kind}" if parameter.kind != "number"
                                                                    else ""))
        lines.append(f"  # {parameter.name}: {format_value(parameter.default)}  # {parameter.unit}")
    return "\n".join(lines) + "\n"
