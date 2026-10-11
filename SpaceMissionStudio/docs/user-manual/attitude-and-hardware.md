# Point the spacecraft, with real sensors and actuators

How to make a spacecraft point somewhere, give it sensors and actuators,
and add the torques that disturb it.

Attitude needs **Simulation mode** *Full attitude* (top of the Scenario
Editor). In *Orbit only* the spacecraft has a position but no
orientation.

## Choose where it points

On the spacecraft's **Attitude control** tab, pick an **FSW mode**:

| FSW mode | Points |
|---|---|
| (none) | Nowhere: it coasts under the torques that are on |
| `inertial3D` | At one fixed attitude relative to the stars |
| `hillPoint` | Along the orbit frame (nadir pointing) |
| `velocityPoint` | Along the velocity direction |
| `sunSafePoint` | A body axis at the Sun |
| `locationPointing` | A body axis at a ground station or a celestial body |

The mode's settings appear under **Pointing parameters**; **Control gains
(MRP feedback)** has the controller's gains, which already scale to the
spacecraft's inertia. **Initial attitude / body rate** sets how it starts.

For a spacecraft that points at the Sun and turns to a ground station
during each pass, tick **Comms pointing** on the same tab instead of
choosing an FSW mode (template **19**).

## Add sensors and actuators

On **Sensors / actuators**, **Add...** a device:

- **Sensors:** star tracker, IMU, coarse sun sensor, magnetometer,
  thermal.
- **Actuators:** reaction wheel, thruster, magnetic torque rod.

In the dialog, **Start from a real device** lists commercially available
devices; **Apply device values** fills in that device's numbers. You can
also type your own. Without actuators, the controller's torque is applied
directly (an ideal actuator).

**New from template...** (under the Spacecraft list) gives you a complete
150, 300 or 500 kg spacecraft with sensors, wheels and torque rods
already set up.

## Unload the wheels

Wheels slowly fill up with momentum. Two ways to unload them, both on
**Power / propulsion / link budget**:

- **Momentum dumping (RW desaturation via thrusters)**: thruster pulses
  (template **12**).
- **Magnetic momentum management (RW desaturation via torque rods)**:
  torque rods against Earth's magnetic field (template **13**).

## Add disturbances

- **Enable gravity gradient torque** (Orbit / mass tab, template **10**).
- **Surface facets** (Orbit / mass tab): drag and solar pressure that
  depend on the attitude and can twist the spacecraft (template **21**).
- **Flexible solar arrays** that swing when the spacecraft turns
  (template **27**).

## Make the navigation imperfect

By default the flight software is told the true state. Tick **Navigation
error** on **Attitude control** to add a bounded random-walk error to the
attitude, rate, Sun heading, position and velocity it is told.

## Templates to learn from

06 (ideal pointing), 07 (the same with real hardware), 11 (thrusters),
14 (finding the Sun with sun sensors), 15 (pointing at the Moon).

**More detail:** User Manual section 6,
[Navigation error](../../USER_MANUAL.md#navigation-error) and
[Flexible solar arrays](../../USER_MANUAL.md#flexible-solar-arrays).

---

**Next:** [Power, link and data](power-link-and-data.md) ·
[Flight software and SIL](flight-software-and-sil.md)
