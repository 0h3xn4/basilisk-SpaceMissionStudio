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
- ``--enable-unsafe-swiftshader``: Results › 3D View draws with WebGL.
  Where no graphics driver can start a WebGL context (the Windows test
  machines of CI, some virtual machines and remote desktops), Chromium
  falls back to its software renderer, SwiftShader, only with this flag;
  without it the view could not draw at all. Chromium calls the fallback
  "unsafe" because SwiftShader exposed to web pages from the internet is
  a larger attack surface; the app's views load only the app's own files
  (:func:`guard_profile`), so that does not apply. A machine with a
  working GPU uses it as before.
- ``--disable-domain-blocking-for-3d-apis``: after a graphics context is
  lost (a driver reset, or the software renderer's GPU process restarting),
  Chromium blocks WebGL for that page's origin, and every page of the app
  shares one (``file://``), so the 3D views stayed empty until the app was
  restarted (seen on the Windows CI job). The blocking protects against
  untrusted sites; the app's views load only its own files.
- ``--no-sandbox``, only when running as root: Chromium will not start its
  renderer as root otherwise (its sandbox works by dropping privileges).

- ``--disable-background-networking``, ``--disable-component-update``,
  ``--disable-domain-reliability``, ``--no-pings``,
  ``--dns-prefetch-disable``: none of Chromium's own background requests
  (component and safe-browsing updates, reliability reports, link
  prefetching), which the views do not need (``docs/reference/network.md``).

A user who sets ``QTWEBENGINE_CHROMIUM_FLAGS`` themselves keeps exactly
theirs. The views load only pages the app writes itself, never remote
content, and :func:`guard_profile` makes that a rule: a request for
anything but the app's own files is blocked and logged
(``network.log``).
"""

from __future__ import annotations

import os


NO_BACKGROUND_NETWORK = ("--disable-background-networking", "--disable-component-update",
                         "--disable-domain-reliability", "--no-pings", "--dns-prefetch-disable")
LOCAL_SCHEMES = ("file", "data", "qrc", "blob", "about")
_interceptors: list = []  # kept alive as long as the profile


def guard_profile(profile=None) -> None:
    """Block every request a web view makes for anything but the app's own
    files (:data:`LOCAL_SCHEMES`). Once per profile; the views use the
    default one."""
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineUrlRequestInterceptor

    profile = profile or QWebEngineProfile.defaultProfile()
    if any(owner is profile for owner, _ in _interceptors):
        return

    class _LocalOnly(QWebEngineUrlRequestInterceptor):
        def interceptRequest(self, info) -> None:  # noqa: N802 -- Qt's name
            url = info.requestUrl()
            if url.scheme().lower() not in LOCAL_SCHEMES:
                info.block(True)
                from .. import network

                network._log("refused", "web view", url.toString())

    interceptor = _LocalOnly()
    profile.setUrlRequestInterceptor(interceptor)
    _interceptors.append((profile, interceptor))


def configure() -> None:
    """Set the flags (see the module docstring), unless the user did."""
    if "QTWEBENGINE_CHROMIUM_FLAGS" in os.environ:
        return
    flags = ["--ignore-gpu-blocklist", "--enable-unsafe-swiftshader", "--disable-domain-blocking-for-3d-apis",
             *NO_BACKGROUND_NETWORK]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        flags.append("--no-sandbox")
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(flags)


configure()
