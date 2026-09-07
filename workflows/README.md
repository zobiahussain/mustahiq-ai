# workflows — Trigger Layer

The 7 event triggers + 2 scheduled jobs (Team_Work_Division.md §3,
End_to_End_Flows.md).

**No workflow engine.** LlamaIndex Workflows was the original plan, but it
solves multi-step LLM-agent orchestration and none of these triggers are that
— every one is a single deterministic function call. So this folder is thin:

| Piece | What it is |
|---|---|
| [`triggers.py`](triggers.py) | The authoritative list of all 9 triggers — what each does, how it fires, and the exact module its logic lives in. `python -m workflows.triggers` prints it. |
| [`scheduled.py`](scheduled.py) | The two scheduled jobs as importable functions: `run_ranking_cycles()` (trigger 8) and `run_marketplace_sweep()` (trigger 9). |
| [`run.py`](run.py) | The CLI a Render cron invokes: `python -m workflows.run ranking-cycles` / `marketplace-sweep`. |

### Events (triggers 1–7)

Fire **inline**, inside the API request that causes them — see `triggers.py`
for where each lives. Registration-time discovery is milliseconds and
deterministic; even the re-scan triggers (5, 6) run inline because there is no
queue/worker infra on a single Render free-tier service. This is the working
answer to CLAUDE.md open question #3 for the hackathon.

### Scheduled (triggers 8, 9)

Have no event to hang off. `render.yaml` (repo root) defines them as Render
cron services:

* **8 — ranking cycle**, bi-weekly. For every active programme whose cycle is
  due (`cycle_frequency_days` since its last `run_at`, and no open cycle), it
  expires stale verifications and ranks the verified pool with the transparent
  rubric. It **stops at `status='ranked'`** — a human still reviews and
  allocates (SRS: never auto-enroll). Also exposed as
  `POST /portal/cycles/run-due` (super-admin) for the demo.
* **9 — marketplace sweep**, daily. Expires matches unanswered for 7 days and
  listings unconfirmed for 6 months
  (`packages/marketplace/lifecycle.py`).

Both jobs are idempotent and safe to re-run: they only act on rows that are
actually due/stale.
