"""A value this task cannot have until the corpus exists.

Placeholders were written straight into the Python as `«MEASURE: ...»`,
which is a syntax error — the file will not import, so nothing can be
compiled, linted or statically checked until every one is filled. That
turns "unfinished" into "unanalysable", and it hides the ordinary
mistakes underneath.

A call that raises is better in every way. The file compiles, the
independence and schema gates can read it, and running it before the
measurement lands fails loudly with the question that still needs
answering — which is the same contract the rest of this engine keeps.
"""


class Unmeasured(RuntimeError):
    """Raised when a task is run before its corpus measurement exists."""


def measure(question: str):
    """Stand in for a value the corpus has not yet been asked for.

        WINDOW_DAYS = measure("how many calendar days hold 180-260 messages")

    Never give this a default. A plausible default is indistinguishable
    from a measured value once it is in the file, and this repo's most
    expensive defect class is a number somebody guessed.
    """

    raise Unmeasured(f"not measured yet: {question}")
