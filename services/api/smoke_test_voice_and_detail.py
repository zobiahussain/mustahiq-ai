"""
Real HTTP tests for the 5 Sep 2026 additions: voice-first listing draft
(POST /listing/draft), single-listing detail (GET /listing/{id}), and
photo upload/delete. Run against port 8001, never the dev port 8000.
"""

import io
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "marketplace"))
import auth as auth_module  # noqa: E402

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


def main():
    import random
    phone = f"+9230088{random.randint(10000, 99999)}"
    token = login(phone)
    headers = {"Authorization": f"Bearer {token}"}

    print("--- POST /listing/draft (voice-first full draft) ---")
    r = requests.post(
        f"{BASE}/listing/draft",
        json={"raw_text": "I stitch school uniforms and shalwar kameez, I need someone to supply me cotton fabric regularly"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    draft = r.json()
    print(f"  draft: {draft}")
    assert draft["role"] in ("supplier", "producer", "retailer", "service", "logistics")
    assert isinstance(draft["seeking_inputs"], bool)
    assert "is_remote_capable" not in draft, "draft must NOT include the safety-gated fields"
    assert "output_is_physical" not in draft, "draft must NOT include the safety-gated fields"
    print("PASS -- draft has role/seeking flags/description, correctly omits the two gated fields")

    print("\n--- POST /listing (save using the draft + explicit gates) ---")
    body = {
        "role": draft["role"],
        "product_or_service_en": draft["product_or_service_en"],
        "product_or_service_original": draft["product_or_service_original"],
        "skills_en": draft.get("skills_en"),
        "seeking_inputs": draft.get("seeking_inputs", False),
        "seeking_workers": draft.get("seeking_workers", False),
        "seeking_partner": draft.get("seeking_partner", False),
        "seeking_work": draft.get("seeking_work", False),
        "business_name": draft.get("business_name"),
        "is_women_led": draft.get("is_women_led", False),
        "monthly_capacity": draft.get("monthly_capacity"),
        "price_range": draft.get("price_range"),
        # the two gates + travel flags -- explicit, never from the draft
        "is_remote_capable": False,
        "output_is_physical": True,
        "will_deliver_outside_area": True,
    }
    r = requests.post(f"{BASE}/listing", json=body, headers=headers)
    assert r.status_code == 200, r.text
    listing_id = r.json()["listing_id"]
    print(f"PASS -- listing created ({listing_id})")

    print("\n--- GET /listing/{id} (detail page) ---")
    r = requests.get(f"{BASE}/listing/{listing_id}", headers=headers)
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["is_owner"] is True
    assert detail["photos"] == []
    assert "other_involvements" in detail
    print(f"PASS -- detail loaded, is_owner=True, photos=[], product_or_service_original={detail['product_or_service_original']!r}")

    print("\n--- 404 for a nonexistent listing ---")
    r = requests.get(f"{BASE}/listing/00000000-0000-0000-0000-000000000000", headers=headers)
    assert r.status_code == 404, r.text
    print("PASS -- 404 for a real miss")

    print("\n--- POST /listing/{id}/photos (upload a real tiny PNG) ---")
    # 1x1 red pixel PNG, valid bytes
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001080600000"
        "01f15c4890000000a4944415478da6360000002000155e621bc0000000049454e44ae426082"
    )
    r = requests.post(
        f"{BASE}/listing/{listing_id}/photos",
        files={"photo": ("test.png", io.BytesIO(png_bytes), "image/png")},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    photo = r.json()
    print(f"  uploaded: {photo}")
    assert photo["url"].startswith("http")
    print("PASS -- photo uploaded, real URL returned")

    print("\n--- verify the photo shows up on GET /listing/{id} now ---")
    r = requests.get(f"{BASE}/listing/{listing_id}", headers=headers)
    assert len(r.json()["photos"]) == 1
    print("PASS -- photo appears in detail view")

    print("\n--- verify the uploaded image is actually fetchable at its public URL ---")
    r = requests.get(photo["url"])
    assert r.status_code == 200, f"expected the public URL to actually serve the image, got {r.status_code}"
    assert r.content == png_bytes
    print("PASS -- public URL genuinely serves the exact bytes uploaded")

    print("\n--- DELETE /photos/{id} ---")
    r = requests.delete(f"{BASE}/photos/{photo['id']}", headers=headers)
    assert r.status_code == 200, r.text
    r = requests.get(f"{BASE}/listing/{listing_id}", headers=headers)
    assert r.json()["photos"] == []
    print("PASS -- photo deleted, gone from detail view")

    print("\n--- non-owner cannot upload to this listing ---")
    other_token = login(f"+9230077{random.randint(10000, 99999)}")
    r = requests.post(
        f"{BASE}/listing/{listing_id}/photos",
        files={"photo": ("test.png", io.BytesIO(png_bytes), "image/png")},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"
    print("PASS -- non-owner correctly rejected")

    print("\nALL VOICE-FIRST + DETAIL + PHOTO CHECKS PASS.")


if __name__ == "__main__":
    main()
