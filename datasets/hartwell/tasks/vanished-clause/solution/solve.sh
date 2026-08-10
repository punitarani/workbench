#!/bin/sh
# Reference solution: surveys every multi-version document and delegates
# the importable version-diff oracle to solve.py.
exec python3 "$(dirname "$0")/solve.py"
