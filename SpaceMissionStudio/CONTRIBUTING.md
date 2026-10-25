# Contributing to SpaceMissionStudio

How to report a problem, propose a change, and get a pull request merged.
This is for SpaceMissionStudio, the tool in this folder; Basilisk's own
guide is the repository root's [`CONTRIBUTING.md`](../CONTRIBUTING.md).

## Report a problem

Open an issue on
[GitHub](https://github.com/0h3xn4/basilisk-SpaceMissionStudio/issues)
with:

- what you did, what you expected and what happened;
- the log file named in the error dialog (`~/.spacemissionstudio/logs/`);
- the output of `spacemissionstudio --version` (or **Settings > About** >
  **About SpaceMissionStudio**) and your operating system;
- the scenario file, if you can share it.

[Troubleshooting](docs/troubleshooting.md) may already have the answer.

## Propose a change

1. Set up a development environment and run the tests:
   [Developer guide](docs/developer/README.md).
2. Make a branch from `develop` (the default branch).
3. Make one logical change per commit. Code commits name the requirement
   they address (for example `SRS-F-19: ...`); documentation commits start
   with `docs:`.
4. Before you push, run what CI runs:

   ```bash
   python -m ruff check spacemissionstudio tests scripts compliance/tools
   QT_QPA_PLATFORM=offscreen python -m pytest tests -q -n auto
   for t in check_drds build_icd_schema build_sdd_components build_test_specs build_traceability; do
     python compliance/tools/$t.py
   done
   git diff --exit-code -- compliance/docs
   ```

   After editing `USER_MANUAL.md`, also run `python scripts/sync_help.py`.
5. Open a pull request into `develop` using the
   [pull request template](../.github/pull_request_template.md).

## What a change needs

- **Tests.** New behaviour has a test, and every test has a docstring.
  Never skip, disable or remove a test to get CI green.
- **Units.** Every physical number in code carries a unit comment, such
  as `1.2  # [s]` (see the repository's [`AGENTS.md`](../AGENTS.md)).
- **A licence header** (ISC) on new source files.
- **No changes to Basilisk.** Do not edit `../src`, patch it, or
  monkey-patch its internals; work around a Basilisk limitation in the
  tool's own code and document it.
- **Real data only.** No synthetic space weather or made-up reference
  data.
- **No silent network access.** Anything that downloads must ask first.
- **Documentation.** User-visible changes update the
  [User Manual](USER_MANUAL.md) or the [how-to pages](docs/user-manual/README.md),
  and add a line to [`CHANGELOG.md`](CHANGELOG.md) under "Unreleased".
  Larger changes also get a [`HISTORY.md`](HISTORY.md) entry: what was
  found, why, what changed, and how it was verified.
- **Compliance records.** If the change touches a requirement, update the
  matching documents in [`compliance/`](compliance/README.md).

## Code of conduct

The repository's [code of conduct](../CODE_OF_CONDUCT.md) applies.

---

**Next:** [Developer guide](docs/developer/README.md) ·
[Architecture](docs/developer/architecture.md) ·
[Documentation index](docs/README.md)
