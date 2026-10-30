# Models, rules and assumptions

One page per model: what it computes and how, every rule and margin it
applies with its value, unit and source, the assumptions it makes, and
what it does not cover. Each rule is a named parameter: `spacemissionstudio
assumptions` lists them with the values in effect, and a project
configuration file changes them without editing code
([Change a parameter](../user-manual/project-configuration.md)).

| Model | Page | Parameters |
|---|---|---|
| Delta-V and propellant budget (ESA AD10) | [Propellant budget](propellant-budget.md) | `propellant_budget.*` |
| Orbital lifetime, disposal rules and drag make-up | [Orbital lifetime](lifetime.md) | `lifetime.*` |

The other areas move into the parameter registry one at a time
(transparency plan, Phase 3: link and power, the run summary, then
dynamics), each with its page here. Until then their values are
listed, with file and line, in the
[transparency audit](../transparency_audit.md), Section 4.
