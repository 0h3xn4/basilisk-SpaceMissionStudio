# Licence texts for Qt and PySide6

The PySide6, PySide6_Essentials, PySide6_Addons and shiboken6 packages carry
**no licence text** in their `.dist-info` folders or elsewhere (checked in the
unpacked 6.11.2 wheels, 2026-11-09), although they contain Qt, which is
LGPL-3.0. The installers redistribute them, so the bundle adds:

* `LGPL-3.0-only.txt`: the SPDX list's text,
  <https://raw.githubusercontent.com/spdx/license-list-data/main/text/LGPL-3.0-only.txt>
  (read 2026-11-09, SHA-256 `996af0513df21f7496288951c41428a03c174e9e4a9d63665c57d670f845ccb1`).
  It already includes the GPL-3.0 text that the LGPL refers to.
* `QT_NOTICE.txt`: a factual notice (draft, waiting for approval).

`bundle_python.py` copies both into `licenses/` of the bundled Python.
