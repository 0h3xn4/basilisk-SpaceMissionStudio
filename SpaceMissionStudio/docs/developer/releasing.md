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
| Windows installer | After the release is published (it bundles the release's wheel): Actions > "SpaceMissionStudio Windows installer" > Run workflow, with the release tag and "attach" ticked. It builds, installs and runs the program on a Windows runner, then attaches it to the release | `spacemissionstudio-X.Y.Z-setup.exe` and `SHA256SUMS-windows` on the release (and in the run's artifact) |

[`packaging/README.md`](../../packaging/README.md) explains each one and
what has been verified where. Record a SHA-256 checksum of each artifact:

```bash
cd dist && sha256sum *.whl *.tar.gz *.deb > SHA256SUMS-linux
```

## 6. Publish

- Create a GitHub release on <https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases/new>:
  a new tag on the release commit (`develop` after the release pull
  request is merged), the title "SpaceMissionStudio X.Y.Z", the
  CHANGELOG section as the notes, and the wheel, sdist, `.deb` and
  `SHA256SUMS-linux` attached. Say in the notes which platforms'
  installers were not run.
- Attach the Windows setup program with the installer workflow
  (section 5); it adds `SHA256SUMS-windows`.
- After publishing, download the assets from the release and run
  `sha256sum -c SHA256SUMS-linux` and `sha256sum -c SHA256SUMS-windows`.
- Update the records that name the release: the Software Release
  Document (status, baseline commit), `compliance/human_actions.md` H05,
  and the compliance assessments (then run `compliance/tools/build_matrix.py`).

**Tag name: use `spacemissionstudio-vX.Y.Z`, not `vX.Y.Z`.** This fork
keeps Basilisk's own workflows, and a `v*` tag starts two of them:
`publish-container.yml`, which pushes a *Basilisk* image tagged with the
version and `latest` to this repository's GHCR, and `publish-wheels.yml`,
which builds Basilisk wheels and tries to upload them to PyPI. Both ran
for a `v3.0.0` tag of the earlier numbering: PyPI refused the upload (no trusted publisher for
the fork), and the container run was cancelled after its arm64 image had
been pushed. A `spacemissionstudio-v*` tag starts neither. The
SpaceMissionStudio workflow also runs on a tag push, on the commit
`develop` already passed.

**Releases.** The tool was renewed on 2026-10-14 and its numbering
restarted at 1.0.0; the releases and tags of the earlier numbering
(1.0.0 to 3.0.0) were removed. 1.0.0 is a Linux release: the wheel,
sdist, `.deb` and `SHA256SUMS-linux`, without the Windows setup program
(SRelD K-14). `pip` and `apt` see 1.0.0 as older than the earlier
3.0.0, so the release notes tell users of that build to remove it first.
It was published on 2026-10-14: tag `spacemissionstudio-v1.0.0` on
`f288e0c73`, and GitHub's SHA-256 digest of each attached file equals
the file built and installed for it (SRelD, status).

1.1.0 was prepared on 2026-10-19 by the same checklist, again for Linux,
and rebuilt on 2026-10-20 with the fix of SRelD K-18:
the version set in the three files, the CHANGELOG section, the SRelD
(issue 6), the build, and the `.deb` installed as an upgrade over 1.0.0
(`packaging/README.md`). Merging, tagging (`spacemissionstudio-v1.1.0`)
and publishing are the user's.

---

**Next:** [Syncing with upstream Basilisk](upstream-sync.md) ·
[Developer guide](README.md)
