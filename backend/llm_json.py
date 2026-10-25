"""
Robust JSON completion helper for Nebius Token Factory models.
Handles reasoning tags, markdown fences, empty content, and retries.
"""

import json
import logging
import re
from typing import Any, Dict, Optional
from openai import OpenAI

logger = logging.getLogger("crisis_sentinel.llm_json")


def clean_llm_json_string(raw: str) -> str:
    """Strips <think>...</think> blocks, markdown fences, and leading/trailing whitespace."""
    if not raw:
        return ""
    # Strip deepseek/nemotron reasoning blocks if present
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    cleaned = cleaned.strip()

    # Match triple backtick json or plain code blocks
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if match:
        return match.group(1).strip()
    return cleaned


def chat_json(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 3500,
    temperature: float = 0.1,
    retries: int = 2,
) -> tuple[Optional[Dict[str, Any]], str, str]:
    """Executes a chat completion guaranteed to parse as a dict.

    Returns:
        (parsed_dict, raw_content, status_flag)
        where status_flag is 'model' or 'degraded'.
    """
    last_raw = ""
    for attempt in range(retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            choice = resp.choices[0]
            raw_content = choice.message.content or ""
            last_raw = raw_content

            cleaned = clean_llm_json_string(raw_content)
            if not cleaned:
                logger.warning(
                    f"[Attempt {attempt+1}] Empty response from {model}, finish_reason: {choice.finish_reason}"
                )
                continue

            parsed = json.loads(cleaned)
            return parsed, raw_content, "model"

        except Exception as e:
            logger.warning(f"[Attempt {attempt+1}] LLM JSON parse failed: {e}")

    logger.error(f"Exhausted retries for {model}. Last raw content: {last_raw[:200]}")
    return None, last_raw, "degraded"