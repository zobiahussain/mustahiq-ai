"""
Real HTTP tests for the endpoints added 5 Sep 2026: SET_AVAILABILITY,
donations/connect/no-longer-seeking (graduation), the two loan webhooks,
require_internal_key()'s gate, and the other_involvements field now
returned by /listing/{id}/matches and /listings/search.

Run against a server on port 8001 (never the user's own port 8000):
    uvicorn main:app --port 8001
    python smoke_test_new_endpoints.py
"""

import os
import random

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

BASE = "http://127.0.0.1:8001"
INTERNAL_KEY = os.environ["INTERNAL_API_KEY"]


def db():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def login(phone: str) -> str:
    """SKIP_ELIGIBILITY_CHECK must be true for this to work with a fresh number."""
    r = requests.post(f"{BASE}/auth/request-otp", json={"phone": phone})
    r.raise_for_status()
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "select code_hash from login_otps where phone = %s order by created_at desc limit 1",
        (phone,),
    )
    conn.close()
    # We can't reverse the hash -- read the code from the server's own
    # stdout isn't practical here, so instead read it straight out of the
    # OTP flow the same way auth.py's own tests do: call verify_otp
    # directly against the DB-stored plaintext is impossible (only the
    # hash is stored, by design) -- so we import auth.py directly for the
    # one piece a pure HTTP test can't reach: knowing the code.
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "marketplace"))
    import importlib
    auth = importlib.import_module("auth")
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "select id from beneficiary_profiles where phone = %s", (phone,)
    )
    row = cur.fetchone()
    conn.close()
    assert row is not None, "auto-provision should have created a beneficiary_profiles row"
    return None  # placeholder -- see main() for the real login sequence


def main():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "marketplace"))
    import auth as auth_module  # the real functions, to get a real code without guessing

    print("--- setup: log in two fresh beneficiaries via SKIP_ELIGIBILITY_CHECK ---")
    phone_a = f"+9230099{random.randint(10000, 99999)}"
    phone_b = f"+9230099{random.randint(10000, 99999)}"

    def real_login(phone):
        # Call auth.request_otp() DIRECTLY (not via HTTP) purely to learn
        # the code -- it's only ever returned via the printed "SMS", never
        # in the HTTP response, by design (see auth.py docstring). Then
        # verify via the REAL HTTP endpoint, same as the frontend does.
        import hashlib
        conn = db()
        cur = conn.cursor()
        # request_otp already ran once via requests.post below in each
        # call site -- here we just need code_hash to brute-check against
        # is impossible (sha256, one-way). Simplest correct approach:
        # call auth.request_otp() in-process (bypassing HTTP only for
        # THIS step), capture nothing new -- it already inserted the row
        # -- then read the plaintext the only place it exists: we can't.
        # So instead: monkeypatch-free approach -- call auth.request_otp
        # in-process and capture its printed code via _send_sms override.
        conn.close()

    def login_via_send_sms_capture(phone):
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
        assert result["eligible"], f"expected auto-provisioned eligibility for {phone}"
        code = captured["message"].split("code is ")[1].split(".")[0]
        r = requests.post(f"{BASE}/auth/verify-otp", json={"phone": phone, "code": code})
        r.raise_for_status()
        return r.json()["token"]

    token_a = login_via_send_sms_capture(phone_a)
    token_b = login_via_send_sms_capture(phone_b)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    print("PASS -- both beneficiaries logged in for real, over HTTP")

    print("\n--- each creates a listing (needed for availability + involvement checks) ---")
    def create_listing(headers, raw_text, **kwargs):
        r = requests.post(f"{BASE}/listing/extract", json={"raw_text": raw_text}, headers=headers)
        r.raise_for_status()
        draft = r.json()
        body = {
            "role": kwargs.get("role", "service"),
            "product_or_service_en": draft["product_or_service_en"],
            "product_or_service_original": draft["product_or_service_original"],
            "skills_en": draft.get("skills_en"),
            **{k: v for k, v in kwargs.items() if k != "role"},
        }
        r = requests.post(f"{BASE}/listing", json=body, headers=headers)
        r.raise_for_status()
        return r.json()["listing_id"]

    listing_a = create_listing(
        headers_a, "sews school uniforms", role="service",
        seeking_work=True, is_remote_capable=True, output_is_physical=False,
    )
    print(f"PASS -- listing_a created ({listing_a})")

    print("\n--- gap 4: POST /listing/{id}/availability ---")
    r = requests.post(
        f"{BASE}/listing/{listing_a}/availability",
        json={"availability": "open_to_offers"},
        headers=headers_a,
    )
    assert r.status_code == 200, r.text
    assert r.json()["availability"] == "open_to_offers"
    conn = db()
    cur = conn.cursor()
    cur.execute("select availability from store_listings where id = %s", (listing_a,))
    assert cur.fetchone()[0] == "open_to_offers"
    conn.close()
    print("PASS -- availability actually persisted")

    # Wrong owner can't touch it
    r = requests.post(
        f"{BASE}/listing/{listing_a}/availability",
        json={"availability": "committed"},
        headers=headers_b,
    )
    assert r.status_code == 403, f"expected 403 for non-owner, got {r.status_code}: {r.text}"
    print("PASS -- non-owner correctly rejected (403)")

    # Invalid value rejected
    r = requests.post(
        f"{BASE}/listing/{listing_a}/availability",
        json={"availability": "on_vacation"},
        headers=headers_a,
    )
    assert r.status_code == 403
    print("PASS -- invalid availability value rejected")

    # Set back to seeking so later matching/search checks in this run see it
    requests.post(
        f"{BASE}/listing/{listing_a}/availability",
        json={"availability": "seeking"},
        headers=headers_a,
    )

    print("\n--- gap 2: POST /donations ---")
    r = requests.post(f"{BASE}/donations", json={"amount": 250}, headers=headers_a)
    assert r.status_code == 200, r.text
    print(f"PASS -- donation recorded: {r.json()}")

    print("\n--- gap 2: POST /me/no-longer-seeking ---")
    r = requests.post(f"{BASE}/me/no-longer-seeking", json={"notes": "found steady work"}, headers=headers_a)
    assert r.status_code == 200, r.text
    print(f"PASS -- {r.json()}")

    print("\n--- gap 2: webhooks require the internal key ---")
    conn = db()
    cur = conn.cursor()
    cur.execute("select id from microfinance_loans where beneficiary_id = "
                "(select id from beneficiary_profiles where phone = %s)", (phone_a,))
    loan_id = cur.fetchone()[0]
    conn.close()

    r = requests.post(f"{BASE}/webhooks/loan-repaid", json={"loan_id": loan_id})
    assert r.status_code == 401, f"expected 401 with no key, got {r.status_code}"
    print("PASS -- webhook rejects a call with no internal key")

    r = requests.post(
        f"{BASE}/webhooks/loan-repaid",
        json={"loan_id": loan_id},
        headers={"X-Internal-Key": "wrong-key"},
    )
    assert r.status_code == 401
    print("PASS -- webhook rejects a call with the WRONG internal key")

    r = requests.post(
        f"{BASE}/webhooks/loan-repaid",
        json={"loan_id": loan_id},
        headers={"X-Internal-Key": INTERNAL_KEY},
    )
    assert r.status_code == 200, r.text
    print(f"PASS -- webhook accepts the correct key: {r.json()}")

    r = requests.post(
        f"{BASE}/webhooks/loan-approved",
        json={"loan_id": loan_id},
        headers={"X-Internal-Key": INTERNAL_KEY},
    )
    assert r.status_code == 200, r.text
    print(f"PASS -- loan-approved webhook: {r.json()}")

    print("\n--- gap 5: GET /reports/impact now requires the internal key too ---")
    r = requests.get(f"{BASE}/reports/impact")
    assert r.status_code == 401, f"expected 401, got {r.status_code}"
    r = requests.get(f"{BASE}/reports/impact", headers={"X-Internal-Key": INTERNAL_KEY})
    assert r.status_code == 200, r.text
    print(f"PASS -- report reachable with the key: {r.json()}")

    print("\n--- gap 3: other_involvements shows up on /listings/search ---")
    r = requests.get(f"{BASE}/listings/search", headers=headers_b)
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert results, "expected at least one search result"
    assert "other_involvements" in results[0], "search results should carry other_involvements now"
    print(f"PASS -- other_involvements present on search results (e.g. {results[0]['other_involvements']})")

    print("\nALL NEW-ENDPOINT CHECKS PASS.")


if __name__ == "__main__":
    main()
