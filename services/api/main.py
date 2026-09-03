"""
The HTTP layer -- turns the tested Python functions in packages/marketplace
into the actual API contract locked in CLAUDE.md/Marketplace_Spec.md:

    POST /auth/request-otp
    POST /auth/verify-otp
    GET  /me/context
    POST /listing/extract
    POST /listing                -- also runs match_and_notify()
                                     automatically now (4 Sep 2026) --
                                     this IS the delayed-match fix
                                     (Marketplace_Spec.md 5.2): both
                                     sides of every genuinely new match
                                     get notified right here, not only
                                     whoever's frontend happens to ask.
    GET  /listing/{id}/matches   -- added here, not in the original locked
                                     contract: nothing shows a beneficiary
                                     their matches without it. Now a plain
                                     read (get_stored_matches()) -- no
                                     recomputation, POST /listing above
                                     already did that.
    POST /matches/{id}/dismiss   -- added 4 Sep 2026: section 7, "either
                                     side may dismiss a match, and that
                                     pair never resurfaces."
    POST /listing/transcribe     -- added 4 Sep 2026: voice input for card
                                     3, transcribed via Groq's hosted
                                     Whisper. Returns text only -- the
                                     result still goes through the SAME
                                     /listing/extract as typed text, and is
                                     still editable before anything saves.
    GET  /listings/search         -- added 4 Sep 2026: browsing/searching
                                     the marketplace directly, independent
                                     of being matched. Deliberately calls a
                                     DIFFERENT function than the matches
                                     endpoint above -- see search.py's file
                                     docstring for why reusing find_matches()
                                     here would be a real bug, not a shortcut.
    POST /listing/{id}/availability -- added 5 Sep 2026: Marketplace_Spec.md
                                     section 8, "a listing carries an
                                     availability status the person
                                     controls" -- the write path that was
                                     missing (see listings.py).
    POST /donations               -- added 5 Sep 2026: graduation.py's
                                     record_donation(), section 11.1.
    POST /matches/{id}/connect    -- added 5 Sep 2026: graduation.py's
                                     confirm_match_connection().
    POST /me/no-longer-seeking    -- added 5 Sep 2026: graduation.py's
                                     record_no_longer_seeking_assistance().
    POST /webhooks/loan-approved  -- added 5 Sep 2026: the real target for
                                     Al-Khidmat's loan system to call the
                                     moment a loan is written with a trade
                                     category (section 2, "the invitation
                                     problem") -- fires
                                     send_invitation_if_eligible().
    POST /webhooks/loan-repaid    -- added 5 Sep 2026: the real target for
                                     "as soon as it's repaid they'll send
                                     us through API" -- fires
                                     graduation.py's record_loan_repaid().
                                     Gated by require_internal_key(), see
                                     below -- neither webhook is a
                                     beneficiary action, so the JWT scheme
                                     doesn't apply to them.

WHY THIS FILE IS THIN
--------------------------
Every endpoint here is a few lines: read the request, call an already-
tested function from packages/marketplace, return its result. No business
logic lives here -- it already lives in, and was already proven against
real data in, matching.py / auth.py / create_listing.py / reasoning.py /
persist.py. This file's only job is HTTP plumbing: parsing requests,
checking the login token, shaping responses, right status codes.

THE LOGIN TOKEN (JWT) IS ISSUED AND CHECKED HERE, NOT IN auth.py
------------------------------------------------------------------------
auth.py stays framework-agnostic on purpose -- it doesn't know what a JWT
is, doesn't import a web framework, is just as testable standalone as it
already was. Issuing and checking tokens is an HTTP-layer concern, so it
lives here instead.

SECURITY NOTE, MATCHING THE FLOWCHART'S OWN RULE
------------------------------------------------------
POST /listing and POST /listing/extract read beneficiary_id from the
verified token (get_current_beneficiary below), NEVER from the request
body -- so nobody can create a listing, or read someone else's draft,
pretending to be a different beneficiary. This was already the rule
create_listing.py's functions were written to expect; this file is what
actually enforces it.
"""

import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "marketplace"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "rag"))
from auth import request_otp, verify_otp, get_me_context  # noqa: E402
from create_listing import enrich_listing_text, save_listing  # noqa: E402
from matching_pipeline import match_and_notify  # noqa: E402
from persist import get_stored_matches, dismiss_match  # noqa: E402
from search import search_listings  # noqa: E402
from groq_client import transcribe_audio  # noqa: E402
from reporting import get_impact_report  # noqa: E402
from ventures import form_venture  # noqa: E402
from logistics import add_logistics_route  # noqa: E402
from listings import set_availability  # noqa: E402
from graduation import (  # noqa: E402
    record_donation,
    confirm_match_connection,
    record_no_longer_seeking_assistance,
    record_loan_repaid,
)
from lifecycle import send_invitation_if_eligible  # noqa: E402

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 30  # session length -- not specified anywhere yet, a
                       # reasonable default for a phone+OTP app people
                       # don't want to re-login to constantly

app = FastAPI(title="Mustahiq AI Marketplace API")

# CORS: without this, a browser (not a script like requests/curl) silently
# BLOCKS every call from the Vite dev server (localhost:5173) to this API
# (localhost:8000) -- different port counts as a different origin. This
# only matters for a real browser; it's why the earlier HTTP smoke test
# (using the `requests` library) worked fine without it. Wide open for
# local dev; narrow this to the real deployed frontend origin before
# going anywhere near production.
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only -- see comment above
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth plumbing -- issuing and checking the token. Business logic (the
# actual eligibility check) already happened inside auth.py; this part
# only wraps its result in something the app can carry around.
# ---------------------------------------------------------------------------

def _issue_token(beneficiary_id: str) -> str:
    payload = {
        "beneficiary_id": beneficiary_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_beneficiary(authorization: str | None = Header(default=None)) -> str:
    """
    A FastAPI dependency -- every endpoint that needs to know WHO is
    calling declares `beneficiary_id: str = Depends(get_current_beneficiary)`
    and gets it for free, verified, instead of trusting anything the
    client claims.

    authorization is OPTIONAL here on purpose (default=None), not
    required -- a required Header() makes FastAPI's own validation reject
    a missing header with a generic 422 before this function's body ever
    runs, so "no token" and "bad token" would come back as two different
    status codes for what a client should see as the same problem. Both
    now cleanly return 401.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "session expired, log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "invalid token")
    return payload["beneficiary_id"]


def require_internal_key(x_internal_key: str | None = Header(default=None)) -> None:
    """
    A SHARED-SECRET GATE, NOT REAL AUTH -- flagged deliberately, same
    spirit as GET /reports/impact's existing "unauthenticated for now"
    note. This guards two kinds of caller that JWT auth doesn't fit at
    all:

      1. Webhooks (POST /webhooks/loan-approved, /loan-repaid) -- these
         are meant to be called by AL-KHIDMAT'S OWN LOAN SYSTEM, not a
         logged-in beneficiary. There's no beneficiary token to check
         because there's no beneficiary in the request at all.
      2. GET /reports/impact -- staff/donor-facing. Real staff auth is
         Supabase Auth, email+password, role-gated -- that belongs to the
         eligibility side's services/api build (CLAUDE.md's stack table),
         not this module, and doesn't exist in this codebase yet.

    A single shared secret (INTERNAL_API_KEY in .env) sent as the
    X-Internal-Key header is the smallest thing that's still an actual
    check rather than nothing -- FastAPI's Header() auto-converts the
    parameter name (x_internal_key) to the header name (X-Internal-Key).
    This is explicitly a placeholder: when either a real loan-system
    integration or real staff auth exists, swap this dependency out for
    that, everywhere it's used below -- nothing else about these routes
    needs to change.
    """
    expected = os.environ.get("INTERNAL_API_KEY")
    if not expected or x_internal_key != expected:
        raise HTTPException(401, "missing or invalid internal key")


# ---------------------------------------------------------------------------
# Request/response shapes
# ---------------------------------------------------------------------------

class RequestOtpBody(BaseModel):
    phone: str


class VerifyOtpBody(BaseModel):
    phone: str
    code: str


class ExtractBody(BaseModel):
    raw_text: str


class SaveListingBody(BaseModel):
    # cluster_id deliberately NOT here -- auto-derived from
    # beneficiary_profiles.cluster_id server-side (create_listing.py),
    # never trusted from the client, same reasoning as beneficiary_id
    # itself never coming from the request body.
    role: str
    product_or_service_en: str
    product_or_service_original: str
    skills_en: str | None = None
    seeking_inputs: bool = False
    seeking_workers: bool = False
    seeking_partner: bool = False
    seeking_work: bool = False
    is_remote_capable: bool = False
    output_is_physical: bool = True
    will_deliver_outside_area: bool = False
    will_relocate_for_work: bool = False
    will_partner_outside_district: bool = False
    monthly_capacity: str | None = None
    price_range: str | None = None
    business_name: str | None = None
    is_women_led: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/auth/request-otp")
def auth_request_otp(body: RequestOtpBody):
    result = request_otp(body.phone)
    if not result["eligible"]:
        # Two distinct rejections, worded differently -- Marketplace_Spec.md
        # section 2: "not on file" vs "on file but not eligible" are
        # different situations for the beneficiary, even though this
        # simplified schema check collapses to one reason code today.
        raise HTTPException(403, "This number isn't recognised, or isn't yet eligible.")
    return result


@app.post("/auth/verify-otp")
def auth_verify_otp(body: VerifyOtpBody):
    result = verify_otp(body.phone, body.code)
    if not result["verified"]:
        raise HTTPException(401, result["reason"])
    token = _issue_token(result["beneficiary_id"])
    return {"token": token}


@app.get("/me/context")
def me_context(beneficiary_id: str = Depends(get_current_beneficiary)):
    return get_me_context(beneficiary_id)


@app.post("/listing/extract")
def listing_extract(body: ExtractBody, beneficiary_id: str = Depends(get_current_beneficiary)):
    try:
        return enrich_listing_text(beneficiary_id, body.raw_text)
    except ValueError as e:
        raise HTTPException(403, str(e))


@app.post("/listing")
def listing_save(body: SaveListingBody, beneficiary_id: str = Depends(get_current_beneficiary)):
    """
    Saves the listing, then immediately runs match_and_notify() --
    Marketplace_Spec.md section 5, matching "fires whenever a listing is
    created." This is also what actually fixes the delayed-match gap:
    running it here, automatically, on every creation (not waiting for a
    separate GET /matches call the frontend might or might not make) is
    what lets an OLDER listing get notified the moment a NEW one matches
    it, without anyone needing to ask.
    """
    try:
        listing_id = save_listing(beneficiary_id=beneficiary_id, **body.model_dump())
    except ValueError as e:
        raise HTTPException(403, str(e))

    matches = match_and_notify(listing_id)
    return {"listing_id": listing_id, "matches": matches}


@app.get("/listing/{listing_id}/matches")
def listing_matches(listing_id: str, beneficiary_id: str = Depends(get_current_beneficiary)):
    """
    A plain read of what POST /listing already computed and persisted --
    see get_stored_matches()'s own docstring for why this deliberately
    does NOT recompute (no fresh Groq calls just to look at a screen).
    """
    return {"matches": get_stored_matches(listing_id)}


class DismissBody(BaseModel):
    dismissing_listing_id: str  # which of the two participants is dismissing


@app.post("/matches/{match_id}/dismiss")
def matches_dismiss(
    match_id: str,
    body: DismissBody,
    beneficiary_id: str = Depends(get_current_beneficiary),
):
    """
    Marketplace_Spec.md section 7: "Either side may dismiss a match, and
    that pair never resurfaces." dismiss_match() itself already checks
    that dismissing_listing_id is actually one of the match's two
    participants -- an extra check here would verify beneficiary_id owns
    dismissing_listing_id too, but that's not enforceable yet without a
    listing-ownership lookup this endpoint doesn't have reason to add on
    its own; flagged rather than silently skipped.
    """
    try:
        dismiss_match(match_id, body.dismissing_listing_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"dismissed": True}


@app.post("/listing/transcribe")
async def listing_transcribe(
    audio: UploadFile = File(...),
    beneficiary_id: str = Depends(get_current_beneficiary),
):
    """
    Card 3's optional voice input. Returns {"text": "..."} -- the
    frontend drops this straight into the same editable text box typing
    would have filled, then continues into POST /listing/extract exactly
    as before. beneficiary_id isn't used here (transcription doesn't
    touch anyone's data), but the dependency still runs -- this endpoint
    stays behind login like every other listing-creation step, not
    because it needs to know who's calling, but because an unauthenticated
    free-transcription endpoint would just be a way for anyone to burn
    through the Groq account's rate limit.
    """
    audio_bytes = await audio.read()
    text = transcribe_audio(audio_bytes, audio.filename or "audio.webm")
    return {"text": text}


@app.get("/listings/search")
def listings_search(
    q: str | None = None,
    trade_category: str | None = None,
    role: str | None = None,
    district: str | None = None,
    is_women_led: bool | None = None,
    seeking_inputs: bool | None = None,
    seeking_workers: bool | None = None,
    seeking_partner: bool | None = None,
    seeking_work: bool | None = None,
    beneficiary_id: str = Depends(get_current_beneficiary),
):
    results = search_listings(
        q,
        trade_category=trade_category,
        role=role,
        district=district,
        is_women_led=is_women_led,
        seeking_inputs=seeking_inputs,
        seeking_workers=seeking_workers,
        seeking_partner=seeking_partner,
        seeking_work=seeking_work,
        exclude_beneficiary_id=beneficiary_id,  # don't show someone their own listing in their own search
    )
    return {"results": results}


class SetAvailabilityBody(BaseModel):
    availability: str  # 'seeking' / 'open_to_offers' / 'committed' -- see listings.py


class DonationBody(BaseModel):
    amount: float
    listing_id: str | None = None
    note: str | None = None


class NoLongerSeekingBody(BaseModel):
    notes: str | None = None


class LoanWebhookBody(BaseModel):
    loan_id: str


@app.post("/listing/{listing_id}/availability")
def listing_set_availability(
    listing_id: str,
    body: SetAvailabilityBody,
    beneficiary_id: str = Depends(get_current_beneficiary),
):
    """Marketplace_Spec.md section 8 -- "a listing carries an availability status the person controls." """
    try:
        set_availability(beneficiary_id, listing_id, body.availability)
    except ValueError as e:
        raise HTTPException(403, str(e))
    return {"availability": body.availability}


@app.post("/donations")
def donations_create(body: DonationBody, beneficiary_id: str = Depends(get_current_beneficiary)):
    """Marketplace_Spec.md section 10/11.1 -- the voluntary donation, and the became_donor graduation trigger it may fire."""
    return record_donation(beneficiary_id, body.amount, body.listing_id, body.note)


@app.post("/matches/{match_id}/connect")
def matches_connect(match_id: str, beneficiary_id: str = Depends(get_current_beneficiary)):
    """
    Marketplace_Spec.md section 7 -- marks a match 'connected' (the two
    parties actually reached each other), distinct from
    POST /matches/{id}/dismiss. For an employment match, this is also the
    real hired_employee graduation moment -- see graduation.py.
    """
    try:
        return confirm_match_connection(match_id, beneficiary_id)
    except ValueError as e:
        raise HTTPException(403, str(e))


@app.post("/me/no-longer-seeking")
def me_no_longer_seeking(body: NoLongerSeekingBody, beneficiary_id: str = Depends(get_current_beneficiary)):
    """Marketplace_Spec.md section 11.1 -- self-reported, deliberately: nobody but the person can assert this."""
    event_id = record_no_longer_seeking_assistance(beneficiary_id, body.notes)
    return {"graduation_event_id": event_id}


@app.post("/webhooks/loan-approved", dependencies=[Depends(require_internal_key)])
def webhook_loan_approved(body: LoanWebhookBody):
    """
    Marketplace_Spec.md section 2, "the invitation problem" -- call this
    the moment Al-Khidmat's loan system writes a microfinance_loans row
    (insert OR update) with a trade_category_id set. Safe to call on
    every loan write unconditionally -- send_invitation_if_eligible() is
    a no-op (returns False) if there's no qualifying trade category yet.
    """
    sent = send_invitation_if_eligible(body.loan_id)
    return {"invitation_sent": sent}


@app.post("/webhooks/loan-repaid", dependencies=[Depends(require_internal_key)])
def webhook_loan_repaid(body: LoanWebhookBody):
    """
    Marketplace_Spec.md section 11.1 -- "loan repaid field can come from
    microfinance db. As soon as it's repaid they'll send us through API."
    This IS that endpoint.
    """
    try:
        event_id = record_loan_repaid(body.loan_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"graduation_event_id": event_id}


class FormVentureBody(BaseModel):
    venture_listing_id: str
    parent_listing_ids: list[str]


@app.post("/ventures/form")
def ventures_form(body: FormVentureBody, beneficiary_id: str = Depends(get_current_beneficiary)):
    """Marketplace_Spec.md section 9 -- see ventures.py's own docstring for the design call made here."""
    try:
        form_venture(beneficiary_id, body.venture_listing_id, body.parent_listing_ids)
    except ValueError as e:
        raise HTTPException(403, str(e))
    return {"formed": True}


class AddLogisticsRouteBody(BaseModel):
    listing_id: str
    from_district: str
    to_district: str
    vehicle_type: str | None = None
    capacity_description: str | None = None


@app.post("/logistics/routes")
def logistics_add_route(body: AddLogisticsRouteBody, beneficiary_id: str = Depends(get_current_beneficiary)):
    """Marketplace_Spec.md section 6 -- register a corridor for an existing logistics-role listing."""
    try:
        route_id = add_logistics_route(
            body.listing_id, body.from_district, body.to_district,
            body.vehicle_type, body.capacity_description,
        )
    except ValueError as e:
        raise HTTPException(403, str(e))
    return {"route_id": route_id}


@app.get("/reports/impact", dependencies=[Depends(require_internal_key)])
def reports_impact():
    """
    Marketplace_Spec.md section 11 -- staff/donor-facing, not a
    beneficiary endpoint (the only one in this file that isn't).
    UPDATED 5 Sep 2026: was fully unauthenticated; now gated by the same
    require_internal_key() shared secret as the loan webhooks below. This
    is still a placeholder, not real staff auth -- see
    require_internal_key()'s own docstring for what "real" looks like and
    why it isn't built yet. An improvement over wide open, not a finished
    answer.
    """
    return get_impact_report()
