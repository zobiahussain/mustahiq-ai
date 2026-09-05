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
-- 1. BENEFICIARY APP ACCOUNTS & LOGIN
-- The marketplace has its own access model, deliberately
-- different from the staff portal's. A beneficiary owns their own
-- listing and matches, so they authenticate as themselves -- but
-- there is no password, no email, no account-recovery flow: login
-- is a phone number plus a one-time code sent by SMS, the same
-- channel already used for match notifications (see NOTIFICATIONS
-- below). The pattern mirrors Easypaisa / JazzCash login, so it is
-- already familiar.
--
-- The phone number is captured on the loan application, so it
-- links straight to the existing beneficiary_profiles row rather
-- than creating a new identity. Changing a registered number is
-- staff-assisted at a facilitation centre, not self-service --
-- self-service recovery without email is not realistic for this
-- clientele.
-- ============================================================

create table beneficiary_app_accounts (
    id                        uuid primary key default gen_random_uuid(),
    beneficiary_id            uuid unique not null
                                references beneficiary_profiles(id) on delete cascade,
    phone                     text unique not null,   -- login identifier
    phone_verified            boolean default false,
    previous_phone            text,
    phone_changed_by_staff_id uuid references staff_users(id),
    phone_changed_at          timestamptz,
    preferred_language        text default 'ur',
    active                    boolean default true,
    last_login_at             timestamptz,
    created_at                timestamptz default now()
);

create index on beneficiary_app_accounts (phone);

create table login_otps (
    id           uuid primary key default gen_random_uuid(),
    phone        text not null,
    code_hash    text not null,      -- store a hash, never the code
    expires_at   timestamptz not null default (now() + interval '10 minutes'),
    consumed_at  timestamptz,
    attempts     int default 0,
    created_at   timestamptz default now()
);

create index on login_otps (phone, expires_at);


-- ============================================================
-- 2. TRADE CATEGORIES
-- Reference table, not an enum, so a category can be added without
-- a migration. "Women-led" is deliberately NOT here -- it is an
-- attribute that cuts across every category, and lives as a flag
-- on the listing.
--
-- Comes before MICROFINANCE LOANS below because that table
-- references it -- the trade category is now decided at loan
-- application time, not at listing creation.
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
-- 3. MICROFINANCE LOANS -- THE MARKETPLACE'S ELIGIBILITY GATE
-- The marketplace is not public. The one thing this module needs
-- to know about someone before they can sign up is whether
-- Al-Khidmat actually financed them into a real business -- not
-- income, not household size, just "did they receive a loan for
-- one of the ten trade categories."
--
-- Loan PROCESSING is not this module's job (that is the
-- eligibility/microfinance side, tracked in applications on the
-- core schema); this table is a thin RECORD of the outcome. In
-- production it is populated by Al-Khidmat's existing loan system
-- via a new field on the loan application: the loan officer picks
-- a trade category (or "Not a business," for bail/medical/debt
-- relief -- including the Liberation Loan) at the same moment they
-- already record the loan's purpose. For the demo it is seeded
-- directly.
--
-- trade_category_id IS NULL means "not a business" -- this
-- REPLACES an earlier leads_to_business boolean that hung its
-- Liberation-Loan case off the loan PRODUCT name, which
-- contradicted this file's own rule that loan_product carries no
-- logic. A category is the real signal; a beneficiary with no
-- category can still log in, but is never offered the
-- listing-creation flow (see REFERENCE QUERIES, G).
--
-- stated_purpose_text is the loan officer's free-text note on what
-- the loan is for -- kept alongside the category so the assistant
-- has something to start the listing-creation conversation from,
-- instead of a blank slate.
--
-- Gate is 'approved' OR 'disbursed', not disbursed-only. The
-- trade category is decided at approval, before money moves --
-- waiting for disbursement (which can lag on banking/admin delays)
-- would hold someone back from a decision that's already made.
-- This is a deliberate loosening of "after their loan is
-- disbursed" language that appears elsewhere in the docs -- see
-- Marketplace_Spec.md and SRS.md, both updated to match.
--
-- No separate 'repaid' status: once disbursed, a loan stays
-- 'disbursed' -- repayment doesn't change marketplace standing, so
-- it's tracked as a positive graduation_events row
-- (event_type = 'loan_repaid'), not a status transition here.
-- 'defaulted' is the one status that closes an EXISTING listing,
-- not just future signup -- application logic must deactivate any
-- store_listings row for this beneficiary when status flips to
-- 'defaulted', not only gate new signups against it.
-- ============================================================

create table microfinance_loans (
    id                    uuid primary key default gen_random_uuid(),
    loan_reference        text unique not null,   -- Al-Khidmat's own ID
    beneficiary_id        uuid not null references beneficiary_profiles(id) on delete cascade,
    loan_product          text not null,          -- one of four, stored loosely --
                                                   -- no logic hangs off the specific product
    trade_category_id     uuid references trade_categories(id),  -- null = not a business
    stated_purpose_text   text,                   -- loan officer's free text; seeds the listing

    status                text not null default 'approved'
                            check (status in
                              ('approved',      -- decided, not yet paid out -- ELIGIBLE
                               'disbursed',     -- paid out -- still eligible
                               'defaulted',     -- written off -- gate closed, existing
                                                -- listings deactivated (application logic)
                               'rejected')),    -- never funded -- never eligible

    amount_disbursed      numeric,
    disbursed_on          date,
    -- Added 4 Sep 2026, alongside the loan_repaid graduation trigger: the
    -- loan term's expected end date, set at disbursement. NOT the same
    -- thing as the actual repaid-on date -- that arrives later via a
    -- real signal from Al-Khidmat's loan system (graduation.py's
    -- record_loan_repaid()), not computed or guessed here.
    expected_repayment_date date,
    created_at            timestamptz default now()
);

create index on microfinance_loans (beneficiary_id);
create index on microfinance_loans (status);


-- ============================================================
-- 4. MARKETPLACE INVITATIONS
-- Solves a gap the eligibility check alone leaves open: a
-- background phone-number lookup can tell the SYSTEM someone is
-- eligible, but nothing tells the PERSON the app exists. Nobody
-- reliably remembers to mention it at the loan desk.
--
-- So this fires automatically the moment a microfinance_loans row
-- is written with a trade_category_id set: an SMS goes out with a
-- short code, doubling as the invitation and a convenience.
--
-- IMPORTANT -- this token is NOT the eligibility gate and is NOT
-- required to sign up. The gate is still the phone + trade-category
-- lookup in REFERENCE QUERIES, G. If the SMS is lost or never
-- arrives, phone + OTP alone still works, because nobody eligible
-- should ever be locked out by a message that didn't arrive. All
-- this table buys is (a) an automatic nudge at the moment someone
-- is likeliest to act on it, and (b) an invited-vs-signed-up ratio
-- worth reporting (REFERENCE QUERIES, I).
-- ============================================================

create table marketplace_invitations (
    id                      uuid primary key default gen_random_uuid(),
    microfinance_loan_id    uuid not null references microfinance_loans(id) on delete cascade,
    code_hash               text not null,      -- store a hash, never the code -- same
                                                -- reasoning as login_otps
    sent_at                 timestamptz,
    signed_up_at            timestamptz,        -- set when this beneficiary's
                                                -- beneficiary_app_accounts row is first created
    created_at              timestamptz default now()
);

create index on marketplace_invitations (microfinance_loan_id);


-- ============================================================
-- 5. STORE LISTINGS
-- A listing is A BUSINESS, not a person. It may be run by one
-- beneficiary or by several who formed a venture -- ownership
-- lives in listing_participants, never on this table.
--
-- TWO independent flags gate travel/distance logic, not one --
-- a physical good and a person's presence don't always move
-- together. A remote consultant who also ships physical sample
-- kits is remote in one sense and not the other; a supplier of
-- design files sold digitally is remote in both.
--
--   is_remote_capable  -- does the WORK need someone physically
--                          present? Gates will_relocate_for_work
--                          and will_partner_outside_district.
--   output_is_physical -- does this listing exchange a physical
--                          good that has to be transported? Gates
--                          will_deliver_outside_area. Defaults to
--                          true because most listings here are
--                          physical goods or in-person services.
--
-- When a flag is true, willingness/distance is asked and applied
-- as normal; when false, that side of proximity is skipped
-- entirely -- full score, no filter, no penalty, nationwide.
-- Neither is inferred from trade category -- a tailor taking
-- custom orders by post is remote-capable even though tailoring
-- generally is not, so the person is asked directly both times.
--
-- product_or_service and skills are each split into an _en and an
-- _original column. This is NOT a contradiction of the platform's
-- "English only" constraint (SRS 7.2) -- that rule is about the
-- SYSTEM's internal matching representation, staying deterministic
-- and simple to embed. It was never a promise that a beneficiary
-- has to speak English to use the app -- Marketplace_Spec.md
-- already commits to "voice or text, in whatever language they
-- speak." The _en column is what gets embedded and matched
-- (English in, English out, one predictable pipeline); _original
-- is what the beneficiary actually said, shown back to THEM and to
-- their eventual match, in their own words and language. Neither
-- column is optional -- both are populated from one extraction
-- call (see apps/marketplace-portal build notes).
-- ============================================================

create table store_listings (
    id                      uuid primary key default gen_random_uuid(),

    -- null for a venture listing; venture ownership is in
    -- listing_participants
    primary_beneficiary_id  uuid references beneficiary_profiles(id) on delete cascade,

    business_name                text,
    trade_category_id            uuid not null references trade_categories(id),

    product_or_service_en        text not null,   -- embedded, matched against
    product_or_service_original  text not null,   -- shown to the beneficiary and their match

    skills_en                    text,            -- what this business can DO,
    skills_original              text,            -- used for employment matching

    monthly_capacity             text,
    price_range                  text,

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

    -- two independent gates -- see section header. Both asked
    -- directly by the assistant.
    is_remote_capable       boolean default false,   -- "Can you do this work
                                                      -- remotely, or does it need
                                                      -- to be in person?"
    output_is_physical      boolean default true,     -- "Does this involve a physical
                                                      -- product that has to be
                                                      -- delivered or picked up?"

    -- willingness to travel, asked per model -- but only for the
    -- side its own gate leaves open.
    will_deliver_outside_area   boolean default false,  -- goods move.
                                                        -- Irrelevant, never asked,
                                                        -- when output_is_physical
                                                        -- is false.
    will_relocate_for_work      boolean default false,  -- the person moves.
                                                        -- Deliberately a plain boolean:
                                                        -- the real decision is made when
                                                        -- they see the actual city and
                                                        -- offer, not declared in advance.
                                                        -- Irrelevant, never asked,
                                                        -- when is_remote_capable is true.
    will_partner_outside_district boolean default false,  -- irrelevant, never asked,
                                                           -- when is_remote_capable is true

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

    embedding               vector(768),  -- computed from product_or_service_en
                                          -- (+ skills_en, for an employment listing)
                                          -- -- never from the _original text

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
-- 6. LOGISTICS ROUTES
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
-- 7. LISTING PARTICIPANTS
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
-- 8. VENTURE LINEAGE
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
-- 9. MARKETPLACE MATCHES
-- Three models, one table.
--
-- No staff review gate: matches go to BOTH parties directly. They
-- weigh their options and choose, as in any real market. Either
-- side may dismiss, and a dismissed pair never resurfaces.
--
-- proximity_multiplier is always 1.00 when the relevant gate is
-- open on the listing that matters for this match_model --
-- is_remote_capable for an employment match (the person doesn't
-- need to relocate), output_is_physical = false for a supply_chain
-- match (nothing needs delivering). There is no cluster/district/
-- province to weight in that case, so it is excluded from the
-- distance calc entirely rather than forced through it.
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
    reason_ur               text,                 -- same reason, real Urdu -- added 5 Sep 2026,
                                                    -- direct request to show it alongside English
                                                    -- the same way product_or_service already does

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
-- 9b. MATCH MESSAGES -- added 5 Sep 2026, direct request: "there should
-- be a chat within the marketplace... as soon as you feel like you
-- already established something, then they can call." Before this,
-- nothing let two matched parties actually communicate through the
-- product at all -- no phone number was ever shown, and "the parties
-- connect themselves" (Marketplace_Spec.md section 7) had no mechanism
-- behind it. One thread per match, not a general inbox -- a
-- conversation only ever makes sense in the context of a specific
-- introduction. Phone numbers are NEVER stored here or added to this
-- table; see packages/marketplace/messaging.py's get_contact_info() for
-- where and how a phone number becomes visible (only once
-- marketplace_matches.status = 'connected', an existing status this
-- table doesn't touch or duplicate).
-- ============================================================

create table match_messages (
    id                      uuid primary key default gen_random_uuid(),
    match_id                uuid not null references marketplace_matches(id) on delete cascade,
    sender_beneficiary_id   uuid not null references beneficiary_profiles(id),
    body                    text not null,
    sent_at                 timestamptz default now()
);

create index on match_messages (match_id, sent_at);


-- ============================================================
-- 10. NOTIFICATIONS
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
-- 11. DONATIONS
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
-- 12. GRADUATION EVENTS
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
-- 13. LISTING PHOTOS -- added 5 Sep 2026, direct request: "I should be
-- able to click on my listing, browse, enter pictures if I want to
-- create a proper portfolio." Files live in Supabase Storage (the
-- "listing-photos" bucket, public-read, 5MB/file, jpeg/png/webp only --
-- created via the Storage REST API, not the dashboard); this table only
-- ever stores the resulting path/URL, never the image bytes themselves
-- -- keeping binary data out of Postgres, same reasoning as embeddings
-- staying a fixed-size vector rather than raw text blobs.
-- ============================================================

create table listing_photos (
    id                      uuid primary key default gen_random_uuid(),
    listing_id              uuid not null references store_listings(id) on delete cascade,
    storage_path            text not null,   -- path within the bucket, e.g. "<listing_id>/<uuid>.jpg"
    url                     text not null,   -- full public URL, computed once at upload time
    uploaded_at             timestamptz default now()
);

create index on listing_photos (listing_id);


-- ============================================================
-- REFERENCE QUERIES
-- ============================================================

-- A. SUPPLY-CHAIN MATCHING for a producer needing inputs.
--    Filters run alongside the ranking, so only genuinely
--    reachable candidates are ever scored. The relevant gate here
--    is output_is_physical, not is_remote_capable -- a supplier can
--    manage their business remotely and their goods still need
--    transport, so what actually excuses the distance check is
--    "nothing physical changes hands" (a digital product), not
--    "the supplier isn't physically present."
--
-- select l.id, l.business_name, l.product_or_service_original,
--        1 - (l.embedding <=> :query_vec) as similarity
-- from store_listings l
-- where l.active = true
--   and l.availability in ('seeking', 'open_to_offers')
--   and l.role = 'supplier'
--   and l.open_request_count < l.max_open_requests
--   and l.id <> :own_listing_id
--   and (l.output_is_physical = false
--        or l.cluster_id = :my_cluster
--        or l.will_deliver_outside_area = true)
-- order by l.embedding <=> :query_vec
-- limit 10;


-- B. EMPLOYMENT MATCHING -- a business needs a skill.
--    Distant candidates appear only if willing to relocate, unless
--    the work itself is remote-capable, in which case distance
--    never enters the decision at all.
--
-- select l.id, l.skills_original, l.district, l.city
-- from store_listings l
-- where l.active = true
--   and l.seeking_work = true
--   and l.availability = 'seeking'
--   and (l.is_remote_capable = true
--        or l.cluster_id = :my_cluster
--        or l.will_relocate_for_work = true)
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


-- G. SIGNUP ELIGIBILITY -- run when a phone number requests an
--    OTP, before the code is sent. This is the ACTUAL gate --
--    the marketplace_invitations token (section 4) is a
--    convenience layered on top, never a substitute for this
--    check. Three distinct outcomes, worded differently to the
--    beneficiary:
--
-- select bp.id as beneficiary_id, ml.trade_category_id, ml.status
-- from beneficiary_profiles bp
-- join microfinance_loans ml on ml.beneficiary_id = bp.id
-- where bp.phone = :entered_phone
--   and ml.status in ('approved', 'disbursed')
-- order by ml.created_at desc
-- limit 1;
--
-- No row at all                    -> phone not on file, reject
--                                      before OTP is sent.
-- Row, trade_category_id is null   -> OTP sent, account created,
--                                      but the listing-creation
--                                      flow is never offered
--                                      (covers the Liberation Loan
--                                      and any other non-business
--                                      purpose).
-- Row, trade_category_id is set    -> OTP sent, full access.
--
-- A loan with status 'defaulted' or 'rejected' does not satisfy
-- the where clause, so it behaves like "no row at all" for this
-- check -- no longer eligible, or never was. 'approved' (loan
-- decided, not yet disbursed) DOES pass -- eligibility starts at
-- approval, not disbursement (see MICROFINANCE LOANS header,
-- section 3, for why).


-- I. INVITATION CONVERSION -- invited vs. actually signed up.
--    A real adoption metric, and free once marketplace_invitations
--    (section 4) exists -- worth showing alongside the impact
--    report (F).
--
-- select
--   count(*) as invitations_sent,
--   count(*) filter (where signed_up_at is not null) as signed_up,
--   round(
--     100.0 * count(*) filter (where signed_up_at is not null)
--       / nullif(count(*), 0), 1
--   ) as conversion_pct
-- from marketplace_invitations
-- where sent_at is not null;


-- J. DEFAULT SWEEP -- deactivate an EXISTING listing when a loan
--    defaults. Run whenever a microfinance_loans row is updated to
--    status = 'defaulted' (a trigger in production; called
--    explicitly by application code for the demo). The signup gate
--    (G) alone only stops FUTURE signups -- it does nothing about a
--    listing that's already live, so this closes that gap
--    explicitly rather than leaving it implicit.
--
-- update store_listings
-- set active = false
-- where primary_beneficiary_id = (
--   select beneficiary_id from microfinance_loans where id = :defaulted_loan_id
-- )
-- and active = true;
--
-- Simplification: only deactivates listings this beneficiary owns
-- solo (primary_beneficiary_id). A venture listing_participants
-- row for a defaulted co-owner is left active -- deliberately out
-- of scope for the hackathon, flag if this needs handling for real.
-- H. SEARCH is not the same query as matching. A beneficiary
--    searching for something they need runs with NO proximity
--    filter and NO willingness check at all -- they already know
--    what they want and will judge distance themselves. The
--    willingness/remote flags apply only to what gets PUSHED to
--    someone automatically (queries A/B), never to what they can
--    find by searching.
--
-- select l.id, l.business_name, l.product_or_service_original, l.district,
--        l.city, l.is_remote_capable, l.output_is_physical
-- from store_listings l
-- where l.active = true
--   and l.availability in ('seeking', 'open_to_offers')
--   and (l.embedding <=> :query_vec) < 1.0   -- no cluster/district condition
-- order by l.embedding <=> :query_vec
-- limit 20;
