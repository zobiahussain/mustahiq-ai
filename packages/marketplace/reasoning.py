"""
generate_match_reason() -- the ONE Groq call per match that turns a raw
score into a sentence a beneficiary can actually read, e.g. "Zainab's
leather supplies would work well for Amina's tailoring business -- leather
is a direct input for garment production." This is what powers the
"matches with proper reasoning" screen.

Matches marketplace_matches.reason in the schema: "plain-language,
LLM-written for readability" -- unlike the ELIGIBILITY side, where match
reasons are templated from a rule breakdown, never LLM-written (CLAUDE.md
"Resolved"). Two different rules for two different things: eligibility
reasons have to be exactly reconstructable from a scoring formula for
audit purposes; a marketplace introduction reason is just... explaining
an introduction. No audit trail needed for "these two businesses might
suit each other."

WHY THIS RUNS ONLY ON THE FINAL, SHOWN MATCHES -- NOT EVERY CANDIDATE
--------------------------------------------------------------------------
find_matches() may filter and rank a dozen candidates before returning the
top few. Calling the LLM for every candidate scored along the way would
burn Groq's per-minute rate limit for reasons nobody will ever read. Only
call this on the matches that survive all the way to find_matches()'s
returned list -- i.e. the ones actually about to be shown to someone.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "rag"))
from groq_client import chat_json  # noqa: E402

PROMPT_TEMPLATE = """
A beneficiary on a small-business marketplace app is being shown a
potential match. Write ONE short, plain sentence explaining why this
match makes sense -- something a small-business owner can read and
understand immediately. No jargon, no percentages, no mention of
"embeddings" or "similarity scores."

Match type: {match_model}
Business A ({role_a}): {desc_a}
Business B ({role_b}): {desc_b}
Distance between them: {proximity_label}

Write it in English, then translate that SAME sentence into real,
natural Urdu (not a transliteration of the English words) -- both shown
to the beneficiary side by side, the same way the listing description
already is.

Return JSON: {{"reason_en": "one plain sentence in English",
               "reason_ur": "the same sentence, in real Urdu"}}
"""


def generate_match_reason(source: dict, match: dict) -> dict:
    """
    source: the listing find_matches() was called for (needs
            product_or_service_en and role).
    match: one item from find_matches()'s returned list (needs
           product_or_service_en, role, match_model, proximity_label).

    Returns {"reason_en": ..., "reason_ur": ...} -- added 5 Sep 2026,
    direct request to show the match reason bilingually, side by side,
    the same "alongside" treatment the listing description review
    already gets, not the small inline Urdu tag used for short UI
    labels elsewhere. ONE Groq call still produces both languages
    together (not two separate calls) -- same rate-limit-conscious
    reasoning as everywhere else in this module.
    """
    result = chat_json(
        PROMPT_TEMPLATE.format(
            match_model=match["match_model"].replace("_", " "),
            role_a=source["role"],
            desc_a=source["product_or_service_en"],
            role_b=match["role"],
            desc_b=match["product_or_service_en"],
            proximity_label=match["proximity_label"],
        )
    )
    return {"reason_en": result["reason_en"], "reason_ur": result["reason_ur"]}


def add_reasons(source: dict, matches: list[dict]) -> list[dict]:
    """
    Mutates and returns matches, adding 'reason' (English -- kept as
    this exact key so nothing already reading match['reason'] breaks)
    and 'reason_ur' (real Urdu, shown alongside it).
    """
    for m in matches:
        pair = generate_match_reason(source, m)
        m["reason"] = pair["reason_en"]
        m["reason_ur"] = pair["reason_ur"]
    return matches
