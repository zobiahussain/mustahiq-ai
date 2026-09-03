"""
The ONE place every Groq call in this project goes through.

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
choice, not a missing feature.
"""

import inspect
import json
import os

from dotenv import load_dotenv
from groq import Groq

# loaded here, once, so every caller gets GROQ_API_KEY for free instead of
# each one having to remember to call load_dotenv() itself first
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

DEFAULT_MODEL = "openai/gpt-oss-120b"

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Add it to .env at the repo root."
            )
        _client = Groq(api_key=api_key)
    return _client


def chat(
    prompt: str,
    *,
    system: str | None = None,
    json_mode: bool = False,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    One prompt in, one answer out.

    json_mode=True asks Groq to return valid JSON only -- use this for the
    listing-enrichment call and the match-reason call, both of which need
    structured fields back, not a free-form paragraph. When json_mode is
    True, your prompt must itself say what JSON shape you want (Groq's
    JSON mode guarantees VALID json, not any particular shape -- that part
    is still on the prompt).
    """
    client = _get_client()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = {"model": model, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)

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

    usage = response.usage
    print(
        f"[groq] {call_site}  model={model}  "
        f"prompt={usage.prompt_tokens} completion={usage.completion_tokens} "
        f"total={usage.total_tokens}"
    )

    return response.choices[0].message.content


def chat_json(prompt: str, *, system: str | None = None, model: str = DEFAULT_MODEL) -> dict:
    """Same as chat(json_mode=True), but parses the JSON for you."""
    raw = chat(prompt, system=system, json_mode=True, model=model)
    return json.loads(raw)
