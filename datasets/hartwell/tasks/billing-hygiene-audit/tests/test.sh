#!/bin/sh
# Deterministic grader; swap for `rewardkit /tests` once runs go through
# Harbor with Reward Kit criteria.
exec python3 "$(dirname "$0")/grade.py"
