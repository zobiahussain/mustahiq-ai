"""
Real HTTP tests for the 5 Sep 2026 chat + contact-reveal feature:
POST/GET /matches/{id}/messages, GET /matches/{id}/contact, and the
two-stage gate (messaging open immediately, contact only after
POST /matches/{id}/connect). Run against port 8001.
"""

import os
import random
import sys
import uuid

import psycopg2
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "marketplace"))
import auth as auth_module  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
BASE = "http://127.0.0.1:8001"


def login(phone):
    captured = {}
    original = auth_module._send_sms

    def spy(ph, message):
        captured["message"] = message
        original(ph, message)

    auth_module._send_sms = spy
    try:
        result = auth_module.request_otp(phone)
    finally:
        auth_module._send_sms = original
    assert result["eligible"], f"expected eligible for {phone}"
    code = captured["message"].split("code is ")[1].split(".")[0]
    r = requests.post(f"{BASE}/auth/verify-otp", json={"phone": phone, "code": code})
    r.raise_for_status()
    return r.json()["token"]


def make_listing(token, headers, raw_text, **kwargs):
    r = requests.post(f"{BASE}/listing/draft", json={"raw_text": raw_text}, headers=headers)
    r.raise_for_status()
    draft = r.json()
    body = {
        "role": draft["role"],
        "product_or_service_en": draft["product_or_service_en"],
        "product_or_service_original": draft["product_or_service_original"],
        "skills_en": draft.get("skills_en"),
        **kwargs,
    }
    r = requests.post(f"{BASE}/listing", json=body, headers=headers)
    r.raise_for_status()
    return r.json()["listing_id"]


def main():
    phone_a = f"+9230099{random.randint(10000, 99999)}"
    phone_b = f"+9230099{random.randint(10000, 99999)}"
    token_a = login(phone_a)
    token_b = login(phone_b)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    listing_a = make_listing(headers=headers_a, token=token_a, raw_text="I run a small tailoring shop",
                              is_remote_capable=False, output_is_physical=True)
    listing_b = make_listing(headers=headers_b, token=token_b, raw_text="I supply cotton fabric",
                              is_remote_capable=False, output_is_physical=True)
    print(f"PASS -- two listings created ({listing_a}, {listing_b})")

    # Insert a deterministic test match directly -- messaging only cares
    # about match_id + party membership, not how the match was found, so
    # this avoids depending on semantic matching actually pairing these
    # two specific listings.
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    match_id = str(uuid.uuid4())
    a, b = sorted([listing_a, listing_b])
    cur.execute(
        "insert into marketplace_matches (id, match_model, listing_a_id, listing_b_id, "
        "similarity_score, proximity_multiplier, final_score, reason) "
        "values (%s, 'supply_chain', %s, %s, 0.9, 1.0, 0.9, 'test match')",
        (match_id, a, b),
    )
    conn.commit()
    conn.close()
    print(f"PASS -- test match inserted ({match_id})")

    print("\n--- messaging is open BEFORE 'connected' ---")
    r = requests.post(f"{BASE}/matches/{match_id}/messages", json={"body": "Hi, do you deliver to Lahore?"}, headers=headers_a)
    assert r.status_code == 200, r.text
    r = requests.post(f"{BASE}/matches/{match_id}/messages", json={"body": "Yes, I can deliver!"}, headers=headers_b)
    assert r.status_code == 200, r.text
    r = requests.get(f"{BASE}/matches/{match_id}/messages", headers=headers_a)
    assert r.status_code == 200, r.text
    messages = r.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["is_mine"] is True and messages[1]["is_mine"] is False
    print(f"PASS -- 2 messages sent and read, is_mine correct from A's perspective: {[m['body'] for m in messages]}")

    print("\n--- a non-party cannot message or read this match ---")
    phone_c = f"+9230099{random.randint(10000, 99999)}"
    token_c = login(phone_c)
    r = requests.post(f"{BASE}/matches/{match_id}/messages", json={"body": "butting in"}, headers={"Authorization": f"Bearer {token_c}"})
    assert r.status_code == 403, f"expected 403, got {r.status_code}"
    print("PASS -- non-party rejected")

    print("\n--- contact is NOT available before 'connected' ---")
    r = requests.get(f"{BASE}/matches/{match_id}/contact", headers=headers_a)
    assert r.status_code == 404, f"expected 404 before connecting, got {r.status_code}: {r.text}"
    print("PASS -- 404, correctly withheld pre-connection")

    print("\n--- connecting the match ---")
    r = requests.post(f"{BASE}/matches/{match_id}/connect", headers=headers_a)
    assert r.status_code == 200, r.text
    print(f"PASS -- {r.json()}")

    print("\n--- contact IS available after 'connected', for BOTH sides ---")
    r = requests.get(f"{BASE}/matches/{match_id}/contact", headers=headers_a)
    assert r.status_code == 200, r.text
    contact_for_a = r.json()
    print(f"  A sees: {contact_for_a}")
    assert contact_for_a["phone"] == phone_b, "A should see B's phone, not their own"

    r = requests.get(f"{BASE}/matches/{match_id}/contact", headers=headers_b)
    assert r.status_code == 200, r.text
    contact_for_b = r.json()
    print(f"  B sees: {contact_for_b}")
    assert contact_for_b["phone"] == phone_a, "B should see A's phone, not their own"
    print("PASS -- each side sees the OTHER's real phone number, not their own")

    print("\nALL MESSAGING + CONTACT-REVEAL CHECKS PASS.")


if __name__ == "__main__":
    main()
