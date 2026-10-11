# Releasing

How to cut a SpaceMissionStudio release. The formal procedure is in the
Software Maintenance Plan,
[`compliance/docs/SMP.md`](../../compliance/docs/SMP.md) section 9; this
page is the checklist.

**Contents**

1. [Before you start](#1-before-you-start)
2. [Set the version](#2-set-the-version)
3. [Update the records](#3-update-the-records)
4. [Check](#4-check)
5. [Build](#5-build)
6. [Publish](#6-publish)

## 1. Before you start

- The release branch has green CI on every job (`test` and both
  `platforms` jobs).
- The bundled space weather is current: download the latest CelesTrak
  `SW-All.txt` and NASA MSFC tables into
  `spacemissionstudio/data/spaceweather/` (see the `README.md` there),
  then run the tests. The forecast part ages within months.
- If the release moves to a new Basilisk version, requalify it first
  (SMP section 8, "Requalify a new Basilisk release"): run the full suite
  and the validation against it before changing
  `QUALIFIED_BASILISK_VERSION` in `spacemissionstudio/dependencies.py`.

## 2. Set the version

The version (semantic versioning) is in three places. Change all three
to the same value:

| File | Line |
|---|---|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `spacemissionstudio/__init__.py` | `__version__ = "X.Y.Z"` |
| `packaging/windows/spacemissionstudio.iss` | `#define MyAppVersion "X.Y.Z"` |

The `.deb` reads `spacemissionstudio.__version__`, so it needs no change.

## 3. Update the records

- [`CHANGELOG.md`](../../CHANGELOG.md): move the "Unreleased" entries
  under a new `## X.Y.Z (date)` heading.
- [`HISTORY.md`](../../HISTORY.md): a short entry for the release.
- The Software Release Document,
  [`compliance/docs/SRelD.md`](../../compliance/docs/SRelD.md): the
  release's contents, known problems and dependency versions.
- Regenerate the generated documents (see the
  [developer guide](README.md#4-generated-files-regenerate-never-edit)).

## 4. Check

```bash
cd SpaceMissionStudio
python -m ruff check spacemissionstudio tests scripts compliance/tools
QT_QPA_PLATFORM=offscreen python -m pytest tests -q -n auto
for t in check_drds build_icd_schema build_sdd_components build_test_specs build_traceability; do
  python compliance/tools/$t.py
done
git diff --exit-code -- compliance/docs
```

## 5. Build

From the `SpaceMissionStudio` folder:

| Artifact | Command | Output |
|---|---|---|
| Wheel (any platform) | `packaging/build_wheel.sh` (Windows: `packaging\build_wheel.ps1`) | `dist/spacemissionstudio-X.Y.Z-py3-none-any.whl` |
| Linux installer | `packaging/build_deb.sh` | `dist/spacemissionstudio_X.Y.Z_all.deb` |
| Windows installer | Compile `packaging/windows/spacemissionstudio.iss` with [Inno Setup](https://jrsoftware.org/isinfo.php) | `spacemissionstudio-X.Y.Z-setup.exe` |

[`packaging/README.md`](../../packaging/README.md) explains each one and
what has been verified where. Record a SHA-256 checksum of each artifact:

```bash
sha256sum dist/*.whl dist/*.deb > SHA256SUMS
```

## 6. Publish

- Tag the release commit: `git tag -a spacemissionstudio-vX.Y.Z -m "SpaceMissionStudio X.Y.Z"`,
  then `git push origin spacemissionstudio-vX.Y.Z`.
- Create a GitHub release from the tag, attach the artifacts and
  `SHA256SUMS`, and paste the CHANGELOG section as the notes.

No release tag exists yet for the tool; the versions so far (1.0.0,
1.1.0, 2.0.0) were set in the files only. The tag name above is a
proposal that keeps the tool's tags apart from Basilisk's own `vX.Y.Z`
tags in this fork.

---

**Next:** [Syncing with upstream Basilisk](upstream-sync.md) ·
[Developer guide](README.md)
