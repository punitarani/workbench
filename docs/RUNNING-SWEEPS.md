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

## The general point

An environment-level failure that produces "no deliverable" is
indistinguishable downstream from an agent that wrote nothing. The DNF
machinery keeps it out of the score, which is the important half; the other
half is knowing to look, because a sweep that returns 0.000 in two seconds
never reached a model at all.
