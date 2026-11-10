#
#  SpaceMissionStudio
#
#  Copyright (c) 2026 0h3xn4 (https://github.com/0h3xn4)
#
#  Licensed under the EUPL
#
#  SPDX-License-Identifier: EUPL-1.2
#
#  The European Union Public Licence v. 1.2 is in the files LICENSE
#  (English) and LICENSE.de (German) of the SpaceMissionStudio folder and
#  of every package. Third-party components, each under its own licence,
#  are listed in THIRD_PARTY_NOTICES.
#
#
#
#
"""Opening an IDM-CIC model file (``.idm``): a ZIP archive whose
``model.xml`` holds the model. Only that entry is read; the other
entries (pictures, managed data, external files) are listed, never
extracted. Entry names may use ``\\`` as the separator and any case."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .errors import IdmError

MODEL_ENTRY = "model.xml"
#: [bytes] The largest file and model.xml read: far above the largest
#: model seen, low enough that a damaged or hostile archive cannot
#: exhaust memory.
MAX_FILE_BYTES = 512 * 1024 * 1024  # [bytes]
MAX_MODEL_BYTES = 1024 * 1024 * 1024  # [bytes] model.xml once uncompressed


@dataclass
class IdmArchive:
    """An opened ``.idm`` file: its path, SHA-256, the text of its
    ``model.xml`` and the names of its other entries (normalised to
    ``/`` separators)."""

    path: Path
    sha256: str
    model_xml: str
    entries: list


def normalised(name: str) -> str:
    """An entry name with ``/`` separators and no leading ``./`` or ``/``."""
    name = name.replace("\\", "/")
    while name.startswith(("./", "/")):
        name = name[2:] if name.startswith("./") else name[1:]
    return name


def read(path) -> IdmArchive:
    """Open ``path`` and read its ``model.xml`` (UTF-8, with or without a
    byte-order mark). Raises :class:`IdmError` with the reason when the
    file cannot be read, is not a ZIP archive or has no ``model.xml``."""
    path = Path(path).expanduser()
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise IdmError(f"could not read {path}: {exc.strerror or exc}") from None
    if not path.is_file():
        raise IdmError(f"{path} is not a file")
    if size > MAX_FILE_BYTES:
        raise IdmError(f"{path} is {size / 2**20:.0f} MiB, more than the {MAX_FILE_BYTES // 2**20} MiB an IDM-CIC "
                       "model may have here")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise IdmError(f"could not read {path}: {exc.strerror or exc}") from None
    sha256 = hashlib.sha256(data).hexdigest()
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise IdmError(f"{path} is not an IDM-CIC model: it is not a ZIP archive ({exc})") from None
    with archive:
        infos = {normalised(info.filename): info for info in archive.infolist() if not info.is_dir()}
        model = next((info for name, info in infos.items() if name.lower() == MODEL_ENTRY), None)
        if model is None:
            raise IdmError(f"{path} is not an IDM-CIC model: it has no {MODEL_ENTRY}")
        if model.file_size > MAX_MODEL_BYTES:
            raise IdmError(f"{path}: {MODEL_ENTRY} is {model.file_size / 2**20:.0f} MiB uncompressed, more than "
                           f"the {MAX_MODEL_BYTES // 2**20} MiB read here")
        try:
            with archive.open(model) as stream:
                raw = stream.read(MAX_MODEL_BYTES + 1)
        except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError) as exc:
            raise IdmError(f"{path}: could not read {MODEL_ENTRY}: {exc}") from None
    if len(raw) > MAX_MODEL_BYTES:
        raise IdmError(f"{path}: {MODEL_ENTRY} is larger than the {MAX_MODEL_BYTES // 2**20} MiB read here")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IdmError(f"{path}: {MODEL_ENTRY} is not UTF-8 text ({exc})") from None
    others = sorted(name for name in infos if name.lower() != MODEL_ENTRY)
    return IdmArchive(path.resolve(), sha256, text, others)
