# apps/marketplace-portal — Marketplace App

**Owner:** Marketplace, Business Matching & Shared RAG Layer role.

> **Naming note:** this folder is still called "portal" from an earlier revision, but per
> [docs/Marketplace_Spec.md](../../docs/Marketplace_Spec.md) — now confirmed consistent
> across every doc — this is **not a staff portal**. It's the beneficiary-facing app.
> Worth renaming the folder at some point; not urgent.

React + Vite, separate codebase from `apps/main-portal`, with its own access model: a
beneficiary logs in themselves with **phone number + SMS one-time code** (no password —
see [docs/Architecture.md §4.2.1](../../docs/Architecture.md)), then talks to a
conversational assistant (voice or text) that turns "what they do" into a structured
listing — there is no form. Also covers match results (with proximity labelled) and
dismiss/respond actions on a match. No staff screens: staff run microfinance and read
reports elsewhere, not here.

The login number is the same one already captured on their loan application, so it links
straight to their existing profile via `beneficiary_app_accounts`; a number change is
staff-assisted at a facilitation centre, not self-service.

**Depends on:** `services/api` (OTP send/verify + profile lookup).

Shares palette, logo, and typography with `apps/main-portal` despite being a separate
codebase.
