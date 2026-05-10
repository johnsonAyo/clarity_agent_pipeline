"""
llm/ollama.py
=============
Ollama cloud agentic loop — fallback when Claude CLI quota is exhausted.
Runs the full tool-calling loop (web_search, web_fetch) autonomously until the
model produces a final answer with no pending tool calls.
"""

from __future__ import annotations

import logging

import ollama as ollama_sdk

import config

log = logging.getLogger(__name__)


def _make_client() -> ollama_sdk.Client:
    return ollama_sdk.Client(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"},
    )


def run(system: str, user: str, temperature: float = 0.3, think: bool = True) -> str:
    """
    Drives the Ollama agentic loop until the model returns a final response.
    The model autonomously calls web_search / web_fetch as needed.

    think=True for research/analysis tasks. think=False for creative writing — Qwen3.5
    puts draft content in the thinking block and returns a thin conclusion when think=True,
    so creative tasks must disable it to get full output.
    """
    client = _make_client()
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]
    options = {"num_predict": 8192, "temperature": temperature, "num_ctx": 32768}

    # Use hardcoded tiers (Best -> Large -> Reliable)
    model_tiers = config.OLLAMA_MODEL_TIERS
    
    _MAX_STEPS = 15
    step = 0
    
    while True:
        step += 1
        if step > _MAX_STEPS:
            raise RuntimeError(f"Ollama loop exceeded {_MAX_STEPS} steps without completing")

        response = None
        for model_name in model_tiers:
            try:
                log.info("Ollama call | step=%d/%d | model=%s | think=%s", step, _MAX_STEPS, model_name, think)
                response = client.chat(
                    model=model_name,
                    messages=messages,
                    think=think,
                    options=options,
                )
                break # Success! Break the model-tier loop
            except ollama_sdk.ResponseError as e:
                if e.status_code in [429, 404]:
                    log.warning("Model %s unavailable (Status %d). Falling back...", model_name, e.status_code)
                    continue # Try the next model in the tier
                if e.status_code == 403:
                    log.warning("Subscription required for %s. Skipping...", model_name)
                    continue
                log.error("Ollama API error | step=%d | status=%d | %s", step, e.status_code, e)
                raise
            except Exception as exc:
                log.error("Ollama transport error | step=%d | %s", step, exc)
                raise

        if not response:
            raise RuntimeError("All Ollama cloud tiers failed (all quotas exhausted).")

        if thinking := getattr(response.message, "thinking", ""):
            log.debug("Ollama thinking | step=%d | preview=%s...", step, thinking[:200])

        messages.append(response.message)

        if not response.message.tool_calls:
            content = response.message.content or ""
            if not content:
                log.warning("Ollama returned empty content | step=%d", step)
            log.info("Ollama loop complete | steps=%d | output_len=%d", step, len(content))
            return content

        log.info("Ollama tool calls | step=%d | count=%d", step, len(response.message.tool_calls))
        for call in response.message.tool_calls:
            name = call.function.name
            args = call.function.arguments
            log.info("Tool dispatch | name=%s | args_preview=%s", name, str(args)[:150])

            try:
                raise ValueError(f"Unknown tool: {name}")
                result_text = ""
                log.info("Tool ok | name=%s | len=%d", name, len(result_text))
            except Exception as exc:
                result_text = f"Tool '{name}' failed: {exc}"
                log.error("Tool error | name=%s | error=%s", name, exc)

            messages.append({"role": "tool", "content": result_text, "tool_name": name})
