#!/usr/bin/env python3
"""
apply_skills.py — applies skills.yaml manifest to ~/clarity-skills/ on Oracle.

For each skill in the manifest:
  enabled: true  → ensures SKILL.md is active (restores from .off if needed)
  enabled: false → renames SKILL.md to SKILL.md.off (non-destructive disable)

For skills whose SKILL.md lives in this repo (under skills/<name>/):
  copies the file into ~/clarity-skills/<name>/ before applying enable/disable state.
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
SKILLS_DIR = Path.home() / "clarity-skills"
MANIFEST = REPO_ROOT / "skills.yaml"


def main() -> None:
    if not MANIFEST.exists():
        print(f"Manifest not found: {MANIFEST}")
        sys.exit(1)

    config = yaml.safe_load(MANIFEST.read_text())
    skills = config.get("skills", [])
    print(f"Applying manifest: {len(skills)} skills")

    for skill in skills:
        name = skill["name"]
        enabled = skill.get("enabled", True)
        skill_dir = SKILLS_DIR / name

        # Deploy SKILL.md from repo if it exists here
        repo_skill_md = REPO_ROOT / "skills" / name / "SKILL.md"
        if repo_skill_md.exists():
            skill_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo_skill_md, skill_dir / "SKILL.md")
            print(f"  [repo] deployed: {name}")

        if not skill_dir.exists():
            print(f"  [skip] not found in clarity-skills: {name}")
            continue

        skill_md = skill_dir / "SKILL.md"
        skill_md_off = skill_dir / "SKILL.md.off"

        if enabled:
            if skill_md_off.exists() and not skill_md.exists():
                skill_md_off.rename(skill_md)
                print(f"  [on]  enabled:  {name}")
            else:
                print(f"  [ok]  active:   {name}")
        else:
            if skill_md.exists():
                skill_md.rename(skill_md_off)
                print(f"  [off] disabled: {name}")
            elif skill_md_off.exists():
                print(f"  [ok]  already disabled: {name}")
            else:
                print(f"  [skip] no SKILL.md found: {name}")

    print("Done.")


if __name__ == "__main__":
    main()
