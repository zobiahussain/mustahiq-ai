"""Trigger layer — the 7 event triggers + 2 scheduled jobs.

The event triggers (1–7) fire inline, inside the API request that causes them
(profile saved → discovery; listing saved → matching; etc.). :mod:`triggers`
is the single place that documents each one and points at where its logic
actually lives.

The two scheduled jobs (8, the bi-weekly per-programme ranking cycle; 9, the
daily marketplace expiry sweep) have no event to hang off, so they run from
:mod:`scheduled` — invoked by ``python -m workflows.run`` on a Render cron
schedule (see ``render.yaml``).
"""
