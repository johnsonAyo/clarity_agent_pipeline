#!/usr/bin/env python3
"""
apply_skills.py — applies skills.yaml manifest to all Hermes skill directories.

Searches two locations for each skill:
  1. ~/clarity-skills/   (custom skills synced from Mac)
  2. ~/.hermes/skills/   (built-in Hermes skills)

enable/disable mechanism: renames the entire skill folder to <name>.off
This is format-agnostic — works whether the skill uses SKILL.md, DESCRIPTION.md, etc.

For skills whose SKILL.md lives in this repo (skills/<name>/SKILL.md):
  deploys the file into ~/clarity-skills/<name>/ before applying state.
"""

import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pyyaml not installed — run: pip install pyyaml")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent
MANIFEST = REPO_ROOT / "skills.yaml"

SEARCH_DIRS = [
    Path.home() / "clarity-skills",
    Path.home() / ".hermes" / "skills",
]


def find_skill(name: str) -> tuple[Path | None, Path | None]:
    """Returns (active_path, disabled_path) — either or both may be None."""
    for base in SEARCH_DIRS:
        active = base / name
        disabled = base / f"{name}.off"
        if active.exists() or disabled.exists():
            return (active if active.exists() else None,
                    disabled if disabled.exists() else None)
    return None, None


def main() -> None:
    if not MANIFEST.exists():
        print(f"Manifest not found: {MANIFEST}")
        sys.exit(1)

    config = yaml.safe_load(MANIFEST.read_text())
    skills = config.get("skills", [])
    print(f"Applying manifest: {len(skills)} skills\n")

    for skill in skills:
        name = skill["name"]
        enabled = skill.get("enabled", True)

        # Deploy SKILL.md from repo if present (always into clarity-skills)
        repo_skill_md = REPO_ROOT / "skills" / name / "SKILL.md"
        if repo_skill_md.exists():
            dest_dir = Path.home() / "clarity-skills" / name
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo_skill_md, dest_dir / "SKILL.md")
            print(f"  [repo]  deployed:  {name}")

        active_path, disabled_path = find_skill(name)

        if active_path is None and disabled_path is None:
            print(f"  [skip]  not found: {name}")
            continue

        if enabled:
            if disabled_path and not active_path:
                disabled_path.rename(disabled_path.parent / name)
                print(f"  [on]    enabled:   {name}")
            else:
                print(f"  [ok]    active:    {name}")
        else:
            if active_path:
                active_path.rename(active_path.parent / f"{name}.off")
                print(f"  [off]   disabled:  {name}")
            else:
                print(f"  [ok]    already disabled: {name}")

    print("\nDone.")


if __name__ == "__main__":
    main()
