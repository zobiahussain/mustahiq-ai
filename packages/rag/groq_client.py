"""
The ONE place every chat-completion call in this project goes through.

WHY ONE SHARED WRAPPER, NOT EACH CALLER USING THE GROQ CLIENT DIRECTLY
--------------------------------------------------------------------------
Groq's free tier is rate-limited PER MINUTE. A 429 (rate-limit error)
appearing mid-demo would be the worst possible moment to discover this.
So every call -- the listing-enrichment call, the match-reason call, the
staff assistant, anything -- has to print what it just spent, in the
terminal, immediately, so we can literally watch consumption happen
during development and know how close we are to the limit. See CLAUDE.md
"LLM token accounting" for the full reasoning. Nothing here gets saved to
a file or database -- print only, on purpose.

WHAT THIS IS NOT
------------------
This is NOT an agent. There's no loop, no "decide what to call next," no
tool-use. Every call here is one prompt in, one answer out, then done.
See CLAUDE.md "No agent framework anywhere" for why that's a deliberate
choice, not a missing feature. Routing to Ollama below is the same kind
of thing -- ONE deterministic switch read from an env var at call time,
not a runtime decision anything gets to make on its own.

MANUAL DEV-TOGGLE: LLM_PROVIDER=ollama, ADDED 6 SEP 2026
--------------------------------------------------------------------------
A teammate deployed qwen3:4b locally via Ollama and shared it over
Tailscale (a private VPN mesh -- only reachable from a machine that's
joined his specific Tailscale network, see `llm inference.md` at the repo
root for his exact setup). Two real constraints, decided on purpose, not
missed:
  1. This can ONLY ever be reached from a machine on that Tailscale
     network -- it is NOT reachable by the deployed Render backend, so
     it can never be a live demo-day fallback unless the whole
     deployment joined that VPN too (a much bigger step, not requested).
  2. qwen3:4b (4 billion parameters) is meaningfully smaller than
     DEFAULT_MODEL (120 billion) -- expect noticeably weaker output,
     especially on JSON-mode reliability and Urdu reasoning quality.
Given both, this is wired in as a MANUAL, VISIBLE toggle for local dev
testing without touching Groq's per-minute quota -- never automatic
failover. Automatic failover would mean a call could silently downgrade
to a much weaker model with zero visible signal, which is exactly what
"never silently decide" exists to prevent. Set `LLM_PROVIDER=ollama` in
.env to route every chat() call there instead; leave it unset (or
"groq") for the normal path. Every Ollama call still prints its own
usage line, same discipline as the Groq path, so switching back and
forth is always visible in the terminal, not just in behavior.
"""

import inspect
import json
import os
import sys

import requests
from dotenv import load_dotenv
from groq import Groq, RateLimitError

# loaded here, once, so every caller gets GROQ_API_KEY for free instead of
# each one having to remember to call load_dotenv() itself first
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# FORCE UTF-8 ON OUR OUTPUT STREAMS -- WHY THIS FILE
# --------------------------------------------------------------------------
# LLM output and the Urdu/original listing text it works with are full of
# characters a default Windows console (cp1252) cannot encode: non-breaking
# hyphens (‑), smart quotes, em dashes, and Urdu script itself. Any
# bare print() of a match reason or a listing field then dies with
# UnicodeEncodeError -- and in match_and_notify() that print sits AFTER
# matches are persisted but BEFORE matches_computed_at is set, so the crash
# leaves the frontend polling forever. This file is imported by every path
# that produces such text, so reconfiguring here fixes it once, everywhere.
# errors="replace" over "strict" -- a mangled character in a terminal log
# line is nothing; a crashed background task is a hung demo.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # already wrapped, or not a real stream
        pass

DEFAULT_MODEL = "openai/gpt-oss-120b"

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()
# Defaults are the teammate's personal machine, from `llm inference.md` --
# expected to change (a different machine, a different model) whenever
# whoever's actually running Ollama changes; override via .env rather
# than editing this file.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://100.72.1.8:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")

# Two clients, built once each: the primary key, and an OPTIONAL fallback
# (a team member's key -- GROQ_API_KEY_FALLBACK in .env). Each Groq org has
# its OWN per-minute token quota, so when the primary's quota is genuinely
# exhausted for the minute, retrying the SAME key just waits; retrying the
# OTHER key actually gets through. See chat() for the switch -- it is loud
# (prints a line), one-directional per call, and only after the SDK's own
# ret/backoff on the primary is exhausted. Never silent.
_clients: dict[str, Groq] = {}


def _client_for(api_key: str) -> Groq:
    if api_key not in _clients:
        # max_retries -- the SDK honours the 429 response's own `retry-after`
        # hint ("try again in 8.4s") and backs off exponentially otherwise.
        # Default is 2; match_and_notify() can fire ~10 reason calls
        # back-to-back and the free tier's per-minute TOKEN limit is easy to
        # trip on a burst. CLAUDE.md's #1 demo risk -- this plus the
        # fallback key below is the mitigation.
        _clients[api_key] = Groq(api_key=api_key, max_retries=6)
    return _clients[api_key]


def _primary_key() -> str:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set. Add it to .env at the repo root.")
    return key


def _chat_ollama(messages: list[dict], *, json_mode: bool, call_site: str) -> str:
    """
    The Ollama half of chat() below -- same call shape (messages in, text
    out), talking to a REST endpoint instead of the Groq SDK. Ollama's own
    JSON-mode equivalent is `"format": "json"` on the request body (not a
    response_format object like Groq's) -- same guarantee (valid JSON, not
    any particular shape; the prompt still has to say what shape it wants).
    """
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                **({"format": "json"} if json_mode else {}),
            },
            timeout=60,  # a local model on someone else's machine, over a
                         # VPN hop -- generous, but not infinite if his
                         # machine or Tailscale itself is offline
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(
            f"Couldn't reach Ollama at {OLLAMA_URL} -- is Tailscale connected, "
            f"and is the teammate's machine still running Ollama? ({e})"
        ) from e

    data = response.json()
    usage = data.get("prompt_eval_count"), data.get("eval_count")
    print(f"[ollama] {call_site}  model={OLLAMA_MODEL}  "
          f"prompt={usage[0]} completion={usage[1]}")
    return data["message"]["content"]


def chat(
    prompt: str,
    *,
    system: str | None = None,
    json_mode: bool = False,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    One prompt in, one answer out.

    json_mode=True asks for valid JSON only -- use this for the
    listing-enrichment call and the match-reason call, both of which need
    structured fields back, not a free-form paragraph. When json_mode is
    True, your prompt must itself say what JSON shape you want (JSON mode
    guarantees VALID json, not any particular shape -- that part is still
    on the prompt). `model` is ignored when LLM_PROVIDER=ollama -- see
    OLLAMA_MODEL above; there's no per-call model override for that path,
    since only the one model the teammate deployed is available.

    Routes to Ollama instead of Groq when LLM_PROVIDER=ollama is set --
    see this file's own "MANUAL DEV-TOGGLE" note above for why, and why
    that's a plain env-var switch here, never an automatic fallback.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Who ACTUALLY called us -- walk past any frames still inside this
    # file, so chat_json() calling chat() internally doesn't make every
    # call site say "groq_client.py" instead of the real caller. Without
    # this, every call routed through chat_json() would be untraceable --
    # exactly the thing this logging exists to prevent.
    this_file = os.path.abspath(__file__)
    call_site = "unknown"
    for frame in inspect.stack()[1:]:
        if os.path.abspath(frame.filename) != this_file:
            call_site = f"{os.path.basename(frame.filename)}:{frame.lineno}"
            break

    if LLM_PROVIDER == "ollama":
        return _chat_ollama(messages, json_mode=json_mode, call_site=call_site)

    kwargs = {"model": model, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    # Primary key first (with the SDK's own retry/backoff). Only if that's
    # a genuine RateLimitError -- the primary org's per-minute quota is
    # spent -- fall back to GROQ_API_KEY_FALLBACK, a different org with its
    # own quota. Loud, not silent.
    fallback_key = os.environ.get("GROQ_API_KEY_FALLBACK")
    keys = [("primary", _primary_key())]
    if fallback_key and fallback_key != _primary_key():
        keys.append(("fallback", fallback_key))

    last_error: RateLimitError | None = None
    for which, key in keys:
        try:
            response = _client_for(key).chat.completions.create(**kwargs)
        except RateLimitError as e:
            last_error = e
            if which != keys[-1][0]:
                print(f"[groq] {call_site}  {which} key rate-limited -- switching to the fallback key")
            continue
        usage = response.usage
        tag = "" if which == "primary" else "  key=fallback"
        print(
            f"[groq] {call_site}  model={model}  "
            f"prompt={usage.prompt_tokens} completion={usage.completion_tokens} "
            f"total={usage.total_tokens}{tag}"
        )
        return response.choices[0].message.content

    raise last_error


def chat_json(prompt: str, *, system: str | None = None, model: str = DEFAULT_MODEL) -> dict:
    """Same as chat(json_mode=True), but parses the JSON for you."""
    raw = chat(prompt, system=system, json_mode=True, model=model)
    return json.loads(raw)


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Speech-to-text via Groq's hosted Whisper -- confirmed live on this
    account (whisper-large-v3), not guessed from docs, same discipline as
    picking the chat model earlier. Used for card 3's optional voice
    input: record -> transcribe -> the transcript becomes `raw_text`,
    still editable by hand before it goes anywhere near the enrichment
    call. Nothing downstream (enrich_listing_text) changes -- it already
    only ever wanted plain text.

    Note on usage logging: transcription is billed by SECONDS of audio,
    not tokens -- a genuinely different unit than every other call
    through this file, which is why the printed line below looks
    different from chat()'s.
    """
    client = _client_for(_primary_key())
    response = client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model="whisper-large-v3",
        response_format="verbose_json",
    )

    this_file = os.path.abspath(__file__)
    call_site = "unknown"
    for frame in inspect.stack()[1:]:
        if os.path.abspath(frame.filename) != this_file:
            call_site = f"{os.path.basename(frame.filename)}:{frame.lineno}"
            break

    duration = getattr(response, "duration", None)
    print(f"[groq] {call_site}  model=whisper-large-v3  audio_duration={duration}s")

    return response.text
