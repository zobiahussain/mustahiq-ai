-- Keep historical candidate scores even after applications enter a later cycle.
-- The core schema stores only the application's latest ranking.
create table if not exists ranking_cycle_candidates (
    id uuid primary key default gen_random_uuid(),
    cycle_id uuid not null references ranking_cycles(id),
    application_id uuid not null references applications(id),
    rank integer not null,
    need_score numeric not null,
    score_breakdown jsonb not null,
    status text not null default 'ranked' check (status in ('ranked', 'approved', 'disbursed', 'rolled_over')),
    amount numeric,
    created_at timestamptz not null default now(),
    unique (cycle_id, application_id)
);
create index if not exists ranking_cycle_candidates_cycle on ranking_cycle_candidates(cycle_id, rank);
