---
name: clarity-pipeline
description: |
  Analyse a viral tweet or social media post — debunk misinformation,
  add missing context, and optionally generate an infographic prompt.
  Invokes the Mind Cache pipeline running on Oracle.
triggers:
  - user pastes a tweet URL or tweet text for fact-checking
  - user says /clarity or "check this post" or "add context to this"
  - user wants to debunk or verify a viral claim
tools:
  - terminal
emoji: 🛸
---

# Clarity Pipeline — Mind Cache

The user has pasted a tweet or viral post. Run the Mind Cache context-completion pipeline.

## How to invoke

The pipeline runs on Oracle at `~/clarity_bot_pipeline/`. Call it via terminal:

```bash
ssh ubuntu@141.147.85.252 "cd ~/clarity_bot_pipeline && source venv/bin/activate && python cli.py --text '<post_text>'"
```

For full output (analysis + tweet thread + infographic prompt), add `--full`:

```bash
ssh ubuntu@141.147.85.252 "cd ~/clarity_bot_pipeline && source venv/bin/activate && python cli.py --text '<post_text>' --full"
```

The pipeline returns JSON. Parse it and relay the results to the user.

## Output

Always show:
1. **`analysis`** — the full fact-check and context (formatted as readable prose)
2. **Verdict** — True / Misleading / False / Missing Context (derive from analysis)

If `--full` was run, also show:
3. **`short_reply`** — a short reply tweet
4. **`thread`** — numbered list of thread tweets
5. **`infographic_prompt`** — show in a code block for easy copy

## Notes
- Strip tweet URLs to extract the text before passing to the pipeline
- Keep the tone factual and neutral, not preachy
- Save a brain page under `context-corrections/<slug>` if the topic is significant
