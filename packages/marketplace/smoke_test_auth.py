"""
Tests request_otp() / verify_otp() against real seeded phone numbers,
including a genuine failure case (wrong code) -- not just the happy path.

The real code never gets printed to the actual SMS -- it goes through
_send_sms(), which we intercept here ONLY for testing, to grab the real
code and use it in verify_otp(). Production code still only ever stores a
hash; this is purely a test-time hook, the same thing you'd do to test
any "sends a message" function without a real provider.

Run: python smoke_test_auth.py
"""

import auth
from auth import request_otp, verify_otp

captured = {}


def _fake_send_sms(phone, message):
    # pulls the 6-digit code back out of the message text, for the test only
    import re
    code = re.search(r"\b(\d{6})\b", message).group(1)
    captured["code"] = code
    print(f"(test intercepted the SMS -- real code is {code})")


auth._send_sms = _fake_send_sms


def main():
    print("--- Case 1: not-found phone number ---")
    result = request_otp("+920000000000")
    print(result)
    assert result == {"eligible": False, "reason": "not_found", "otp_sent": False}

    print("\n--- Case 2: rejected loan (Nadia) ---")
    result = request_otp("+923001234575")
    print(result)
    assert result["eligible"] is False, "a rejected loan should not be eligible"

    print("\n--- Case 3: real eligible number (Amina, disbursed) ---")
    result = request_otp("+923001234567")
    print(result)
    assert result["eligible"] is True
    assert result["can_create_listing"] is True

    print("\n--- Case 4: verify with the WRONG code -- should fail cleanly ---")
    result = verify_otp("+923001234567", "000000")
    print(result)
    assert result["verified"] is False

    print("\n--- Case 5: verify with the REAL code -- should succeed ---")
    result = verify_otp("+923001234567", captured["code"])
    print(result)
    assert result["verified"] is True
    assert result["beneficiary_id"] is not None

    print("\n--- Case 6: reusing the SAME code again -- should fail (already consumed) ---")
    result = verify_otp("+923001234567", captured["code"])
    print(result)
    assert result["verified"] is False, "a consumed code must not work twice"

    print("\nPASS -- eligible/ineligible, right/wrong code, and one-time-use all behave correctly.")


if __name__ == "__main__":
    main()
