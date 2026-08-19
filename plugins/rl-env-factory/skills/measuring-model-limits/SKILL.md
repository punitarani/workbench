---
name: measuring-model-limits
description: Use when building or fixing an RL environment, eval task, or agent benchmark - the entry point that routes to world-building, task-authoring, gating, rollout analysis, and difficulty iteration. Enforces the rule that only a model failure may ship.
---

# Measuring a model, not your environment

An environment exists to measure a model. Every point a task takes away
is a claim about the model, and the claim is only honest if the model is
what took it away.

This skill is the index. Load the one that matches your phase.

| phase | skill |
|---|---|
| generating a world, its records, its documents | `building-simulated-worlds` |
| turning that world into a graded task | `authoring-graded-tasks` |
| proving the task is fair before spending a rollout | `gating-environment-quality` |
| reading trials and classifying what went wrong | `analyzing-rollout-failures` |
| the score is out of band and you need to move it | `iterating-task-difficulty` |

## The one rule everything else serves

Five things can take a point away. Only the last may ship.

| class | what it means | what it demands |
|---|---|---|
| **E — environment** | the fact is not reachable through the served surface, or the record contradicts itself with no stated precedence | postmortem; the environment is wrong |
| **D — data** | the world's content is incoherent — a document whose body contradicts its registered name, an entry booked against the wrong parent | postmortem; the world is wrong |
| **H — harness** | the agent never got to answer: incompatible tool bridge, rate limit, setup timeout, abandoned delegation | not a score at all; fix or discard |
| **T — task** | ambiguous instruction, wrong oracle, wrong grader, unfair tolerance | fix and re-measure |
| **M — model** | reachable, unambiguous, oracle independently confirmed, and it got it wrong anyway | **the only one that may ship** |

These are not equally likely. On a mature environment **T is the most
common and the easiest to mistake for M**, because a task defect and a
model failure both present as a number below 1.0.

## The decisive question

> **A defect blocks every trial. Difficulty just makes most of them miss.**

Before calling any miss M, ask whether *any* trial of *any* model found
that row. If one did, the row is findable and the rule is applicable —
whatever the others did is theirs. If none did across many trials,
suspect yourself first.

## The loop

1. **Record a world.** Deterministic, fails loudly, coherence green.
2. **Rebuild derived state wholesale** and reconcile counts against the
   source of truth.
3. **Cut a task.** Brief, stated rule, declared rule-kind, structural
   floors met.
4. **Gate it.** Falsify each gate once — break the thing deliberately and
   confirm the gate fails.
5. **Measure at k≥3, and k=9 wherever completion is unreliable.** Read
   every trial log before recording a number.
6. **Classify every miss.** Anything not M is a defect: fix it and return
   to step 4.
7. **When the numbers move, re-derive the queue from the blocking
   condition** rather than extending the previous plan. Long asynchronous
   work drifts silently: nothing errors, and the runs keep measuring
   something you have stopped needing.
8. **Write down what generalizes** — as guidance, not as a run record.

## Where findings go

A finding that generalizes is not a run record. If a measurement changes
how the *next* environment should be built, it belongs in the guidance
tree where the next build will read it. Filing it under a dated run
folder means re-deriving it later at full cost.

Record falsified hypotheses with their measurements, including the ones
that make a headline result smaller. Correct earlier conclusions **in
place** rather than appending a softening note. And date difficulty
claims separately from defect claims: a defect is permanent once found,
while a difficulty claim is only true of the tiers that were measured.
