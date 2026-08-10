"""Security contract tests for Hartwell's staged Harbor boundary."""

import runpy
import subprocess
import tempfile
from pathlib import Path

HARTWELL = Path(__file__).parent
FEE_TASK = HARTWELL / "tasks" / "fee-dispute-reconstruction"
STAGE_MODULE: dict[str, object] = runpy.run_path(str(HARTWELL / "harbor_stage.py"))
INSTALL_SH: str = str(STAGE_MODULE["INSTALL_SH"])
ORACLE_EXECUTABLE: str = "/usr/local/libexec/workbench/oracle"


def test_installer_confines_oracle_to_root_mounted_solution() -> None:
    assert f"ORACLE={ORACLE_EXECUTABLE}" in INSTALL_SH
    assert 'test "$#" -eq 0' in INSTALL_SH
    assert "test -f /solution/solve.py" in INSTALL_SH
    assert "test ! -L /solution/solve.py" in INSTALL_SH
    assert "test ! -w /solution/solve.py" in INSTALL_SH
    assert "WORKBENCH_STATE=/home/environment/state" in INSTALL_SH
    assert "python3 /solution/solve.py" in INSTALL_SH
    assert 'chown environment:environment "$ORACLE"' in INSTALL_SH
    assert 'chmod 750 "$ORACLE"' in INSTALL_SH


def test_rendered_installer_is_valid_shell() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        install = Path(temporary) / "install.sh"
        install.write_text(INSTALL_SH)
        subprocess.run(["sh", "-n", str(install)], check=True)


def test_installer_proves_normal_agent_cannot_inject_or_widen_oracle() -> None:
    assert 'agent -c "mkdir /solution"' in INSTALL_SH
    assert "run-as-environment /bin/cat" in INSTALL_SH
    assert f"run-as-environment {ORACLE_EXECUTABLE} /bin/cat" in INSTALL_SH


def test_solution_keeps_privileged_read_and_agent_write_on_opposite_sides() -> None:
    solve = (FEE_TASK / "solution" / "solve.sh").read_text()
    assert f'/usr/local/bin/run-as-environment {ORACLE_EXECUTABLE} > "$TEMP"' in solve
    assert 'mv -f "$TEMP" dispute.json' in solve
    assert "run-as-environment python3" not in solve
