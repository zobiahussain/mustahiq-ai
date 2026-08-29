-- ============================================================
-- Al-Khidmat Beneficiary Marketplace
-- MARKETPLACE MODULE SCHEMA  --  Supabase / Postgres
--
-- Run AFTER al_khidmat_core_schema.sql. Depends on
-- beneficiary_profiles and staff_users from that file.
--
-- Embedding dimension is 768.
--
-- SCOPE NOTE: the marketplace runs on the beneficiary app with NO
-- staff dependency. Staff run microfinance and read reports; they
-- do not create listings, approve matches, or make introductions.
--
-- NOTHING IS CHARGED AT ANY POINT. There is no registration fee,
-- no premium ranking, and no claim on business earnings. The only
-- money flow is a voluntary donation a beneficiary may choose to
-- make once established.
-- ============================================================


-- ============================================================
-- 1. TRADE CATEGORIES
-- Reference table, not an enum, so a category can be added without
-- a migration. "Women-led" is deliberately NOT here -- it is an
-- attribute that cuts across every category, and lives as a flag
-- on the listing.
-- ============================================================

create table trade_categories (
    id                      uuid primary key default gen_random_uuid(),
    name                    text unique not null,
    notes                   text,
    active                  boolean default true
);

insert into trade_categories (name) values
    ('Trading businesses'),
    ('Grocery / Karyana'),
    ('Tailoring & embroidery'),
    ('Livestock'),
    ('Manufacturing'),
    ('Services'),
    ('Food'),
    ('Three-wheeler / rickshaw'),
    ('Agriculture'),
    ('Freelancing / technology');


-- ============================================================
-- 2. STORE LISTINGS
-- A listing is A BUSINESS, not a person. It may be run by one
-- beneficiary or by several who formed a venture -- ownership
-- lives in listing_participants, never on this table.
--
-- Willingness to travel is asked PER MODEL, because different
-- things move in each: goods in a supply match, a person in an
-- employment match, both parties in a joint venture. There is no
-- transportability lookup table -- the person is asked directly,
-- since they know and a table would only guess.
-- ============================================================

create table store_listings (
    id                      uuid primary key default gen_random_uuid(),

    -- null for a venture listing; venture ownership is in
    -- listing_participants
    primary_beneficiary_id  uuid references beneficiary_profiles(id) on delete cascade,

    business_name           text,
    trade_category_id       uuid not null references trade_categories(id),
    product_or_service      text not null,
    skills                  text,                 -- what this business can DO,
                                                  -- used for employment matching
    monthly_capacity        text,
    price_range             text,

    -- location. cluster is Al-Khidmat's own operating unit and is
    -- the primary proximity signal; district is the fallback.
    cluster_id              text,
    district                text not null,
    city                    text,

    role                    text not null
                              check (role in
                                ('supplier', 'producer', 'retailer',
                                 'service', 'logistics')),

    -- what this listing is looking for. Drives which of the three
    -- models it participates in. A listing may seek more than one.
    seeking_inputs          boolean default false,   -- supply chain
    seeking_workers         boolean default false,   -- employment
    seeking_partner         boolean default false,   -- joint venture
    seeking_work            boolean default false,   -- this person wants employment

    -- willingness to travel, asked per model
    will_deliver_outside_area   boolean default false,  -- goods move
    will_relocate_for_work      boolean default false,  -- the person moves.
                                                        -- Deliberately a plain boolean:
                                                        -- the real decision is made when
                                                        -- they see the actual city and
                                                        -- offer, not declared in advance.
    will_partner_outside_district boolean default false,

    -- cuts across every trade category; useful for donor reporting
    is_women_led            boolean default false,

    -- availability. The person controls this, but see
    -- open_request_count for the automatic backstop.
    availability            text default 'seeking'
                              check (availability in
                                ('seeking',          -- actively looking
                                 'open_to_offers',   -- will hear a good one
                                 'committed')),      -- capacity spoken for

    -- auto rate limiting: a listing stops surfacing in new matches
    -- once too many requests sit unanswered. Nobody marks
    -- themselves busy voluntarily, so this protects both sides --
    -- a supplier buried in 40 requests answers none of them.
    open_request_count      int default 0,
    max_open_requests       int default 5,

    embedding               vector(768),

    -- listings expire so dead ones self-clean instead of
    -- accumulating
    expires_at              date default (current_date + interval '6 months'),
    active                  boolean default true,

    created_at              timestamptz default now(),
    updated_at              timestamptz default now()
);

create index on store_listings (trade_category_id);
create index on store_listings (cluster_id);
create index on store_listings (district);
create index on store_listings (role);
create index on store_listings (availability, active);
create index on store_listings (expires_at);
create index on store_listings using hnsw (embedding vector_cosine_ops);


-- ============================================================
-- 3. LOGISTICS ROUTES
-- Rickshaw and three-wheeler operators cover a corridor, not a
-- point, so a single district column cannot describe them.
--
-- Logistics surfaces TWO ways:
--   1. automatically attached to a cross-cluster match
--   2. searched directly by anyone needing transport, including
--      for business that has nothing to do with the marketplace
-- ============================================================

create table logistics_routes (
    id                      uuid primary key default gen_random_uuid(),
    listing_id              uuid not null references store_listings(id) on delete cascade,
    from_district           text not null,
    to_district             text not null,
    vehicle_type            text,                 -- rickshaw | loader | pickup | ...
    capacity_description    text,                 -- what fits, what does not
    active                  boolean default true,
    created_at              timestamptz default now()
);

create index on logistics_routes (from_district, to_district);
create index on logistics_routes (listing_id);


-- ============================================================
-- 4. LISTING PARTICIPANTS
-- Who is involved in a listing and how. One row per person per
-- listing. A solo trader has one row; a venture between two people
-- has two; an employee has a row with role = 'employee'.
--
-- This is also what powers the public transparency view: opening
-- someone's listing shows every OTHER confirmed listing they are
-- involved in, so availability is visible without asking.
-- Pending involvement is never shown.
-- ============================================================

create table listing_participants (
    id                      uuid primary key default gen_random_uuid(),
    listing_id              uuid not null references store_listings(id) on delete cascade,
    beneficiary_id          uuid not null references beneficiary_profiles(id) on delete cascade,

    role                    text not null
                              check (role in ('owner', 'employee')),
    equity_share            numeric,              -- optional, owners only

    status                  text default 'confirmed'
                              check (status in ('confirmed', 'ended')),

    joined_at               timestamptz default now(),
    ended_at                timestamptz,

    unique (listing_id, beneficiary_id)
);

create index on listing_participants (beneficiary_id, status);
create index on listing_participants (listing_id);


-- ============================================================
-- 5. VENTURE LINEAGE
-- When listings combine into a venture, the venture is a NEW
-- listing that declares its own cluster, district, trade and role
-- -- nothing is inherited, because the combined shop may be
-- somewhere neither parent was.
--
-- Lineage is recorded separately: partly so the same two people
-- are not re-matched to each other, partly because "this venture
-- grew from three beneficiaries across two clusters" is a real
-- outcome worth reporting.
-- ============================================================

create table venture_lineage (
    id                      uuid primary key default gen_random_uuid(),
    venture_listing_id      uuid not null references store_listings(id) on delete cascade,
    parent_listing_id       uuid not null references store_listings(id) on delete cascade,
    formed_at               timestamptz default now(),
    unique (venture_listing_id, parent_listing_id),
    check (venture_listing_id <> parent_listing_id)
);

create index on venture_lineage (venture_listing_id);
create index on venture_lineage (parent_listing_id);


-- ============================================================
-- 6. MARKETPLACE MATCHES
-- Three models, one table.
--
-- No staff review gate: matches go to BOTH parties directly. They
-- weigh their options and choose, as in any real market. Either
-- side may dismiss, and a dismissed pair never resurfaces.
-- ============================================================

create table marketplace_matches (
    id                      uuid primary key default gen_random_uuid(),

    match_model             text not null
                              check (match_model in
                                ('supply_chain',    -- supplier <-> producer
                                 'employment',      -- business needs a skill <-> person has it
                                 'joint_venture')), -- owner + owner -> new business

    listing_a_id            uuid not null references store_listings(id) on delete cascade,
    listing_b_id            uuid not null references store_listings(id) on delete cascade,

    similarity_score        numeric not null,     -- raw vector similarity
    proximity_multiplier    numeric not null,     -- 1.00 same cluster, down to 0.50
    final_score             numeric not null,     -- similarity x multiplier
    proximity_label         text,                 -- 'same cluster' | 'Sukkur -> Hyderabad'

    reason                  text,                 -- plain-language, LLM-written for readability

    -- suggested transport for a cross-cluster goods match
    suggested_logistics_id  uuid references store_listings(id),

    status                  text default 'active'
                              check (status in
                                ('active',        -- live, both sides can act
                                 'dismissed',     -- one side declined; never resurfaces
                                 'connected',     -- they made contact
                                 'expired')),     -- no response within the window

    dismissed_by_listing_id uuid references store_listings(id),

    -- requests expire so nobody waits indefinitely and slots free up
    expires_at              timestamptz default (now() + interval '7 days'),

    created_at              timestamptz default now(),
    unique (match_model, listing_a_id, listing_b_id),
    check (listing_a_id <> listing_b_id)
);

create index on marketplace_matches (listing_a_id, status);
create index on marketplace_matches (listing_b_id, status);
create index on marketplace_matches (status, expires_at);
create index on marketplace_matches (final_score desc);


-- ============================================================
-- 7. NOTIFICATIONS
-- SMS and email only. No phone calls -- that would put the burden
-- back on Al-Khidmat staff, which this module deliberately avoids.
-- ============================================================

create table notifications (
    id                      uuid primary key default gen_random_uuid(),
    beneficiary_id          uuid not null references beneficiary_profiles(id) on delete cascade,
    match_id                uuid references marketplace_matches(id) on delete cascade,

    channel                 text not null check (channel in ('sms', 'email')),
    body                    text,
    status                  text default 'pending'
                              check (status in ('pending', 'sent', 'failed')),
    sent_at                 timestamptz,
    created_at              timestamptz default now()
);

create index on notifications (beneficiary_id, status);


-- ============================================================
-- 8. DONATIONS
-- Voluntary only. There is no schedule, no amount owed, no overdue
-- state, and nothing that could be read as an obligation on a
-- beneficiary's business income.
--
-- A gentle reminder may be offered once a business is established;
-- whether to give, and how much, is entirely theirs.
-- ============================================================

create table donations (
    id                      uuid primary key default gen_random_uuid(),
    beneficiary_id          uuid not null references beneficiary_profiles(id) on delete cascade,
    listing_id              uuid references store_listings(id),
    amount                  numeric not null,
    donated_at              timestamptz default now(),
    note                    text
);

create index on donations (beneficiary_id);


-- ============================================================
-- 9. GRADUATION EVENTS
-- Al-Khidmat's own stated goal is turning beneficiaries into
-- self-reliant businesses and eventually into donors. In Islamic
-- terms this is the move from mustahiq (eligible to receive) to
-- someone who gives.
--
-- Tracking it turns a narrative into a reportable metric, which is
-- worth more to the organisation than any fee this module could
-- have charged.
-- ============================================================

create table graduation_events (
    id                      uuid primary key default gen_random_uuid(),
    beneficiary_id          uuid not null references beneficiary_profiles(id) on delete cascade,

    event_type              text not null
                              check (event_type in
                                ('loan_repaid',
                                 'business_established',
                                 'hired_employee',       -- created work for someone else
                                 'became_donor',
                                 'no_longer_seeking_assistance')),

    listing_id              uuid references store_listings(id),
    recorded_at             timestamptz default now(),
    notes                   text
);

create index on graduation_events (beneficiary_id, event_type);


-- ============================================================
-- REFERENCE QUERIES
-- ============================================================

-- A. SUPPLY-CHAIN MATCHING for a producer needing inputs.
--    Filters run alongside the ranking, so only genuinely
--    reachable candidates are ever scored.
--
-- select l.id, l.business_name, l.product_or_service,
--        1 - (l.embedding <=> :query_vec) as similarity
-- from store_listings l
-- where l.active = true
--   and l.availability in ('seeking', 'open_to_offers')
--   and l.role = 'supplier'
--   and l.open_request_count < l.max_open_requests
--   and l.id <> :own_listing_id
--   and (l.cluster_id = :my_cluster or l.will_deliver_outside_area = true)
-- order by l.embedding <=> :query_vec
-- limit 10;


-- B. EMPLOYMENT MATCHING -- a business needs a skill.
--    Distant candidates appear only if willing to relocate; the
--    actual decision is theirs once they see the city and offer.
--
-- select l.id, l.skills, l.district, l.city
-- from store_listings l
-- where l.active = true
--   and l.seeking_work = true
--   and l.availability = 'seeking'
--   and (l.cluster_id = :my_cluster or l.will_relocate_for_work = true)
-- order by l.embedding <=> :needed_skill_vec
-- limit 10;


-- C. TRANSPORT for a cross-cluster match, or for any direct search.
--
-- select l.id, l.business_name, r.vehicle_type, r.capacity_description
-- from logistics_routes r
-- join store_listings l on l.id = r.listing_id
-- where r.active = true
--   and l.active = true
--   and l.availability in ('seeking', 'open_to_offers')
--   and r.from_district = :from_district
--   and r.to_district   = :to_district;


-- D. TRANSPARENCY -- everywhere else this person is involved.
--    Confirmed only; pending involvement is never shown.
--
-- select l.business_name, lp.role, tc.name as trade
-- from listing_participants lp
-- join store_listings l on l.id = lp.listing_id
-- join trade_categories tc on tc.id = l.trade_category_id
-- where lp.beneficiary_id = :beneficiary_id
--   and lp.status = 'confirmed'
--   and l.id <> :current_listing_id;


-- E. EXPIRE STALE MATCHES and free up request slots. Runs daily.
--
-- update marketplace_matches
-- set status = 'expired'
-- where status = 'active' and expires_at < now();


-- F. IMPACT REPORT -- what Al-Khidmat shows donors.
--
-- select
--   (select count(*) from marketplace_matches where status = 'connected')
--     as connections_made,
--   (select count(*) from venture_lineage) as ventures_formed,
--   (select count(*) from listing_participants where role = 'employee')
--     as jobs_created,
--   (select count(*) from graduation_events where event_type = 'became_donor')
--     as beneficiaries_now_donors,
--   (select count(*) from store_listings where is_women_led and active)
--     as women_led_businesses;
