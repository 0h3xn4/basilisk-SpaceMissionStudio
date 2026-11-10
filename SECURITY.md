# Security policy

This policy covers **SpaceMissionStudio**, the application in the
[`SpaceMissionStudio/`](SpaceMissionStudio/) folder of this repository.
The rest of the repository is a fork of
[Basilisk](https://github.com/AVSLab/basilisk); a problem in Basilisk
itself belongs to the Basilisk project.

## Supported versions

Only the latest release of SpaceMissionStudio receives fixes. Older
releases are not updated.

## Reporting a vulnerability

Please do **not** open a public issue, pull request or discussion for a
security problem.

Report it privately through GitHub: open the repository's **Security**
tab and choose **Report a vulnerability**. Only the maintainer can read
the report.

Please include:

- the SpaceMissionStudio version (Help › About, or
  `spacemissionstudio --version`) and the operating system;
- how the installation was made (Windows installer, `.deb`, or `pip`);
- the steps to reproduce the problem, and what an attacker could do with it.

## What to expect

SpaceMissionStudio is a non-commercial project with one volunteer
maintainer. Reports are handled on a best-effort basis; there is no
fixed response time and no bug bounty. A confirmed problem is fixed in a
new release, and the release notes name it once the fix is available.

## Checking a download

Each release lists the SHA-256 of every file (`SHA256SUMS-linux`,
`SHA256SUMS-windows`, `SHA256SUMS-sources`). From release 2.7.0, the
files built by the release workflow also carry a signed build provenance
(Sigstore), which the GitHub CLI checks:

```bash
gh attestation verify <downloaded file> --repo 0h3xn4/basilisk_space-mission-studio
```

The Windows setup program is not code-signed, so Windows SmartScreen may
warn before it runs.
