"""
Marketplace_Spec.md section 6: logistics as a distinct role, surfacing
two ways -- automatically attached to a cross-cluster goods match, or
found by direct search for transport that has nothing to do with the
marketplace otherwise.

WHY A LOGISTICS LISTING NEEDS ITS OWN ROUTE-ADDING STEP
------------------------------------------------------------
save_listing() (create_listing.py) creates the STORE_LISTINGS row -- a
logistics operator gets one of those like anyone else (role='logistics').
But a route ("Sukkur to Hyderabad, three-wheeler, fits up to 200kg") is a
SEPARATE fact -- an operator covers a corridor, not a point, and the
schema's own comment on logistics_routes says exactly that: "an operator
covers a corridor, not a point." One listing can have several routes.
add_logistics_route() is that separate step, called after the listing
itself exists.
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def add_logistics_route(
    listing_id: str,
    from_district: str,
    to_district: str,
    vehicle_type: str | None = None,
    capacity_description: str | None = None,
) -> str:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("select role from store_listings where id = %s", (listing_id,))
    row = cur.fetchone()
    if row is None:
        cur.close()
        conn.close()
        raise ValueError(f"no store_listings row with id={listing_id}")
    if row[0] != "logistics":
        cur.close()
        conn.close()
        raise ValueError(
            f"listing {listing_id} has role={row[0]!r}, not 'logistics' -- "
            "routes only make sense on a logistics-role listing"
        )

    cur.execute(
        """
        insert into logistics_routes (listing_id, from_district, to_district, vehicle_type, capacity_description)
        values (%s, %s, %s, %s, %s)
        returning id
        """,
        (listing_id, from_district, to_district, vehicle_type, capacity_description),
    )
    route_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return route_id


def search_transport(from_district: str, to_district: str) -> list[dict]:
    """Schema reference query C -- for a cross-cluster match, or for any direct search."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        """
        select l.id, l.business_name, r.vehicle_type, r.capacity_description
        from logistics_routes r
        join store_listings l on l.id = r.listing_id
        where r.active = true
          and l.active = true
          and l.availability in ('seeking', 'open_to_offers')
          and r.from_district = %s
          and r.to_district = %s
        """,
        (from_district, to_district),
    )
    columns = [d[0] for d in cur.description]
    results = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return results


def find_logistics_for_route(from_district: str, to_district: str) -> str | None:
    """
    The AUTOMATIC half of section 6.1 -- called from matching_pipeline.py
    right after a cross-cluster supply_chain match is persisted, to
    suggest an operator for it. Checks both directions (a route registered
    Sukkur->Hyderabad is exactly as usable for a Hyderabad->Sukkur need,
    physically) since an operator's OWN description of their route
    doesn't necessarily match which side the goods start from. Returns
    just one listing_id -- the schema column this feeds
    (marketplace_matches.suggested_logistics_id) is a single suggestion,
    not a list to choose from.
    """
    for a, b in [(from_district, to_district), (to_district, from_district)]:
        results = search_transport(a, b)
        if results:
            return results[0]["id"]
    return None
