"""
groq_client.py — talks to the Groq API.

* Asks Groq which models exist RIGHT NOW (models get retired often).
* Skips non-chat and tiny-context models.
* Handles free-tier token limits: waits and retries on 429, skips on 413.
* Reports the real reason when everything fails.
"""
import os
import re
import time

import requests

GROQ_BASE = "https://api.groq.com/openai/v1"

PREFERRED_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

_SKIP = ("whisper", "tts", "guard", "compound", "safeguard", "embed",
         "orpheus", "playai", "distil", "prompt", "allam")

MIN_CONTEXT = 16000          # ignore models that can't hold our pipeline


class GroqAuthError(Exception):
    """API key missing or rejected."""


def _headers(api_key):
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def list_chat_models(api_key: str) -> list[str]:
    """Return currently available chat models, best first."""
    try:
        r = requests.get(f"{GROQ_BASE}/models", headers=_headers(api_key), timeout=20)
    except requests.exceptions.ConnectionError:
        raise Exception("Cannot reach api.groq.com — check your internet / firewall / VPN.")

    if r.status_code in (401, 403):
        raise GroqAuthError("Groq rejected your API key. Create a new one at console.groq.com.")
    r.raise_for_status()

    ids = [
        m["id"] for m in r.json().get("data", [])
        if m.get("active", True)
        and not any(w in m["id"].lower() for w in _SKIP)
        and (m.get("context_window") or MIN_CONTEXT) >= MIN_CONTEXT
    ]

    ordered = []
    override = os.getenv("GROQ_MODEL", "").strip()
    if override:
        ordered.append(override)
    ordered += [m for m in PREFERRED_MODELS if m in ids and m not in ordered]
    ordered += [m for m in ids if m not in ordered]

    if not ordered:
        raise Exception("Groq returned no usable chat models for this key.")
    return ordered


def _clean(text: str) -> str:
    """Strip <think> blocks and collapse runs of blank lines."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _retry_seconds(resp) -> float:
    """How long Groq says to wait after a 429."""
    header = resp.headers.get("Retry-After") if hasattr(resp, "headers") else None
    try:
        if header:
            return float(header)
    except (TypeError, ValueError):
        pass
    try:
        msg = resp.json().get("error", {}).get("message", "")
    except Exception:
        msg = ""
    m = re.search(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s", msg)
    if m:
        return int(m.group(1) or 0) * 60 + float(m.group(2))
    return 20.0


def call_groq(api_key: str, system_prompt: str, context: str, models: list[str],
              max_tokens: int = 1200, status_cb=None) -> tuple[str, str]:
    """
    Try each model until one answers. Returns (text, model_used).
    status_cb(message) is called when we have to wait on a rate limit.
    """
    errors = []

    for model in models:
        waited = 0
        for attempt in range(3):
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.8,
            }
            if model.startswith("openai/gpt-oss"):
                payload["reasoning_effort"] = "low"

            try:
                resp = requests.post(f"{GROQ_BASE}/chat/completions",
                                     headers=_headers(api_key), json=payload, timeout=90)
            except requests.exceptions.ConnectionError:
                raise Exception("Cannot reach api.groq.com — check your internet / firewall / VPN.")
            except requests.exceptions.Timeout:
                errors.append(f"{model}: timed out")
                continue

            if resp.status_code == 200:
                content = _clean(resp.json()["choices"][0]["message"].get("content") or "")
                if content:
                    return content, model
                errors.append(f"{model}: empty reply")
                break

            try:
                msg = resp.json().get("error", {}).get("message", resp.text)
            except Exception:
                msg = resp.text
            msg = re.sub(r"\s+", " ", msg)[:200]
            errors.append(f"{model}: HTTP {resp.status_code} — {msg}")

            if resp.status_code in (401, 403):
                raise GroqAuthError("Groq rejected your API key. Create a new one at console.groq.com.")

            if resp.status_code == 429:                    # per-minute token limit
                wait = _retry_seconds(resp) + 1
                if wait <= 60 and waited < 70 and attempt < 2:
                    if status_cb:
                        status_cb(f"⏳ Free-tier limit reached — waiting {int(wait)}s, then retrying…")
                    time.sleep(wait)
                    waited += wait
                    continue                               # retry SAME model
                break

            if resp.status_code >= 500:
                time.sleep(3)
                continue

            break                                          # 400 / 404 / 413 → next model

    raise Exception("All models failed:\n" + "\n".join(errors[-4:]))