# apps/marketplace-portal — Marketplace App

**Owner:** Marketplace, Business Matching & Shared RAG Layer role.

> **Naming note:** this folder is still called "portal" from the earlier revision, but per
> [docs/Marketplace_Spec.md](../../docs/Marketplace_Spec.md) this is **not a staff
> portal** — it's the beneficiary-facing app. Architecture.md and Team_Work_Division.md
> both still describe a "Marketplace Portal (staff + listing views)," which directly
> contradicts the spec. Treat the spec as correct; see the reconciliation note in root
> `CLAUDE.md` before assuming which one governs the actual build. Worth deciding whether
> to rename this folder once that's settled.

React + Vite, separate codebase from `apps/main-portal`. A beneficiary opens it
themselves and talks to a conversational assistant (voice or text) that turns "what they
do" into a structured listing — there is no form. Also covers match results (with
proximity labelled), and dismiss/respond actions on a match. No staff screens: staff run
microfinance and read reports elsewhere, not here.

**Open question:** the platform's other side is explicit that "beneficiaries never log in"
(SRS §4, §7.5 — staff are the only authenticated actor). This app assumes a beneficiary
can open it and act on *only their own* listing without a staff intermediary, which needs
some identifying mechanism (a phone number, most likely) that isn't a traditional login.
Not specified anywhere yet — needs an explicit answer before auth/access on this app can
be built.

**Depends on:** `services/api`.

Shares palette, logo, and typography with `apps/main-portal` despite being a separate
codebase.
