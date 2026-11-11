# Releasing

How to cut a SpaceMissionStudio release. The formal procedure is in the
Software Maintenance Plan,
[`compliance/docs/SMP.md`](../../compliance/docs/SMP.md) section 10.6; this
page is the checklist.

**Contents**

1. [Before you start](#1-before-you-start)
2. [Set the version](#2-set-the-version)
3. [Update the records](#3-update-the-records)
4. [Check](#4-check)
5. [Build](#5-build)
6. [Publish](#6-publish)

## 1. Before you start

- The release branch has green CI on every job (`test` and the
  `platforms` job).
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
  under a new `## X.Y.Z (date)` heading. The release notes are built from
  this section (section 5), so write it for someone deciding whether to
  download:
  - start with one or two paragraphs that say what the release is for:
    they become the notes' summary;
  - then the list of changes, which becomes "What's new";
  - optionally, after the list, `### Who should update` and
    `### Known limits` (each runs to the next `###` heading): they get a
    section of their own, and the known limits follow the standing ones
    (the unsigned Windows setup, no installer for ARM Linux).
- [`HISTORY.md`](../../HISTORY.md): a short entry for the release.
- [`README.md`](../../README.md): the version badge and the "Version" and
  "Platforms" lines of its status section (they name the release).
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
- runs the SpaceMissionStudio workflow on the tagged commit (job
  `tests`): lint, the document checks, the whole test suite on Linux and
  Windows and pip-audit on every pinned package. Nothing is attached
  unless it passes;
- builds the wheel, sdist and the self-contained `.deb` (the bundled
  Python of `packaging/bundle_python.py`) on Linux, installs the `.deb`
  with the network cut off and runs the installed tool offline: version,
  support data, every template validated, template 01 run from the
  bundled kernels, the Earth orientation files found and the main window
  opened in Inter;
- builds the bundled Python on Windows, then the setup program around
  it, installs it silently and runs it the same way;
- takes each installer's software bill of materials
  (`SPACEMISSIONSTUDIO_SBOM.cdx.json`, written by `bundle_python.py`;
  every package with the file installed and its SHA-256) and attaches it
  beside the installer as `spacemissionstudio_X.Y.Z_amd64.cdx.json` and
  `spacemissionstudio-X.Y.Z-setup.cdx.json`;
- downloads the complete source of the Qt and PySide6 libraries the
  installers carry (`packaging/legal/qt-sources.json`), checked against
  the size and SHA-256 Qt publishes, with `SHA256SUMS-sources`, and signs
  a build provenance of every built file (Sigstore; `gh attestation
  verify <file> --repo 0h3xn4/basilisk_space-mission-studio`);
- writes `SHA256SUMS-linux` and `SHA256SUMS-windows` (the bills of
  materials included), checks every file against them and attaches all
  of them, and the source archives, to the tag's release. A release
  that does not exist yet is created as a draft. An existing release
  keeps its notes unless they are empty, and its files are replaced.
- writes the notes with `packaging/release_notes.py`, in a fixed layout:
  summary, who should update, downloads with their sizes, install or
  upgrade, how to check a download (with the installers' SHA-256), what's
  new, what the installers contain (the Python, Basilisk and PySide6
  versions and the bundled space weather, read from this checkout), how
  the files were checked (linking the run), and the known limits. The
  text comes from the CHANGELOG section (section 3); a release without
  one gets no notes and the job fails. To see the notes before tagging:
  `python3 packaging/release_notes.py --version X.Y.Z --files <folder
  with the four packages> --run-url <any URL>`.

Actions > "SpaceMissionStudio release" > Run workflow, with the tag, runs
it again for an existing tag. A pull request that changes the workflow
runs the tests, the build and the install jobs for its own commit and
attaches nothing.

To check a build locally before tagging, from the `SpaceMissionStudio`
folder:

| Artifact | Command | Output |
|---|---|---|
| Wheel (any platform) | `packaging/build_wheel.sh` (Windows: `packaging\build_wheel.ps1`) | `dist/spacemissionstudio-X.Y.Z-py3-none-any.whl` |
| Linux installer | `packaging/build_deb.sh` (about 8 minutes; downloads CPython, the packages and the support data) | `dist/spacemissionstudio_X.Y.Z_amd64.deb` |
| Windows installer | Windows only (`bundle_python.py --platform windows`, then Inno Setup): the release workflow above, or Actions > "SpaceMissionStudio Windows installer" > Run workflow | `spacemissionstudio-X.Y.Z-setup.exe` |

[`packaging/README.md`](../../packaging/README.md) explains each one and
what has been verified where.

## 6. Publish

- Check the commit first: Actions > "SpaceMissionStudio release check" >
  Run workflow, on `develop` (`.github/workflows/spacemissionstudio-release-check.yml`).
  It changes nothing. It fails unless CI passed on the commit at
  `develop`'s head, pip-audit finds no vulnerability that
  `packaging/audit-exceptions.txt` does not accept (today's advisories),
  the version files agree, the CHANGELOG's newest section is that version
  dated today, no Unreleased entries are left out, the tag does not exist
  yet and the notes render (`packaging/release_check.py`, which also runs
  locally). Its summary names the commit and gives the two commands
  below with it filled in. Tag that commit, once.
- Tag it, preferably with Actions > "SpaceMissionStudio tag release" >
  Run workflow, giving the version (`.github/workflows/spacemissionstudio-tag-release.yml`;
  the assistant can start it when asked to tag). It runs the release
  check above and stops on any failure; otherwise it tags exactly the
  commit the check passed and starts the release workflow for the tag
  (a tag pushed with a workflow's token starts no workflow by itself).
  If a tag ruleset (Settings > Rules > Rulesets) restricts creating
  tags, GitHub Actions needs to be on its bypass list. Or tag by hand:
- Tag the release commit (`develop` after the release pull request is
  merged) and push the tag:

  ```bash
  git tag -a spacemissionstudio-vX.Y.Z <commit> -m "SpaceMissionStudio X.Y.Z"
  git push origin spacemissionstudio-vX.Y.Z
  ```

  The release workflow (section 5) builds, checks and attaches the files
  to a draft release titled "SpaceMissionStudio X.Y.Z". If the tests, the
  Linux or the Windows job fail, nothing is attached; fix the cause and run the
  workflow again for the tag.
- Read the draft on
  <https://github.com/0h3xn4/basilisk_space-mission-studio/releases>: the
  eleven files (the wheel, the sdist, each installer and its bill of
  materials, `SHA256SUMS-linux` and `SHA256SUMS-windows`, and from 2.7.0
  the two Qt source archives and `SHA256SUMS-sources`), and the notes, which say which platform has which file and
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
and publishing are the user's. 1.1.0 was published on 2026-10-20: tag
`spacemissionstudio-v1.1.0` on `1f8ad1663`, its six files (the first
with a Windows setup program) built and attached by the release workflow.

1.1.1 was prepared on 2026-10-21 by this checklist: the self-contained
installers of PR #89 and no change to the app. The space weather is the
copy refreshed for 1.1.0 (observations to 2026-10-18), one release
earlier. It was published on 2026-10-21: tag `spacemissionstudio-v1.1.1`
on `57a54ae92`, its six files built, installed and attached by the
release workflow. A first tag and release were deleted and the tag
pushed again; a release created by hand before the workflow has attached
its files is public with none, so push the tag and let the workflow
create the draft.

1.2.0 was prepared on 2026-10-21 by this checklist: starting a mission
from scratch (PR #92) and the end of macOS support (PR #92, #93), with
no change to what the tool computes. The space weather is again the copy
refreshed for 1.1.0 (observations to 2026-10-18, updated 2026-10-19), two
days old. It is the first release whose notes the release workflow writes
with `packaging/release_notes.py`. It was published on 2026-10-21: tag
`spacemissionstudio-v1.2.0` on `c92f90040`, its six files built,
installed and attached by the release workflow, which also wrote the
notes because the release had none. The release had been published by
hand before the workflow ran, so it was public without files for
13 minutes: push the tag first and publish the draft the workflow makes.

1.3.0 was prepared on 2026-10-23 by this checklist: the UI overhaul (PRs
#96 to #107), with no change to what the tool computes (the engine, the
schema, the command line and the exported files are unchanged; the
exports are tested byte for byte). The space weather was refreshed for
it on 2026-10-26 (observations to 2026-10-24, updated 2026-10-25); NASA
MSFC's October 2026 prediction is still the latest issue (checked on
2026-10-26: the shipped copy matches the published file but for
whitespace). Its notes come from `CHANGELOG.md` 1.3.0, which has a
summary, "Who should update" and "Known limits". It was published on
2026-10-26: tag `spacemissionstudio-v1.3.0` on `7bdfa21ac`, its six files
built, installed and attached by the release workflow, which wrote the
notes. As with 1.2.0, the release was published by hand before the
workflow ran, so it was public without files for 12 minutes, and the
CHANGELOG heading was dated after the tag: date the heading, then push
the tag, then publish the draft the workflow makes.

1.3.1 was prepared on 2026-10-26 by this checklist: three changes that
shorten the window's pauses (PRs #116 to #118), with no change to what
the tool computes. The space weather is 1.3.0's (observations to
2026-10-24, updated 2026-10-25). The CHANGELOG heading is dated
2026-10-26, the day it was prepared: if the tag is pushed on another
day, correct the date first. It was published on 2026-10-27: tag
`spacemissionstudio-v1.3.1` on `081f74079`, its six files built,
installed and attached by the release workflow, which wrote the notes.
The tag was pushed the day after the heading's date, so `develop`'s
heading was corrected to 2026-10-27 afterwards (the tagged CHANGELOG
reads 2026-10-26). For the third release running, the release was
published four seconds after the tag was pushed, before the workflow
started, so it was public without files or notes for 12 minutes: push
the tag, wait for the workflow's draft (about 13 minutes), read it, then
publish it.

2.0.0 was prepared on 2026-11-03 by this checklist: the audit of
2026-10-27 and the transparency work (PRs #120 to #205), and Python 3.14
only. Two steps could not be done as written. The space weather was not
refreshed: CelesTrak reset every connection from the environment the
release was prepared in, so it is 1.3.0's (observations to 2026-10-24),
said in the CHANGELOG's known limits and SRelD K-13. And by the user's
instruction of the day, the release pull request was merged without
asking, but the tag could not be pushed from that environment (its git
proxy refused tags), so the user tagged and published. It was published
on 2026-11-03 at 12:30 UTC: tag `spacemissionstudio-v2.0.0` on
`6608682a3`, with the user's own notes, which the workflow kept. Published before the workflow
started, it was public without files for 32 minutes, until the workflow
attached them at 13:02, the fourth release so. Push the tag first,
or save the release as a draft and run the workflow on its tag, and
publish only once the files are there.

2.1.0 was prepared on 2026-11-04 by this checklist: the analyses built
on the 3D model (#209), the 3D model editor's equipment, stowed,
materials, budget and launcher tabs (#210, #211) and the IDM-CIC import
(#212). The space weather again could not be refreshed (CelesTrak reset
the connection), so it is 1.3.0's, said in the known limits and SRelD
K-13. The release pull request (#213) was merged once CI was green, and
the user tagged and published (the environment cannot push tags). It was
published on 2026-11-04 at 14:57 UTC: tag `spacemissionstudio-v2.1.0` on
`4346b4189`, with notes written for it, which the workflow kept.
Published two seconds before the workflow started, it was public without
files for 37 minutes, until the workflow attached them at 15:34, the
fifth release so. Push the tag, wait for the workflow's draft (about 37
minutes now that it runs the whole suite on both platforms), then edit
its notes and publish.

2.1.1 was prepared on 2026-11-04 by this checklist, a patch release with
the fixes reported on 2.1.0 (#215: the 3D model editor as a window of its
own, the IDM-CIC import from a template, Vizard's battery in watt-hours).
No scenario field, template or golden file changed. The space weather is
still 1.3.0's (CelesTrak reset the connection again, K-13). The release
pull request (#216) was merged once CI was green, and the user tagged
`spacemissionstudio-v2.1.1` on `a6413c1cb` and published it on
2026-11-04 at 19:58 UTC, with notes written for it, which the workflow
kept. Published two seconds before the workflow started, it was public
without files for 35 minutes, until the workflow attached them at 20:33,
the sixth release so. To avoid it: push the tag, or save the release as
a draft, wait for the files (about 35 minutes), then publish.

2.2.0 was prepared on 2026-11-05 by this checklist: CCSDS orbit files in
the app (#218) and more windows of their own, a minor release because it
adds features. No scenario
field, template or golden file changed. The space weather is still
1.3.0's (CelesTrak reset the connection again, K-13). The release pull
request (#219) was merged once CI was green, and the user tagged
`spacemissionstudio-v2.2.0` on `fa9d2b6b9` and published it on
2026-11-05 at 08:55 UTC, with notes written for it, which the workflow
kept. Published two seconds before the workflow started, it was public
without files for 38 minutes, until the workflow attached them at 09:34,
the seventh release so. To avoid it: push the tag, or save the release as
a draft, wait for the files (about 40 minutes), then publish.

2.3.0 was prepared on 2026-11-05 by this checklist: a Walker
constellation that holds its spacing (#220) and the satellite's
components from IDM-CIC (#222 devices, #223 power, #224 properties), a
minor release because it adds features. No template or golden file
changed; the scenario format gained the import record targets `devices`
and `power`, which 2.2.0 refuses (K-30). The space weather is still
1.3.0's (CelesTrak reset the connection again, K-13). The release pull
request (#225) was merged once CI was green, and the user tagged
`spacemissionstudio-v2.3.0` on `3f11a0227` and published it on
2026-11-05 at 16:17 UTC, with notes written for it, which the workflow
kept. Published two seconds before the workflow started, it was public
without files for 39 minutes, until the workflow attached them at 16:56,
the eighth release so. To avoid it: push the tag, or save the release as
a draft, wait for the files (about 40 minutes), then publish.

2.4.0 was prepared on 2026-11-05 by this checklist: device axes read
from the IDM-CIC model's shapes (#227) and, added on the release branch
at the user's question, the body frame's origin at the centre of gravity,
a minor release because it adds features. No template, golden file or scenario field changed; 2.3.0
opens the files 2.4.0 saves (checked with 2.3.0's code on a file with
devices imported along the model's axes). The space weather is still
1.3.0's (CelesTrak refused the connection again, K-13). The release pull
request (#228) was merged once CI was green, and the user tagged
`spacemissionstudio-v2.4.0` on `ac4b90065` and published it on
2026-11-05 at 20:58 UTC, with notes written for it, which the workflow
kept. Published two seconds before the workflow started, it was public
without files for 35 minutes, until the workflow attached them at 21:33,
the ninth release so. To avoid it: push the tag, or save the release as
a draft, wait for the files (about 40 minutes), then publish.

2.5.0 was prepared on 2026-11-08 by this checklist: thrusters from the
IDM-CIC model (#230) and the JSON page as a code editor (#231, #232),
with the documentation refresh and the 2.4.0 publication record (#229),
a minor release because it adds features. No template, golden file or
scenario field changed; 2.4.0 opens the files 2.5.0 saves (checked with
2.4.0's code on a file with a thruster imported at the centre of
gravity). The space weather is still 1.3.0's (CelesTrak refused the
connection again, K-13). The release pull request (#233) was merged once
CI was green, and the user tagged `spacemissionstudio-v2.5.0` on
`1951a028c` and published it on 2026-11-08 at 19:29 UTC, with notes
written for it, which the workflow kept. Published one second before the
workflow started, it was public without files for 33 minutes, until the
workflow attached them at 20:01, the tenth release so. To avoid it: push
the tag, or save the release as a draft, wait for the files (about 35
minutes), then publish.

2.6.0 was prepared on 2026-11-09 by this checklist: network use enforced
and offline mode (#235), the network audit (#236), hash-checked
installers with a bill of materials (#237) and the 3D View in place of
the Vizard download (#239), with the documentation refresh and the 2.5.0
publication record (#234), a minor release because it adds features.
The first release whose files include each installer's bill of
materials (`*.cdx.json`), listed in `SHA256SUMS-*`. No template, golden
file or scenario field changed; 2.5.0 opens the files 2.6.0 saves
(checked with 2.5.0's code on the 32 templates as 2.6.0 saves them). The
space weather is still 1.3.0's (CelesTrak reset the connection again,
K-13). The release pull request (#240) was merged once CI was green, and
the user tagged `spacemissionstudio-v2.6.0` on `dcbb95e09`, pushed the
tag and published the release on 2026-11-10 at 06:51 UTC, with notes
written for it, which the workflow kept. The release had been saved as a
draft first, as advised, but was published about two minutes after the
tag, so it was public without files for 38 minutes, until the workflow
attached its eight files at 07:29, the eleventh release so. To avoid
it: keep the draft until the workflow has attached the files (about 40
minutes: the full suite runs on both platforms first), then publish.

2.7.0 was prepared on 2026-11-10 by this checklist: the 3D View as a
renderer (#248) that can show a run live (#249), the start on Home with
no scenario open (#246), the external viewer support removed (#247),
and the legal groundwork (#241 to #243, #245), with the 2.6.0
publication record and the repository's new name (#244), a minor release
because it adds features. The first release under the EUPL-1.2, and the
first whose files include the Qt and PySide6 source archives with
`SHA256SUMS-sources` (eleven files) and a signed build provenance of
each built file. No golden file changed and no scenario field was added
(the templates lost only the external viewer's fields); 2.6.0 opens the
files 2.7.0 saves (checked with 2.6.0's
code on the 32 templates as 2.7.0 saves them). The space weather was
refreshed: CelesTrak answered for the first time since 1.3.0
(observations to 2026-11-09). NASA MSFC's November 2026 prediction was
not adopted, because it changes every template's drag (SRelD K-33).
It was published on 2026-11-11 at 18:25 UTC, after a day of detours
(SRelD issue 34). A first tag on #250's merge was deleted while its run
was starting. The release was then published from the web, which made
the tag on #251's merge, and was public without files; its run passed
every test and built both installers but failed at pip-audit on a pillow
advisory published that day (accepted in #252). The user deleted the
tag (the release became a draft and kept its notes), tagged #252's
merge `ae5525cb8`, the workflow attached the eleven files at 18:00
([run 43067454786](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/43067454786)),
and the draft was published after them. It had been public without
files from 09:31 until the tag was deleted. Two lessons: tag only once, the commit
the release pull request's last CI ran on; and since advisories appear
daily, run the pip-audit step locally just before tagging, so a new
advisory is handled before the tag rather than after.

---

**Next:** [Syncing with upstream Basilisk](upstream-sync.md) ·
[Developer guide](README.md)
