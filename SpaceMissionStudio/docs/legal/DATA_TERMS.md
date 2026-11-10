# Reference data: provider, terms, redistribution

Milestone M1 of [`PHASE1_PLAN.md`](PHASE1_PLAN.md). This is not legal advice.
It records what each provider's own page says, read on **2026-11-09** by a
helper agent from the URL shown. I re-read three of the sources myself (ECSS,
NAIF, ITU) and they match. `VERIFIED` means the provider's page states the
term. `OPEN` means no term was found or the page could not be read.

The same facts are in `packaging/legal/components.json` (field
`redistribution_status`); the licence gate warns on `open` and fails on
`restricted` (`packaging/legal/README.md`).

## Decisions needed from you

| # | Item | Why | Options |
|---|---|---|---|
| D1 | **DECIDED 2026-11-10: not bundled, no contact with ITU** (owner). Before: **ITU-R P.676-13 data file, bundled in both installers** | ITU: "No part of this publication may be reproduced, by any means whatsoever, without written permission of ITU." The data file is "an integral part of this Recommendation". Status: `restricted`. | (a) Write to `jur@itu.int` for permission and keep the file; (b) stop bundling it: the app already fetches it on request (`gaseous-attenuation --fetch`), but the installers are meant to work offline, so this changes what the installers do. Until you decide, the Linux bundle build **fails the licence gate**. |
| D2 | **CelesTrak `SW-All.txt`, in the repository and the wheel** | No CelesTrak page states a licence or redistribution term. The data folder's README says CelesTrak permits it, but the pages I could read do not say so. | Ask CelesTrak (Dr. T.S. Kelso) in writing, or stop bundling and use the fetch. |
| D3 | **ECSS requirement text in `compliance/requirements/*.csv`** | ESA holds the copyright; "No ECSS document may be reproduced in any form without the explicit consent of ESA." See §8. | Ask ECSS for consent (`ecss-secretariat@esa.int`), or replace the text by clause number and title. A replacement touches the compliance tools; I will not do it without your yes. |
| D4 | **Seven Basilisk support-data files** (GGM03S, GGM2B, two albedo maps, US 1976, Earth-GRAM, NRLMSISE-00 tables) | No term found for any of them. | Read the providers' pages (more hosts needed), ask, or drop files the app does not need. |
| D5 | **CCSDS 502.0-B-3 example messages** (`tests/data/ccsds/*.txt`) and requirement text | The CCSDS site could not be read from this sandbox. | Allow `public.ccsds.org` or paste the Blue Book's copyright notice. |
| D6 | **MSFC solar-cycle table** | NASA says its content is "generally not subject to copyright in the United States" (media guideline); no statement for this data file; its inputs come from SILSO, Environment Canada and GFZ. | Write to the MSFC contact on the page. |
| D7 | **IERS C04 excerpt in `tests/data/validation/`** | No licence or citation term on any Paris Observatory page read. | Ask the EOP Product Centre; the excerpt is a test fixture, so it can also be replaced by synthetic data. |

## 1. NASA/JPL NAIF SPICE kernels: VERIFIED

Used: `naif0012.tls`, `de430.bsp`, `de-403-masses.tpc`, `pck00010.tpc`, the
Earth-orientation `earth_*_combined.bpc` and `earth_latest_high_prec.bpc`
(bundled), 433 Eros kernels (fetched at run time only).

* Source: <https://naif.jpl.nasa.gov/naif/rules.html> (page last modified 2024-04-20), <https://naif.jpl.nasa.gov/naif/credit.html>.
* "Redistribution of SPICE kernels distributed by NAIF is permitted as long as they have not been modified. If a kernel distributed by NAIF has been modified in any way, any embedded or otherwise allied attribution of the original kernel producer must be replaced with the name and institution of whomever has made the last modification." (quotation)
* "No fees or licensing are required. Acknowledgement of the use of NASA's SPICE system is encouraged." (quotation)
* The page also carries a disclaimer and an indemnity clause for recipients of NAIF *software*; kernels are data.
* **What the project does:** keeps the kernels byte-identical with the registry hashes (the bundle checks Basilisk's checksums), cites Acton 1996 and Acton et al. 2018 in `THIRD_PARTY_NOTICES`.
* **Open:** the Eros kernel path and its kernel comments; kernels from "any other entity" follow that entity's rules.

## 2. CelesTrak space-weather file: OPEN

* Pages read: <https://celestrak.org/SpaceData/>, `.../SpaceWx-format.php`, <https://celestrak.org/webmaster.php>. None has a copyright, licence, redistribution or citation statement. A direct download from this sandbox was reset by the server.
* The data derive from GFZ Potsdam (Kp/ap), SILSO (sunspot number), spaceweather.gc.ca (F10.7), NOAA SWPC (forecasts) and NASA (monthly predictions); their terms were not read (hosts not allowed).
* The repository's own data README quotes Dr. Kelso: only the URL is asked. That is a statement in this repository; I found no matching statement on a CelesTrak page. **Decision D2.**

## 3. NASA MSFC solar-cycle prediction: partly open

* <https://www.nasa.gov/solar-cycle-progression-and-forecast/>; media guideline <https://www.nasa.gov/nasa-brand-center/images-and-media/>.
* "generally are not subject to copyright in the United States"; "NASA's use does not convey any rights to others to use the same material" for third-party material. The NASA insignia is not in the public domain (the project does not use it).
* The page names third-party inputs (SILSO, Environment Canada, GFZ). **Decision D6.**

## 4. ITU-R P.676-13 data file Part 1: restricted

* <https://www.itu.int/oth/R1101000002/en>, <https://www.itu.int/en/Pages/copyright.aspx>, the Recommendation PDF.
* Recommendation, first page: "(c) ITU 2022 All rights reserved. No part of this publication may be reproduced, by any means whatsoever, without written permission of ITU."
* Website copyright page: "ITU holds copyright in the information available on this Web site, unless otherwise stated." "Request for permission to reproduce the ITU materials available on this Web site should be sent to jur@itu.int." (quotation, re-read by me)
* The data file has no licence header. "Free" on ITU's page describes access, not redistribution. **Decision D1.**

## 5. NOAA/NCEI World Magnetic Model WMM2025: VERIFIED

* <https://www.ncei.noaa.gov/products/world-magnetic-model>.
* "The WMM source code is in the public domain and not licensed or under copyright. The information and software may be used freely by the public. As required by 17 U.S.C. 403, third parties producing copyrighted works consisting predominantly of the material produced by U.S. government agencies must provide notice with such work(s) identifying the U.S. Government material incorporated and stating that such material is not subject to copyright protection." (quotation)
* Citation: NOAA NCEI Geomagnetic Modeling Team; British Geological Survey. 2024: World Magnetic Model 2025. doi:10.25921/aqfd-sd83. The citation and the 17 U.S.C. 403 notice are in `THIRD_PARTY_NOTICES`.
* **Open (small):** compare the checksum of the bundled `WMM2025.COF` with NCEI's current file.

## 6. Basilisk support data (as fetched by Basilisk's data fetcher)

Basilisk's repository documents no licence or source for these files except
the atmosphere README ("All of the data provided here are from publicly
available sources and not export-controlled", which is not a licence grant).

| File | What Basilisk says | Provider's terms | Status |
|---|---|---|---|
| `GGM03S.txt` | nothing | UT Austin Center for Space Research; page not readable here | OPEN |
| `GGM2BData.txt` | nothing | NASA PDS; host not allowed | OPEN |
| `Earth_ALB_2018_CERES_All_5x5.csv` | from CERES, converted to CSV | NASA CERES; host not allowed | OPEN |
| `Mars_ALB_TES_5x5.csv` | from TES, converted to CSV | ASU Mars Space Flight Facility; host not allowed | OPEN |
| `USStandardAtmosphere1976.csv` | table from a third-party web app (digitaldutch.com) | web app's terms not read; the 1976 report is NOAA/NASA/USAF | OPEN |
| `EarthGRAMNominal.txt` | output of Earth-GRAM2016, "under General Public Release from NASA but must be requested for download" | `software.nasa.gov`; host not allowed | OPEN |
| `NRLMSISE00Nominal.txt` | output of CCMC ModelWeb | CCMC publication policy asks for acknowledgement; says nothing about redistribution | OPEN |

**Decision D4.** The app uses only part of these; the notices will name the
sources and credits once the terms are read.

## 7. IERS Earth-orientation parameters (test fixture)

<https://hpiers.obspm.fr/iers/eop/eopc04/>: no licence, copyright or citation
statement on the directory, the readme or the file header. The file header
names a person's e-mail address; the repository copy keeps it as the source
file has it. **Decision D7.**

## 8. Standards: ECSS and CCSDS

**ECSS: VERIFIED** (<https://ecss.nl/license-agreement-disclaimer/>, re-read by me; it quotes ECSS-P-00C clause 5.8):

* "The European Space Agency, on behalf of the participating members, holds copyright for all ECSS documents. No ECSS document may be reproduced in any form without the explicit consent of ESA." (quotation)
* For non-members: "direct use of ECSS standards themselves should be made rather than rewriting using quotation of ECSS standards." Where text is used, "ECSS copyright is acknowledged, quotations clearly identified in the document together with exact reference/version" and the Steering Board decides. Contact: `ecss-secretariat@esa.int`.
* **Consequence:** `compliance/requirements/ECSS-*.csv` (about 1,380 rows of requirement text) is a reproduction. **Decision D3.**

**CCSDS: OPEN.** `public.ccsds.org` was blocked. No statement was read.

## 9. Qt and Qt WebEngine (LGPL-3.0)

* The Qt Company, <https://www.qt.io/development/open-source-lgpl-obligations> (read 2026-11-09): "Complete corresponding source code of the library used with the application or the device built using LGPL, including all modifications to the library, should be delivered with the application (or alternatively provide a written offer with instructions on how to get the source code). It should be noted that the complete corresponding source code has to be delivered even if the library has not been modified at all." The user must be allowed "to change and re-link the library". A copy of the LGPL text and "a prominent notice about using the LGPL library" are needed. (quotations)
* Qt WebEngine: "users need to comply to both the licenses of the Qt WebEngine part ... as well as the licenses that are part of Chromium"; the Chromium part's most restrictive licence is LGPL-2.1; the list has about 100 components (<https://doc.qt.io/qt-6.11/qtwebengine-licensing.html>).
* Some Qt modules are **GPL only** for open-source use (for example Qt Graphs, Qt Quick 3D, Qt Virtual Keyboard, Qt Wayland Compositor, Qt MQTT, Qt HTTP Server; <https://doc.qt.io/qt-6/licensing.html>). The `PySide6_Addons` wheel is installed whole. **Open:** list which of these modules' libraries sit in the bundle; the app does not use them. A measure in your power: remove unused Qt modules from the installers (a change of packaging contents, to decide).
* Source archives, Qt 6.11.3 (<https://download.qt.io/official_releases/qt/6.11/6.11.3/>): `qtbase` 48 MB (`.tar.xz`), `qtwebengine` 554 MB (`.tar.xz`), the whole `single` archive 973 MB. The 6.11 folder also lists CVE patches for several modules. The bundled version is 6.11.2, so the matching archive is in `6.11.2/`. **Open:** my plan to attach the exact archives to each release (the largest is under GitHub's 2 GiB limit per file; I did not verify that limit from GitHub's page).
