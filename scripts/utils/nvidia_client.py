"""Shared NVIDIA API client for Nemotron, GPT-OSS, and other models via NVIDIA API.

Model is sourced from .env (NVIDIA_MODEL). Defaults to nvidia/nemotron-3-nano-omni-30b-a3b-reasoning.
Stories can override this with NVIDIA_STORY_MODEL=openai/gpt-oss-120b.

This client uses the OpenAI-compatible interface provided by NVIDIA's API.
Supports reasoning models with thinking capabilities (enable_thinking).
"""
from __future__ import annotations
import os
import re
import json
import time as _time
import logging
import threading as _threading

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

from scripts.utils import model_config

log = logging.getLogger("neverquit.nvidia")
if not log.handlers:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s | %(message)s")

# Fallback model when a caller doesn't pass model_name. Agents resolve their own
# model via model_config; this is just the safety net. Single source of truth:
# scripts/utils/model_config.py.
MODEL = model_config.model_for("research")

_client: "OpenAI | None" = None

# Pacing — be respectful to the API
_MIN_INTERVAL = float(os.getenv("NVIDIA_MIN_INTERVAL_S", "0.5"))
_CONCURRENCY = int(os.getenv("NVIDIA_MAX_CONCURRENT", "1"))
_call_lock = _threading.Lock()
_sema = _threading.BoundedSemaphore(_CONCURRENCY)
_last_call_at = 0.0
_dynamic_interval = _MIN_INTERVAL


def client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY is required (set it in .env)")
        _client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
    return _client


def _pace():
    global _last_call_at, _dynamic_interval
    with _call_lock:
        if _dynamic_interval > _MIN_INTERVAL:
            _dynamic_interval = max(_MIN_INTERVAL, _dynamic_interval * 0.95)
        delta = _time.time() - _last_call_at
        if delta < _dynamic_interval:
            _time.sleep(_dynamic_interval - delta)
        _last_call_at = _time.time()


def _bump_interval(reason: str):
    global _dynamic_interval
    with _call_lock:
        _dynamic_interval = min(60.0, max(_dynamic_interval * 1.5, _MIN_INTERVAL * 1.5))
        log.warning("NVIDIA throttle bumped to %.1fs/req (%s)", _dynamic_interval, reason)


def _retry_after_seconds(exc: BaseException) -> float | None:
    """Parse 'try again in X seconds' from rate limit errors."""
    m = re.search(r"in\s+([0-9]+(?:\.[0-9]+)?)\s*s", str(exc), re.I)
    return float(m.group(1)) + 1.0 if m else None


def _is_retryable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if any(k in msg for k in ("429", "rate", "quota", "exhausted", "deadline",
                              "unavailable", "internal", "503", "502", "504",
                              "timeout", "connection")):
        return True
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name


# ---------- Tolerant JSON extraction ----------

_SMART_QUOTES = {
    """: '"', """: '"', "„": '"', "‟": '"',
    "'": "'", "'": "'", "‚": "'", "‛": "'",
    "–": "-", "—": "-", "…": "...",
}


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def _replace_smart(s: str) -> str:
    for k, v in _SMART_QUOTES.items():
        s = s.replace(k, v)
    return s


def _balanced_extract(s: str, open_ch: str, close_ch: str) -> str | None:
    start = s.find(open_ch)
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return s[start: i + 1]
    return None


def _strip_trailing_commas(s: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", s)


def _strip_comments(s: str) -> str:
    out = []
    i = 0
    in_str = False
    esc = False
    while i < len(s):
        c = s[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < len(s) and s[i + 1] == "/":
            j = s.find("\n", i)
            i = len(s) if j == -1 else j
            continue
        if c == "/" and i + 1 < len(s) and s[i + 1] == "*":
            j = s.find("*/", i + 2)
            i = len(s) if j == -1 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_json(raw: str):
    if not raw or not raw.strip():
        raise ValueError("Empty response from model")
    text = _replace_smart(_strip_fences(raw))
    try:
        return json.loads(text)
    except Exception:
        pass
    cleaned = _strip_trailing_commas(_strip_comments(text))
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    for o, c in [("{", "}"), ("[", "]")]:
        cand = _balanced_extract(cleaned, o, c)
        if cand:
            try:
                return json.loads(_strip_trailing_commas(cand))
            except Exception:
                continue
    try:
        from json_repair import repair_json  # type: ignore
        return json.loads(repair_json(text))
    except Exception:
        pass
    raise ValueError("Could not parse JSON. First 500 chars:\n" + text[:500])


# ---------- LLM calls ----------

def _do_call(system: str, user: str, max_tokens: int, enable_reasoning: bool = True, model_name: str = None):
    """Make streaming call to NVIDIA API with optional reasoning."""
    model = model_name or MODEL
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 1 if "gpt-oss" in model.lower() else (0.7 if "glm" in model.lower() else 0.5),
        "top_p": 1 if "gpt-oss" in model.lower() else 0.9,
        "stream": True
    }
    
    # Add reasoning budget ONLY when explicitly enabled
    if enable_reasoning:
        if "nemotron" in model.lower():
            # Small reasoning budget for faster turnaround
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": min(4096, max_tokens // 8)  # ~12.5% for speed
            }
        elif "glm" in model.lower():
            # GLM 5.1 uses enable_thinking and clear_thinking
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": True, "clear_thinking": False}
            }
    
    return client().chat.completions.create(**kwargs)


def _call(system: str, user: str, max_tokens: int, enable_reasoning: bool = True, model_name: str = None) -> str:
    """Execute call with rate limiting and error handling."""
    with _sema:
        _pace()
        try:
            stream = _do_call(system, user, max_tokens, enable_reasoning, model_name)
        except Exception as e:
            wait = _retry_after_seconds(e)
            if wait is not None and _is_retryable(e):
                _bump_interval("rate limit")
                log.warning("NVIDIA rate limit — sleeping %.1fs as instructed by API", wait)
                _time.sleep(wait)
                stream = _do_call(system, user, max_tokens, enable_reasoning, model_name)
            else:
                log.warning("NVIDIA call failed (%s): %s", type(e).__name__, str(e)[:300])
                raise
    
    # Collect streamed chunks (reasoning + content)
    reasoning_parts = []
    content_parts = []
    try:
        for chunk in stream:
            if not getattr(chunk, "choices", None) or not chunk.choices:
                continue
            
            # Capture reasoning content if present
            reasoning_content = getattr(chunk.choices[0].delta, "reasoning_content", None)
            if reasoning_content is not None:
                reasoning_parts.append(reasoning_content)
            
            # Capture regular content
            delta_content = chunk.choices[0].delta.content
            if delta_content is not None:
                content_parts.append(delta_content)
    except Exception as e:
        log.warning("Stream collection failed (%s): %s", type(e).__name__, str(e)[:300])
        raise
    
    # Log reasoning if captured
    if reasoning_parts:
        reasoning_text = "".join(reasoning_parts).strip()
        if reasoning_text:
            log.debug("Model reasoning: %s", reasoning_text[:300])
    
    text = "".join(content_parts).strip()
    if not text:
        raise RuntimeError("Empty response from NVIDIA API")
    return text


@retry(
    stop=stop_after_attempt(6),
    wait=wait_exponential(multiplier=4, min=8, max=120),
    reraise=True,
    before_sleep=before_sleep_log(log, logging.WARNING),
)
def complete(system: str, user: str, max_tokens: int = 20000,
             enable_reasoning: bool = False, model_name: str = None, **_ignore) -> str:
    """Get text completion from NVIDIA API with optional reasoning."""
    return _call(system, user, max_tokens, enable_reasoning, model_name)


@retry(
    stop=stop_after_attempt(6),
    wait=wait_exponential(multiplier=4, min=8, max=120),
    reraise=True,
    before_sleep=before_sleep_log(log, logging.WARNING),
)
def complete_json(system: str, user: str, max_tokens: int = 20000,
                  enable_reasoning: bool = False, model_name: str = None, **_ignore):
    """Get JSON completion from NVIDIA API with strict JSON output."""
    sys2 = system + "\nReturn ONLY valid JSON. No prose. No markdown fences. No comments. No trailing commas."
    raw = _call(sys2, user, max_tokens, enable_reasoning, model_name)
    return parse_json(raw)
