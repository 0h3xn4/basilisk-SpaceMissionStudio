# Licence inventory, gate and notices

Milestone M1 of [`docs/legal/PHASE1_PLAN.md`](../../docs/legal/PHASE1_PLAN.md).
`licences.py` (standard library only) answers three questions about a package:
what is in it, under which licence, and does every licence text travel with it.

| File | What it is |
|---|---|
| `licences.py` | `sbom`, `check` and `notices` sub-commands |
| `components.json` | Components that are not Python distributions (fonts, icons, data, CPython and the libraries linked into it). Each names the files it owns (`match`), where its licence text is, and its evidence. |
| `overrides.json` | Python distributions whose metadata states no usable licence, with the evidence |
| `allowlist.txt` | The SPDX ids the project may redistribute |
| `texts/` | Licence texts the packages themselves lack (the libraries inside the Python build) |

## How it works

`sbom --root TREE` walks every file under `TREE`. A Python distribution owns the files in its `RECORD`;
a declared component owns the files its patterns match. A file nobody owns is listed as **unclaimed**.
`check` fails on: a component with no known licence; a licence not on the allowlist; a component with no
licence text in the package; an unclaimed file; a component missing from the notices file; a data set whose
provider forbids redistribution (`redistribution_status: restricted`) with no `waived_by` decision.
Data whose redistribution right is `open` warns; `--strict` makes it fail. `notices` writes
`THIRD_PARTY_NOTICES`: one entry per component, then each distinct licence text once.

The tool decides nothing about the law. An entry whose licence is unclear is **left out**, so the check
fails until a person has read the source and written the entry (with the evidence and the date).

## Where it runs

| Package | Tree | When |
|---|---|---|
| Wheel | the unpacked wheel | every change to the files that feed it (`.github/workflows/spacemissionstudio-licences.yml`). The committed `SpaceMissionStudio/THIRD_PARTY_NOTICES` must equal what the tool generates from the wheel. |
| `.deb` | the bundled Python folder | in `bundle_python.py`, at the end of the build (`--licence-gate fail`, the default on Linux). It writes `licenses/`, `SPACEMISSIONSTUDIO_LICENCES.cdx.json` and `THIRD_PARTY_NOTICES.txt` into the folder; `build_deb.sh` copies the notices to `/usr/share/doc/spacemissionstudio/`. |
| Windows setup | the same folder | same step, default `warn`: the list of Windows libraries (python-build-standalone's Windows build) is not read yet. The first release build prints the unclaimed files; they become entries in `components.json`. |

The older `SPACEMISSIONSTUDIO_SBOM.cdx.json` that `bundle_python.py` writes (pip's install report with
hashes) stays; it records where each package came from. The licence SBOM records which licence owns which
file. Merging the two is a later task.

## Regenerate the committed notices

```bash
python -m build --wheel --outdir /tmp/dist SpaceMissionStudio
python -m zipfile -e /tmp/dist/spacemissionstudio-*.whl /tmp/wheelx
python SpaceMissionStudio/packaging/legal/licences.py sbom --root /tmp/wheelx --name wheel --out /tmp/wheel.cdx.json
python SpaceMissionStudio/packaging/legal/licences.py notices --sbom /tmp/wheel.cdx.json --root /tmp/wheelx \
    --out SpaceMissionStudio/THIRD_PARTY_NOTICES
```
