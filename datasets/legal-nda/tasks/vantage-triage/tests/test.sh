#!/bin/sh
# Verifier entry point. Runs in the agent workspace; rewards land in
# /logs/verifier. Becomes `rewardkit /tests` once runs go through Harbor.
exec python3 "$(dirname "$0")/grade.py"
