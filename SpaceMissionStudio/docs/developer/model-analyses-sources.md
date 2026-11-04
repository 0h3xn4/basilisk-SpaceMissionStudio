# Sourced default values for small-satellite (100-500 kg) design analyses

Compiled 2026-11-03 while building the model analyses, by reading the
sources from the build environment. Each value below is either
**VERIFIED**, read in the cited document, or **NOT VERIFIED**. The notes
are the reader's own, kept as written (first person).

## Access limitations (read first)

This session's network allow-list let me reach only `ntrs.nasa.gov` (and `www.nasa.gov`). These hosts were blocked (proxy 403 / DNS refused):
moog.com, spacex.com, esa.int (sci/technology/indico), iso.org, legifrance.gouv.fr,
population.un.org / un.org, nssdc.gsfc.nasa.gov, orbitaldebris.jsc.nasa.gov,
standards.nasa.gov, iopscience.iop.org, arxiv.org, terma.com, jena-optronik.de, sodern.com, amostech.com.
So every VERIFIED value comes from a NASA NTRS PDF that I downloaded and read with
`pdftotext`. I checked equations that were images by rendering the page.
For values marked "search snippet only", I saw the number in a web-search summary but could not open the
source. Treat them as **NOT VERIFIED**.

All NTRS URLs have the form `https://ntrs.nasa.gov/citations/<ID>`. The PDF is at
`https://ntrs.nasa.gov/api/citations/<ID>/downloads/<ID>.pdf`.

---

## 1. Mass maturity margins

| Item | Value | Status |
|---|---|---|
| ESA "Margin philosophy for science assessment studies", SRE-PA/2011.097: equipment margins (off-the-shelf / modified / new) and system margin | (commonly quoted as 5 / 10 / 20 % equipment and 20 % system) | **NOT VERIFIED**: document not found or accessible |
| ANSI/AIAA S-120A-2015 MGA table | - | **NOT VERIFIED**: standard is paywalled. NTRS 20250005278 (AIAA S-120B update slides) gives no percentages. It says only that the 2015 revision made Margin and MGA percentages "based on 'Basic Mass'". |
| **AIAA S-120-2006 MGA and depletion schedule** (the predecessor of S-120A, reproduced by NASA) | see below | **VERIFIED** |

Source: NASA GRC COMPASS Team, *COMPASS Final Report: Advanced Long-Life Lander Investigating the Venus Environment (ALIVE)*, CD-2012-72, March 2012, Table 2.3 "MGA and Depletion Schedule (AIAA S-120-2006)", p. 10. NTRS 20160011272.
https://ntrs.nasa.gov/citations/20160011272 . The same table appears as Table 3 in NASA/TP-2020-220152 (NTRS 20200013062).

MGA [%] by maturity code (rows) and subsystem (columns):

| Cat. | Code: basis | Elec 0-5 kg | Elec 5-15 kg | Elec >15 kg | Structure | Brackets | Battery | Solar array | Thermal | Mechanisms | Propulsion | Wire harness | Instrumentation | ECLSS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E (estimated) | 1: Estimated | 30 | 25 | 20 | 25 | 30 | 25 | 30 | 25 | 25 | 25 | 55 | 55 | 23 |
| E | 2: Layout | 25 | 20 | 15 | 15 | 20 | 15 | 20 | 20 | 15 | 15 | 30 | 30 | 15 |
| C (calculated) | 3: Pre-release design | 20 | 15 | 10 | 10 | 15 | 10 | 10 | 15 | 10 | 10 | 25 | 25 | 10 |
| C | 4: Released design | 10 | 5 | 5 | 5 | 6 | 5 | 5 | 5 | 5 | 5 | 10 | 10 | 6 |
| A (actual) | 5: Existing hardware | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 2 | 3 | 3 | 5 | 5 | 4 |
| A | 6: Actual (measured) mass | 0 ("No mass growth allowance - use appropriate measurement uncertainty values") | | | | | | | | | | | | |
| A | 7: CFE / spec value | "Typically a 'not-to-exceed' value" | | | | | | | | | | | | |

System level: the same report (Sec. 2.4.2, p. 9) says COMPASS adds system-level growth so that the total is **30 %** of basic dry mass. This is a COMPASS practice, not an S-120 requirement.
Confidence: high for the S-120-**2006** values. S-120A-2015 may differ, so do not label these values "S-120A".

## 2. ESPA rideshare envelopes

| Item | Value | Source | Status |
|---|---|---|---|
| Standard ESPA | 6 ports, 15 in diameter, 180 kg/port, envelope "24"x24"x38"" | Burt & Steinfeld (NASA GSFC), *CapSat: A Low-Cost, Reliable, Rapid-Response Spacecraft Platform*, 2017 IEEE Aerospace Conf., GSFC-E-DAA-TN45679, slide "Historical Rideshare Data". NTRS 20180002117 | **VERIFIED (secondary)**. Note that the envelope here is 24x**24**x38 in, while most other sources give 24x**28**x38 in. Treat it as unconfirmed until the Moog guide is read. |
| ESPA Grande | 4 ports, 24 in diameter, 318 kg/port, envelope "42"x46"x56"" | same slide | **VERIFIED (secondary)** |
| USAF RUG form factor | "180kg, 15" diameter ESPA attached payload" | Burt & Steinfeld, *CapSat: an ESPA Class CubeSat Model*, NTRS 20180004071 | VERIFIED (secondary) |
| Moog ESPA User's Guide: envelope, mass, CG limits (e.g. 181 kg at CG <= 20 in / 50.8 cm; 24x28x38 in) | - | moog.com blocked | **NOT VERIFIED** (search snippet only) |
| SpaceX Rideshare Payload User's Guide: 15 in / 24 in plate envelopes, mass, CoM limits | - | spacex.com blocked | **NOT VERIFIED** |

Recommendation: do not ship ESPA defaults until the Moog ESPA User's Guide (current rev.) is read directly.

## 3. Re-entry casualty risk

**(a) Breakup altitude 78 km: VERIFIED.**
Liou et al., *Debris Assessment Software User's Guide, Version 3.0*, NASA/TP-2019-220300, July 2019. Sec. 3.8 (p. 33) and Sec. 4.1.3 (p. 47) say: "the outermost structure (i.e., the 'parent' object) is assumed to break apart at an altitude of 78 km."
NTRS 20190027721, https://ntrs.nasa.gov/citations/20190027721 .
The same assumption ("breakup occurring at 78 km") is used by Rochelle et al., *Spacecraft Orbital Debris Reentry: Aerothermal Analysis*, NTRS 19970040121. Confidence: high.

**(b) Casualty cross-section 0.36 m^2: VERIFIED (as 0.6 m = sqrt).**
R.L. Kelley, *Using the Design for Demise Philosophy to Reduce Casualty Risk due to Reentering Spacecraft*, IAC-12-A6.2.18, 2012, Sec. II.I, Eq. 1. It states: "The term 0.6 represents the square root of the average cross-sectional area of a standing person, as viewed from above." It attributes the method to NASA-STD-8719.14A. NTRS 20120002794.
0.6^2 = **0.36 m^2**, which I derived from that statement. I did not read NASA-STD-8719.14 itself (standards.nasa.gov blocked).

**(c) 15 J threshold: VERIFIED.**
DAS 3.0 User's Guide, Appendix B (reproducing NASA-STD-8719.14B Req. 4.7-1), p. B-6: "The potential for human casualty is assumed for any object with an impacting kinetic energy in excess of 15 joules."
Also in Sec. 3.8 p. 33 and the Glossary p. A-1 ("kinetic energy of 15 joules or greater").

**(d) Risk thresholds**

| Regime | Value | Status |
|---|---|---|
| NASA-STD-8719.14B Req. 4.7-1a (uncontrolled re-entry) | "shall not exceed 0.0001 (1:10,000)" | **VERIFIED** via DAS 3.0 UG Appendix B p. B-6 (verbatim reproduction of 8719.14B). Kelley 2012 also says "Since 1995 NASA has held a maximum human casualty risk of 1:10,000". |
| NASA-STD-8719.14B Req. 4.7-1b (controlled) | no surviving debris >15 J within 370 km of foreign landmasses or 50 km of US / Antarctic ice pack | VERIFIED (same page) |
| NASA-STD-8719.14**C** (if a newer revision exists) | - | NOT VERIFIED |
| ISO 24113:2023 | (search snippets suggest 1e-4) | **NOT VERIFIED** |
| ESA ESSB-ST-U-007 / ESA/ADMIN/IPOL(2023)1 | search snippet: "shall not exceed 1 to 10,000 (10^-4) for each re-entry event" | **NOT VERIFIED** (search snippet only, technology.esa.int blocked) |
| French Space Operations Act technical regulation (2e-4?) | - | **NOT VERIFIED**: no source found |

**(e) Sutton-Graves stagnation-point heating**
- Original form, **VERIFIED**: Sutton & Graves, *A General Stagnation-Point Convective-Heating Equation for Arbitrary Gas Mixtures*, NASA TR R-376, Nov. 1971, Eq. (33), p. 13: `K = q_w * sqrt(R / p_s) / (h_s - h_w)`. Table II (p. 38) gives K for air (0.2320 O2 - 0.7680 N2 by mass) = **0.1113 kg/(s m^1.5 atm^0.5)**. Average correlation error 3.3 %, maximum 9.8 %. NTRS 19720003329.
- Simplified form `q = K1 sqrt(rho/R_n) V^3`, **VERIFIED as a form**: Carroll et al., *Stagnation Point Convective Heating Correlations for Entry into H2/He Atmospheres*, AIAA Aviation 2022, Eq. (1). It also states that the form follows from Eq. (2) when h_e ~ V^2/2, h_w << h_inf and p_stag ~ rho V^2. NTRS 20220018610.
- **k = 1.7415e-4 kg^0.5/m for Earth: NOT VERIFIED** in any document I read. For reference, my own calculation from K_air = 0.1113 with p_s = rho V^2 and h_s - h_w = V^2/2 is K_air / (2 sqrt(101325 Pa/atm)) = **1.748e-4 kg^0.5/m**. Label it "derived from Sutton & Graves 1971 Table II" if you use it.

**(f) Casualty area formula: VERIFIED.**
Kelley 2012 (NTRS 20120002794) Eq. 1: `DCA = sum_{i=1..N} (0.6 + sqrt(A_i))^2`, with A_i in m^2. Expected casualties: `E = DCA x PD` (Eq. 2), where PD is the mean population density for the inclination and re-entry year.

## 4. Material properties (re-entry demise)

Source: **DAS 3.0 User's Guide, NASA/TP-2019-220300, Appendix C.6, Table C-4 "Properties of DAS 3 Built-In Materials", pp. C-6 to C-8.** NTRS 20190027721. **VERIFIED** (values copied from the table).

| Material (DAS name) | Density [kg/m^3] | Melt T [K] | Heat of fusion [J/kg] | Specific heat [J/(kg K)] |
|---|---|---|---|---|
| Aluminum 6061-T6 | 2707.0 | 867.0 | 386116.0 | 896 |
| Aluminum (generic) | 2700.0 | 850.0 | 390000.0 | 1100 |
| Titanium (6 Al-4 V) | 4437.0 | 1943.0 | 393559.0 | 450.0 < Cp < 1110.0 |
| Titanium (generic) | 4400.0 | 1950.0 | 470000.0 | 600 |
| Steel AISI 304 | 7900.0 | 1700.0 | 286098.0 | 482.0 < Cp < 608.0 |
| Steel AISI 316 | 8026.85 | 1644.0 | 286098.0 | 460.6 |
| Stainless Steel (generic) | 7800.0 | 1700.0 | 270000.0 | 600 |
| Cu alloy (copper) | 8938.0 | 1356.0 | 204921.0 | 385.0 < Cp < 472.0 |
| Inconel 718 | 8190.0 | 1571.0 | 311664.0 | 435 |
| Graphite epoxy 1 (CFRP) | 1550.50 | 700.0 | 232.6 | 879 |
| Zerodur (glass-ceramic) | 2530.00 | 1424.0 | 250000.0 | 800.0 < Cp < 1600.0 |
| Gallium Arsenide | 5316.00 | 1510.0 | 0.0 | 325 |

- **Emissivity: NOT in DAS Table C-4.** Section C.6 lists only specific heat, heat of fusion, melt temperature and density. I found no per-material re-entry emissivity in any read source (ORSAT, DRAMA and SESAM databases were not accessible). For context, Rochelle et al. 1997 (NTRS 19970040121) used "surface emittances of 1.0 and 0.3" in parametric runs and 0.3 for beryllium. These are analysis assumptions, not material data. For room-temperature emittance of metals, see item 6.
- Generic glass (fused silica / borosilicate): **NOT VERIFIED**. DAS lists only Zerodur and Macor.

## 5. Atomic oxygen erosion yields

Primary source: de Groh & Banks, *Atomic Oxygen Erosion Data From the MISSE 2-8 Missions*, NASA/TM-2019-219982, May 2019, Table 3. NTRS 20190025445. Cross-check: de Groh, Banks et al., *MISSE PEACE Polymers Atomic Oxygen Erosion Results*, NASA/TM-2006-214482, Table 4, p. 17, NTRS 20070002707. **VERIFIED.**

| Material | Ey [cm^3/atom] | Mission / note |
|---|---|---|
| Kapton H (PMDA polyimide) | **3.00e-24** (stated as 3.0 +/- 0.07e-24 for LEO 4.5 eV AO, TM-2019-219982 p. 2) | reference witness material |
| Kapton HN | 2.81e-24 | MISSE 2 |
| Mylar / PET | 3.01e-24 (MISSE 2); 3.22e-24 (MISSE 7) | |
| Teflon FEP | 2.00e-25 (MISSE 2); 1.69e-25 (MISSE 7) | |
| Al-backed FEP (silvered/aluminised Teflon) | 2.11e-25 (MISSE 2) | |
| Teflon PTFE | 1.42e-25 (MISSE 2); 1.33e-25 (MISSE 7) | |
| Black Kapton XC (10^-7 ohm/sq) | 2.20e-24 | MISSE 7 |
| Black Kapton CB | 2.70e-24 | MISSE 7 |
| Polyimide clear CP1 | 1.91e-24 | MISSE 2 |
| Silicone DC 93-500 | 3.81e-27 | MISSE 8; "silicones convert to a glassy silicate layer" |

- **ASTM E2089 citation: NOT VERIFIED directly.** The 3.0e-24 value is attributed in TM-2006-214482 to Banks 1997 (*Modern Fluoropolymers*, ch. 4). E2089-00 is cited by NASA/TM-2009-215812 and NASA/TM-2011-216904 for ground-test practice. I did not read the ASTM standard.
- **Metals, VERIFIED (qualitative):** Banks, Miller & de Groh, NASA/TM-2004-213223 (AIAA-2004-5638), NTRS 20040087142: "for most metals, the oxides tend to shield the underlying metal from oxidation. Silver is one exception, because silver oxide tends to spall". Banks, de Groh & Miller, NASA/TM-2004-213400, NTRS 20040191331, p. 3: "The atomic oxygen erosion yield is not a meaningful number for materials such as most metals and silicones." Use Ey ~ 0 for Al, Au and anodised Al, and flag Ag as non-negligible (no numeric Ey given).
- Anodised aluminium specifically: **NOT VERIFIED** (no explicit statement found; covered by "most metals").

## 6. Optical properties (solar absorptance alpha_s / normal emittance eps_n)

Source: J.H. Henninger, *Solar Absorptance and Thermal Emittance of Some Common Spacecraft Thermal-Control Coatings*, NASA RP-1121, 1984 (GSFC, Dec. 1983). NTRS 19840015630. **VERIFIED.**
The report says these are average values with a typical tolerance of +/-0.02. eps is **normal** emittance at ~300 K.

| Surface | alpha_s | eps_n | Table (section) |
|---|---|---|---|
| Z-93 white paint (Zerlaut) | 0.17 | 0.92 | White Coatings, p. 8 |
| S-13G white paint (Zerlaut) | 0.20 | 0.90 | White Coatings, p. 8 |
| Chemglaze Z306 black paint | 0.96 | 0.91 | Black Coatings |
| 3M Black Velvet paint | 0.97 | 0.91 | Black Coatings |
| Kapton film, Al backing (MLI outer layer, Kapton facing out), 1.0 mil | 0.38 | 0.67 | Films and Tapes, p. 15 |
| same, 2.0 mil / 5.0 mil | 0.41 / 0.46 | 0.75 / 0.86 | p. 15 |
| Teflon, silver backing (silvered Teflon), 5 mil / 10 mil | 0.08 / 0.09 | 0.81 / 0.88 | p. 16 |
| Teflon, aluminium backing, 5 mil | 0.13 | 0.81 | p. 16 |
| Second-surface mirror, silver backing (Helios OSR), initial | 0.07 | 0.79 | Composite Coatings, p. 14 |
| Buffed aluminium | 0.16 | 0.03 | Metals, p. 11 |
| Vapour-deposited aluminium | 0.08 | 0.02 | Vapor-Deposited, p. 12 |
| Electroplated gold | 0.23 | 0.03 | Metals, p. 11 |
| Vapour-deposited gold | 0.19 | 0.02 | p. 12 |
| Stainless steel, polished | 0.42 | 0.11 | p. 11 |
| Buffed copper | 0.30 | 0.03 | p. 11 |
| Inconel X foil (1 mil) | 0.52 | 0.10 | p. 11 |
| Vapour-deposited titanium | 0.52 | 0.12 | p. 12 |
| Opal glass | 0.28 | 0.87 | White Coatings |
| Solar cells (Si-era flight values, e.g. IUE / OAO) | 0.77 to 0.91 | 0.79 to 0.86 | Solar Cells, p. 13 (not GaAs) |

- **Triple-junction GaAs cell with coverglass, VERIFIED (modelled):** Russell & Jones (Thales), *Development of a High Efficiency UVR/IRR Coverglass for Triple Junction Solar Cells*, Proc. 19th Space Photovoltaic Research and Technology Conf. (SPRAT XIX), 2007, Table 1. NTRS 20090022294. With an AR-coated coverglass (baseline): alpha_s = **0.895**, eps(5-50 um) = **0.89**. With UVR/IRR coverglass: alpha_s = 0.797, eps = 0.88. Confidence: medium (a vendor model, not a measurement compilation).
- **AZ-93, S13G-LO, and the Gilmore Handbook tables: NOT VERIFIED** (not accessible).

## 7. Brightness

- **Sun V magnitude -26.74, VERIFIED (secondary):** Hostetler & Cowardin, *Experimentally-Derived Phase Function Approximations in Support of the Orbital Debris Program Office*, 1st International Orbital Debris Conference (IOC), Dec. 2019, paper IOC 6148 / JSC-E-DAA-TN73676, Eqs. (7) to (9): "M_abs(v) = -26.74 + Delta mag". NTRS 20190033905.
- **Willmer 2018, ApJS 236:47: NOT VERIFIED** (iopscience/arXiv blocked).
- **Lambertian sphere phase function, VERIFIED:** same paper, Eq. (10): `f(phi) = (2/(3 pi^2)) [sin(phi) + (pi - phi) cos(phi)]`, with Eq. (11) f(0) = 0.212207 (= 2/(3 pi)). It attributes the function to Barker et al., *Analysis of Working Assumptions in the Determination of Populations and Size Distributions of Orbital Debris from Optical Measurements*, 2004 AMOS Technical Conference. The paper also assumes a geometric albedo of 0.175 for debris size estimation.
- Hejduk 2011 and McCue 1971: **NOT VERIFIED** (not read). Hostetler cites Hejduk et al. 2012 AMOS for the illuminance-ratio formulation.

## 8. Star tracker exclusion angles

- **Fields of view, VERIFIED (NASA compilation):** NASA/TP-20250000142, *State-of-the-Art Small Spacecraft Technology*, Jan. 2025, Table 5-5 "Star Trackers Suitable for Small Spacecraft", p. 150. NTRS 20250000142. Values: Terma T1 "20° circular"; Terma T3 "20° circular"; Sodern Hydra-M 22°; Sodern Hydra-TC 23.6°; Sodern Auriga-CP 30°; Leonardo Spacestar 20° x 20°; Ball (BAE) CT-2020 "-" (not given). The table does **not** list exclusion angles.
- **Sun / Earth-limb / Moon exclusion half-angles: NOT VERIFIED.** Manufacturer datasheets (terma.com, jena-optronik.de, sodern.com) were blocked. Search snippets only, not read: Terma T1 datasheet (2024-03-06) lists baffle options of 26°, 30° and 35° Sun exclusion, and "full moon accepted in FOV". Jena-Optronik ASTRO CL lists 26° Sun exclusion half-cone (one listing says 32°). Do not use these values until the datasheets are read.

## 9. Disturbance torques (SMAD 3rd ed., Sec. 11.1 / Table 11-9)

- **SMAD text: NOT VERIFIED** (book not accessible). This covers the specific SMAD forms: gravity gradient `3 mu/(2R^3)|Iz - Iy| sin(2 theta)`, `T_a = 0.5 rho Cd A V^2 (c_pa - cg)`, magnetic `T_m = D B` with `B = 2M/R^3`, M = 7.8e15 T m^3, lambda factor, and momentum rule `h = T P 0.707/4`.
- **Gravity-gradient torque (general vector form), VERIFIED:** NASA SP-8024, *Spacecraft Gravitational Torques*, May 1969, Sec. 2.5, Eq. (2), p. 7: `L_g = (3k/R^3) (R_hat x I . R_hat)`, with k = 3.986032e14 N m^2/kg for Earth. For a circular orbit, k/R^3 = omega_0^2. NTRS 19700014113. (The SMAD scalar worst case follows for a principal-axis offset theta. I did not verify that step in a source.)
- **SRP torque, VERIFIED (same form as SMAD):** C. Barret, *Spacecraft Flight Control System Design Selection Process for a Geostationary Communication Satellite*, NASA TP-3289, Sept. 1992, Sec. II: `T_sp = P_s A_s L_s (1 + q) cos i`, with P_s = 4.617e-6 N/m^2 and q = 0.6 (reflectance factor). The paper cites SMAD (Wertz & Larson) as Ref. 6. NTRS 19930001814.
- Aerodynamic and magnetic SMAD formulas, the 7.8e15 T m^3 constant, the lambda factor and the 0.707/4 momentum rule: **NOT VERIFIED**.

## 10. Population and Earth area

- **UN WPP 2024 world population (1 July 2024): NOT VERIFIED.** UN sites were blocked. Secondary search coverage says "~8.2 billion", and I did not confirm the exact figure.
- **Earth surface area 5.10e14 m^2: NOT VERIFIED** from a cited table (NSSDC fact sheet blocked). Derived value: 4 pi (6.371e6 m)^2 = 5.101e14 m^2, where the mean radius 6371 km is itself not verified in a read source.
- Note: DAS 3.0 does not use a global mean density. It uses inclination- and year-dependent, longitude-averaged population density up to 2100 (UG Sec. 3.8 p. 33; App. C.5 p. C-5).

## 11. Definitions

- **Equivalent sun hours, VERIFIED:** Bourassa & Gillis, *Solar Exposure of LDEF Experiment Trays*, NASA CR-189554, Feb. 1992, abstract: "cumulative equivalent sun hours (CESH) or the hours of direct, zero-incidence solar radiation that would cause the same irradiance of a surface". Fig. 3 gives the calculation as "Solar Form Factor x Hours + Earth Form Factor x Albedo x Hours". NTRS 19920013256. Henninger RP-1121 also gives "ESH = equivalent Sun hours of ultraviolet radiation". An ASTM ESH definition: **NOT VERIFIED**.
- **AO flux, VERIFIED:** Bourassa & Gillis, *Atomic Oxygen Exposure of LDEF Experiment Trays*, NASA CR-189627, May 1992, Sec. 4.3, Eq. (10): in the zero-temperature limit, `F = N v cos(alpha)`, where N is number density, v is spacecraft velocity relative to the atmosphere, and alpha is the angle from the surface normal to ram. The full thermal form is Eq. (8): `F = (1/4) N <c> {exp(-U^2) + U sqrt(pi) [1 + erf(U)]}`, with `U = (2/sqrt(pi)) (v/<c>) cos(alpha)` and `<c> = sqrt(8RT/(pi M))`. The text says the two "are nearly equal" for incidence angles below ~87.5°. NTRS 19920016713. Fluence = time integral of F.
- Related value, VERIFIED: TM-2006-214482 p. 1 gives the ISS ram AO flux as ~5.23e13 atoms/(cm^2 s) at 400 km, averaged over the solar cycle, with mean impact energy 4.5 eV.
