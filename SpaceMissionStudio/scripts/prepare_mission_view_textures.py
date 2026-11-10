#
#  SpaceMissionStudio
#
#  Licensor: 0h3xn4 (https://github.com/0h3xn4)
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
"""Prepare the textures of Results › 3D View from NASA's originals.

Sources (NASA Goddard Space Flight Center Scientific Visualization
Studio, svs.gsfc.nasa.gov; "All of our content is in the public domain
(unless otherwise noted)", https://svs.gsfc.nasa.gov/help/, read
2026-11-10), each checked against the SHA-256 below before use:

* **Earth:** SVS 2915, "Blue Marble - A Seamless Image Mosaic of the
  Earth", ``bluemarble-west-4096.png`` (longitude -180 to 0 degrees) and
  ``bluemarble-east-4096.png`` (0 to 180 degrees), 4096 x 4096 each,
  equirectangular, north up. Credit: NASA Goddard Space Flight Center
  Scientific Visualization Studio; Blue Marble data courtesy of Reto
  Stockli (NASA/GSFC).
* **Stars:** SVS 4851, "Deep Star Maps 2020", ``starmap_2020_4k.exr``
  (4096 x 2048, half-float linear RGB, celestial coordinates, centred on
  right ascension 0 h, right ascension increasing to the left). Credit:
  NASA/Goddard Space Flight Center Scientific Visualization Studio; star
  data from Hipparcos, Tycho-2, UCAC3 and Gaia DR2 (ESA/Gaia/DPAC).

Processing (``spacemissionstudio/gui/assets/mission_view/``):

* ``earth_day_4k.jpg``: west and east side by side (8192 x 4096,
  longitude -180 to 180 degrees left to right), resized to 4096 x 2048
  (Lanczos), JPEG quality 88; ``earth_day_2k.jpg``: the same at
  2048 x 1024, quality 85 (the 3D View's reduced quality).
* ``stars_4k.jpg``: the linear values times 1.0, clipped to [0, 1],
  encoded with the sRGB transfer curve, JPEG quality 85;
  ``stars_2k.jpg``: the linear values averaged over 2 x 2 pixels first,
  then the same, 2048 x 1024. The orientation is NASA's (right ascension
  0 h in the middle, increasing to the left).

Tools, used here only, never at run time: Pillow (resizing, JPEG) and the
OpenEXR Python bindings (reading the EXR). Run from the SpaceMissionStudio
folder::

    python scripts/prepare_mission_view_textures.py --sources DIR [--download]

``--download`` fetches the three originals into ``DIR`` first (about
58 MB). The SHA-256 of every output is printed;
``docs/THIRD_PARTY_ASSETS.md`` records them (Pillow 13.0.0 and OpenEXR 3.5.3
made the committed files).
"""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "spacemissionstudio" / "gui" / "assets" / "mission_view"
_SVS = "https://svs.gsfc.nasa.gov/vis/a000000"
SOURCES = {
    "bluemarble-west-4096.png": (f"{_SVS}/a002900/a002915/bluemarble-west-4096.png",
                                 "c9fab796a66645bf03537522d9c152bd8af9ef97081de177b6fee2cd25a945d7"),
    "bluemarble-east-4096.png": (f"{_SVS}/a002900/a002915/bluemarble-east-4096.png",
                                 "374c94c0d5060044c28fec4c72348cd15f5c06e039fc7a876cc241a0bd80798a"),
    "starmap_2020_4k.exr": (f"{_SVS}/a004800/a004851/starmap_2020_4k.exr",
                            "69b841cd048c2ef35543eb1c5819b322530e78aa4b0cab97ec1de3ef56a4ddcd"),
}
STAR_EXPOSURE = 1.0  # [-] linear scale before the sRGB curve


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(sources: Path) -> None:
    sources.mkdir(parents=True, exist_ok=True)
    for name, (url, _digest) in SOURCES.items():
        if not (sources / name).is_file():
            print(f"downloading {url}")
            urllib.request.urlretrieve(url, sources / name)  # noqa: S310 -- a fixed https URL


def verified(sources: Path, name: str) -> Path:
    path = sources / name
    digest = sha256(path)
    if digest != SOURCES[name][1]:
        raise SystemExit(f"{name}: SHA-256 {digest} is not the recorded {SOURCES[name][1]}")
    return path


def earth(sources: Path) -> list[Path]:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    west = Image.open(verified(sources, "bluemarble-west-4096.png")).convert("RGB")
    east = Image.open(verified(sources, "bluemarble-east-4096.png")).convert("RGB")
    whole = Image.new("RGB", (west.width + east.width, west.height))
    whole.paste(west, (0, 0))
    whole.paste(east, (west.width, 0))
    out = []
    for name, size, quality in (("earth_day_4k.jpg", (4096, 2048), 88), ("earth_day_2k.jpg", (2048, 1024), 85)):
        whole.resize(size, Image.Resampling.LANCZOS).save(ASSETS / name, "JPEG", quality=quality, optimize=True)
        out.append(ASSETS / name)
    return out


def _srgb(linear):
    import numpy as np

    linear = np.clip(linear * STAR_EXPOSURE, 0.0, 1.0)
    encoded = np.where(linear <= 0.0031308, 12.92 * linear, 1.055 * np.power(linear, 1.0 / 2.4) - 0.055)
    return np.round(encoded * 255.0).astype(np.uint8)


def stars(sources: Path) -> list[Path]:
    import numpy as np
    import OpenEXR
    from PIL import Image

    with OpenEXR.File(str(verified(sources, "starmap_2020_4k.exr"))) as exr:
        linear = np.asarray(exr.channels()["RGB"].pixels, dtype=np.float64)  # (2048, 4096, 3)
    half = linear.reshape(linear.shape[0] // 2, 2, linear.shape[1] // 2, 2, 3).mean(axis=(1, 3))
    out = []
    for name, pixels in (("stars_4k.jpg", linear), ("stars_2k.jpg", half)):
        Image.fromarray(_srgb(pixels), "RGB").save(ASSETS / name, "JPEG", quality=85, optimize=True)
        out.append(ASSETS / name)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sources", type=Path, required=True, help="folder holding NASA's original files")
    parser.add_argument("--download", action="store_true", help="download the originals into --sources first")
    args = parser.parse_args(argv)
    if args.download:
        fetch(args.sources)
    for name in SOURCES:
        print(f"{verified(args.sources, name).name}: SHA-256 checked")
    ASSETS.mkdir(parents=True, exist_ok=True)
    for path in earth(args.sources) + stars(args.sources):
        print(f"{sha256(path)}  {path.name} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
