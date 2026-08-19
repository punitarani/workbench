def test_simulation_imports() -> None:
    import simulation

    assert simulation.__doc__


def test_sibling_namespace_packages_coexist() -> None:
    import core
    import simulation

    assert core.__name__ == "core"
    assert simulation.__name__ == "simulation"
