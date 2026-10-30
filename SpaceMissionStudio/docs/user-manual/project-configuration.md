# Change a parameter

The rules and margins the analyses use are named parameters, for example
`propellant_budget.cam_count_factor`, AD10's x4 on the number of collision
avoidances. Each has a default, a unit, a source and limits. A project
changes them in a configuration file. No code is edited, and every result
records what was changed.

So far the rules of the propellant budget, the orbital lifetime, the RF
link and data handling, and how a run's results are read are parameters. The other areas follow ([Models](../models/README.md)).

## See the parameters

```console
$ spacemissionstudio assumptions
propellant_budget:
  propellant_budget.cam_count_factor              4.0 [-]   AD10 Sec. 5.6
  propellant_budget.residual_fraction            0.01 [-]   AD10 Sec. 5.8
  ...
```

Each model's page in [Models](../models/README.md) explains what each
parameter does, with its source.

## Change one for a project

1. Write the defaults file next to your scenario. Every line in it is
   commented out, so it changes nothing yet:

   ```console
   $ spacemissionstudio assumptions --yaml > project.yaml
   ```

2. Uncomment the lines to change and set the values, with the reason in a
   comment:

   ```yaml
   format: 1
   parameters:
     propellant_budget.residual_fraction: 0.05   # [-] our tanks: 5 % measured
   ```

3. Name the file in the scenario, relative to the scenario file's folder.
   In the app, use the scenario's **JSON** view; there is no form field for
   it yet:

   ```json
   "config_file": "project.yaml"
   ```

4. Check it. Each value is checked against its parameter's limits, and a
   value outside them makes the scenario invalid, naming the parameter:

   ```console
   $ spacemissionstudio validate scenario.json
   OK: 'my mission' -- 1 spacecraft, schema version 4, epoch 2030-01-01T00:00:00
   CONFIG: project.yaml changes 1 parameter(s); ...
   $ spacemissionstudio assumptions scenario.json --changed
   Configuration: project.yaml (SHA-256 ...)
   propellant_budget:
     propellant_budget.residual_fraction  0.05 [-]  AD10 Sec. 5.8  CHANGED (default 0.01)
   ```

A file is read only when a scenario names it: a configuration file lying
in the folder does not change anything on its own.

## What results record

- The budget's rows and notes use the values in effect: with the file
  above, the residual row reads "5% of tank".
- A run's `provenance.json`, and the `--out` records of `lifetime` and
  `budget`, hold `configuration`: the file, its SHA-256, and each value it
  changes with the default it replaces.
- A reproduction bundle (`run --bundle`) copies the file, and `reproduce`
  uses the copy.
