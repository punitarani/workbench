def test_simulation_imports() -> None:
    import workbench.simulation

    assert workbench.simulation.__doc__


def test_sibling_namespace_packages_coexist() -> None:
    import workbench.core
    import workbench.simulation

    assert workbench.core.__name__ == "workbench.core"
    assert workbench.simulation.__name__ == "workbench.simulation"
