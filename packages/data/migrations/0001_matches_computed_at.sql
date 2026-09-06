-- Backs the async match_and_notify() change (6 Sep 2026): POST /listing now
-- returns as soon as the listing itself is saved, and match_and_notify()
-- (which finds candidates, writes an LLM reason for EACH one, and sends
-- notifications) runs afterwards, in the background -- see main.py's
-- listing_save() docstring for why.
--
-- The frontend needs a way to tell "matching hasn't run yet" apart from
-- "matching ran and genuinely found nothing" -- both look like an empty
-- list otherwise. This column is that signal: null means still pending
-- (or never triggered), a real timestamp means match_and_notify() finished
-- for this listing as of that moment.
alter table store_listings
    add column if not exists matches_computed_at timestamptz;

comment on column store_listings.matches_computed_at is
    'Set by match_and_notify() once it finishes for this listing (background '
    'task, not part of the POST /listing request itself). NULL means '
    'matching is still running or was never triggered -- GET '
    '/listing/{id}/matches uses this to tell the frontend whether to keep '
    'polling or show the real (possibly empty) result.';
