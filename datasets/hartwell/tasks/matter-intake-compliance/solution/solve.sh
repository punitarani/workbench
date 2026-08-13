#!/bin/sh
# Harbor's oracle uploads this directory to /solution and runs it as the agent
# user. Unlike the read-only audit tasks, this is a WRITE workflow: the reference
# solution MUTATES firm state (compliance.db) through the compliance tools rather
# than emitting a deliverable file, so there is no stdout-to-file handoff — the
# verifier grades the resulting world-state. The mutation must run as the
# environment user (which owns compliance.db), via the one allowlisted oracle
# executable; outside a container (the task's pytest) it runs directly.
set -eu

SOLVE="$(cd "$(dirname "$0")" && pwd)/solve.py"

if [ -x /usr/local/bin/run-as-environment ]; then
    /usr/local/bin/run-as-environment /usr/local/libexec/workbench/oracle
else
    python3 "$SOLVE"
fi
