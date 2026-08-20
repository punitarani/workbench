# plugins

`rl-env-factory` — the method for building RL environments, packaged so
it travels. Everything in it is domain-independent: no dataset, task,
model or vendor is named anywhere in the skills.

## Install

```bash
claude plugin marketplace add ./plugins
```

Then `claude plugin install rl-env-factory@workbench-marketplace`.

## The skills

| skill | load it when |
|---|---|
| `measuring-model-limits` | entry point — the E/D/H/T/M taxonomy and the loop |
| `building-simulated-worlds` | generating a world, its records, its documents |
| `running-recorded-simulations` | supervising a run measured in hours, without corrupting it |
| `validating-task-premises` | checking a task idea against what the world actually holds |
| `authoring-graded-tasks` | turning a surviving premise into a graded task |
| `gating-environment-quality` | adding a check, or deciding whether to trust one |
| `analyzing-rollout-failures` | reading trials, classifying a miss |
| `iterating-task-difficulty` | the score is out of band and must move |

## Relationship to `docs/METHOD.md`

`METHOD.md` is this repository's copy, kept because the repository's own
`AGENTS.md` files link into it and because it carries the reasoning at
length. The skills are the operational extract: what to do, in order,
with the traps that cost real measurements.

When a new finding generalizes, it goes in both. When they disagree, the
skills are wrong — `METHOD.md` is edited in place as measurements land.
