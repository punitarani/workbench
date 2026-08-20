"""An independent derivation of the same answer.

**Transcribe the rule from `instruction.md`, never from `solve.py`.**
Copying the solver's expression reproduces its bug and then certifies
that the two agree — two published scores were the answer key rather than
a measurement, certified exactly that way.

Where more than one computation is defensible, use the one the solver did
not. Sum-then-round and round-then-sum are both reasonable; if they agree
here, that agreement means something.

And derive separately anything the generator and the solver both rest on
— a window boundary, a cutoff. Their mutual agreement is not evidence: a
shifted boundary makes every row wrong together while every row-level
check stays green.
"""

raise SystemExit("verify.py is a template; write the independent derivation")
