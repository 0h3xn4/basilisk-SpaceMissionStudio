# The material library

The materials a part or face can name (`config/materials.py`). Every value
carries its source; a value no read source gave is left blank, never
filled in (model-analyses decision D-12). A model can add its own
materials (`model.materials`), each with the source of its values.

Generated from the code: `config/materials.py` is the reference.

| Key | Description | Density [kg/m^3] | Melting [K] | Heat of fusion [J/kg] | Specific heat [J/(kg K)] | Absorptance [-] | Emittance [-] | AO erosion yield [cm^3/atom] |
|---|---|---|---|---|---|---|---|---|
| `aluminium_6061_t6` | Aluminium 6061-T6 | 2707 [1] | 867 [1] | 386116 [1] | 896 [1] |  |  |  |
| `aluminium` | Aluminium (generic) | 2700 [1] | 850 [1] | 390000 [1] | 1100 [1] |  |  |  |
| `titanium_6al_4v` | Titanium Ti-6Al-4V | 4437 [1] | 1943 [1] | 393559 [1] | 780 [2] |  |  |  |
| `titanium` | Titanium (generic) | 4400 [1] | 1950 [1] | 470000 [1] | 600 [1] |  |  |  |
| `steel_aisi_304` | Stainless steel AISI 304 | 7900 [1] | 1700 [1] | 286098 [1] | 545 [3] |  |  |  |
| `steel_aisi_316` | Stainless steel AISI 316 | 8026.85 [1] | 1644 [1] | 286098 [1] | 460.6 [1] |  |  |  |
| `stainless_steel` | Stainless steel (generic) | 7800 [1] | 1700 [1] | 270000 [1] | 600 [1] |  |  |  |
| `copper` | Copper alloy | 8938 [1] | 1356 [1] | 204921 [1] | 428.5 [4] |  |  |  |
| `inconel_718` | Inconel 718 | 8190 [1] | 1571 [1] | 311664 [1] | 435 [1] |  |  |  |
| `cfrp` | Graphite epoxy (CFRP), DAS "Graphite epoxy 1" | 1550.5 [1] | 700 [1] | 232.6 [1] | 879 [1] |  |  |  |
| `zerodur` | Zerodur glass-ceramic | 2530 [1] | 1424 [1] | 250000 [1] | 1200 [5] |  |  |  |
| `gallium_arsenide` | Gallium arsenide | 5316 [1] | 1510 [1] | 0 [1] | 325 [1] |  |  |  |
| `white_paint_z93` | White paint Z-93 |  |  |  |  | 0.17 [6] | 0.92 [6] |  |
| `white_paint_s13g` | White paint S-13G |  |  |  |  | 0.2 [6] | 0.9 [6] |  |
| `black_paint_z306` | Black paint Chemglaze Z306 |  |  |  |  | 0.96 [7] | 0.91 [7] |  |
| `buffed_aluminium` | Buffed aluminium surface |  |  |  |  | 0.16 [8] | 0.03 [8] |  |
| `polished_stainless_steel` | Polished stainless steel surface |  |  |  |  | 0.42 [8] | 0.11 [8] |  |
| `buffed_copper` | Buffed copper surface |  |  |  |  | 0.3 [8] | 0.03 [8] |  |
| `vapour_deposited_aluminium` | Vapour-deposited aluminium |  |  |  |  | 0.08 [9] | 0.02 [9] |  |
| `gold_electroplated` | Electroplated gold |  |  |  |  | 0.23 [8] | 0.03 [8] |  |
| `silvered_teflon_5mil` | Silver-backed Teflon, 5 mil |  |  |  |  | 0.08 [10] | 0.81 [10] |  |
| `aluminised_teflon_5mil` | Aluminium-backed Teflon (FEP), 5 mil |  |  |  |  | 0.13 [10] | 0.81 [10] | 2.11e-25 [11] |
| `mli_kapton_aluminised_1mil` | MLI outer layer: Kapton, aluminium backing, 1 mil |  |  |  |  | 0.38 [10] | 0.67 [10] | 3e-24 [12] |
| `kapton_h` | Kapton H polyimide |  |  |  |  |  |  | 3e-24 [13] |
| `kapton_hn` | Kapton HN polyimide |  |  |  |  |  |  | 2.81e-24 [14] |
| `black_kapton_xc` | Black Kapton XC |  |  |  |  |  |  | 2.2e-24 [15] |
| `mylar_pet` | Mylar (PET) |  |  |  |  |  |  | 3.01e-24 [14] |
| `teflon_fep` | Teflon FEP |  |  |  |  |  |  | 2e-25 [14] |
| `teflon_ptfe` | Teflon PTFE |  |  |  |  |  |  | 1.42e-25 [14] |
| `silicone_dc93_500` | Silicone DC 93-500 |  |  |  |  |  |  | 3.81e-27 [16] |
| `solar_cell_triple_junction` | Triple-junction solar cell, AR-coated coverglass |  |  |  |  | 0.895 [17] | 0.89 [17] |  |

## Sources

1. NASA DAS 3.0 User's Guide (Liou et al., NASA/TP-2019-220300, 2019), Appendix C.6, Table C-4 "Properties of DAS 3 Built-In Materials"
2. NASA DAS 3.0 User's Guide (Liou et al., NASA/TP-2019-220300, 2019), Appendix C.6, Table C-4 "Properties of DAS 3 Built-In Materials"; DAS gives 450 < cp < 1110: the midpoint
3. NASA DAS 3.0 User's Guide (Liou et al., NASA/TP-2019-220300, 2019), Appendix C.6, Table C-4 "Properties of DAS 3 Built-In Materials"; DAS gives 482 < cp < 608: the midpoint
4. NASA DAS 3.0 User's Guide (Liou et al., NASA/TP-2019-220300, 2019), Appendix C.6, Table C-4 "Properties of DAS 3 Built-In Materials"; DAS gives 385 < cp < 472: the midpoint
5. NASA DAS 3.0 User's Guide (Liou et al., NASA/TP-2019-220300, 2019), Appendix C.6, Table C-4 "Properties of DAS 3 Built-In Materials"; DAS gives 800 < cp < 1600: the midpoint
6. Henninger, Solar Absorptance and Thermal Emittance of Some Common Spacecraft Thermal-Control Coatings, NASA RP-1121, 1984 (normal emittance at about 300 K; tolerance about 0.02), White Coatings
7. Henninger, Solar Absorptance and Thermal Emittance of Some Common Spacecraft Thermal-Control Coatings, NASA RP-1121, 1984 (normal emittance at about 300 K; tolerance about 0.02), Black Coatings
8. Henninger, Solar Absorptance and Thermal Emittance of Some Common Spacecraft Thermal-Control Coatings, NASA RP-1121, 1984 (normal emittance at about 300 K; tolerance about 0.02), Metals
9. Henninger, Solar Absorptance and Thermal Emittance of Some Common Spacecraft Thermal-Control Coatings, NASA RP-1121, 1984 (normal emittance at about 300 K; tolerance about 0.02), Vapor-Deposited
10. Henninger, Solar Absorptance and Thermal Emittance of Some Common Spacecraft Thermal-Control Coatings, NASA RP-1121, 1984 (normal emittance at about 300 K; tolerance about 0.02), Films and Tapes
11. de Groh & Banks, Atomic Oxygen Erosion Data From the MISSE 2-8 Missions, NASA/TM-2019-219982, 2019, Table 3 (MISSE 2, Al-backed FEP)
12. de Groh & Banks, Atomic Oxygen Erosion Data From the MISSE 2-8 Missions, NASA/TM-2019-219982, 2019, Table 3 (the yield of Kapton H, taken for the Kapton film of the outer layer)
13. de Groh & Banks, Atomic Oxygen Erosion Data From the MISSE 2-8 Missions, NASA/TM-2019-219982, 2019, Table 3 (reference value for 4.5 eV LEO atomic oxygen)
14. de Groh & Banks, Atomic Oxygen Erosion Data From the MISSE 2-8 Missions, NASA/TM-2019-219982, 2019, Table 3 (MISSE 2)
15. de Groh & Banks, Atomic Oxygen Erosion Data From the MISSE 2-8 Missions, NASA/TM-2019-219982, 2019, Table 3 (MISSE 7)
16. de Groh & Banks, Atomic Oxygen Erosion Data From the MISSE 2-8 Missions, NASA/TM-2019-219982, 2019, Table 3 (MISSE 8)
17. Russell & Jones, Development of a High Efficiency UVR/IRR Coverglass for Triple Junction Solar Cells, SPRAT XIX, 2007, Table 1 (AR-coated coverglass)

The atomic oxygen erosion yield is not a meaningful number for most metals, whose oxide shields them; silver is an exception (its oxide spalls). Banks, de Groh & Miller, NASA/TM-2004-213400; Banks, Miller & de Groh, NASA/TM-2004-213223.
