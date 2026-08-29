# workflows — Trigger Layer

LlamaIndex Workflow definitions for the 7 event triggers + 2 scheduled jobs (the bi-weekly
per-program ranking cycle, and the daily platform-wide marketplace expiry sweep — new
since the previous revision, replacing the single grace-period sweep). Cross-cutting — see
[docs/Team_Work_Division.md §3](../docs/Team_Work_Division.md#3-trigger-ownership) for
per-trigger ownership, and
[docs/End_to_End_Flows.md](../docs/End_to_End_Flows.md) for what each one actually does
step by step. Wired together last, once the functions each trigger calls are stable (see
build order).
