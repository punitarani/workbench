# Concurrency, and the failure that looks like a model failure

Sweeps run one Docker network per trial, and this machine's daemon has
three `/24` default pools. Past roughly a dozen concurrent trials the
daemon refuses:

    Error response from daemon: all predefined address pools have been
    fully subnetted

Harbor reports that as a trial with no deliverable. `band.py` and
`certify.py` correctly exclude it as a DNF rather than averaging it as a
zero — but the reader is told "no deliverable", which reads exactly like a
model that failed to answer.

**It cost two sweeps.** A `mail-promise-register` sweep returned
`3/3 Mean: 0.000` in two seconds, and a `live-commitment-register` sweep
lost its third trial the same way. Neither is a fact about a model.

## What to do

- **Keep concurrent sweeps at four or fewer** (twelve trials). Five was
  where it broke here.
- **`docker network prune -f` between batches.** Networks leak from killed
  runs: 29 existed, 11 survived a prune, and the 18 dead ones were holding
  the pool.
- **Or widen the pool**, which needs the daemon restarted and so has to
  wait for a quiet moment. For OrbStack, `~/.orbstack/config/docker.json`:

      {"default-address-pools": [{"base": "10.200.0.0/16", "size": 24}]}

  That is 256 networks instead of three.

## Two false DNFs that are not the address pool, and not the model

A trial with no `verifier/reward.json` looks identical whatever killed it.
Two seen here had the agent finishing the work and losing it afterwards,
and both are in `trial.log`'s last line rather than anywhere a score
aggregator looks:

    Trial ... failed: Expected exactly 1 session, found 2
    Trial ... cancelled

The first is a harness assertion: the agent opened a second Codex session
and the collector refuses to guess which one to keep. Its transcript ends
in `turn.completed` with every todo ticked, including *"Compute
superseded/live commitments and write output"*. The second is a
cancellation after the agent's last tool call returned. In both the work
was done and the deliverable never reached the workspace, so nothing can
be re-scored -- unlike a DNF with a saved answer, these are gone.

**Read `trial.log`'s last line before recording a tier's completion rate.**
One task read 2-of-3 and then 1-of-3 answered on its weakest-completing
tier, which reads as a model that cannot finish. Both losses were
harness-side, on a task whose single trial spends 32 million input tokens
against a 6.6 MB transcript -- the longest in the pack. Length is what
these two failures have in common, and length is a property of the task.

**Report the completion rate beside the score, never folded into it.** How
often a model manages to answer and how well it answers are different
facts, and only one of them is about the model.

## The general point

An environment-level failure that produces "no deliverable" is
indistinguishable downstream from an agent that wrote nothing. The DNF
machinery keeps it out of the score, which is the important half; the other
half is knowing to look, because a sweep that returns 0.000 in two seconds
never reached a model at all.
