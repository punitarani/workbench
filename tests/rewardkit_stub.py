"""One stand-in for rewardkit, shared by every test that needs it.

rewardkit lives in the Harbor verifier image, not this venv, so a test
that exercises a grading file has to supply it. There were two ways to
get that wrong and this file exists to prevent the second.

**Permissive is useless.** A stub accepting any name with any arguments
passes every grading script ever written. Three rollouts were spent
discovering what it would have caught in a second: a criterion called
under a name nobody defined, a call carrying one more positional argument
than the criterion takes, and a description template naming a parameter
that had been removed. Each is an import-time death in the verifier, so
Harbor reports a missing reward file rather than a score, and the run is
paid for in full before anyone learns anything.

**Two stubs are worse than one.** The registration stub below lived
inside a single test module; a second test needing to *call* a criterion
would have written its own, and the two would have drifted — which is the
same defect the shared grader itself exists to remove, one level up.

So there are two modes over one implementation. `registering()` records
calls and checks binding, for auditing a grading file. `calling()` leaves
the functions callable, for exercising the criteria themselves.
"""

import inspect
import types


def registering(calls: list) -> types.ModuleType:
    """Record `criterion(...)` invocations and validate their binding.

    Mimics the three things rewardkit does at registration: resolve the
    name against the shared criteria, bind the caller's arguments to the
    signature (less `workspace`, which the runner injects), and format
    the description against that binding.
    """

    module = types.ModuleType("rewardkit")
    registered: dict[str, tuple] = {}

    def criterion(*_args, description: str | None = None, **_kwargs):
        def decorate(fn):
            registered[fn.__name__] = (fn, description)
            return fn

        return decorate

    def __getattr__(name: str):
        if name not in registered:
            raise AttributeError(f"module 'rewardkit' has no attribute {name!r}")
        fn, description = registered[name]
        signature = inspect.Signature(
            [
                parameter
                for parameter in inspect.signature(fn).parameters.values()
                if parameter.name != "workspace"
            ]
        )

        def register(*args, **kwargs):
            own = {k: v for k, v in kwargs.items() if k not in ("name", "weight")}
            bound = signature.bind_partial(*args, **own)
            if description:
                description.format(**{**kwargs, **bound.arguments})
            calls.append((name, args, kwargs))

        return register

    module.criterion = criterion
    module.__getattr__ = __getattr__
    module.registered = registered
    return module


def calling() -> types.ModuleType:
    """Leave decorated criteria as plain callables.

    For testing the criteria themselves rather than a grading file that
    registers them. The real decorator also returns the function
    unchanged, so what a test calls here is exactly what the verifier
    calls.
    """

    module = types.ModuleType("rewardkit")

    def criterion(*_args, **_kwargs):
        def decorate(fn):
            return fn

        return decorate

    module.criterion = criterion
    return module
