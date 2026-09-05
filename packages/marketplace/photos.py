"""
upload_photo() / list_photos() / delete_photo() -- direct request, 5 Sep
2026: "I should be able to click on my listing, browse, enter pictures
if I want to create a proper portfolio."

WHERE THE ACTUAL IMAGE BYTES LIVE
--------------------------------------
Not in Postgres. Supabase Storage's "listing-photos" bucket (public-read,
5MB/file cap, jpeg/png/webp only -- created via the Storage REST API,
see packages/data/schema's listing_photos comment for how). This file
only ever writes the resulting URL to listing_photos -- same reasoning
as embeddings staying a fixed-size vector rather than raw text: keep
binary data out of the database that's also doing vector search on
every request.

WHY THE SERVICE ROLE KEY, NOT THE ANON KEY
--------------------------------------------------
Uploads happen SERVER-SIDE, after this module has already verified the
caller owns the listing -- the service_role_key (which bypasses Supabase
Storage's row-level security) is appropriate here because the actual
authorization check already happened in Python, in upload_photo() below,
before this key is ever used. It never reaches the browser.

WHY A PLAIN requests.post() CALL, NOT THE supabase-py CLIENT LIBRARY
--------------------------------------------------------------------------
supabase-py isn't a dependency anywhere else in this codebase, and the
Storage REST API for a single file upload is one HTTP call -- pulling in
a whole SDK for that would be more surface area, not less. Same
philosophy as everywhere else in packages/marketplace: plain
psycopg2/requests, no framework wrapping a simple HTTP call.
"""

import os
import uuid

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

BUCKET = "listing-photos"
MAX_PHOTOS_PER_LISTING = 6  # a portfolio, not an unlimited gallery -- keeps
                             # storage bounded and a listing page scannable

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _verify_ownership(cur, beneficiary_id: str, listing_id: str) -> None:
    """Same ownership check as listings.py:set_availability() -- never trust the caller."""
    cur.execute(
        """
        select 1 from listing_participants
        where listing_id = %s and beneficiary_id = %s
          and role = 'owner' and status = 'confirmed'
        """,
        (listing_id, beneficiary_id),
    )
    if cur.fetchone() is None:
        raise ValueError(f"beneficiary {beneficiary_id} is not a confirmed owner of listing {listing_id}")


def upload_photo(beneficiary_id: str, listing_id: str, file_bytes: bytes, content_type: str) -> dict:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"unsupported image type '{content_type}' -- must be one of {list(ALLOWED_CONTENT_TYPES)}")
    if len(file_bytes) > 5 * 1024 * 1024:
        raise ValueError("image is larger than 5MB")

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    _verify_ownership(cur, beneficiary_id, listing_id)

    cur.execute("select count(*) from listing_photos where listing_id = %s", (listing_id,))
    if cur.fetchone()[0] >= MAX_PHOTOS_PER_LISTING:
        cur.close()
        conn.close()
        raise ValueError(f"this listing already has {MAX_PHOTOS_PER_LISTING} photos -- delete one before adding another")

    ext = ALLOWED_CONTENT_TYPES[content_type]
    storage_path = f"{listing_id}/{uuid.uuid4()}.{ext}"

    project_url = os.environ["SUPABASE_PROJECT_URL"]
    service_key = os.environ["service_role_key"]
    upload_url = f"{project_url}/storage/v1/object/{BUCKET}/{storage_path}"

    r = requests.post(
        upload_url,
        headers={
            "Authorization": f"Bearer {service_key}",
            "Content-Type": content_type,
            "x-upsert": "false",
        },
        data=file_bytes,
    )
    if r.status_code not in (200, 201):
        cur.close()
        conn.close()
        raise RuntimeError(f"Supabase Storage upload failed ({r.status_code}): {r.text[:300]}")

    public_url = f"{project_url}/storage/v1/object/public/{BUCKET}/{storage_path}"

    photo_id = str(uuid.uuid4())
    cur.execute(
        "insert into listing_photos (id, listing_id, storage_path, url) values (%s, %s, %s, %s)",
        (photo_id, listing_id, storage_path, public_url),
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"id": photo_id, "url": public_url}


def list_photos(listing_id: str, conn=None) -> list[dict]:
    """
    Plain read -- no auth needed, same as everything else a listing shows
    publicly.

    conn: an already-open connection to reuse -- see involvement.py's
    docstring for why this matters on this project's database (a fresh
    connection can cost seconds, not milliseconds). Added 5 Sep 2026
    after get_listing_detail() was caught opening THREE separate
    connections for one page load (its own, plus one each inside
    get_other_involvements() and this function) -- the exact bug
    persist.py/search.py already fixed once, reintroduced here because
    this function was written fresh without threading a connection
    through it.
    """
    owns_connection = conn is None
    if owns_connection:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        "select id, url, uploaded_at from listing_photos where listing_id = %s order by uploaded_at",
        (listing_id,),
    )
    columns = [d[0] for d in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    if owns_connection:
        conn.close()
    return results


def delete_photo(beneficiary_id: str, photo_id: str) -> None:
    """
    Deletes the database row AND the underlying Storage file. Ownership
    verified via listing_photos -> store_listings -> listing_participants
    -- the same three-table join involvement.py uses for the opposite
    direction (a listing's owners' other listings).
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        """
        select lp.storage_path, lp.listing_id
        from listing_photos lp
        join listing_participants part
          on part.listing_id = lp.listing_id and part.beneficiary_id = %s
             and part.role = 'owner' and part.status = 'confirmed'
        where lp.id = %s
        """,
        (beneficiary_id, photo_id),
    )
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        raise ValueError(f"photo {photo_id} doesn't exist, or beneficiary {beneficiary_id} doesn't own its listing")
    storage_path, _listing_id = row

    cur.execute("delete from listing_photos where id = %s", (photo_id,))
    conn.commit()
    cur.close()
    conn.close()

    project_url = os.environ["SUPABASE_PROJECT_URL"]
    service_key = os.environ["service_role_key"]
    requests.delete(
        f"{project_url}/storage/v1/object/{BUCKET}/{storage_path}",
        headers={"Authorization": f"Bearer {service_key}"},
    )
    # Deliberately not raising on a failed Storage delete -- the
    # database row (the thing everything else actually reads) is
    # already gone; an orphaned file in Storage is a cleanup nuisance,
    # not a correctness problem the caller needs to see.
