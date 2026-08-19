# Working in datasets

Root rules in [`../AGENTS.md`](../AGENTS.md) apply, and
[`../docs/METHOD.md`](../docs/METHOD.md) governs how tasks are built and
measured — read it before authoring a task or acting on a score. Datasets are data plus
shell scripts: they import nothing from the workspace at task runtime,
reference the prebuilt image, and every task ships a `solution/solve.sh`
that earns full reward.

## The bundle split

`build_*.py` materializes one environment bundle per task. The agent's
working directory is `bundle/workspace` — documents only. `state/`,
`mcp.json`, and `environment.toml` are its siblings, offstage.

* Scripts that read the databases (`solution/solve.sh`, a baseline, a
  grader that needs them) run with `bundle/workspace` as cwd and open
  `${WORKBENCH_STATE:-../state}`. They are the oracle and the verifier;
  reading offstage is their privilege, and it says nothing about whether
  the task is solvable through the products — `measure_floors.py` proves
  that separately, against the real servers.
* Nothing the agent can reach may name the databases. A deliverable path
  is a plain filename in the workspace, never an absolute path and never a
  path into `state/`.

## Instructions are briefs, not task specs

`instruction.md` is the only prose the agent gets, and it must read as a
colleague's handoff: who the agent is, what happened, why it matters, the
precise professional rule defining any answer set, and the deliverable's
filename and shape. Name the firm's products (Gmail, Slack, iManage,
Clio) as things the professional simply has.

Never name the scaffolding: no config files, no servers or tool wiring,
no databases, no `state/`, no timestamp arithmetic (the products serve
true calendar dates), no grading, scoring, or weights, and nothing that
reveals the work is being scored. Rules that define an exact answer set
are professional standards — phrase them the way the firm would ("you are
certifying this list"), not as grading criteria.
`test_instruction_immersion.py` enforces the mechanical half of this.

## Floors every task clears before a rollout is spent on it

* **≥ 12 rows**, or partial credit cannot exist and the task reads 1.000
  or near zero with nothing between.
* **No constant-valued graded field.** A column with one value grades
  nothing: an agent that never looks scores full marks on it.
* **Every graded value reachable through the served surface.** A rule the
  agent cannot evaluate through the products is not a task rule.
* **The reference answer scores 1.000 against its own grader.** Otherwise
  the ceiling is not 1.0 and every score below it is misread.
* **A second derivation of the answer**, computed from raw events rather
  than from the projection the solver reads. Disagreement means one of
  the two is wrong and neither may be trusted.

## If the rule matches words in prose, say which kind of rule it is

An instruction whose prose describes a concept ("a register of promises",
"work reported complete") and whose test is string matching will be read
two ways, and the careful reader loses. State in the instruction that the
test is textual rather than editorial, and state separately whether a
form counts inside a longer phrase. This class has cost more measurements
here than every other combined.

## If a task sums quantities, say which order it rounds in

Adding durations then rounding is not the same as rounding then adding,
and on a realistic record the two disagree on a third of rows. An
instruction that does not name the order grades a coin toss.
