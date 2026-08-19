"""The packaged skills must not name anything in this repository.

The plugin exists so the method travels to the next environment, in
another domain, measured against different models. A skill that names
this repo's datasets, vendors, or model tiers stops being method and
becomes a run record with a `SKILL.md` extension — and the whole reason
the plugin exists is that findings filed as run records get re-derived
later at full cost.

The leak is easy to introduce and invisible in review: the natural way to
make guidance concrete is to cite the measurement it came from, and the
measurement has a dataset name in it. Cite the *number* instead. "One
rule required an article the corpus used once while the firm wrote the
bare form 34 times" carries the whole lesson and names nothing.

Frontmatter is checked here too. A skill whose `name` disagrees with its
directory never loads, and nothing else in the suite would notice.
"""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGINS = REPO / "plugins"
SKILLS = sorted(PLUGINS.rglob("SKILL.md"))

# Datasets, workplaces, served vendors, model tiers, providers, the task
# runner, and the repo itself. Word-bounded so "core" or "legal" as
# ordinary English do not trip it.
_LOCAL = re.compile(
    r"\b("
    r"ashgrove|calder|hartwell|workbench"
    r"|clio|imanage|gmail|slack"
    r"|harbor|rewardkit|openrouter|bedrock"
    r"|gpt-\d|opus|sonnet|haiku|glm|claude"
    r")\b",
    re.IGNORECASE,
)

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def test_the_audit_found_skills_to_check() -> None:
    """Guard the guard: a glob that matches nothing passes vacuously."""

    assert len(SKILLS) >= 5, [str(p) for p in SKILLS]


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_no_local_names(skill: Path) -> None:
    hits = sorted({m.group(0).lower() for m in _LOCAL.finditer(skill.read_text())})
    assert not hits, (
        f"{skill.relative_to(REPO)} names {hits}. Skills ship to other "
        "environments; cite the measured number, not the thing it was "
        "measured on."
    )


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_frontmatter_is_loadable(skill: Path) -> None:
    matter = _FRONTMATTER.match(skill.read_text())
    assert matter, f"{skill.relative_to(REPO)}: no YAML frontmatter"
    name = re.search(r"^name:\s*(.+)$", matter.group(1), re.M)
    description = re.search(r"^description:\s*(.+)$", matter.group(1), re.M)
    assert name and description, (
        f"{skill.relative_to(REPO)}: name and description required"
    )
    assert name.group(1).strip() == skill.parent.name, (
        f"{skill.relative_to(REPO)}: frontmatter name {name.group(1).strip()!r} "
        f"must equal its directory {skill.parent.name!r}, or the skill never loads"
    )
    # The description is the only thing read when deciding whether to load
    # a skill, so it states the trigger, not the contents.
    assert "Use when" in description.group(1), (
        f"{skill.relative_to(REPO)}: description must say when to load the skill"
    )


def test_every_skill_is_reachable_from_the_manifest() -> None:
    """A plugin directory that the marketplace does not list is dead weight."""

    marketplace = json.loads(
        (PLUGINS / ".claude-plugin" / "marketplace.json").read_text()
    )
    listed = {entry["name"] for entry in marketplace["plugins"]}
    # The manifest sits in `<plugin>/.claude-plugin/`, so the plugin's own
    # name is two levels up, not one.
    on_disk = {
        p.parent.parent.name for p in PLUGINS.glob("*/.claude-plugin/plugin.json")
    }
    assert on_disk == listed, f"on disk {sorted(on_disk)}, listed {sorted(listed)}"
