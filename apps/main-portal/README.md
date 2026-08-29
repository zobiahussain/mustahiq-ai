# apps/main-portal — Main Platform Portal

**Owner:** NLP, Conversational Assistant & Main Platform Portal role.

React + Vite, **staff-facing only** — beneficiaries never log in; a field officer or
department admin operates this on a beneficiary's behalf, in conversation. Scope grew
substantially from "profile entry + recommendations view": now covers profile entry, the
**match review worklist** (approve/dismiss AI-suggested matches), the **outreach list**
(people pooled, waiting for verification), **verification** (recording outcomes: verified
/ no_actual_need / assisted_elsewhere / not_eligible / unreachable / declined), the
**ranked candidate pool** (bi-weekly prioritization results, with allocation), and the
department view. See [docs/End_to_End_Flows.md](../../docs/End_to_End_Flows.md) for the
full staff workflow this portal needs to support.

**Depends on:** `services/api`.

Shares palette, logo, and typography with `apps/marketplace-portal` despite being a
separate codebase.
