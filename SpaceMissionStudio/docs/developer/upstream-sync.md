# Syncing with upstream Basilisk

This repository is a fork of [AVSLab/basilisk](https://github.com/AVSLab/basilisk).
This page covers how to take new upstream commits, how to move the tool
to a new Basilisk release, and how to refresh the upstream part of the
root `README.md`.

## Two different things

- **The Basilisk sources in this repository** (`src/`, `docs/`,
  `examples/`, ...) are upstream's. The tool does not build or import
  them.
- **The Basilisk the tool runs** is the `bsk` wheel from PyPI, pinned to
  the verified version (`QUALIFIED_BASILISK_VERSION` in
  `spacemissionstudio/dependencies.py`, currently 2.12.0).

So merging upstream commits changes nothing the tool runs. Moving the
tool to a new Basilisk is a separate, deliberate step.

## Take new upstream commits

```bash
git remote add upstream https://github.com/AVSLab/basilisk.git   # once
git fetch upstream develop
git switch develop
git switch -c sync-upstream
git merge upstream/develop
```

Conflicts can only appear in the few files the fork changed outside
`SpaceMissionStudio/`: `README.md`, `.gitignore` and
`.github/workflows/`. Resolve them, then open a pull request.

## Refresh the upstream README

The root `README.md` has the tool's part at the top and upstream's
README below it, between these two markers:

```
<!-- BEGIN UPSTREAM README -->
...
<!-- END UPSTREAM README -->
```

An untouched copy of the same upstream text is kept in
`docs/upstream/README.upstream.md` (in the repository root's `docs/`
folder). To see whether upstream changed its README since the last sync:

```bash
git fetch upstream develop
git show upstream/develop:README.md > /tmp/README.upstream.new
diff -u docs/upstream/README.upstream.md /tmp/README.upstream.new
```

If it did:

1. Copy the new text over the copy:
   `cp /tmp/README.upstream.new docs/upstream/README.upstream.md`.
2. Replace everything between the two markers in `README.md` with the
   same text. Only change what the README's location breaks (relative
   links and images); there are none today, because the README stays at
   the repository root where upstream has it.
3. Update the commit named under "Original Basilisk README" in
   `README.md` and at the top of `docs/upstream/README.upstream.md`.
4. Note what changed in `SpaceMissionStudio/docs/DOCS_AUDIT.md` section 5.

## Move the tool to a new Basilisk release

This is a requalification, described in
[`compliance/docs/SMP.md`](../../compliance/docs/SMP.md) section 8:

1. Install the new release in a fresh environment:
   `pip install "bsk[all]==X.Y.Z"`.
2. Run the full suite and the validation cases against it.
3. Only then change `QUALIFIED_BASILISK_VERSION`, the installers'
   `bsk[all]==` pins (`packaging/deb/DEBIAN/postinst` and
   `packaging/windows/bootstrap_env.ps1`), and the `bsk[all]==` commands
   in the documentation (`grep -rn "bsk\[all\]==" --include=*.md .`).
4. Re-vendor the flight-software sources the export uses
   (`spacemissionstudio/fsw_export/basilisk_fsw_sources.*`, from the new
   release's sources) and run `tests/test_fsw_vendored_sources.py`.

---

**Next:** [Releasing](releasing.md) · [Developer guide](README.md)
