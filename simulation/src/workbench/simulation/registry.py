"""The single enumeration of optimizable DSPy programs.

GEPA (and tests) iterate exactly this; a program not registered here is not
an optimization target.
"""

import dspy

from workbench.simulation.persona.programs import ProfessionalActor


def programs() -> dict[str, dspy.Module]:
    return {"professional_actor": ProfessionalActor()}
