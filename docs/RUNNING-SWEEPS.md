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

## Three false DNFs that are not the address pool, and not the model

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

The third is the provider dropping the stream, and its payload names the
cause more precisely than the reconnect line does:

    {"error":{"message":"Server tool request failed","code":400,
              "metadata":{"provider_name":null, ...}}}

A 400 on a TOOL request, with no provider attributed — a router-level
rejection, not a timeout and nothing the task controls. The transcript's
last events are:

    "type":"error"
    "message":"Reconnecting... 1/5 (stream disconnected before completion:
               Server tool request failed)"
    "type":"turn.failed"

and `trial.log` ends normally at "Collecting main service artifacts", so
nothing upstream looks wrong. These trials are SHORT -- 0.3 to 0.8 MB of
transcript against 7 to 12 MB for a completed one on the same task -- which
is the tell: a model that abandons work has read a great deal first, and a
dropped stream has not.

That distinction matters because the shapes invert the obvious reading. On
one task the strongest tier answered 2 of 7 while both weaker tiers
answered 3 of 3, which looks like the task defeating the model that thinks
hardest about it. Both of its failures were dropped streams. Completion
there is a fact about the provider that day.

**It clusters, so do not read a run of them as a model result.** One tier
lost 1 of 3 on its first sweep of a task and 3 of 3 on the next. Three in a
row at the 6.2% base rate is about one chance in four thousand, so the
failures are not independent — something about a particular model, task and
hour draws them. The response is the same either way (re-run under a fresh
tag), but a tier reading 0-of-3 on a task it answered twice yesterday is
reporting the router, not the model.

**The dropped-stream rate is 6.2%, measured over every finished trial in
this tree** — 37 of 598, spread across sixteen days, every model tier and a
dozen tasks. It is background weather, not an incident, so the response is
more trials rather than waiting for it to pass: a tier needing three graded
trials should expect to spend closer to four.

It also means a k=3 sweep has roughly a **1 in 6** chance of losing at
least one trial to something that says nothing about the model. That is
the arithmetic behind re-running a tier under a fresh tag rather than
reading 2-of-3 as a completion rate.

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
