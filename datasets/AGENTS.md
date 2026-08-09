# Working in datasets

Root rules in [`../AGENTS.md`](../AGENTS.md) apply. Datasets are data plus
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
