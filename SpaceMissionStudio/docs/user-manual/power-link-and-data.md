# Model power, the radio link and onboard data

How to add a solar panel and battery, a downlink to a ground station, and
instruments that fill an onboard memory.

All three are groups on the spacecraft's **Power / propulsion /
link budget** page. The power budget, and any antenna pattern other than
*Fixed gain*, need *Full attitude*: they depend on where the spacecraft
points.

## Power: panel and battery

Tick **Power budget (solar panel + battery)** and set:

| Field | Meaning |
|---|---|
| Panel area [m^2], Panel efficiency [-] | The solar cells |
| Panel normal (body frame, 3 components) | Which way the cells face |
| Bus idle power [W] | What the spacecraft always draws |
| Battery capacity [W*hr], initial state of charge [-] | The battery |

The run records the battery's charge and the power in and out. Watch it
drop in eclipse. Flexible solar arrays can feed the same budget from
their own cells (template **27**).

An [IDM-CIC import](idm-cic.md#power-from-the-model) can set the bus
idle power from the power of the imported equipment in one of the
model's system modes (or their duty-cycle average), the panel area and
normal from its solar arrays' panels, and the battery capacity from a
property your team keeps. The file does not give the panel efficiency:
set it yourself.

The panel efficiency is the beginning-of-life one, and by default it does
not change. To see the end of life, choose a degradation model in the
project configuration file
([Change a parameter](project-configuration.md)):

```yaml
parameters:
  power.degradation: yearly_rate          # [-] or radiation_dose, none (default)
  power.degradation_per_year: 0.02        # [-] your cells' and orbit's
  power.years_in_orbit_at_start: 5.0      # [year] the run starts 5 years after launch
```

`radiation_dose` is NRL and NASA's fit for triple-junction cells; it
needs your orbit's yearly displacement damage dose from SPENVIS
(`power.displacement_damage_dose_per_year_mev_g`). The run then records
`<spacecraft>.power.degradation_factor`, the fraction of the efficiency
kept. The equations, their sources and flight data to choose a rate from
are in [the power model](../models/link-data-and-power.md#solar-array-degradation-degradation).

## Radio link to the ground

1. Add a ground station (**Ground stations > Add**).
2. Tick **Downlink RF link budget** and set **TX power [W]**, **Carrier
   frequency [GHz]**, **Data rate [Mbit/s]**, **TX antenna gain [dBi]**,
   the losses and **Required Eb/N0 [dB]**.
3. Choose an **Antenna pattern**:

| Pattern | Use it for |
|---|---|
| Fixed gain | An antenna that tracks the station, or a first estimate |
| Patch antenna (cos^n from the peak gain) | A patch antenna on one face, before you have its datasheet |
| Gain table from the datasheet | A real antenna's datasheet: gain against angle |

The run records, per station, `link_margin_db` and `link_closed`. The link
closes when the station is in view and the margin is 0 dB or more; a
project configuration can require more (`link.required_margin_db`,
[the link model](../models/link-data-and-power.md)).

To size the link before a run, `spacemissionstudio link-budget
scenario.json` gives the budget at the longest range of a pass, at the
station's minimum elevation. Add `--explain` for how each figure was
computed ([Use the command line](command-line.md)).

To point the antenna at the station during passes, use **Comms
pointing** on the **Attitude control** page (template **19**).

## Instruments and memory

Tick **Data handling: instruments, memory and downlink** and set the
**Memory capacity [Gbit]**, the **Transmitter power draw [W]**, and one
row per instrument with its data rate (housekeeping counts as an
instrument). With the RF link on, the transmitter sends whenever the link
closes. A full memory takes nothing more; the run counts what was lost.

The run records `data_handling.stored`, `data_generated`,
`data_downlinked` and `data_lost`, and the Timeline lists each
downlink. Template **26** fills a 3 Gbit memory from a camera and sends it
to Berlin.

## Thermal

A `thermal` sensor (**Sensors / actuators** page) models a component on an
outside face that heats in sunlight and cools in eclipse. Template **20**.

## Templates to learn from

19 (power and link together), 23 (a complete small satellite), 26 (data
from instrument to ground), 20 (thermal).

**More detail:** User Manual section 6,
[Data handling and the downlink](../../USER_MANUAL.md#data-handling-and-the-downlink).

---

**Next:** [Monte Carlo](monte-carlo.md) ·
[Read the results](read-the-results.md)
