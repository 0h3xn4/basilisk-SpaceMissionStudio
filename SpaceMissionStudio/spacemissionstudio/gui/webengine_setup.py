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

"""The Chromium flags the app's web views (the Results tab's plots, the 3D
model view) need. Qt WebEngine reads ``QTWEBENGINE_CHROMIUM_FLAGS`` once,
when ``PySide6.QtWebEngineWidgets`` is first imported, so every module
that imports it imports this one first: importing it sets the flags.

- ``--ignore-gpu-blocklist``: the 3D model view draws with WebGL. Without
  a usable GPU (a virtual machine, a remote desktop, an old driver)
  Chromium falls back to software rendering, which it then blocklists for
  WebGL, and the view shows "WebGL is not supported". Found in this
  project's own GPU-less test environment; with the flag the same view
  rendered. A machine with a working GPU uses it as before.
- ``--no-sandbox``, only when running as root: Chromium will not start its
  renderer as root otherwise (its sandbox works by dropping privileges).

A user who sets ``QTWEBENGINE_CHROMIUM_FLAGS`` themselves keeps exactly
theirs. The views load only pages the app writes itself, never remote
content.
"""

from __future__ import annotations

import os


def configure() -> None:
    """Set the flags (see the module docstring), unless the user did."""
    if "QTWEBENGINE_CHROMIUM_FLAGS" in os.environ:
        return
    flags = ["--ignore-gpu-blocklist"]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        flags.append("--no-sandbox")
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)


configure()
