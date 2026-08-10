"""Stage a materialized bundle into a Harbor task's ``environment/`` context.

Harbor gives a prebuilt-image task exactly one channel into the container:
when ``[environment].docker_image`` is set and ``environment/`` holds no
Dockerfile or compose file, the whole directory is uploaded into the task
workdir at the end of environment start
(``BaseEnvironment._upload_environment_dir_after_start``). That upload lands
in the agent's own workspace, which is the wrong home for three of the four
things a Hartwell task needs, so the staging tree carries an installer and
the task's ``[environment.healthcheck]`` runs it — the one hook Harbor runs
after start and before agent setup::

    environment/
      <the professional's document folders>   already where they belong
      .workbench/state/*.db                   the projected tool databases
      .workbench/runtime/                     MCP servers + their dependencies
      .workbench/install.sh                   root; moves the first two offstage

``install.sh`` puts the databases at ``/home/environment/state`` (0700,
environment-owned), installs the runtime at ``/opt/workbench-runtime`` with a
``.pth`` so ``python3 -m workbench.tools.serve`` resolves for every user,
asserts that the agent user cannot read a database, and only then deletes the
staging tree. A failure leaves the tree intact, so the healthcheck's retry is
a clean re-run rather than a half-installed environment.

The installer also adds one oracle executable to the environment-owned
allowlist. It accepts no arguments and runs only ``/solution/solve.py`` with a
fixed state path. Harbor mounts that root-level file for the trusted solution
phase; it is absent and cannot be created by the agent during a normal run.

The runtime is needed because ``workbench:dev`` carries no Python packages of
its own: ``mcp``, ``pydantic``, and the ``workbench`` distributions are all
absent from the image, and the MCP servers cannot start without them. They are
resolved for the *container's* platform, not the host's, and cached under
``out/`` between builds.
"""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

STAGE_DIR_NAME = ".workbench"
"""Where the staging tree lands inside the workdir. Removed before the agent runs."""

CONTAINER_STAGE = "/home/agent/workspace/.workbench"
CONTAINER_STATE = "/home/environment/state"
CONTAINER_RUNTIME = "/opt/workbench-runtime"
CONTAINER_SOLUTION: str = "/solution/solve.py"
ORACLE_EXECUTABLE: str = "/usr/local/libexec/workbench/oracle"
ORACLE_COMMAND: str = (
    "exec env -i "
    "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin "
    "HOME=/home/environment USER=environment LOGNAME=environment "
    f"WORKBENCH_STATE={CONTAINER_STATE} "
    "WORKBENCH_WORKSPACE=/home/agent/workspace "
    f"python3 {CONTAINER_SOLUTION}"
)

HEALTHCHECK_COMMAND = f"sh {CONTAINER_STAGE}/install.sh"
"""What the task's [environment.healthcheck] must run."""

# Source trees whose ``workbench.*`` subpackages merge into one namespace
# package inside the runtime, exactly as the uv workspace assembles them.
SOURCE_PACKAGES = ("tools/src/workbench", "workbench/src/workbench")

# The runtime's third-party half is resolved from this member's metadata, so
# the container tracks the same floor the workspace does.
RUNTIME_REQUIREMENTS_FROM = "tools/pyproject.toml"
WORKSPACE_MEMBERS = frozenset({"workbench", "workbench-tools"})

PLATFORM_TAGS = {
    "arm64": "aarch64-manylinux2014",
    "aarch64": "aarch64-manylinux2014",
    "x86_64": "x86_64-manylinux2014",
    "amd64": "x86_64-manylinux2014",
}

PYTHON_VERSION = "3.14"
"""Ubuntu 26.04's interpreter, asserted by the image build."""

TOOLS = ("clio", "gmail", "imanage", "slack")

MCP_WRAPPER_PREFIX = "/usr/local/bin/workbench-mcp-"
"""One argument-free executable per tool system.

Harbor's Codex adapter collapses ``command`` and ``args`` into a single
string and writes it to Codex's ``command`` field, which Codex treats as the
program name — so a task declaring ``command = "run-as-environment"`` with
``args`` reaches Codex as a program literally named
``run-as-environment python3 -m ...``, fails to spawn, and the agent silently
gets no tools at all. Verified: the first pilot run showed Codex with only its
own built-in MCP tools. Naming a single executable survives that join intact
and is equally correct for adapters that honor the split.
"""


def mcp_command(tool: str) -> str:
    return f"{MCP_WRAPPER_PREFIX}{tool}"


INSTALL_SH = f"""#!/bin/sh
# Installed by datasets/hartwell/harbor_stage.py; run as root by the task's
# [environment.healthcheck] after the environment starts and before the agent
# is set up. Idempotent by construction: the staging tree is removed last, so
# any failure leaves a retry with the same work to do.
set -eu

STAGE={CONTAINER_STAGE}
STATE={CONTAINER_STATE}
RUNTIME={CONTAINER_RUNTIME}
TOOLS="{" ".join(TOOLS)}"
PTH=/usr/local/lib/python{PYTHON_VERSION}/dist-packages/workbench-runtime.pth
WRAPPER={MCP_WRAPPER_PREFIX}
LIBEXEC=/usr/local/libexec/workbench
SERVE="exec run-as-environment $LIBEXEC/serve"
ORACLE={ORACLE_EXECUTABLE}

if [ -d "$STAGE" ]; then
    # The tool databases are the record. Only the environment user may open
    # them; the agent reaches them through the MCP servers or not at all.
    install -d -o environment -g environment -m 700 "$STATE"
    for db in "$STAGE"/state/*.db; do
        install -o environment -g environment -m 600 "$db" "$STATE/$(basename "$db")"
    done

    # workbench:dev ships no Python packages, so the servers bring their own.
    # A .pth puts the tree on every interpreter's path, and file permissions
    # decide who can actually read it: environment-owned 0700, so the server
    # imports it and the agent gets ModuleNotFoundError. Ownership, not group:
    # run-as-environment is setuid and not setgid, so the server process keeps
    # the caller's groups and only the owner bits reach it. Handing the agent an
    # importable MCP client would let it drive the servers itself, which is
    # exactly the aperture the design is about. (PYTHONPATH cannot do this
    # job: CPython ignores the environment when euid != uid, which is
    # precisely the case behind run-as-environment.)
    rm -rf "$RUNTIME"
    mkdir -p "$(dirname "$RUNTIME")"
    mv "$STAGE/runtime" "$RUNTIME"
    chown -R environment:environment "$RUNTIME"
    chmod -R u=rwX,go= "$RUNTIME"
    mkdir -p "$(dirname "$PTH")"
    printf '%s\\n' "$RUNTIME" > "$PTH"

    # One argument-free executable per system. Harbor's Codex adapter joins
    # command and args into Codex's `command` field, which Codex execs as a
    # program name, so a multi-word command never spawns; a single path
    # survives the join and is equally correct for adapters that keep args.
    # run-as-environment only execs programs directly inside $LIBEXEC, which
    # is environment-owned 0750. That allowlist is what stops the agent from
    # running `run-as-environment cat <db>` and reading the record directly, so
    # the privileged half lives there and the wrapper merely names it.
    install -d -o environment -g environment -m 750 "$LIBEXEC"
    printf '%s\\n' \\
        '#!/bin/sh -p' \\
        '# Runs as environment. The tool name is validated against the set the' \\
        '# installer staged, so an extra argument cannot widen the aperture.' \\
        'set -eu' \\
        'case "$1" in' \\
        "  $(echo $TOOLS | tr ' ' '|')) ;;" \\
        '  *) echo "unknown tool: $1" >&2; exit 2 ;;' \\
        'esac' \\
        'exec python3 -m workbench.tools.serve "$1" --db {CONTAINER_STATE}/"$1".db' \\
        > "$LIBEXEC/serve"
    chown environment:environment "$LIBEXEC/serve"
    chmod 750 "$LIBEXEC/serve"

    # The trusted solution phase mounts /solution at the filesystem root.
    # This wrapper accepts no arguments, rejects links and environment-writable
    # code, pins the database path, and executes that one script. The agent can
    # name the wrapper but cannot supply a program or create /solution during
    # its normal phase.
    printf '%s\\n' \\
        '#!/bin/sh -p' \\
        'set -eu' \\
        'test "$#" -eq 0 || exit 2' \\
        'test -f {CONTAINER_SOLUTION} || exit 2' \\
        'test ! -L {CONTAINER_SOLUTION} || exit 2' \\
        'test ! -w {CONTAINER_SOLUTION} || exit 2' \\
        '{ORACLE_COMMAND}' \\
        > "$ORACLE"
    chown environment:environment "$ORACLE"
    chmod 750 "$ORACLE"

    for tool in $TOOLS; do
        printf '%s\\n' \\
            '#!/bin/sh' \\
            '# Generated by the task installer. The MCP surface is the aperture.' \\
            "$SERVE $tool" \\
            > "$WRAPPER$tool"
        chmod 755 "$WRAPPER$tool"
    done

    # docker cp carries the host's numeric ownership into the container, so
    # the professional's own folders would arrive owned by a uid that does
    # not exist here. They are the agent's documents; give them to the agent.
    chown -R agent:agent /home/agent/workspace
fi

# Readiness is asserted, not assumed: four databases, unreadable by the agent,
# a runtime the agent cannot import, and a server that starts and speaks MCP.
for tool in $TOOLS; do
    test -s "$STATE/$tool.db" || {{ echo "missing $STATE/$tool.db" >&2; exit 1; }}
    test -x "$WRAPPER$tool" || {{ echo "missing $WRAPPER$tool" >&2; exit 1; }}
done
test -x "$ORACLE" || {{ echo "missing $ORACLE" >&2; exit 1; }}
if su -s /bin/sh agent -c "test -r $STATE/clio.db"; then
    echo "the agent can read $STATE/clio.db" >&2
    exit 1
fi
if su -s /bin/sh agent -c "run-as-environment /bin/cat $STATE/clio.db" \
        >/dev/null 2>&1; then
    echo "run-as-environment ran a command outside the allowlist" >&2
    exit 1
fi
if su -s /bin/sh agent -c "run-as-environment {ORACLE_EXECUTABLE} /bin/cat" \
        >/dev/null 2>&1; then
    echo "the oracle wrapper accepted an arbitrary command" >&2
    exit 1
fi
if [ -e /solution ]; then
    echo "/solution leaked into the normal agent phase" >&2
    exit 1
fi
if su -s /bin/sh agent -c "mkdir /solution" >/dev/null 2>&1; then
    rmdir /solution
    echo "the agent can inject /solution" >&2
    exit 1
fi
if su -s /bin/sh agent -c "test -r $RUNTIME/mcp"; then
    echo "the agent can import the MCP runtime" >&2
    exit 1
fi
# The agent starts a server and it reaches EOF cleanly: proof the aperture
# opens from the side that will use it, not just from root's.
su -s /bin/sh agent -c "{MCP_WRAPPER_PREFIX}clio < /dev/null > /dev/null"

rm -rf "$STAGE"
"""


def _runtime_requirements(repo_root: Path) -> list[str]:
    """Third-party requirements for the MCP servers, read from the member's
    own metadata so the container never drifts from the workspace."""

    metadata = tomllib.loads((repo_root / RUNTIME_REQUIREMENTS_FROM).read_text())
    return [
        requirement
        for requirement in metadata["project"]["dependencies"]
        if requirement.strip().split(">=")[0].split("==")[0].strip()
        not in WORKSPACE_MEMBERS
    ]


def _platform_tag() -> str:
    machine = os.environ.get("WORKBENCH_TARGET_PLATFORM") or platform.machine()
    if machine in PLATFORM_TAGS:
        return PLATFORM_TAGS[machine]
    if "-" in machine:  # already a uv platform tag
        return machine
    raise SystemExit(
        f"unknown container platform {machine!r}; set WORKBENCH_TARGET_PLATFORM "
        f"to one of {sorted(set(PLATFORM_TAGS.values()))}"
    )


def _dependency_tree(repo_root: Path) -> Path:
    """Resolve the servers' dependencies for the container's platform.

    Cached under ``out/`` and keyed by platform and requirement set, because
    the resolve costs a few seconds and every task stages the same tree.
    """

    requirements = _runtime_requirements(repo_root)
    tag = _platform_tag()
    key = hashlib.sha256(
        "\n".join([tag, PYTHON_VERSION, *requirements]).encode()
    ).hexdigest()[:12]
    cache = repo_root / "out" / "harbor-runtime" / f"{tag}-{key}"
    if (cache / ".complete").exists():
        return cache

    shutil.rmtree(cache, ignore_errors=True)
    cache.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--target",
            str(cache),
            "--python-version",
            PYTHON_VERSION,
            "--python-platform",
            tag,
            "--no-installer-metadata",
            *requirements,
        ],
        check=True,
        capture_output=True,
    )
    (cache / ".complete").write_text(
        f"{tag}\n{PYTHON_VERSION}\n" + "\n".join(requirements)
    )
    return cache


def _copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def stage(
    bundle: Path, environment_dir: Path, *, repo_root: Path | None = None
) -> Path:
    """Rebuild ``environment_dir`` from a materialized ``bundle``.

    Returns the staging subdirectory. The directory is derived data: it is
    rewritten wholesale on every build and never committed.
    """

    repo_root = repo_root or REPO_ROOT
    workspace = bundle / "workspace"
    state = bundle / "state"
    if not workspace.is_dir() or not state.is_dir():
        raise SystemExit(
            f"{bundle} is not a materialized bundle; run build_tasks.py first"
        )

    shutil.rmtree(environment_dir, ignore_errors=True)
    environment_dir.mkdir(parents=True)

    # The professional's own folders are the workdir, so they upload as-is.
    _copy_tree(workspace, environment_dir)

    stage_dir = environment_dir / STAGE_DIR_NAME
    (stage_dir / "state").mkdir(parents=True)
    for database in sorted(state.glob("*.db")):
        target = stage_dir / "state" / database.name
        shutil.copyfile(database, target)
        target.chmod(0o600)

    runtime = stage_dir / "runtime"
    _copy_tree(_dependency_tree(repo_root), runtime)
    shutil.rmtree(runtime / "bin", ignore_errors=True)
    (runtime / ".complete").unlink(missing_ok=True)
    for source in SOURCE_PACKAGES:
        _copy_tree(repo_root / source, runtime / "workbench")

    install = stage_dir / "install.sh"
    install.write_text(INSTALL_SH)
    install.chmod(0o755)
    return stage_dir


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        raise SystemExit("usage: harbor_stage.py <task_dir> [task_dir ...]")
    for raw in argv:
        task = Path(raw)
        stage_dir = stage(task / "bundle", task / "environment")
        print(f"{task.name}: staged -> {stage_dir.parent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
