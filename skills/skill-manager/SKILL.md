---
name: skill-manager
description: List active Telegram skills, show which are enabled/disabled, and explain how to manage them.
triggers:
  - user says /skill_manager or /skills
  - user asks "what skills do i have" or "list my skills"
  - user asks "how do i disable a skill" or "how do i add a skill"
  - user asks about hermes config or settings
emoji: ⚙️
---

# Skill Manager

You are the configuration interface for this Hermes instance.

## How skills are managed

There are two types of skills:

**Custom skills** (in the public repo `clarity_bot_pipeline/skills/<name>/`):
- clarity-pipeline, skill-manager
- To add: create `skills/<name>/SKILL.md` in the repo and add it to `skills.yaml`
- Changes go live when pushed to GitHub (CI deploys automatically)

**Private skills** (in `~/skills/` on Mac, never on GitHub):
- All other skills (job-application, validate-post, tdd, etc.)
- To add: create a folder in `~/skills/<name>/SKILL.md` on Mac — auto-syncs to Oracle in seconds

## Enabling / disabling skills

Edit `skills.yaml` in the repo and set `enabled: false` for any skill. Push to GitHub — the CI disables it on Oracle and it disappears from Telegram. Set back to `enabled: true` and push to restore it.

## Listing active skills

To see what's currently active on Oracle:
```bash
ls ~/clarity-skills/
```

To see what's disabled:
```bash
ls ~/clarity-skills/*/*.off 2>/dev/null
```

## Hermes config

The Hermes agent config lives at `~/skills/hermes-config/config.yaml` on Mac. Edit it locally and save — launchd auto-syncs to Oracle and restarts the gateway in seconds.

Key settings:
- `display.personality` — bot personality (helpful, concise, technical, kawaii, etc.)
- `agent.system_prompt` — custom system prompt
- `model.default` — which model the bot uses
