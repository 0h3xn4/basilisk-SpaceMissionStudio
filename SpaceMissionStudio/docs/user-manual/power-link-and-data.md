# Model power, the radio link and onboard data

How to add a solar panel and battery, a downlink to a ground station, and
instruments that fill an onboard memory.

All three are groups on the spacecraft page's **Power / propulsion /
link budget** tab. The power budget, and any antenna pattern other than
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

## Radio link to the ground

1. Add a ground station (**Ground stations > Add...**).
2. Tick **Downlink RF link budget** and set **TX power [W]**, **Carrier
   frequency [GHz]**, **Data rate [Mbit/s]**, **TX antenna gain [dBi]**,
   the losses and **Required Eb/N0 [dB]**.
3. Choose an **Antenna pattern**:

| Pattern | Use it for |
|---|---|
| Fixed gain | An antenna that tracks the station, or a first estimate |
| Patch (cos^n) | A patch antenna on one face, before you have its datasheet |
| Gain table | A real antenna's datasheet: gain against angle |

The run records, per station, `link_margin_db` and `link_closed`. The link
closes when the station is in view and the margin is 0 dB or more.

To point the antenna at the station during passes, use **Comms
pointing** on the **Attitude control** tab (template **19**).

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

A `thermal` sensor (**Sensors / actuators** tab) models a component on an
outside face that heats in sunlight and cools in eclipse. Template **20**.

## Templates to learn from

19 (power and link together), 23 (a complete small satellite), 26 (data
from instrument to ground), 20 (thermal).

**More detail:** User Manual section 6,
[Data handling and the downlink](../../USER_MANUAL.md#data-handling-and-the-downlink).

---

**Next:** [Monte Carlo](monte-carlo.md) ·
[Read the results](read-the-results.md)
