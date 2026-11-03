# Add your own models and rules (plugins)

How to give SpaceMissionStudio your organization's own models, checks
and parameters without editing its code: write them in a small Python
package of your own, install it next to SpaceMissionStudio, and they are
there, recorded with every run like the built-in ones.

## What a plugin can add

| It can add | How it shows | Recorded |
|---|---|---|
| **Parameters** of its own, `<plugin>.<name>` | On the Assumptions page and in `assumptions`, set in a project configuration file like any other ([Change a parameter](project-configuration.md)) | In the run's configuration |
| **Rules**: a pre-run check, with its rule, why it matters and how to fix what it finds | With the other pre-run warnings, under the rule `<plugin>.<rule>` | In the run's warnings |
| **Models** of a choice that takes one (below) | As one more model of that choice, with its method, inputs, outputs, assumptions, references and evidence | In the run's models, naming the plugin |

The choices that take a plugin's model:

| Choice | The plugin's model gives |
|---|---|
| `link.atmospheric_loss` | `implementation(rf_link, elevation_deg, scenario)`: the loss [dB] at that elevation. It is in the link margin, the margin series and the live link of data handling and flight software, as the ITU-R P.676 model is, and the link-budget calculation shows it as "Atmospheric gases". |
| `power.degradation` | `implementation(years, scenario)`: F(t) [-], the fraction the arrays keep after that many years in orbit. The ultraviolet and thermal-cycling factors apply as for the built-in models. |
| `propellant_budget.margin_policy` | No code: the margins it sets (`sets`) are the model. |

What a plugin **cannot** add is anything Basilisk must simulate: a
sensor, an actuator, a flight-software mode, an atmosphere or a shadow
model. Those are wired into the simulation and still need
SpaceMissionStudio's code.

A plugin is Python code: it runs with your rights, as any package you
install does. Install only plugins you trust.

## Write one

A plugin is a function `register(api)` that the package names as an entry point
in the group `spacemissionstudio.models`. The entry point's name
(`acme` below) is the plugin's name: the area of its parameters and the
prefix of its rules. It must be new: lower-case letters, digits and
underscores, and not one of SpaceMissionStudio's own areas.

This example adds one parameter of each model, a check and three models.
Its references are placeholders: put your own document's number there.
The code below is run as it is by the tests
(`tests/test_plugins.py`), so it works.

```python
"""acme_rules: ACME's own SpaceMissionStudio models and checks."""

import math

from spacemissionstudio.config import registry

DOCUMENT = "ACME-EXAMPLE-001 (a placeholder: your own document here)"


def register(api):
    zenith = api.add_parameter(
        "zenith_loss_db", 0.4, "[dB]",
        "The atmosphere's loss at the zenith in acme's flat-atmosphere model.", DOCUMENT, minimum=0.0)
    lowest = api.add_parameter(
        "lowest_elevation_deg", 5.0, "[deg]",
        "Below this elevation acme's flat-atmosphere model takes the loss at it.", DOCUMENT,
        minimum=0.1, maximum=90.0)
    yearly = api.add_parameter(
        "loss_per_year", 0.02, "[-]",
        "The fraction of their power the arrays lose each year in acme's linear model.", DOCUMENT,
        minimum=0.0, maximum=1.0)
    stations = api.add_parameter(
        "min_ground_stations", 2, "[-]",
        "The fewest ground stations acme accepts for a mission.", DOCUMENT, kind="integer", minimum=1)

    def flat_atmosphere(rf_link, elevation_deg, scenario):
        theta = max(float(elevation_deg), registry.value(lowest, scenario))  # [deg]
        return registry.value(zenith, scenario) / math.sin(math.radians(theta))  # [dB]

    api.add_model(
        "link.atmospheric_loss", "acme_flat", "ACME's flat atmosphere",
        "A = A_zenith / sin(max(theta, theta_min)).",
        inputs=("The station's elevation theta [deg]", f"{zenith} A_zenith [dB]", f"{lowest} theta_min [deg]"),
        outputs=("The loss A [dB] at each elevation",),
        assumptions=("A flat, uniform atmosphere: the path is the zenith one over sin(theta)",
                     "The frequency does not change the loss"),
        references=(DOCUMENT,), evidence=("tests/test_plugins.py",), implementation=flat_atmosphere)

    def linear(years, scenario):
        return max(0.0, 1.0 - registry.value(yearly, scenario) * years)  # [-]

    api.add_model(
        "power.degradation", "acme_linear", "ACME's linear loss",
        "F(t) = max(0, 1 - k t).",
        inputs=("The years in orbit t [year]", f"{yearly} k [-]"),
        outputs=("The fraction of power the arrays keep, F(t) [-]",),
        assumptions=("The same loss every year",), references=(DOCUMENT,),
        evidence=("tests/test_plugins.py",), implementation=linear)

    api.add_model(
        "propellant_budget.margin_policy", "acme_margins", "ACME's margins",
        "ACME's own residual and uncertainty margins.",
        inputs=("None: the margins are ACME's fixed values",),
        outputs=("propellant_budget.residual_fraction and .uncertainty_fraction [-]",),
        assumptions=("ACME's margins for every phase of the mission",), references=(DOCUMENT,),
        evidence=("tests/test_plugins.py",),
        sets=(("propellant_budget.residual_fraction", 0.03),  # [-]
              ("propellant_budget.uncertainty_fraction", 0.15)))  # [-]

    def enough_stations(scenario):
        needed = registry.value(stations, scenario)
        found = len(scenario.ground_stations)
        if found < needed:
            yield (f"{found} ground station(s): acme needs at least {needed}", found, needed)

    api.add_rule(
        "ground_stations", "A mission has at least acme.min_ground_stations ground stations.",
        "ACME's operations need a second station for the passes the first one misses.",
        "Add a ground station, or set acme.min_ground_stations in the project file.",
        enough_stations, parameter=stations)
```

A check gives one item for each thing it finds: the message, or the
message, the value found and the limit. A check that fails to run says
so in a warning ("check not run"); it does not stop the other checks.

Declare the entry point in your package's `pyproject.toml`, and install
it in the same Python environment as SpaceMissionStudio
(`pip install -e .` while you work on it):

```toml
[project.entry-points."spacemissionstudio.models"]
acme = "acme_rules:register"
```

## Check it

```console
$ spacemissionstudio plugins
acme  (acme-rules 1.0)
  parameters: acme.zenith_loss_db, acme.lowest_elevation_deg, acme.loss_per_year, acme.min_ground_stations
  rules: acme.ground_stations
  models: link.atmospheric_loss: acme_flat, power.degradation: acme_linear, propellant_budget.margin_policy: acme_margins
```

The Assumptions page names the loaded plugins under its file field, and
lists their parameters with the others, as `spacemissionstudio
assumptions` does. Their models are among the values each choice may take.

A plugin that fails to load (an error in `register`, a name already
taken, a model of a choice that takes none) is left out, with everything
it had added taken back, and the reason is shown on the Assumptions page
and by `plugins`. That command then exits with status 5.
The other plugins still load. `SPACEMISSIONSTUDIO_PLUGINS=0` in the
environment loads none.

## Choose its models

A plugin's models are chosen like the built-in ones, in the project
configuration file:

```yaml
parameters:
  link.atmospheric_loss: acme_flat
  power.degradation: acme_linear
  acme.zenith_loss_db: 0.6
```

## What a run records

- The provenance (`provenance.json`, Results › Provenance) lists the
  plugins loaded: name, distribution, version and what each added.
- Each model used is recorded with its plugin's name.
- Each value is recorded where it came from, as for the built-in parameters.
- A colleague who opens your exported file sees which plugins it needs.
  A configuration that chooses a plugin's model is refused, naming the
  model, where the plugin is not installed.

---

**Next:** [Change a parameter](project-configuration.md) ·
[How-to guides](README.md)
