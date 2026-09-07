-- logistics_routes had no uniqueness on the route itself, and
-- add_logistics_route() did a blind INSERT -- so an operator adding the
-- same corridor twice (a re-run smoke test, a double-tap in the UI) piled
-- up identical rows, and search_transport() then listed that operator once
-- per row (observed: "Kashif Rickshaw Transport" x7 for one corridor).
--
-- 1. Collapse the existing exact-duplicate rows, keeping the earliest id.
-- 2. Add a unique index so it can't recur at the DB level.
--    add_logistics_route() also now checks-then-inserts so the normal path
--    stays idempotent instead of raising on this constraint.

delete from logistics_routes a
using logistics_routes b
where a.id > b.id
  and a.listing_id = b.listing_id
  and a.from_district = b.from_district
  and a.to_district = b.to_district
  and a.vehicle_type is not distinct from b.vehicle_type
  and a.capacity_description is not distinct from b.capacity_description;

create unique index if not exists logistics_routes_unique_route
    on logistics_routes (
        listing_id,
        from_district,
        to_district,
        (coalesce(vehicle_type, '')),
        (coalesce(capacity_description, ''))
    );
