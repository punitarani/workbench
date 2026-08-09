# Working in adapters

Nothing lives here yet, deliberately — do not create the package without a
named target framework and a real integration to test against. An adapter
depends on `workbench.core` and the target's task format, never on a
workplace. The environment-side seam is `ActTransport`; build against it
rather than reaching into the engine.
