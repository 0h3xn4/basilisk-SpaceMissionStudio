# RF link, data handling and power

Whether the downlink closes, how much data the spacecraft makes, stores
and sends, and the power it collects and draws. Code:
`spacemissionstudio/engine/link_budget.py`, `engine/data_handling.py`,
`engine/fsw.py` (comms pointing), and Basilisk's power modules. How to use
it: [Model power, the radio link and onboard data](../user-manual/power-link-and-data.md).

## The link budget

A free-space Eb/N0 budget, worked out for each sample in which a ground
station is in view. The scenario gives every input: the spacecraft's
`rf_link` and the station's receive gain and noise temperature.

    EIRP    = 10 log10(P_tx) + G_tx - L_impl                       [dBW]
    FSPL    = 20 log10(4 pi R f / c)                                [dB]
    C/N0    = EIRP - FSPL - L_point + G_rx - (k + 10 log10(T_sys))  [dB-Hz]
    Eb/N0   = C/N0 - 10 log10(data rate)                            [dB]
    margin  = Eb/N0 - required Eb/N0                                [dB]

- **R** is the slant range from Basilisk's `groundLocation`.
- **k** is Boltzmann's constant, -228.6 dBW/K/Hz.
- **c** is 299 792 458 m/s.

**The link closes** while the station is in view and the margin is at
least `required_margin_db` (0 dB). The margin already counts the required
Eb/N0, so 0 dB means the link closes with nothing to spare. Projects
usually require a few dB more, and set that here. The rule decides four
things:

- whether the simulated downlink may send data (the gate below; the run's
  `link_closed` series);
- the link status Vizard shows during comms pointing;
- the badge on the mission dashboard;
- whether the results overview marks the lowest link margin as critical.
  A run is judged by the value it was run with, which its provenance
  records.

**Pointing loss (L_point)** is the gain toward the station below the
peak. It depends on the antenna pattern:

- **Fixed:** no loss, unless the antenna has a beamwidth. With one, the
  loss is `pointing_loss_coeff_db` * (angle / beamwidth)^2: the parabolic
  main-lobe approximation, which with 12 gives 3 dB at half a beamwidth.
  The loss is at most `max_pointing_loss_db` (30 dB), because the
  approximation holds only near boresight.
- **Patch (cos^n):** a cos^n(theta) pattern whose directivity, 2(n + 1),
  is the given peak gain (Balanis, *Antenna Theory*, ch. 2). Behind the
  ground plane, the gain is the peak minus the front-to-back ratio.
- **Gain table:** the datasheet's gain, interpolated in dB. The last row's
  gain holds beyond the last angle.

The angle is measured from the simulated attitude:
`rf_link.antenna_boresight_b` against the line of sight to the station.
Without a boresight, pointing is taken as perfect.

The half-power beamwidth reported for a gain table is found on a 0.05°
grid.

## Data handling

Basilisk's own chain, wired as in its `examples/scenarioGroundDownlink.py`:

- **Instruments** (`simpleInstrument`): each at a constant data rate,
  always on.
- **Memory** (`partitionedStorageUnit`): one partition per instrument, up
  to the memory's capacity. A step's data that does not fit is refused
  whole and counted as lost.
- **Transmitter** (`spaceToGroundTransmitter`): sends at the link's data
  rate while the link closes, taking data from the fullest partition in
  packets of `packet_size_bits` (1 Mbit, the example's size). Nothing is
  sent while the fullest partition holds less than one packet.

A ledger counts what was generated, lost and downlinked. It switches the
transmitter's power draw on while the transmitter sends.

**Before a run**, the scenario's explanation estimates three things:

- the data made per day;
- how long the memory takes to fill, without any downlink;
- what one pass carries, for a pass of `explainer_pass_minutes`
  (10 min).

These are arithmetic on the settings. A run predicts the real passes.

## Power

Basilisk's own modules; SpaceMissionStudio sets no power rule of its own.

- **Solar panel** (`simpleSolarPanel`):

      P = 1361 W/m^2 * (1 AU / r)^2 * illumination * A * max(0, n . s) * efficiency

  - 1361 W/m^2 is Basilisk's solar flux at 1 AU (`SOLAR_FLUX_EARTH`).
  - r is the distance to the Sun.
  - The illumination comes from the eclipse model: 0 in shadow, partial
    in penumbra.
  - n is the panel normal and s the direction to the Sun, both in the body
    frame.
- **Loads** (`simplePowerSink`): the bus's constant idle power; the
  instruments' power; the transmitter's power while it sends; and the
  comms power while the spacecraft points at a station.
- **Battery** (`simpleBattery`): integrates the net power each step and
  holds the charge between 0 and its capacity.

Flexible solar arrays can feed the same battery from their own cells.

## Rules and parameters

Each is a named parameter, `link.<name>` or `data_handling.<name>`.
`spacemissionstudio assumptions --area link` lists the values in effect,
and a project configuration file changes them
([Change a parameter](../user-manual/project-configuration.md)).

| Parameter | Default | Unit | What it changes | Source |
|---|---|---|---|---|
| `link.required_margin_db` | 0 | [dB] | The margin at which the link closes: the simulated downlink, Vizard, the dashboard, the overview | SpaceMissionStudio's own choice |
| `link.pointing_loss_coeff_db` | 12 | [dB] | The "fixed" pattern's pointing loss per (angle / beamwidth)^2 | Parabolic main-lobe approximation (Wertz & Larson, *Space Mission Analysis and Design*, ch. 13) |
| `link.max_pointing_loss_db` | 30 | [dB] | The most pointing loss the "fixed" pattern gives | SpaceMissionStudio's own choice |
| `data_handling.packet_size_bits` | 1 000 000 | [bit] | The transmitter's packet size | Basilisk's `examples/scenarioGroundDownlink.py` |
| `data_handling.explainer_pass_minutes` | 10 | [min] | The pass length of the explanation's "per pass" note | SpaceMissionStudio's own choice |

**Constants**, not parameters:
- c;
- k, rounded to -228.6 dBW/K/Hz (10 log10(1.380649e-23) = -228.599);
- Basilisk's solar flux and astronomical unit.

The solar flux and the AU are the one set's, Basilisk's
([Physical constants](constants.md)); in the solar panel they are inside
Basilisk's C++ module, which SpaceMissionStudio does not change.

**Scenario inputs, not parameters:** the transmitter, antenna,
station, panel, battery and instrument values are the scenario's own,
saved in its file. Their defaults are listed in the
[transparency audit](../transparency_audit.md), Appendix C.

## Assumptions

- **Link:** free-space path loss and one lumped implementation loss only.
  No atmosphere, rain, scintillation, polarisation or coding gain. The
  noise temperature does not change with elevation.
- **Data:** instruments make data at a constant rate and are always on.
  There is no downlink schedule: the transmitter sends whenever the link
  closes, to any station in view.
- **Power:** a constant efficiency with no degradation (beginning of life
  equals end of life). One panel normal, with no temperature effect or
  packing factor, and no depth-of-discharge limit on the battery.
- **Timing:** the transmitter's power draw takes effect one step after it
  starts sending (the power sinks run before the battery).

## Checked against

`tests/test_data_handling.py`:
- the per-step margin equals the full link budget;
- the patch and table patterns give their gains and beamwidths;
- every generated bit is downlinked, lost or still on board;
- what the ledger counts as downlinked is what the transmitter sent.

`tests/test_comms_pointing.py`: the Vizard link status follows the margin
and the required margin.

## Outputs and records

A run records, for each station and spacecraft:
- `link_margin_db`;
- with a data-handling chain or an antenna pattern, `link_closed` and the
  angle off boresight;
- the data series (`stored`, `data_generated`, `data_downlinked`,
  `data_lost`, `downlink_rate`);
- the battery's charge and net power.

The mission dashboard shows the link budget's breakdown at the time cursor.

A run's `provenance.json` holds `configuration`, with each link and
data-handling parameter the project changed and the default it replaces.
