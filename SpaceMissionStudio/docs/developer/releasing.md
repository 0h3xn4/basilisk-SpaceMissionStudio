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

**The release files are built in CI.** Pushing the tag (section 6) starts
the workflow `.github/workflows/spacemissionstudio-release.yml` ("SpaceMissionStudio
release"). On GitHub's runners it:

- checks that the tag matches the version files and that the CHANGELOG
  has a section for the version;
- builds the wheel, sdist and `.deb` on Linux, installs the `.deb` with
  `apt` and runs the installed tool: version, support data, every
  template validated, template 01 run and the main window opened;
- builds the Windows setup program around that wheel, installs it
  silently and runs it the same way;
- on an Apple-silicon Mac, installs that wheel with `packaging/install.sh`
  and Basilisk's wheel from PyPI, and runs it. macOS has no installer;
- writes `SHA256SUMS-linux` and `SHA256SUMS-windows`, checks every file
  against them and attaches all of them to the tag's release. A release
  that does not exist yet is created as a draft with the CHANGELOG
  section as its notes. An existing release keeps its notes unless they
  are empty, and its files are replaced.

Actions > "SpaceMissionStudio release" > Run workflow, with the tag, runs
it again for an existing tag. A pull request that changes the workflow
runs the build and install jobs for its own commit and attaches nothing.

To check a build locally before tagging, from the `SpaceMissionStudio`
folder:

| Artifact | Command | Output |
|---|---|---|
| Wheel (any platform) | `packaging/build_wheel.sh` (Windows: `packaging\build_wheel.ps1`) | `dist/spacemissionstudio-X.Y.Z-py3-none-any.whl` |
| Linux installer | `packaging/build_deb.sh` | `dist/spacemissionstudio_X.Y.Z_all.deb` |
| Windows installer | Inno Setup on Windows only: the release workflow above, or Actions > "SpaceMissionStudio Windows installer" > Run workflow | `spacemissionstudio-X.Y.Z-setup.exe` |

[`packaging/README.md`](../../packaging/README.md) explains each one and
what has been verified where.

## 6. Publish

- Tag the release commit (`develop` after the release pull request is
  merged) and push the tag:

  ```bash
  git tag -a spacemissionstudio-vX.Y.Z <commit> -m "SpaceMissionStudio X.Y.Z"
  git push origin spacemissionstudio-vX.Y.Z
  ```

  The release workflow (section 5) builds, checks and attaches the files
  to a draft release titled "SpaceMissionStudio X.Y.Z". If the Linux or
  Windows job fails, nothing is attached; fix the cause and run the
  workflow again for the tag. macOS produces no file, so a macOS check
  that fails, or that GitHub cannot start for lack of a runner, does not
  hold the release back: the notes say so.
- Read the draft on
  <https://github.com/0h3xn4/basilisk-SpaceMissionStudio/releases>: the
  six files, and the notes, which say which platform has which file and
  name the workflow run that installed them. Then publish it.
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
(`packaging/README.md`). On 2026-10-20 the user chose to release from
`develop`, which by then held the first step of the UI overhaul (M1, the
new look), so 1.1.0 includes it: its CHANGELOG section and SRelD issue 8
say so, and the files were built and installed again. A first tag, made
before those records on commit `c931ccd4d`, is replaced by one on the
merge of that pull request. Merging, tagging (`spacemissionstudio-v1.1.0`)
and publishing are the user's.

---

**Next:** [Syncing with upstream Basilisk](upstream-sync.md) ·
[Developer guide](README.md)
