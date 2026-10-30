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
import os
import re
from pathlib import Path

from . import registry
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


def new_file(path) -> Path:
    """Write :data:`DEFAULTS_FILE`'s text to ``path``, a new project file
    that changes nothing yet; refused when ``path`` exists."""
    path = Path(path)
    if path.exists():
        raise ConfigError(f"configuration {path}: already exists")
    _write(path, defaults_yaml())
    return path


def set_value(path, name: str, value) -> None:
    """Set ``name`` to ``value`` in the project file ``path``, editing only
    that parameter's line so every comment stays: its line is replaced (and
    uncommented, for a line of the defaults file), or added at the end of
    ``parameters``. The value is checked first, and the file read back
    after; on any error :class:`ConfigError` and the file is left as it was."""
    checked = registry.parameter(name).check(value)
    unit = registry.parameter(name).unit
    _edit(path, name, lambda indent, comment: f"{indent}{name}: {format_value(checked)}{comment or f'  # {unit}'}")


def reset_value(path, name: str) -> None:
    """Back to the default: ``name``'s line in ``path`` commented out, as
    in the defaults file (nothing to do when no line sets it)."""
    default = registry.parameter(name).default
    _edit(path, name, lambda indent, comment: f"{indent}# {name}: {format_value(default)}{comment}", add=False)


def _edit(path, name: str, line_for, add: bool = True) -> None:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"configuration {path}: could not be read ({exc.strerror or exc})") from None
    lines = text.splitlines()
    pattern = re.compile(rf"^(\s*)(#\s*)?{re.escape(name)}\s*:[^#]*?(\s+#.*)?$")
    matches = [(i, m) for i, line in enumerate(lines) if (m := pattern.match(line))]
    chosen = next(((i, m) for i, m in matches if not m.group(2)), matches[0] if matches else None)
    if chosen is not None:
        index, match = chosen
        if match.group(2) and not add:
            return  # commented out already: the default
        lines[index] = line_for(match.group(1) or "  ", match.group(3) or "")
    elif add:
        if not any(re.match(r"^parameters\s*:", line) for line in lines):
            lines.append("parameters:")
        lines.append(line_for("  ", ""))
    else:
        return
    edited = "\n".join(lines) + "\n"
    _write(path, edited)
    try:
        read(path)
    except ConfigError:
        _write(path, text)  # the edit made the file unreadable: put it back
        raise


def _write(path: Path, text: str) -> None:
    """``text`` into ``path`` atomically: a reader never sees half a file."""
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
