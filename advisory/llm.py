"""Local LLM access through Ollama (http://localhost:11434).

The LLM only writes language: explanations, summaries and field extraction from
free-text notes. It never produces scores, allocations or PASS/FAIL decisions;
those stay in deterministic Python. Every call has a template fallback, so the
app keeps working when Ollama is not installed or not running.

Configuration (environment variables):
  OLLAMA_URL     default http://localhost:11434
  OLLAMA_MODEL   default llama3.2:3b
  ADVISORY_LLM   "off" disables the LLM entirely (used by tests)
"""

import json
import os
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
TIMEOUT = 60

_enabled = os.environ.get("ADVISORY_LLM", "on").lower() != "off"
_status_cache = {"at": 0.0, "value": None}

SYSTEM = (
    "You are an assistant inside an academic wealth-advisory prototype that uses synthetic data. "
    "Write clear, professional, plain English for a financial advisor. Use only the facts provided; "
    "never invent numbers, products or rules, and never change any figure you are given. "
    "Do not give personalised financial advice or guarantees. Be concise."
)


def set_enabled(value):
    global _enabled
    _enabled = bool(value)


def is_enabled():
    return _enabled


@contextmanager
def disabled():
    """Temporarily turn the LLM off (e.g. while seeding 16 demo cases)."""
    global _enabled
    previous, _enabled = _enabled, False
    try:
        yield
    finally:
        _enabled = previous


def status(max_age=20):
    """(available, message). Cached briefly so the UI does not poll on every rerun."""
    if time.time() - _status_cache["at"] < max_age and _status_cache["value"]:
        return _status_cache["value"]
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as resp:
            models = [m["name"] for m in json.load(resp).get("models", [])]
        if any(m == MODEL or m.split(":")[0] == MODEL for m in models):
            value = (True, f"{MODEL} via Ollama")
        else:
            value = (False, f"Ollama is running but '{MODEL}' is not downloaded. Run: ollama pull {MODEL}")
    except (urllib.error.URLError, OSError, ValueError):
        value = (False, "Ollama is not running. Install it from ollama.com and start the app.")
    _status_cache.update(at=time.time(), value=value)
    return value


def available():
    return _enabled and status()[0]


def _chat(prompt, json_mode=False, max_tokens=220):
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": max_tokens},
    }
    if json_mode:
        body["format"] = "json"
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)["message"]["content"].strip()


def _clean(text):
    """Drop a leading 'Here is a ...:' preamble line that small models often add."""
    lines = text.strip().splitlines()
    if len(lines) > 1 and lines[0].rstrip().endswith(":") and lines[0].lower().startswith(("here", "sure")):
        lines = lines[1:]
    return "\n".join(lines).strip()


def generate(prompt, max_tokens=220):
    """Return (text, error). text is None when the LLM is unavailable or fails."""
    if not available():
        return None, "LLM unavailable"
    try:
        start = time.perf_counter()
        text = _clean(_chat(prompt, max_tokens=max_tokens))
        return text, f"{MODEL}, {time.perf_counter() - start:.1f}s"
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        _status_cache["at"] = 0
        return None, f"LLM call failed: {e}"


def generate_json(prompt, max_tokens=200):
    """Return (dict, info). dict is None when unavailable or the output is not valid JSON."""
    if not available():
        return None, "LLM unavailable"
    try:
        start = time.perf_counter()
        data = json.loads(_chat(prompt, json_mode=True, max_tokens=max_tokens))
        return (data if isinstance(data, dict) else None), f"{MODEL}, {time.perf_counter() - start:.1f}s"
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        _status_cache["at"] = 0
        return None, f"LLM call failed: {e}"
