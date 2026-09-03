-- ============================================================
-- Al-Khidmat Unified Beneficiary Matching & Allocation Platform
-- CORE SCHEMA  --  Supabase / Postgres
--
-- Run top to bottom in the Supabase SQL Editor.
-- Embedding dimension is 768. If the embedding provider changes,
-- this number must change everywhere it appears.
--
-- SCOPE: eligibility discovery, verification, and need-based
-- allocation. The marketplace module is deliberately NOT in this
-- file and will be specified separately.
--
-- 11 tables.
--
-- CORE PRINCIPLE ENCODED HERE:
--   AI discovers potential beneficiaries. It does not make them
--   applicants and it does not give them priority. Every candidate
--   -- however found -- passes through verification and is then
--   ranked in ONE pool using identical criteria.
--
--   The two paths converge at `applications`. Nothing downstream
--   can tell how a candidate got there except entry_path, which is
--   for audit ONLY and must never be a ranking input.
-- ============================================================

create extension if not exists vector;


-- ============================================================
-- 1. DEPARTMENTS
-- Al-Khidmat's programme-running teams. A department owns
-- programmes and its staff see the candidates matched to them.
-- ============================================================

create table departments (
    id                      uuid primary key default gen_random_uuid(),
    name                    text not null,
    domain                  text not null,        -- education | healthcare | financial |
                                                  -- vocational | community | microfinance | ...
    created_at              timestamptz default now()
);


-- ============================================================
-- 2. STAFF USERS
-- The only authenticated actor on the ELIGIBILITY side of the
-- platform -- no beneficiary accounts, passwords, or login flow
-- here. The marketplace module has its own, separate access
-- model (beneficiary_app_accounts + login_otps, phone + SMS
-- one-time code) -- see al_khidmat_marketplace_schema.sql.
-- ============================================================

create table staff_users (
    id                      uuid primary key default gen_random_uuid(),
    full_name               text not null,
    email                   text unique not null,
    department_id           uuid references departments(id),

    role                    text default 'area_manager'
                              check (role in ('area_manager', 'department_admin', 'super_admin')),
    -- area_manager     : registers beneficiaries, verifies, reviews matches
    -- department_admin : also defines programme criteria and rubric weights
    -- super_admin      : sees across departments

    active                  boolean default true,
    created_at              timestamptz default now()
);

create index on staff_users (department_id);


-- ============================================================
-- 3. BENEFICIARY PROFILES
-- One row per person, entered BY STAFF on their behalf.
--
-- PURELY STRUCTURED. Every column is a feature the rule check or
-- the XGBoost model reads directly. There is no embedding on this
-- table: eligibility is decided by structured data, never by
-- semantic similarity.
--
-- Everything except full_name and district is nullable on purpose.
-- Staff can skip what a person is uncomfortable answering and fill
-- it in later; a half-complete profile that still matches three
-- programmes beats a complete form nobody finished.
-- ============================================================

create table beneficiary_profiles (
    id                      uuid primary key default gen_random_uuid(),

    -- identity
    full_name               text not null,
    cnic                    text unique,          -- unique and exact: the primary duplicate check
    phone                   text,

    -- household
    household_size          int,
    dependents              int,
    school_age_children     int,
    marital_status          text,

    -- economic situation
    monthly_income          numeric,
    employment_status       text,                 -- unemployed | daily_wage | self_employed | salaried
    owns_home               boolean default false,

    -- location
    district                text not null,
    city                    text,
    -- Al-Khidmat's own 53 operational clusters -- a smaller, more
    -- specific unit than district, and NOT derivable from district name
    -- (a district can span multiple clusters). Added 4 Sep 2026 --
    -- previously had no source anywhere, which silently blocked the
    -- marketplace's proximity weighting. Same shape of gap
    -- trade_category_id was: a new field staff fill in, here at profile
    -- creation, since cluster membership is a general fact about the
    -- person, not something tied to a specific loan.
    cluster_id              text,

    -- education & health
    education_level         text,                 -- none | primary | matric | intermediate | graduate
    has_disability          boolean default false,
    chronic_illness_flag    boolean default false,

    -- assistance history
    prior_assistance_count  int default 0,

    -- escape hatch for genuinely programme-specific fields that
    -- would otherwise be null for most rows
    domain_attributes       jsonb default '{}'::jsonb,

    -- short caseworker note. Human context only.
    -- NOT embedded, NOT scored, NOT a matching input.
    staff_notes             text,

    completeness_score      numeric default 0,

    created_by_staff_id     uuid references staff_users(id),
    consent_given           boolean default false,
    created_at              timestamptz default now(),
    updated_at              timestamptz default now()
);

create index on beneficiary_profiles (district);
create index on beneficiary_profiles (cnic);
create index on beneficiary_profiles (phone);
create index on beneficiary_profiles (monthly_income);
create index on beneficiary_profiles (cluster_id);


-- ============================================================
-- 4. PROGRAMMES
-- Criteria AND prioritisation weights both live here as DATA, so a
-- department can change how its pool is ranked without any code
-- change. Adding a new programme is an INSERT -- never a code
-- change and never a new enum.
-- ============================================================

create table programs (
    id                      uuid primary key default gen_random_uuid(),
    department_id           uuid references departments(id),
    name                    text not null,
    domain                  text not null,
    description             text,

    -- hard rules the scoring engine checks directly, e.g.
    -- {"max_income": 30000, "min_dependents": 1, "districts": ["Lahore"]}
    criteria_structured     jsonb default '{}'::jsonb,
    has_document_criteria   boolean default false,

    -- PRIORITISATION RUBRIC -- transparent weights, not a learned
    -- model. Every weight is visible, defensible and tunable. e.g.
    -- {"income_inverse": 0.30, "dependents": 0.20,
    --  "disability": 0.15, "no_prior_assistance": 0.20,
    --  "school_age_children": 0.15}
    --
    -- entry_path is NOT a permitted key. Enforce at validation time.
    priority_weights        jsonb default '{}'::jsonb,

    -- Some programmes must NEVER be pushed to someone who did not
    -- ask. A loan creates a debt obligation, so a person cannot be
    -- surfaced as a microfinance candidate: they have to request it.
    -- When true, discovery still SCORES the person (so a department
    -- can see who would qualify) but SUPPRESSES the match instead
    -- of pooling it for outreach.
    requires_explicit_application  boolean default false,

    -- allocation capacity per cycle
    budget_per_cycle        numeric,
    capacity_per_cycle      int,
    cycle_frequency_days    int default 14,       -- bi-weekly default

    -- how long a verification stays fresh before re-contact
    verification_valid_days int default 90,

    active                  boolean default true,
    created_at              timestamptz default now(),
    updated_at              timestamptz default now()
);

create index on programs (domain);
create index on programs (active);
create index on programs (department_id);
create index on programs (requires_explicit_application);


-- ============================================================
-- 5. PROGRAMME CRITERIA CHUNKS
-- The retrieval side. A criteria document is chunked and embedded
-- so the ASSISTANT can cite it on demand.
--
-- NOTE: this is NOT used during eligibility scoring. Scoring reads
-- programs.criteria_structured, which is extracted from the same
-- document once at upload and confirmed by a department admin.
-- ============================================================

create table program_criteria (
    id                      uuid primary key default gen_random_uuid(),
    program_id              uuid not null references programs(id) on delete cascade,
    chunk_text              text not null,
    chunk_index             int,
    embedding               vector(768),
    created_at              timestamptz default now()
);

create index on program_criteria (program_id);
create index on program_criteria using hnsw (embedding vector_cosine_ops);


-- ============================================================
-- 6. MATCH RECORDS
-- What the AI FOUND. A row here is a suggestion and nothing more:
-- it confers no applicant status and no priority.
--
--   source = beneficiary_profiles, target = programs
--
-- The score is CONFIDENCE that someone may qualify. It is never a
-- need score and is never used in prioritisation.
-- ============================================================

create table match_records (
    id                      uuid primary key default gen_random_uuid(),

    beneficiary_id          uuid not null references beneficiary_profiles(id) on delete cascade,
    program_id              uuid not null references programs(id) on delete cascade,

    score                   numeric not null,
    reason                  text,                 -- plain-language, generated for readability
    source_chunk_id         uuid references program_criteria(id),

    status                  text default 'pending_review'
                              check (status in
                                ('pending_review',   -- awaiting staff judgement
                                 'pooled',           -- staff moved them to the eligible pool
                                 'dismissed',        -- staff judged it not sensible
                                 'suppressed')),     -- programme requires explicit application

    reviewed_by_staff_id    uuid references staff_users(id),
    reviewed_at             timestamptz,
    staff_notes             text,

    created_at              timestamptz default now(),
    unique (beneficiary_id, program_id)
);

create index on match_records (beneficiary_id);
create index on match_records (program_id, status);
create index on match_records (status, created_at);


-- ============================================================
-- 7. POTENTIALLY ELIGIBLE POOL
-- Between "the AI found them" and "they are a candidate".
-- These people have NOT been contacted and are NOT applicants.
-- They wait here until the programme's assessment cycle reaches
-- them -- outreach happens on the department's schedule, not the
-- algorithm's.
-- ============================================================

create table potentially_eligible_pool (
    id                      uuid primary key default gen_random_uuid(),
    beneficiary_id          uuid not null references beneficiary_profiles(id) on delete cascade,
    program_id              uuid not null references programs(id) on delete cascade,
    match_record_id         uuid references match_records(id),

    added_at                timestamptz default now(),
    added_by_staff_id       uuid references staff_users(id),

    outreach_status         text default 'awaiting_outreach'
                              check (outreach_status in
                                ('awaiting_outreach', 'in_verification',
                                 'verified', 'exited')),

    unique (beneficiary_id, program_id)
);

create index on potentially_eligible_pool (program_id, outreach_status);


-- ============================================================
-- 8. VERIFICATIONS
-- THE GATE. Outreach happens here: real need confirmed, assistance
-- received elsewhere checked, circumstances re-confirmed.
--
-- Verification CAN FAIL, and failure must land somewhere -- an
-- unreachable or already-assisted person leaves the pool rather
-- than sitting in it forever inflating every cycle's statistics.
--
-- Applies to BOTH entry paths. A direct applicant is verified on
-- the same form as an AI-identified one. This is the single gate
-- everyone passes through, not an extra hurdle for one group.
-- ============================================================

create table verifications (
    id                      uuid primary key default gen_random_uuid(),
    beneficiary_id          uuid not null references beneficiary_profiles(id) on delete cascade,
    program_id              uuid not null references programs(id) on delete cascade,

    conducted_by_staff_id   uuid references staff_users(id),
    conducted_at            timestamptz default now(),

    outcome                 text not null
                              check (outcome in
                                ('verified',              -- passes; joins the candidate pool
                                 'no_actual_need',        -- flagged but does not need it
                                 'assisted_elsewhere',    -- already received similar help
                                 'not_eligible',          -- fails programme-specific criteria
                                 'unreachable',           -- contact details stale
                                 'declined')),            -- does not wish to proceed

    -- what outreach actually established
    need_confirmed          boolean,
    urgency_level           text check (urgency_level in ('low', 'medium', 'high', 'critical')),
    assistance_elsewhere    boolean,
    assistance_details      text,
    verified_income         numeric,
    verified_household_size int,
    program_specific_data   jsonb default '{}'::jsonb,
    notes                   text,

    -- verification goes stale; set from programs.verification_valid_days
    valid_until             date,

    created_at              timestamptz default now()
);

create index on verifications (beneficiary_id, program_id);
create index on verifications (outcome);
create index on verifications (valid_until);


-- ============================================================
-- 9. APPLICATIONS  --  THE UNIFIED CANDIDATE POOL
-- Where the two paths converge. Direct applicants and verified
-- AI-identified candidates sit in ONE table, ranked by IDENTICAL
-- criteria.
--
-- entry_path exists so the organisation can audit how well
-- discovery is working. It must NEVER appear in
-- programs.priority_weights or in any ranking computation.
-- ============================================================

create table applications (
    id                      uuid primary key default gen_random_uuid(),
    beneficiary_id          uuid not null references beneficiary_profiles(id) on delete cascade,
    program_id              uuid not null references programs(id) on delete cascade,

    -- AUDIT ONLY. Never a ranking input.
    entry_path              text not null
                              check (entry_path in ('direct', 'ai_identified')),

    verification_id         uuid references verifications(id),

    status                  text default 'active'
                              check (status in
                                ('active',            -- in the pool, awaiting a cycle
                                 'ranked',            -- scored in the current cycle
                                 'approved',          -- staff approved for allocation
                                 'disbursed',         -- resources allocated
                                 'rolled_over',       -- not funded, carried to next cycle
                                 'expired',           -- verification went stale
                                 'withdrawn')),

    -- filled by the periodic prioritisation run
    need_score              numeric,
    score_breakdown         jsonb,                -- per-factor contribution, so any rank
                                                  -- can be explained to staff or a donor
    rank_in_cycle           int,
    cycles_waited           int default 0,

    -- what was actually given, once allocated
    amount_requested        numeric,
    amount_disbursed        numeric,
    disbursed_at            timestamptz,

    applied_at              timestamptz default now(),
    created_by_staff_id     uuid references staff_users(id),
    updated_at              timestamptz default now(),

    unique (beneficiary_id, program_id)
);

create index on applications (program_id, status);
create index on applications (need_score desc);
create index on applications (entry_path);        -- audit reporting only


-- ============================================================
-- 10. RANKING CYCLES
-- One row per prioritisation run per programme. The audit trail:
-- "on 15 Jan, 85 candidates in pool, 20 funded, budget X".
-- ============================================================

create table ranking_cycles (
    id                      uuid primary key default gen_random_uuid(),
    program_id              uuid not null references programs(id) on delete cascade,

    run_at                  timestamptz default now(),
    pool_size               int,
    budget_available        numeric,
    capacity_available      int,

    -- snapshot of the weights used, so a past decision stays
    -- explainable even after a department changes its rubric
    weights_snapshot        jsonb,

    approved_count          int default 0,
    disbursed_count         int default 0,

    reviewed_by_staff_id    uuid references staff_users(id),
    status                  text default 'ranked'
                              check (status in ('ranked', 'under_review', 'finalised')),

    created_at              timestamptz default now()
);

create index on ranking_cycles (program_id, run_at desc);


-- ============================================================
-- 11. DUPLICATE FLAGS
-- Output of duplicate detection: exact CNIC match first, then
-- fuzzy name + phone via RapidFuzz. No vector similarity --
-- profiles carry no embedding, and CNIC is unique and exact, which
-- catches nearly every real duplicate.
--
-- Separate from match_records because a duplicate is a
-- data-quality task for staff, not a recommendation.
-- ============================================================

create table duplicate_flags (
    id                      uuid primary key default gen_random_uuid(),
    profile_a_id            uuid not null references beneficiary_profiles(id) on delete cascade,
    profile_b_id            uuid not null references beneficiary_profiles(id) on delete cascade,
    similarity_score        numeric,
    matched_on              text,                 -- 'cnic_exact' | 'name_phone_fuzzy'
    status                  text default 'pending'
                              check (status in ('pending', 'confirmed', 'dismissed')),
    reviewed_by_staff_id    uuid references staff_users(id),
    reviewed_at             timestamptz,
    created_at              timestamptz default now(),
    check (profile_a_id <> profile_b_id)
);

create index on duplicate_flags (status);


-- ============================================================
-- REFERENCE QUERIES
-- ============================================================

-- A. PROGRAMMES ELIGIBLE FOR PROACTIVE OUTREACH.
--    Discovery pools matches for these. Programmes requiring an
--    explicit application (microfinance) are excluded: a person
--    must ask for those.
--
-- select id, name, criteria_structured
-- from programs
-- where active = true
--   and requires_explicit_application = false;


-- B. OUTREACH LIST -- who to contact this assessment cycle.
--    These are NOT applicants yet.
--
-- select p.full_name, p.phone, p.district, pe.added_at
-- from potentially_eligible_pool pe
-- join beneficiary_profiles p on p.id = pe.beneficiary_id
-- where pe.program_id = :program_id
--   and pe.outreach_status = 'awaiting_outreach'
-- order by pe.added_at;


-- C. THE UNIFIED CANDIDATE POOL -- what gets ranked.
--    Note: no entry_path filter and no entry_path ordering. Both
--    paths are treated identically from here on.
--
-- select a.id, a.beneficiary_id, a.cycles_waited,
--        v.urgency_level, v.verified_income
-- from applications a
-- join verifications v on v.id = a.verification_id
-- where a.program_id = :program_id
--   and a.status in ('active', 'rolled_over')
--   and v.valid_until >= current_date;


-- D. EXPIRE STALE VERIFICATIONS -- run at the start of each cycle,
--    before scoring. Circumstances change; stale data is not ranked.
--
-- update applications a
-- set status = 'expired'
-- from verifications v
-- where v.id = a.verification_id
--   and a.status in ('active', 'rolled_over')
--   and v.valid_until < current_date;


-- E. ASSISTANT RETRIEVAL -- passages relevant to a STAFF QUESTION.
--    The assistant only. Eligibility scoring never runs retrieval.
--
-- select pc.id, pc.chunk_text, p.name,
--        1 - (pc.embedding <=> :question_vec) as score
-- from program_criteria pc
-- join programs p on p.id = pc.program_id
-- where p.active = true
-- order by pc.embedding <=> :question_vec
-- limit 3;


-- F. AUDIT -- is discovery actually finding people who go on to
--    qualify? Reporting only; never feeds ranking.
--
-- select entry_path,
--        count(*) as candidates,
--        count(*) filter (where status = 'disbursed') as funded
-- from applications
-- where program_id = :program_id
-- group by entry_path;
