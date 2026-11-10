# SpaceMissionStudio: Software Release Document (SRelD)

DRD: ECSS-E-ST-40C Annex G
Document: SMS-SRelD, issue 33, 2026-11-10. Remediation R14.

**Status:** release **2.7.0**, prepared 2026-11-10: **Results › 3D View**
as a renderer (#248, SRS-F-16) that can show a run live while it is
computed (#249, SRS-F-16), the start on Home with no scenario open
(#246, SRS-O-02), the external viewer support removed (#247; SRS-I-08,
ICD-08 and security analysis S-05, S-06 and S-11 retired), and the legal
groundwork: the licence inventory, gate and notices of every package
(#241, milestone M1), the licence change to EUPL-1.2 with the provenance
scan (#242, M2 and M3), the owner's decisions on it (#243: no copyright
claimed, ITU-R P.676-13's data file and the GPL-only Qt modules left
out of the installers, the Qt and PySide6 sources with every release),
and the risk register, security policy, sign-off check, signed build
provenance and the Windows licence gate (#245, M4); with the 2.6.0
publication and the repository's new name recorded (#244). The 3D View
is drawn by three.js 0.187.0 (MIT, bundled) in the lazily created web
view: the Earth with NASA's Blue Marble, turning by the IERS Earth
rotation angle and lit by the Sun, NASA's star map (J2000), the Moon,
each spacecraft's model shaded with its path, body axes, fields of view
and plumes, the ground stations with their line of sight and the ground
track, from the whole orbit, a followed spacecraft, the Earth's frame
or along a body axis or instrument. With **Show in 3D View while
running**, a probe last in the dynamics task samples each spacecraft
about 200 times an orbit into a feed the view draws as the run goes,
optionally paced at 1×, 10×, 100× or 1000× real time; every series of
every template is equal bit for bit with and without it. The app opens
on Home with no scenario open and lists only the open scenario's runs.
Nothing of the external viewer is left: its settings, run options,
exports, commands, CLI options and the five scenario fields, which older
files still carry and which are dropped on load and recorded in the
run's provenance (schema version 4, unchanged). From 2.7.0 the app is
licensed under the EUPL-1.2 (1.0.0 to 2.6.0 stay ISC). No template,
golden file or scenario field a 2.6.0 file can hold changed: every
template's outputs are as in 2.6.0, and 2.6.0 opens the files 2.7.0
saves (checked with 2.6.0's code on the 32 templates as 2.7.0 saves
them: all open and validate with no message). The bundled CelesTrak
space weather was refreshed (observations to 2026-11-09; K-13); NASA
MSFC's November 2026 prediction was not adopted (K-33). The release
pull request is merged once CI is green; tagging and publishing are the
user's (the environment cannot push tags).

**Previous release:** 2.6.0, published 2026-11-10 (06:51 UTC): the run in 3D inside
the app in place of the Vizard download (#239, SRS-F-16), network use
enforced and offline mode (#235, SRS-S-05), the network audit (#236),
and hash-checked installers with a bill of materials (#237, security
analysis S-08), with the documentation brought up to 2.5.0 and the 2.5.0
publication recorded (#234). **Results › 3D View** draws the run from its
own series with the app's plotly.js: the Earth turning by the IERS Earth
rotation angle and shaded by Basilisk's albedo map, each spacecraft's
path and 3D model turned by its attitude, the ground stations and the
Sun's direction, played back and kept with the shared time cursor; it
follows one spacecraft at true size with its body axes. The Vizard AVS
Lab publishes has Unity Analytics switched on (its project settings,
Unity's analytics libraries, AVS Lab's Unity project ID and Unity's
event addresses, read from the program, not run), so the tool no longer
downloads Vizard, no longer looks for one and ignores a copy an earlier
version downloaded; only a Vizard the user chooses is started (K-32).
Every download goes through one gateway that knows its hosts; offline
mode, set by the user or locked by an administrator's policy file,
switches them all off; a Python audit hook refuses any other network use
in every process the tool starts, and every use is logged. The network
audit traces every network call of a full GUI and command-line session
and fails on any call to another computer (CI on every change; here: 146
processes, none to another computer). Both installers install every
package against its recorded SHA-256, from wheels only, and carry a
CycloneDX 1.6 bill of materials, attached to the release beside them.
No template, golden file or scenario field changed: every template's
outputs are as in 2.5.0, and 2.5.0 opens the files 2.6.0 saves (checked
with 2.5.0's code on the 32 templates as 2.6.0 saves them). The bundled
space weather is still 1.3.0's: CelesTrak reset the connection again
(K-13). The release pull request (#240) was merged once CI was green;
tagging and publishing were the user's (the environment cannot push tags).
- Tagged `spacemissionstudio-v2.6.0` (not signed, D-13) on commit
  `dcbb95e09` (`dcbb95e097c42013433438cc92196ee78139f97d`), the merge of
  #240 into `develop`, by the user. GitHub release "Space Mission Studio
  2.6.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.6.0>).
  The user saved it as a draft first and published it at 06:51:54 UTC,
  about 1 minute 40 s after the tag started the release workflow, so it
  was public without files until the workflow attached them at 07:29.
- Its eight files were built, installed, checked and attached by the
  release workflow
  ([run 42771178369](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/42771178369)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.6.0_amd64.deb`, 451 353 268 bytes)
  `a853e7b6...4505`, setup program (`spacemissionstudio-2.6.0-setup.exe`,
  395 789 722 bytes) `1d655470...2c9e`, wheel (4 952 642 bytes)
  `b56926b2...e541`, sdist (5 155 285 bytes) `37515fb5...73f4`, the
  `.deb`'s bill of materials (`spacemissionstudio_2.6.0_amd64.cdx.json`,
  36 033 bytes) `f3dd942b...2c5b`, the setup program's
  (`spacemissionstudio-2.6.0-setup.cdx.json`, 37 155 bytes)
  `f9748a6f...c1c5`, `SHA256SUMS-linux` `1df98586...dae5`,
  `SHA256SUMS-windows` `514a9fe8...74cc`.
- The repository was renamed on 2026-11-10, after the release, from
  `0h3xn4/basilisk-SpaceMissionStudio` to
  `0h3xn4/basilisk_space-mission-studio`. GitHub redirects the old
  addresses, so the release's notes, which use them, still work; this
  document and the others now use the new name.

Before it: 2.5.0, published 2026-11-08 (19:29 UTC): thrusters from the
IDM-CIC model (#230, SRS-F-28, decision IDM-32) and the JSON page as a
code editor (#231, #232, SRS-F-15, decisions JE-01 to JE-10), with the
documentation brought up to 2.4.0 and the 2.4.0 publication recorded
(#229). A thruster whose plume the team drew as a cone is now added to
the 3D model's equipment, where the design checks use it: placed where
the plume starts, pushing against it, with the plume's half-angle and
the thrust of the catalog product or of a mapped property
(`thruster.MaxThrust`, N or mN); it has no mass, the equipment's being
counted already. The JSON page (**Form · JSON**) colours the text, numbers
its lines, shows the matching bracket and marks every problem of the
**Problems** list where it is; it offers completion from the scenario's
own records (fields with their defaults, choices, names, a device's and a
mission step's `params`), describes the key under the cursor, renames a
spacecraft, ground station or 3D model part everywhere (F2), goes to a
name's definition (F12), offers quick fixes (Ctrl+.) and formats the text
(Shift+Alt+F). No template, golden file or scenario field changed: every
template's outputs are as in 2.4.0, and 2.4.0 opens the files 2.5.0 saves
(checked with 2.4.0's code on a file with a thruster imported at the
centre of gravity; its design checks run on the thruster). The bundled
space weather is still 1.3.0's: CelesTrak refused the connection again
(K-13). The release pull request (#233) was merged once CI was green;
tagging and publishing were the user's (the environment cannot push tags).
- Tagged `spacemissionstudio-v2.5.0` (not signed, D-13) on commit
  `1951a028c` (`1951a028ce436c6ba0452056da4c4dfed2c05b6c`), the merge of
  #233 into `develop`, by the user. GitHub release "Space Mission Studio
  2.5.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.5.0>).
  It was published at 19:29:07 UTC, one second before the release
  workflow started, so it was public without files until the workflow
  attached them at 20:01.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 42515265320](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/42515265320)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.5.0_amd64.deb`, 451 057 276 bytes)
  `ef4d8e89...a530`, setup program (`spacemissionstudio-2.5.0-setup.exe`,
  395 336 265 bytes) `0a8842a2...e884`, wheel (4 786 182 bytes)
  `c4131028...ca91`, sdist (4 983 209 bytes) `17d2bf77...7515`,
  `SHA256SUMS-linux` `dc4881a3...bbd2`, `SHA256SUMS-windows`
  `4d046517...deac`.

Earlier: 2.4.0, published 2026-11-05 (20:58 UTC): each device's axis
from the IDM-CIC model (#227, SRS-F-28, decision IDM-30), and the body
frame's origin at the centre of gravity (decision IDM-31, on the release
branch, asked by the user while it was prepared). The import
already placed a sensor or actuator as its equipment is placed; it now
also reads which way it points or spins from the equipment's shapes: a
field-of-view cone gives a sensor's boresight and field of view (shown in
the 3D view, not simulated), a cylinder a wheel's spin axis or a
magnetorquer's rod axis, and +z of the equipment frame is kept when the
shapes show none. On the example models it gives the magnetorquers their
rod axes, which the +z rule of 2.3.0 had swapped. On request, the import
puts the origin of the body frame at the model's centre of gravity
(0.35 m and 0.39 m from the element's origin in the example satellites)
and moves every position of the spacecraft with it; by default it stays
the element's, as before. No template, golden file or scenario field
changed: every template's outputs are as in 2.3.0, and 2.3.0 and 2.4.0
open each other's files (checked with 2.3.0's code on files with devices
imported along the model's axes and with the origin at the centre of
gravity); a 2.3.0 re-import of a spacecraft centred by 2.4.0 does not
keep it centred (K-31). The bundled space
weather is still 1.3.0's: CelesTrak refused the connection again (K-13).
The release pull request (#228) was merged once CI was green; tagging
and publishing were the user's (the environment cannot push tags).
- Tagged `spacemissionstudio-v2.4.0` (not signed, D-13) on commit
  `ac4b90065` (`ac4b9006573dee84f68bcb1cf7800edc2a843544`), the merge of
  #228 into `develop`, by the user. GitHub release "Space Mission Studio
  2.4.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.4.0>).
  It was published at 20:58:24 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 21:33.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 42108301360](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/42108301360)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.4.0_amd64.deb`, 451 140 540 bytes)
  `890a7bc9...71a7`, setup program (`spacemissionstudio-2.4.0-setup.exe`,
  395 007 143 bytes) `51fe6365...d442`, wheel (4 670 778 bytes)
  `7d9e5360...67b4`, sdist (4 860 633 bytes) `a277c3c1...a708`,
  `SHA256SUMS-linux` `ee7cd196...cb81`, `SHA256SUMS-windows`
  `bddb791d...882b`.

Earlier: 2.3.0, published 2026-11-05 (16:17 UTC): the satellite's
components from IDM-CIC, and a Walker constellation that holds its
spacing. The IDM-CIC import (SRS-F-28) finds the sensors and actuators an
IDM-CIC model names (#222), sets the power budget's bus load from the
model's power modes and its panel from the solar arrays' shapes (#223),
and reads the values a team keeps as properties through a mapping the
user gives (#224); the Walker generator can give every plane's
satellites phasing keeping on its first (#220, SRS-F-10). Nothing is
estimated: what the file does not give stays a product's, Basilisk's or
the editor's, and the pre-run checks say so (`import.device_defaults`,
`import.power_defaults`). No template or golden file changed: every
template's outputs are as in 2.2.0. The scenario format gained the
import record targets `devices` and `power`; 2.2.0 refuses a file that
has one (K-30) and opens every other file 2.3.0 saves; 2.3.0 opens every
2.2.0 file. The bundled space weather is still 1.3.0's: CelesTrak reset
the connection again (K-13). The release pull request (#225) was merged
once CI was green; tagging and publishing were the user's (the
environment cannot push tags).
- Tagged `spacemissionstudio-v2.3.0` (not signed, D-13) on commit
  `3f11a0227` (`3f11a022715c41bc16094d34937b586c1eb0910b`), the merge of
  #225 into `develop`, by the user. GitHub release "Space Mission Studio
  2.3.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.3.0>).
  It was published at 16:17:58 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 16:56.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 42062956336](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/42062956336)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.3.0_amd64.deb`, 451 386 808 bytes)
  `d5622c3b...b616`, setup program (`spacemissionstudio-2.3.0-setup.exe`,
  395 189 224 bytes) `d494bb23...8b0d`, wheel (4 662 880 bytes)
  `c2009352...931a`, sdist (4 847 062 bytes) `e5b3469c...5e7d`,
  `SHA256SUMS-linux` `33822d77...499f`, `SHA256SUMS-windows`
  `d55fdf53...6dee`.

Earlier: 2.2.0, published 2026-11-05 (08:55 UTC): CCSDS orbit files in
the app (#218, SRS-F-14). What the command line already did with CCSDS
502.0-B-3 orbit messages, the GUI now does too, through one module both
use (`spacemissionstudio.ccsds_files`): import a spacecraft's orbit from
an OPM or a TLE-based OMM (recorded as `ccsds-import` records it), export
the starting orbits (OPM, or OMM for a TLE) and a run's OEMs, and check an
OPM, OMM or OEM against the standard. The windows read beside the main
window (change history, CCSDS check, input differences, manual, reference
data, run record) are windows of their own. Since 2.1.1 no scenario field,
template or golden file changed, and the command line writes the same
files: every template's outputs are as in 2.1.1, and 2.1.1 and 2.2.0 open
each other's files. The bundled space weather is still 1.3.0's: CelesTrak
reset the connection again (K-13). The release pull request (#219) was
merged once CI was green; tagging and publishing were the user's (the
environment cannot push tags).
- Tagged `spacemissionstudio-v2.2.0` (not signed, D-13) on commit
  `fa9d2b6b9` (`fa9d2b6b9f015d70cdec7f21360a762b2d26fd22`), the merge of
  #219 into `develop`, by the user. GitHub release "Space Mission Studio
  2.2.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.2.0>).
  It was published at 08:55:50 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 09:34.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 41998260915](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/41998260915)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.2.0_amd64.deb`, 450 735 196 bytes)
  `2e4cfab3...72ae`, setup program (`spacemissionstudio-2.2.0-setup.exe`,
  395 168 677 bytes) `68715e0b...9b52`, wheel (4 629 618 bytes)
  `cf71e95e...5f99`, sdist (4 804 357 bytes) `eeffa315...b7ee`,
  `SHA256SUMS-linux` `f58d682e...96de`, `SHA256SUMS-windows`
  `5530d333...0372`.

Earlier: 2.1.1, published 2026-11-04 (19:58 UTC): fixes to problems
reported on 2.1.0 (#215, K-29). The 3D model editor is a window of its
own (it was a modal dialog, which GNOME moved with the main window); the
editor no longer writes into the built-in templates' folder (an IDM-CIC
import from a template failed with "Permission denied"); a failed
IDM-CIC import changes nothing (it left parts naming a mesh file the
model did not have); Vizard's battery panel shows watt-hours (it showed
watt-seconds). Since 2.1.0 no scenario field, template or golden file
changed, and only `engine/vizard.py`, `idm_import.py` and four GUI
modules changed in the code: every template's outputs are as in 2.1.0,
and 2.1.0 and 2.1.1 open each other's files. The bundled space weather is
still 1.3.0's: CelesTrak reset the connection again (K-13). The release
pull request (#216) was merged once CI was green; tagging and publishing
were the user's (the environment cannot push tags).
- Tagged `spacemissionstudio-v2.1.1` (not signed, D-13) on commit
  `a6413c1cb` (`a6413c1cb44fa3ec98c47ed11cd43b254b5f44c2`), the merge of
  #216 into `develop`, by the user. GitHub release "Space Mission Studio
  2.1.1", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.1.1>).
  It was published at 19:58:37 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 20:33.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 41902117432](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/41902117432)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.1.1_amd64.deb`, 451 169 664 bytes)
  `4e8533e5...8909`, setup program (`spacemissionstudio-2.1.1-setup.exe`,
  394 813 391 bytes) `275df5b9...2b62`, wheel (4 619 166 bytes)
  `a1673f6a...a8eb`, sdist (4 793 047 bytes) `ed2b28cf...fbda`,
  `SHA256SUMS-linux` `bc123a74...f328`, `SHA256SUMS-windows`
  `0fb42dad...3ce0`.

Earlier: 2.1.0, published 2026-11-04 (14:57 UTC): the
spacecraft as designed. The analyses built on the 3D model (#209:
mounted equipment, a stowed configuration, materials and maturity;
design checks of fields of view, thrusters and plumes, the mass budget
and the launcher envelope; disturbance torques, blinding, antenna
obstruction, array shading, exposure and brightness after a run; a
preliminary re-entry casualty estimate), the 3D model editor's tabs for
all of it (#210, #211), and the import of IDM-CIC models (#212; IDM-CIC
is (c) CNES, read by the tool's own code). Requirements SRS-F-25 to
F-28, ICD-12. Every new scenario field is optional and written only when
set: every template's outputs are as in 2.0.0 (the golden baseline), and
2.0.0 opens a file 2.1.0 saves unless it uses them (K-27). The bundled
space weather is still 1.3.0's: CelesTrak reset the connection again
(K-13). The release pull request (#213) was merged once CI was green;
tagging and publishing were the user's.
- Tagged `spacemissionstudio-v2.1.0` (not signed, D-13) on commit
  `4346b4189` (`4346b41899378824855e190f2a6834d506ceb8c7`), the merge of
  #213 into `develop`, by the user. GitHub release "Space Mission Studio
  2.1.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.1.0>).
  It was published at 14:57:45 UTC, two seconds before the release
  workflow started, so it was public without files until the workflow
  attached them at 15:34.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 41852813354](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/41852813354)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.1.0_amd64.deb`, 451 211 836 bytes)
  `5bacd782...cb04`, setup program (`spacemissionstudio-2.1.0-setup.exe`,
  395 109 752 bytes) `b930ab76...7b94`, wheel (4 615 131 bytes)
  `b7e363c9...fe3e`, sdist (4 788 403 bytes) `fb695401...3dd2`,
  `SHA256SUMS-linux` `0a91eb5c...0b00`, `SHA256SUMS-windows`
  `ddbd3093...b376`.

Earlier: 2.0.0, published 2026-11-03 (12:30 UTC): a
glass box, and Python 3.14. It takes the audit of 2026-10-27 (#120 to
#148: engine E1-E5, interface G1-G10, robustness R1-R14) and the
transparency work (`docs/transparency_audit.md`, Phases 0 to 10, #149
to #205): every figure with its calculation, every rule a parameter
a project file can change, a record of what each run, lifetime, budget
and batch came from, a reproduction bundle, value marks for computed,
overridden, preset and imported values, a change history, plugins, units
everywhere and a Python API. `docs/definition-of-done.md` says how each
of its four criteria is checked. The major version is for Python 3.14
only (`requires-python = ">=3.14"`) and for the scenario files 2.0.0
saves, which 1.3.1 and earlier do not open (K-26).

Results change where a defect was fixed, each with its before and after
values: in `CHANGELOG.md` 2.0.0 and RD1 for the audit's (the propellant
budget's rocket equation, E2: 232 kg for a 1 km/s transfer, now 93 kg;
the lifetime at the critical inclination, E1; the integrator's
tolerances, E3; the generators' mean elements, E4; the noise seeds, E5),
and in `docs/changes.md` for the transparency work's. Since Phase 1a
(2026-10-29) the golden baseline of every template's outputs
(`tests/golden/`) has held every other result, and the export files are still tested byte
for byte against those 1.1.0 wrote, less the keys added since and the
Monte Carlo table's new provenance file (`tests/gui/test_export_files.py`).
The bundled space weather is 1.3.0's (observations to 2026-10-24,
updated 2026-10-25): CelesTrak refused the download for this release
(K-13). By the user's instruction of 2026-11-03 the release pull request
(#206) was merged without asking; the tag could not be pushed from the
environment that prepared it (the git proxy refused it, HTTP 403), so
tagging and publishing were the user's.
- Tagged `spacemissionstudio-v2.0.0` (not signed, D-13) on commit
  `6608682a3` (`6608682a34c3694a1df7de86b5553d85e7ea9167`), the merge of
  #206 into `develop`, by the user. GitHub release "Space Mission Studio
  2.0.0", published by the user with notes written for it
  (<https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v2.0.0>).
  It was published at 12:30:59 UTC, before the release workflow had
  started, so it was public without files until the workflow attached
  them at 13:02.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 41636370025](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/41636370025)),
  which kept the release's notes. GitHub's SHA-256 digests: `.deb`
  (`spacemissionstudio_2.0.0_amd64.deb`, 450 924 188 bytes)
  `c54f6dad...1fb7`, setup program (`spacemissionstudio-2.0.0-setup.exe`,
  394 949 676 bytes) `84da6c46...0fbf`, wheel (4 433 556 bytes)
  `3af733a6...fb9f`, sdist (4 617 680 bytes) `ddabb97a...c2d8`,
  `SHA256SUMS-linux` `d7aded00...23ea`, `SHA256SUMS-windows`
  `84b0360a...3e05`.

Earlier still: 1.3.1, published 2026-10-27 (06:05 UTC): a
faster window (#116, #117, #118). What the tool computes is unchanged
from 1.3.0: since commit `7bdfa21ac` the only change in `engine/`,
`schema/`, `sil/`, `fsw_export/`, `model3d/`, `cli.py` or
`output_provenance.py` is in `engine/spaceweather.py`, where
`real_data_path` takes each file's last observed day from a value found
once per file (`CelestrakData.last_observed`), the same day as before
(`test_the_last_observed_day_is_found_once`). No template, data file or
golden file changed, packaging only in the version, and nothing outside
`SpaceMissionStudio/`. The export files are still tested byte for byte
against those 1.1.0 wrote (`tests/gui/test_export_files.py`). The
bundled space weather is 1.3.0's (observations to 2026-10-24, updated
2026-10-25). Merging the release pull request (#119), tagging and
publishing were the user's.
- Tagged `spacemissionstudio-v1.3.1` (not signed, D-13) on commit
  `081f74079` (`081f7407938d97abf8bcff3aae402b8235ea7c86`), the merge of
  #119 into `develop`. GitHub release "Space Mission Studio 1.3.1",
  published by the user:
  <https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v1.3.1>.
  It was published at 06:05:53 UTC, before the release workflow had
  started, so it was public without files or notes until the workflow
  attached them at 06:18. The tagged `CHANGELOG.md` heading reads
  "1.3.1 (2026-10-26)", the day the release was prepared; `develop` has
  2026-10-27, the day it was published.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 40459074482](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/40459074482)),
  which also wrote the notes because the release had none. GitHub's
  SHA-256 digests: `.deb` (`spacemissionstudio_1.3.1_amd64.deb`,
  447 262 520 bytes) `09d9a34c...4f44`, setup program
  (`spacemissionstudio-1.3.1-setup.exe`, 395 406 016 bytes)
  `486abd52...0a7e`, wheel (4 210 164 bytes) `a5b687ae...5593`, sdist
  (4 303 416 bytes) `8ffad3c5...1154`, `SHA256SUMS-linux`
  `71ab4063...1f3f`, `SHA256SUMS-windows` `2b4dbc8e...e1a9`.

Earlier: 1.3.0, published 2026-10-26 (11:55 UTC), the
UI overhaul (`docs/ui/UI_OVERHAUL_PLAN.md`, milestones M2a to M9, PRs #96
to #107; the user's brief, `docs/ui/UI_OVERHAUL.md`). What the tool
computes is unchanged from 1.2.0: since commit `c92f90040` nothing changed
in `engine/`, `schema/`, `sil/`, `fsw_export/`, `model3d/`, `cli.py` or
`output_provenance.py`, three templates changed their description text
only, and the golden files are unchanged. The export files are tested
byte for byte against those 1.1.0 wrote (`tests/gui/test_export_files.py`;
1.2.0's code writes the same bytes). Merging the release pull request,
tagging and publishing were the user's (decision of 2026-10-19, HISTORY
"Towards release 1.1.0"). After the preparation it also took the
documentation refresh (#109), the Alt+Backspace fix and the engine
messages (#110), the space weather refreshed to 2026-10-24 (#111, which
changes drag on dates from 2026-09-09 to 2026-12-07 and in 2027-01 and
2027-02), the MSFC check (#112), the theme switch (#113) and the
spacecraft page built a section at a time (#114).
- Tagged `spacemissionstudio-v1.3.0` (a lightweight tag, not signed,
  D-13) on commit `7bdfa21ac` (`7bdfa21ac8262e358e18ae040972ed95944c4246`),
  the merge of #114 into `develop`. GitHub release "Space Mission Studio
  1.3.0", published by the user:
  <https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v1.3.0>.
  It was published at 11:55 UTC, before the release workflow had attached
  anything, so it was public without files or notes until the workflow
  finished at 12:07. The tagged `CHANGELOG.md` still reads "1.3.0 (not
  yet released)"; `develop` has the date.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 40318662400](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/40318662400)),
  which also wrote the notes because the release had none. GitHub's
  SHA-256 digests: `.deb` (`spacemissionstudio_1.3.0_amd64.deb`,
  447 092 940 bytes) `77cae8f5...5d8f`, setup program
  (`spacemissionstudio-1.3.0-setup.exe`, 395 419 705 bytes)
  `d36d40c8...036a`, wheel (4 207 447 bytes) `f1c69d00...0fd2`, sdist
  (4 300 623 bytes) `f0aaa103...9fd7`, `SHA256SUMS-linux`
  `cbaef561...bc7c`, `SHA256SUMS-windows` `e95391ec...7964`.

Before that: 1.2.0, published 2026-10-21 (17:20 UTC), starting a
mission from scratch, guided, and the end of macOS support:
- Tagged `spacemissionstudio-v1.2.0` (a lightweight tag, not signed,
  D-13) on commit `c92f90040` (`c92f9004075bb28bbad361d55408b827670c0e1a`),
  the merge of the release pull request (#94) into `develop`. GitHub
  release "Space Mission Studio 1.2.0", published by the user:
  <https://github.com/0h3xn4/basilisk_space-mission-studio/releases/tag/spacemissionstudio-v1.2.0>.
  It was published at 17:20 UTC, before the release workflow had
  attached anything, so it was public without files or notes until the
  workflow finished at 17:33.
- Its six files were built, installed, checked and attached by the
  release workflow
  ([run 39642864007](https://github.com/0h3xn4/basilisk_space-mission-studio/actions/runs/39642864007)).
  GitHub's SHA-256 digests: `.deb` (`spacemissionstudio_1.2.0_amd64.deb`,
  446 730 028 bytes) `92760538...0809`, setup program
  (`spacemissionstudio-1.2.0-setup.exe`, 394 968 402 bytes)
  `747bdee3...f3bc`, wheel (4 066 610 bytes) `db73117d...3d23`, sdist
  (4 177 942 bytes) `6b940d87...8a5d`, `SHA256SUMS-linux`
  `50ec7c8c...c4ed`, `SHA256SUMS-windows` `fec5c2f8...46e0`.
- Its release notes were the first the workflow wrote itself
  (`packaging/release_notes.py`, from `CHANGELOG.md` 1.2.0).

And before: 1.1.1, published 2026-10-21 (tag `spacemissionstudio-v1.1.1` on
`57a54ae92`, PR #90), the self-contained installers; 1.1.0, published
2026-10-20 (tag `spacemissionstudio-v1.1.0` on `1f8ad1663`, PR #86),
whose installers set up a virtual environment while installing, needing
internet access and, for the setup program, Python 3.11 on `PATH`
(K-20).

## 1 Introduction (G.2.1<1>)

This SRelD describes release 2.7.0 of SpaceMissionStudio in
`0h3xn4/basilisk_space-mission-studio`: what it contains, what changed since 2.6.0
(commit `dcbb95e09`), what is known to be wrong, and how to use it.

## 2 Applicable and reference documents (G.2.1<2>)

| Ref. | Document |
|---|---|
| RD1 | `HISTORY.md`: the change log, with an entry per change |
| RD2 | SVR (`SVR.md`): the verification and validation results of this release |
| RD3 | SRF (`SRF.md`): the reused software baseline |
| RD4 | `compliance/deviations.md`, `compliance/human_actions.md` |
| RD5 | SUM (`SUM.md`) |

## 3 Terms, definitions and abbreviated terms (G.2.1<3>)

| Term | Meaning |
|---|---|
| SPR | Software problem report: here, a known open problem listed in 5.2 (no SPR system exists yet, H05) |
| SW&D | Software waiver and deviation: the deviations D-01 to D-13 |

## 4 Software release overview (G.2.1<4>)

| Item | Value |
|---|---|
| Configuration item | SpaceMissionStudio (`SpaceMissionStudio/` in the repository) |
| Baseline | `develop` after the 2.7.0 release pull request (the changes of #241 to #249 and the release's records), to be tagged `spacemissionstudio-v2.7.0` by the user. Previous release: 2.6.0, commit `dcbb95e09` (`dcbb95e097c42013433438cc92196ee78139f97d`), tagged `spacemissionstudio-v2.6.0`. |
| Reused software baseline | Basilisk 2.12.0 (PyPI), numpy, sgp4, pyerfa, PySide6, plotly (RD3); the tested versions are pinned in `packaging/constraints.txt`. Bundled with the GUI as files, not packages: Inter 4.1 and JetBrains Mono 2.304 (SIL OFL 1.1), 43 Lucide icons from lucide-static 1.52.0 (ISC), and for the 3D View three.js 0.187.0 (MIT, one bundle built from the pinned npm packages) and resized copies of NASA's Blue Marble and Deep Star Maps 2020 (public domain), with versions, sources and checksums in `docs/THIRD_PARTY_ASSETS.md`. The installers also carry CPython 3.14.8 (python-build-standalone 20261013, SHA-256 pinned) with every installed package and the reference data; each build lists them in its `SPACEMISSIONSTUDIO_RUNTIME.json`, and `docs/THIRD_PARTY_ASSETS.md` ("In the installers") gives their licences |
| Platform | The installers: Linux x86_64 with glibc 2.34 or newer (`.deb`), Windows 10/11 x64; no Python needed. From source: Python 3.14 (3.11 to 3.13 are no longer supported; Basilisk 2.12.0 and PySide6 6.11 do not install on 3.15 yet) |
| Delivery | Attached to the GitHub release by the release workflow (`.github/workflows/spacemissionstudio-release.yml`): the wheel and sdist, the Debian package `spacemissionstudio_2.7.0_amd64.deb`, the Windows setup program `spacemissionstudio-2.7.0-setup.exe` (not signed, D-13), each installer's bill of materials (`spacemissionstudio_2.7.0_amd64.cdx.json`, `spacemissionstudio-2.7.0-setup.cdx.json`, CycloneDX 1.6), `SHA256SUMS-linux` and `SHA256SUMS-windows`; new in 2.7.0, the complete source of the LGPL-3.0 Qt libraries the installers carry (`qt-everywhere-src-6.11.2.tar.xz`, `pyside-setup-everywhere-src-6.11.2.tar.xz`, checked against the size and SHA-256 Qt publishes, `packaging/legal/qt-sources.json`) with `SHA256SUMS-sources`, and a Sigstore-signed build provenance of every built file (`gh attestation verify`) |
| Documentation | SUM and `USER_MANUAL.md`; the documents in `compliance/docs/` |
| Basilisk framework | No Basilisk source, module or test changed. Since 2.6.0 nothing outside `SpaceMissionStudio/` changed but the repository's front-page `README.md` (this release's badge and version, the licence, independence and warranty, the new name), `SECURITY.md` (the security policy, #245), `.github/pull_request_template.md` (the sign-off) and SpaceMissionStudio's own workflows `.github/workflows/spacemissionstudio.yml`, `spacemissionstudio-release.yml`, `spacemissionstudio-windows-installer.yml`, and the new `spacemissionstudio-licences.yml` and `spacemissionstudio-signoff.yml` (the licence gate, the Qt sources, the signed provenance, the sign-off check; `git diff --name-only dcbb95e09 develop`). The installers carry Basilisk 2.12.0 from PyPI, not this repository's framework, and add its support data next to the installed package, in the folder its own `dataFetcher` reads |

## 5 Status of the software configuration item

### 5.1 Evolution since previous version (G.2.1<5.1>)

`CHANGELOG.md` 2.7.0 lists the changes since 2.6.0 (commit `dcbb95e09`);
RD1 has the full story. In summary:

- **The licence inventory, gate and notices** (#241, legal milestone M1;
  plan `docs/legal/PHASE1_PLAN.md`, `docs/legal/OBLIGATIONS.md`,
  `docs/legal/DATA_TERMS.md`): `packaging/legal/licences.py` ties every
  file of the wheel and of the installers' Python to a component with a
  known licence and fails the build on an unknown licence, one off the
  allowlist, a missing text or a file nobody owns; `THIRD_PARTY_NOTICES`
  in the wheel, `THIRD_PARTY_NOTICES.txt` in the installers; the workflow
  `spacemissionstudio-licences.yml`.
- **The licence change to EUPL-1.2, and the provenance scan** (#242, M2
  and M3; brief `docs/LEGAL_AND_WEBSITE.md`, `docs/legal/PROVENANCE.md`):
  `LICENSE` and `LICENSE.de`, a header naming the licence in every source
  file, `License-Expression: EUPL-1.2`, the About box and the
  **Third-Party Licences** window; no file copied or adapted from
  Basilisk but the flight-software source zip, which keeps its ISC
  notice.
- **The owner's decisions on the legal groundwork** (#243;
  `docs/DECISIONS.md`, "the owner's answers of 2026-11-10"): no copyright
  claimed in the app's own code (the files name the licensor); ITU-R
  P.676-13's data file no longer bundled; the Qt modules offered only
  under the GPL and Python's Tcl/Tk left out of the installers (about
  42 MB); the Qt and PySide6 source archives attached to every release.
- **The 2.6.0 publication and the repository's new name recorded**
  (#244): documents only.
- **The risk register, security policy, sign-off, signed provenance and
  the Windows licence gate** (#245, M4; `docs/legal/RISK_REGISTER.md`,
  `docs/legal/WORDING_DRAFTS.md`, `SECURITY.md`): the sign-off check of
  contributions from forks (`spacemissionstudio-signoff.yml`), a
  Sigstore-signed build provenance of every release file, the
  independence and no-warranty statements in the READMEs, the manual and
  the About box, and the licence gate on the Windows build of Python,
  which now stops the build as the Linux one does.
- **The start on Home with no scenario open** (#246, SRS-O-02;
  `docs/DECISIONS.md`, "Landing page at start-up"): `MainWindow` has an
  explicit "scenario open" state; the work areas show an empty state and
  the scenario's commands are disabled until a scenario is opened; the
  run store lists only the open scenario's runs (matched by name).
- **The external viewer support removed** (#247; `docs/DECISIONS.md`,
  "Vizard removed"): its engine, launcher and dialog modules, their
  callers, settings, run options, exports, commands and `run` options;
  the five scenario fields dropped on load by `schema/migrations.py`
  (step "retired fields", recorded in the run's provenance); SRS-I-08,
  ICD-08 and security analysis S-05, S-06 and S-11 retired.
- **Results › 3D View as a renderer** (#248, SRS-F-16;
  `docs/DECISIONS.md`, "The 3D View as a renderer: three.js"): the page
  in `gui/assets/mission_view/` (three.js 0.187.0, built reproducibly by
  `scripts/build_three_bundle.py`; NASA's textures prepared by
  `scripts/prepare_mission_view_textures.py`, SHA-256-checked
  originals), the scene from `engine/scene3d.py` (normals, the Moon, the
  ground track, stations' elevation, altitude, equipment), positions
  relative to the camera's focus before the GPU's single precision, and
  reduced quality chosen when frames take over 50 ms.
- **Results › 3D View live** (#249, SRS-F-16; `docs/DECISIONS.md`, "The
  3D View live"): `engine/live_view.py` (the probe, the feed, the pacing
  on the worker thread in 50 ms slices with Cancel), `scene3d.extend_scene`
  shared with the finished run's scene, the view drained every 50 ms in
  batches of at most 400 frames, the result replacing the live frames in
  the same view; reduced quality from the start on a software renderer
  (SwiftShader, llvmpipe, Windows' WARP).

**Unchanged:** what runs compute, every template and golden file, the
schema version (4) and every field a 2.6.0 file can hold, the exit
statuses, and the files the tool writes for an existing scenario.
**Changed in the interface:** the scenario file loses the external
viewer's five fields (dropped on load from older files), `run` loses its
options, and ICD-08 is retired; the app's licence (EUPL-1.2); the
installers carry `THIRD_PARTY_NOTICES.txt` and no longer ITU-R
P.676-13's data file (`gaseous-attenuation --fetch` downloads it, as
before) (ICD).

**Tests:** see HISTORY.md, "Release 2.7.0 prepared". The added tests
cover the licence gate and the headers, the landing page, the retired
fields' migration and the refused `run` options, the 3D scene against
published values (the Moon against Meeus's example 47.a, a station's
elevation, the altitude above WGS-84), the renderer's page state, the
live probe in four kinds of run with the results equal bit for bit, the
pacing on a fake clock, and a real run shown live. Tests of the
external viewer are removed with it, and the tests that edit, save or
run a scenario open one first, all logged in `docs/ui/TEST_CHANGES.md`.

**Still open:** K-19 (about 0.4 s), K-22, K-23 (smaller), K-24, K-25,
K-26, K-27, K-28, K-30, K-31, K-33 (2.6.0 and 2.7.0 open each other's
files). Closed: K-05 and K-32 (the external viewer support is removed).

**Changes users notice:** the app opens on Home with nothing open;
**Results › 3D View** as a renderer with **View** and **Show** menus;
**Show in 3D View while running** and **Pace** on **Run › Run**; no
external viewer anywhere; **Settings > About** and **Third-Party
Licences...** with the EUPL-1.2.

### 5.2 Known problems and limitations (G.2.1<5.2>)

**Known problems (no SPR system exists, so these stand in for SPRs):**

| # | Problem | Effect | Ref. |
|---|---|---|---|
| K-01 | Closed: the drag figures published before F-07 and F-09 (5-year runs, re-entry from 300 km, launch-delay sweep, altitude trade, disposal, templates 05 and 21) were re-measured on Basilisk 2.12.0. Station-keeping and trade figures fall 12-20 %; HISTORY, the template 05 and 21 descriptions, the template 21 claim test and the drag make-up docstring now give the new values. The bundled space weather has also changed since some were published, and the re-measurement does not separate the two; the disposal figures move both ways, not explained | – | `compliance/drag_remeasure.md`; HISTORY.md |
| K-02 | The drag case of V-04 has an unexplained 1.6 % decay difference from GMAT (within tolerance) | Drag results carry it | `phase3_log.md` |
| K-03 | The time argument is TDB, not TAI (F-05) | About 0.1 m/day in LEO | `phase3_log.md` |
| K-04 | Radius part closed (2026-10-19): Basilisk put the body's radius in place of the field file's (F-03), which scaled Mars's GGM2B J2 by 4.8e-4 and Earth's by 1e-7. The tool now rescales the coefficients so that the file's field is applied (`engine/gravity_field.py`, `tests/test_gravity_field.py`). The field's GM is still the body's (D-07) | GM: 1.4e-8 (Earth) and 1.4e-6 (Mars) on the harmonic terms | `phase3_log.md` F-03 |
| K-05 | Closed in 2.7.0 (#247): the tool no longer streams to an external viewer, so no live stream and no listening viewer exist. Before: during a live stream Vizard, a separate program, listened on port 5556; the tool opened no port. Earlier issues of the security analysis wrongly said Basilisk binds 5556 and 5570 on all interfaces | – | security analysis S-06 (retired 2026-11-10) |
| K-06 | The Windows setup program has not been run by hand on a Windows machine; 1.1.0 to 1.3.0 ship it, built, installed silently and run on a GitHub Windows runner (K-12) | Unknown for interactive use | SValP 9 |
| K-07 | Closed (decision 19): SRS-P-09 and SRS-R-02 measured and met on the reference PC | – | SVR; `compliance/performance.md` |
| K-10 | Closed: the test suite failed on Windows (34 tests) and macOS (10 tests) in CI run 20. Four causes were tool defects (F-09 to F-12, fixed); the rest were tests that assumed Linux. Since commit `41b73b1c3` the suite passes on all three (2259 passed, 11 skipped, 0 failed; run 37854361784). The GUI has not been used by hand on Windows or macOS | – | SVR 4.6; `review_log.md` |
| K-11 | F-09, fixed: parallel runs could read a half-written space-weather file. Altitude trades with more than one worker and Monte Carlo runs with NRLMSISE-00 drag, made before the fix, may have used wrong solar activity | Those results are to be re-run | `review_log.md` F-09 |
| K-08 | Closed: the PNG/SVG export polled the page with overlapping asynchronous queries; a late timer tick read the cleared state (the CI tracebacks), and several answers could save the file twice. One query at a time now, late answers ignored (F-12) | – | `review_log.md` F-12 |
| K-09 | Closed (2026-10-19): 1054 of the 2314 unit and integration test functions had no docstring. Every one now has a docstring stating what it checks, read from its body; no test code changed (each file's syntax tree without docstrings equals the one before) | – | `SUITP_test_cases.md`; HISTORY.md |
| K-12 | The Windows setup program is built, installed silently and the installed tool run on a GitHub Windows runner (1.1.1: with an empty support-data cache, the GUI opened offscreen); the wizard has not been clicked through by hand and the GUI not opened on a real Windows machine, and an upgrade over an installed 1.1.0 has not been tried. The graceful SIL close (M15) has not run on Windows | Unknown for interactive use on Windows | `AUDIT.md` sections 5 and 6; `packaging/README.md` |
| K-13 | Closed: the bundled CelesTrak space weather (observations to 2025-07-20) was refreshed for this release: observations to 2026-10-11, updated 2026-10-12. Refreshed again on 2026-10-19 for the next release: observations to 2026-10-18, CelesTrak's daily forecast to 2026-12-02, updated 2026-10-19 20:34 UTC. Refreshed for 1.3.0 on 2026-10-26: observations to 2026-10-24, daily forecast to 2026-12-07, updated 2026-10-25 23:32 UTC (CelesTrak revised its values from 2026-09-09 and the monthly forecast's 2027-01 and 2027-02). Results of drag runs dated after 2025-07-20 change, because observed solar activity replaces the earlier forecasts. Not refreshed for 2.0.0, 2.1.0, 2.1.1, 2.2.0, 2.3.0, 2.4.0, 2.5.0 nor 2.6.0: on 2026-11-03, twice on 2026-11-04, three times on 2026-11-05, on 2026-11-08 and on 2026-11-09 CelesTrak reset or refused every connection from the environment the release was prepared in, so 2.0.0 to 2.6.0 carry 1.3.0's file (observations to 2026-10-24, forecast to 2026-12-07). Refreshed for 2.7.0 on 2026-11-10: observations to 2026-11-09, daily forecast to 2026-12-24, updated 2026-11-10 21:33 UTC (CelesTrak revised its observed values from 2026-09-17 and NOAA the monthly forecast's 2027-01 to 2031-09, which no run uses while an MSFC prediction is there); drag on dates from 2026-09-17 to 2026-12-24 changes, no template does. Users fetch the current one in the app (Home's reference-data card, **Settings > Reference data**) or with `spacemissionstudio spaceweather-download` | Drag on dates after 2026-11-09 uses CelesTrak's forecast until the file is fetched | `spacemissionstudio/data/spaceweather/README.md` |
| K-14 | Addressed, under watch: platform test failures. On Windows, two tests fail intermittently in CI (PR #64, 2026-10-14; each passed on the same commit in another run). `test_the_altitude_trade_runs_its_altitudes_in_parallel_processes`: a worker hit a Basilisk error whose exception cannot be pickled, so its message is lost (cause not yet known; suspected: the cached space-weather file opened by one worker while another replaces it). `test_a_step_without_deadline_waits_while_earlier_steps_are_still_answered`: its fake flight software went over the 0.3 s step timeout on a loaded runner (a test margin). On macOS (PR #65, 2026-10-14), `test_forms_stay_at_a_readable_width` and `test_a_template_row_keeps_its_customize_button_close` fail their own precondition: Qt's `cocoa` platform fits the 2560 x 1440 test window to the runner's screen, so the page is 618 px wide and there is no wide screen to check (a test set-up problem, not the layout). Fixed on the ROE branch (PR #73, commit `f601576c1`, 2026-10-18): the test window is laid out with `WA_DontShowOnScreen`, which the screen does not constrain, and the fixture asserts its 2560 x 1440 size; macOS CI then passed both (3347 passed, 0 failed, 11 skipped, run 39165811899). On the release commit `f288e0c73` (run 38633749308) Windows passed (3224 passed, 16 skipped) and macOS failed these two (3229 passed, 2 failed, 11 skipped). By the user's decision 1.0.0 is a Linux release; Windows and macOS are fixed and released later. Windows pair addressed on 2026-10-18 (after PR #73): the SIL test's step timeout is 1 s against 30 ms answers (it was 0.3 s against 20 ms), and the altitude trade's lost message is a confirmed bug, now fixed: Basilisk's `BasiliskError` cannot be pickled (its module `_bskLogging` does not import by that name), so any Basilisk error in a worker arrived as a pickling error. Workers now send such an error as a `BudgetError` with its type, message and traceback. The suspected cause is removed too: a complete space-weather file is no longer replaced by a second worker's copy, which on Windows could meet the first worker opening it. The Basilisk error behind the 2026-10-14 failure was never seen, so its cause is not confirmed; if it recurs, its message now shows. macOS, 2026-10-19 (PR #75, run 39218996167): `test_the_keys_work_where_results_has_the_focus` timed out waiting for its window to become active (passed on the PR's previous commit). On macOS activation is per application, and the parallel test workers are separate processes whose windows can keep it from this one; the test now sets Qt's active window itself (`QApplication.setActiveWindow`), which is what the shortcut map checks. Not reproducible on Linux (offscreen activates every shown window); confirmed only by the next macOS CI runs. Windows, 2026-10-19 (PR #76, job 118026573080): `test_thousands_of_dropped_steps_never_block_the_link[tcp]` failed with "the flight software took no STEP for 10 s" at step 16172 of 20000; the other Windows job on the same commit and the one re-run passed. The fake flight software was waiting to read when the link closed, so the simulation side's send found the socket not writable for 10 s, or did not run for that long. Cause not confirmed: not reproduced on Linux in 60 runs under CPU overload. A related defect was confirmed and fixed: `SocketTransport.send` gave up as soon as its time had run out, before trying the socket again, so a stall of the simulation's own process counted as the flight software's silence. The send now counts its time from the last bytes the peer took and tries once more without waiting before it gives up (`test_a_stall_of_this_process_is_not_the_peers_silence`, which fails on the previous code). Whether this was the Windows failure is confirmed only if it does not recur. It recurred on 2026-10-21 (PR #90, job 119083739177, on the 1.1.1 release commit `9dca37d5f`): the same message at step 10907 of 20000, and again the fake flight software was waiting to read when the link closed. So the send's stall handling was not the cause, and the cause is still not known. Not a Basilisk thread holding Python's interpreter lock: a Basilisk run in a second thread let the other thread run at least every 0.03 s (measured on Linux). Only this test has shown it (20000 steps, every one dropped, over TCP on a Windows runner); it may also stop a Windows SIL session that drops thousands of steps, with "the flight software took no STEP for 10 s". Not reproduced since (PR #91, 2026-10-21): the test alone passed 240 times on `windows-latest` (four workers side by side, two processes keeping the CPU busy) and the whole suite passed seven times on Windows (six runs of the new workflow "SpaceMissionStudio SIL stress (Windows)" and the platforms job). On a stall the test now fails with the state of both ends of the link: frames sent and dropped, bytes received and not read, the socket buffer sizes, what the fake flight software last did, when, and its stack, and the last `select()` calls of the send. The next recurrence names its cause. It recurred three times on 2026-10-27 (runs 40526819275 and 40543074495, twice) and named it: every `select()` of the stalled send saw the socket readable and not writable, the fake flight software alive and reading its backlog (12462 frames sent, 4568 read). The send's 10 s limit counted only bytes the peer took, and Windows reopens a full receive window only once the reader has freed much of it, so a peer that was answering looked silent. Fixed in 2.0.0 (#128): bytes the peer sends count too (`SocketTransport.send`); `test_a_peer_that_keeps_answering_is_not_silent` fails without the fix | Windows: an altitude trade with several workers may have failed with an unexplained error; a recurrence now names the error. macOS: the wide-screen layout was not checked in CI until PR #73 | PR #64 and #65 comments |
| K-15 | Fixed (2026-10-19): a run around, or with a third body, `mars` or `jupiter` passed validation and then failed. The bundled DE430 ephemeris has the Mars and Jupiter system barycentres, not the planets: a `mars` run stopped the whole process with `SPICE(SPKINSUFFDATA)` (the GUI runs in its own process, so the app closed), and Basilisk has no body named `jupiter`. The schema now offers `mars barycenter` and `jupiter barycenter` (Basilisk gives them the planet's mass and radius) and refuses the two old names with the one to use; a test flies every offered body | A scenario with `mars` or `jupiter` could not be run, and in the GUI closed the app; no result was ever produced with them | `tests/test_central_bodies.py`; HISTORY.md |
| K-16 | Fixed (2026-10-19): a thermal sensor's heat balance used the solar flux at Earth's distance from the Sun on the epoch, whatever the central body. Basilisk's `sensorThermal` assumes 1366 W/m^2 at any distance, and the tool's correction of it took Earth's flux. The flux is now the one at the spacecraft's own distance from the Sun when the run starts (SPICE), for every central body | Thermal sensors around the Sun, Mercury or Venus ran too cold, and around Mars, Jupiter or Eros too hot: around Mars on 2030-01-01 they absorbed 1408 W/m^2 instead of 713 W/m^2. Runs around Earth or the Moon are unchanged | `tests/test_sensor_thermal_flux.py`; HISTORY.md |
| K-17 | Fixed (2026-10-19): coarse sun sensors read the Sun in the planet's shadow. Basilisk's `coarseSunSensor` takes the eclipse as an optional input and, with it unlinked, counts itself fully lit; the tool linked it for thermal sensors and solar panels but not for sun sensors. Both the per-sensor telemetry and the cluster behind the CSS sun-heading estimate now take the spacecraft's eclipse message | In eclipse, sun-sensor telemetry was as in sunlight (template 14: 0.73 in Earth's shadow, now 0.0), and the CSS sun-heading estimate kept the true Sun direction, which real sensors cannot see. Runs that never enter a shadow are unchanged | `tests/test_template_claims.py::test_14_css_estimate_settles_on_the_sun_axis_and_is_lost_in_the_shadow`; HISTORY.md |
| K-18 | Fixed in 1.1.0 (2026-10-20, before its publication): a Monte Carlo batch started from the GUI with `thread_count` 1 (the default, and template 09) failed every run. Basilisk's `MonteCarlo.Controller` calls `signal.signal()` at the start of each case, which Python allows only on a process's main thread, and with one thread the controller runs the cases in the calling process: the GUI's worker `QThread`. The GUI now runs the batch in a spawned child process (`gui/monte_carlo_process.py`); Basilisk is unchanged | In 1.0.0 and the first 1.1.0 candidate, GUI batches with one thread produced no results ("N of N runs failed"). The command line runs batches on its main thread and is not affected; with more than one thread each case runs in a pool process, so GUI batches should not have been affected either (read from the controller, not re-run on 1.1.0). Found by the UI screenshot harness | `tests/gui/test_run_worker.py::test_monte_carlo_worker_runs_a_single_thread_batch`; HISTORY.md |
| K-19 | Limitation (2026-10-20, re-measured 2026-10-22): applying a theme (Settings > Appearance, or a change of the desktop's scheme with System) took about 2.0-2.1 s on a main window with template 23 open, against 6.1 s for the interface before the overhaul on the same machine (`docs/ui/BEFORE_AFTER.md`). Re-measured 2026-10-26 after a fix (every switch set the Fusion style again, a second restyle of every widget): 1.0-1.2 s with the same probe, against 2.0-2.2 s for the code before the fix in the same session; about 0.5 s in a session that has not opened the spacecraft editor dialog. After 1.3.0 (2026-10-26), the hidden spacecraft form kept for messages' titles (about 1,000 widgets) is no longer kept: 359 ms against 532 ms with every template opened, then template 23. The overhaul brief's target is 0.1 s. Qt re-polishes every widget under the application style sheet, shown or not, at a fixed cost per widget (a one-rule sheet takes about 0.3 s of it) | The window does not respond for that time after a theme change | `docs/DECISIONS.md` M1, M9; `docs/ui/BEFORE_AFTER.md` |
| K-20 | Fixed in 1.1.1 (2026-10-20): the 1.1.0 installers built a virtual environment while installing. The setup program stopped before its wizard when no Python 3.11 was on `PATH` ("SpaceMissionStudio needs Python 3.11 or later, which was not found"), and both needed internet access. The `.deb`'s `postinst` also fetched the SPICE kernels as root, into root's own cache (`~/.cache/bsk_support_data` of root), so every other user had no kernels until they downloaded them. The 1.1.1 installers carry their own Python and the data, in the folder Basilisk's `dataFetcher` reads for every user | 1.1.0: no install on a Windows machine without Python 3.11 on `PATH`; no offline install; Linux users other than root had to download the kernels | `packaging/README.md`, "The bundled Python"; HISTORY.md |
| K-21 | Fixed (2026-10-21): `test_autosave.py::test_read_with_no_recovery_file_returns_none` failed now and then on Windows CI (PR #89). A main window an earlier GUI test had left open kept its 30 s autosave timer; pytest-qt processes Qt events after each test's set-up, so the overdue tick wrote that window's scenario into the recovery file the test had just pointed at its temporary folder. Reproduced with a window holding template 22, as in the failure; the test now stops such timers first. A test defect: the app writes its recovery file only where it should | None for users | `docs/ui/TEST_CHANGES.md`; HISTORY.md |
| K-22 | Open (2026-10-21): on Windows CI a test worker crashed with "Windows fatal exception: access violation" in `tests/gui/test_template_wizard.py::test_wizard_is_sized_to_fit_its_own_busiest_page_not_a_flat_default[17_fuel_tank_depletion.json]` (PR #91, job 119157936897, commit `895ebcb96`); the other 3557 tests passed. The Python stack ends in pytest's call of the test, with no frame inside it, so the crash came in native code as the test returned, most likely when Python freed a Qt object whose C++ side Qt had already deleted. Seen once: the other seven whole-suite Windows runs of the same commit passed, and the file passed three times on Linux. The test and the wizard did not change in that PR. Cause not known | A crash of this kind could also end the app on Windows; none has been reported | PR #91 comment; HISTORY.md |
| K-23 | Limitation (2026-10-22): some actions hold the window for longer than the 50 ms the UI overhaul aims at, measured on one Linux container: opening a template 156-463 ms, the first visit to a spacecraft page 456 ms and the spacecraft editor dialog 381 ms (the editor is built at once; re-measured 2026-10-26 with the page built a section at a time: 157-168 ms, against 403 ms for the code before the change in the same session; the dialog used on its own still builds every section), the end of a run 474 ms (the results, the events and the garbage collector's full collections). Re-measured 2026-10-26 after 1.3.0, every template opened in turn: 72-134 ms (median 94 ms), against 82-459 ms (median 111 ms) for the code before the change in the same session; a scenario loaded is checked once, and the titles for spacecraft messages are prepared after start-up in turns of up to 0.13 s, once per process. The end of a run, re-measured 2026-10-26 after 1.3.0 (template 23, the longest stall of a 2 ms heartbeat): the first run of a session 191-244 ms before plotly's figure classes were loaded in a worker after start-up, 27-38 ms after; later runs 31-52 ms before, 31-35 ms after. Most are shorter than before the overhaul on the same machine; opening template 23 a second time measured 222 against 175 ms, one run each | The window does not respond for that time | `docs/ui/BEFORE_AFTER.md`; `docs/DECISIONS.md` M9 |
| K-24 | Limitation (2026-10-28): two Monte Carlo batches of the same scenario draw the same samples. Basilisk's Monte Carlo controller seeds Python's and NumPy's generators with the run number times 10 (`src/utilities/MonteCarlo/Controller.py`, `np.random.seed(simParams.index * 10)`) before a run's dispersions and model seeds are drawn, and disperses every model's seed itself, so `sim_settings.seed` does not change a batch. Not fixed from SpaceMissionStudio: the seeding is in Basilisk's controller, which this project does not change | Run k of every batch gets the same dispersed values; within a batch every run differs, as it should | Audit E5; `HISTORY.md` "Random seeds" |
| K-25 | Limitation (2026-10-28): the installers ship pillow 12.2.0, which has 52 published advisories (pip-audit; 13 fixed in 12.3.0, 39 in 13.0.0). The qualified Basilisk, bsk 2.12.0, requires pillow <= 12.2.0, so no fixed version can be installed with it. Every advisory is about decoding a crafted image file; neither SpaceMissionStudio nor the Basilisk modules it uses decodes an image with pillow (searched: no Image.open, imread or imsave), and pillow is loaded only because Basilisk imports matplotlib. CI's pip-audit accepts exactly these 52 (`packaging/audit-exceptions.txt`) and fails on any other | None found in what the app does; a script block that opened an image with pillow would be exposed | `packaging/audit-exceptions.txt`; HISTORY.md "Dependency security" |
| K-26 | Limitation (2026-11-03): 1.3.1 and earlier do not open a scenario file saved by 2.0.0. They refuse any key they do not know, and 2.0.0 saves fields added since, starting with `sim_settings.seed` (audit E5), which it always writes: 1.3.1's `load_scenario` refused all 31 templates as 2.0.0 saves them ("malformed scenario structure (SimSettings.__init__() got an unexpected keyword argument 'seed')"). 2.0.0 opens every 1.x file (its 31 templates as 1.3.1 saved them load) | A team updates together; a file saved by 2.0.0 and sent to a 1.x user does not open | `CHANGELOG.md` 2.0.0, Who should update |
| K-27 | Limitation (2026-11-04): 2.0.0 does not open a scenario file saved by 2.1.0 that uses a field added since: a mount, model equipment, a stowed pose, a material or maturity, model analyses, face properties, a mass budget or launcher, or an IDM-CIC import (`source_id`, an import record of target `model`). It refuses unknown keys, naming the first ("spacecraft[0].sensors[0]: unexpected field 'mount', not one this version knows"; "spacecraft[0].model.parts[0]: unexpected field 'subsystem'..."). Every new field is written only when set, so a file that uses none opens: checked with 2.0.0's code on the 32 templates as 2.1.0 saves them (31 open; template 32, which uses mounts, is refused). 2.1.0 opens every 2.0.0 file | A file using the new fields, sent to a 2.0.0 user, does not open | `CHANGELOG.md` 2.1.0, Who should update |
| K-28 | Limitation (2026-11-04): the IDM-CIC import is verified against hand calculations on a synthetic model (`tests/test_idm_import.py`), not against IDM-CIC's own mass, centre-of-gravity and inertia report, which no example model stores. Some conventions are assumed and reported in each import's summary (the extruded shapes' corner, sphere and torus centres, inward thicknesses, the tank's straight part). Unsupported shapes (STEP, Collada, pipes, labels, intersections, section planes) become point masses; a typed-in inertia, margins and maturity levels are reported, not applied. The IDM-CIC licence was not available to review; the reader uses the format's published description only | Mass properties of models with assumed or unsupported shapes are approximate, as their summary says | `docs/developer/idm-cic-integration.md` sections 12 and 14; `docs/reference/limitations.md` |
| K-29 | Fixed in 2.1.1 (2026-11-04), reported by the user on 2.1.0: (1) the 3D model editor was a modal dialog of the main window; GNOME attaches a modal dialog to its parent, so dragging the editor dragged the whole application. (2) A scenario opened from a built-in template has the templates' folder as its folder, so the IDM-CIC import wrote its meshes there: "Permission denied" in an installed copy, the repository's templates in a source checkout. (3) That failed import had already added its parts, which named a mesh file the model did not have, so the editor's OK refused the model ("mesh_index must name one of the model's 0 mesh file(s)"). (4) Vizard's battery panel showed watt-seconds ("2520000 / 2520000 W-s" for 700 Wh), the numbers Basilisk's battery message carries. Each fix has a test that fails on 2.1.0's code | 2.1.0: the editor could not be moved apart from the main window; no IDM-CIC import into a scenario opened from a template; a confusing battery unit in Vizard. Workaround in 2.1.0: save a template-based scenario as your own file before importing | `CHANGELOG.md` 2.1.1; `docs/ui/TEST_CHANGES.md`; HISTORY.md |
| K-30 | Limitation (2026-11-05): 2.2.0 does not open a scenario file saved by 2.3.0 in which an IDM-CIC import added devices or set the power budget: its import record's target (`devices`, `power`) is one 2.2.0 does not know ("imports[1].target must be one of ('orbit', 'model')"). Checked with 2.2.0's code on three files saved by 2.3.0 after an IDM-CIC import: the model only (opens), devices added (refused), the power budget set (refused). 2.3.0 opens every 2.2.0 file | A file using them, sent to a 2.2.0 user, does not open | `CHANGELOG.md` 2.3.0, Who should update |

| K-31 | Limitation (2026-11-05): a spacecraft whose body frame origin 2.4.0 put at the centre of gravity (`idm-import --origin cog`) opens and validates in 2.3.0, but a re-import of its IDM-CIC model in 2.3.0, which does not know the recorded origin, puts the model's parts and point masses back in the body element's frame and leaves the other positions (devices, facets, tank) at the centre of gravity's: the spacecraft's positions no longer agree. Checked with 2.3.0's code on the devicesat fixture: after the re-import the centre of mass is 0.447 m from B and the gyro where 2.4.0 put it | A team re-importing in 2.3.0 a file saved by 2.4.0 with the origin at the centre of gravity | `CHANGELOG.md` 2.4.0, Who should update |

| K-32 | Closed in 2.7.0 (#247): the tool no longer starts any external viewer, so none the user chooses runs from it. Before, limitation (2026-11-09): the Vizard AVS Lab publishes has Unity Analytics switched on (its project settings, Unity's analytics libraries, AVS Lab's Unity project ID and Unity's event addresses, read from the program on 2026-11-09; it was not run, so what it sends was not measured). 2.6.0 no longer downloads or looks for Vizard and ignores a copy an earlier version downloaded; a Vizard the user chooses in **Settings > Vizard** is still started, as a separate program outside the tool's network rules. A build of Vizard without analytics was prepared (`0h3xn4/vizard`, branch `sms/telemetry-free-build`) and parked: it needs a Unity licence, and **Results › 3D View** replaces the need | A user who starts AVS Lab's Vizard may send usage data to Unity | security analysis S-05; `CHANGELOG.md` 2.6.0, Removed |

| K-33 | Limitation (2026-11-10): the bundled NASA MSFC solar-cycle prediction is the October 2026 issue (`oct2026f10-prd.txt`). The November 2026 issue (`nov2026f10-prd.txt`) was published before 2.7.0 was prepared; it moves the 2030 values a little (January 2030 at the 50th percentile: F10.7 74.1 sfu and Ap 11.3, were 74.2 and 11.5), so adopting it changes every template's drag and golden outputs, and is the owner's decision, not taken for the release | Drag after CelesTrak's daily forecast uses the October 2026 prediction unless the study sets its own file (**MSFC prediction**, Scenario › Environment) | `spacemissionstudio/data/spaceweather/README.md`; `CHANGELOG.md` 2.7.0, Known limits |

**Waivers and deviations:** D-01 to D-13 (RD4). D-08 to D-13 are signed; D-01 to D-07
are not (decision 14, H08).

## 6 Operational aspects (G.2.1<6>)

- **Use the installers, or Python 3.14 with Basilisk 2.12.0.**
  The installers carry Python 3.14.8, Basilisk 2.12.0 and the versions
  in `packaging/constraints.txt`. Other Basilisk versions run, but with a
  warning: their results are not covered by the validation.
- **Earth orientation:** the installers carry the IERS-based files as
  current as their build; for later runs, fetch newer ones:
  - the reference-data card on Home at start-up, or **Settings >
    Reference data**, or
  - `spacemissionstudio earth-orientation --fetch`.

  Installed from source, install them before any run with a gravity
  field. Without them, the Earth frame costs about 160 m/day at degree 20.
- **Re-run drag-dependent studies made with earlier versions.** F-07
  changes drag.
- **Re-run propellant budgets made with 1.x** (E2) and lifetimes at the
  critical inclinations (E1).
- **Fetch the current space weather before a drag study** (K-13): the
  bundled file's observations end on 2026-11-09, and its MSFC prediction
  is October 2026's (K-33).
- **Update a team together** (K-26, K-27, K-30, K-31).
- **Run script blocks only from scenarios you trust and have read**
  (SUM 9.9).
- **Exchanging OEMs with GMAT R2026a:** use
  `run --oem-interpolation lagrange`, and convert to version 1.0
  (F-08).

## 7 Future evolutions (G.2.1<7>)

Planned, in order:
1. Windows: fix K-22, and run the installers by hand (K-06, K-12).
2. The interface's remaining pauses (K-19, K-23): the spacecraft editor
   built a tab at a time (done for the Scenario editor's page,
   2026-10-26), a theme change that restyles what is shown first.
3. The human actions of RD4: reviews, PA organisation, signatures;
   and the definition of done's timing with an engineer who did not
   build the tool (`docs/definition-of-done.md`).

Dropping the two Basilisk workarounds also depends on Basilisk: they go
once a qualified Basilisk release fixes F-01 and F-07 (H10).
