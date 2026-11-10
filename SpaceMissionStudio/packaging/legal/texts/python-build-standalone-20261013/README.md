# Licence texts of the libraries inside the bundled Python

The installers bundle CPython from python-build-standalone release 20261013
(`cpython-3.14.8+20261013`, `install_only_stripped`). That build links
OpenSSL, SQLite, libffi, expat, Tcl/Tk and other libraries into its
extension modules, but the `install_only` archives carry no licence texts
for them.

The `LICENSE.*.txt` files here (except `LICENSE.zstd.txt`) are the files in
the `licenses/` folder of that release's full archive,
`cpython-3.14.8+20261013-x86_64-unknown-linux-gnu-pgo+lto-full.tar.zst`
(SHA-256 `6ea47477c59736c51914214a1608cc4fceb37a238e5b0ba6bb351bb665d6aca6`,
the value in the release's `SHA256SUMS`; read 2026-11-09). They are unchanged, except that `LICENSE.libX11.txt` lost one empty line at its end (the repository's end-of-file check).
`bundle_python.py` copies them into `licenses/` of the bundled Python.

`LICENSE.zstd.txt` is the file `LICENSE` of the zstd project,
<https://raw.githubusercontent.com/facebook/zstd/dev/LICENSE>, read
2026-11-09. Python 3.14's `_zstd` module links libzstd, and the release's
`licenses/` folder has no text for it.

The text of OpenSSL 1.1 is not included: the 3.14 build links OpenSSL 3.

Since the owner's decision D9 the bundle leaves out `_tkinter` and `_dbm`, so
`bundle_python.py` does not copy the texts of Tcl/Tk, Tix, the X11 client
libraries and Berkeley DB (`PRUNED_LIBRARY_TEXTS`); they stay here in case
those modules return.
