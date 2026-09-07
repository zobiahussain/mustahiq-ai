# Mustahiq AI — hackathon submission

The first Alibaba Cloud AI Hackathon in Pakistan · hosted by Al-Khidmat Foundation

---

## 1. Public repository URL

```
https://github.com/zobiahussain/mustahiq-ai
```

**Before submitting, make the repo public and confirm it opens in an incognito window.**
Work currently sits on the `merge-leftovers` branch — merge it to `main` (or point the
submission at the branch) so the judges see the complete project.

### Secrets check — done

- `.env`, `_env` and any key/password/PEM file: **never committed** — verified across the
  full git history (`git log --diff-filter=A`, `git rev-list --all --objects`) and against
  live-secret patterns (`gsk_…`, `sk-…`, JWTs, `postgres://…:pass@…`). Nothing found.
- `.gitignore` covers `.env`, `.env.*` (keeps `.env.example`), `.local/`, `.venv/`.
- The tracked `*.env.example` files contain only placeholders (`<password>`, `<groq-api-key>`).
- Test data is synthetic (`+92300555…` template rows).
- Only cosmetic exposure: a Tailscale CGNAT IP (`100.72.1.8`) as a default Ollama URL —
  not reachable outside the team's tailnet, not a secret. Optional to scrub.

---

## 2. Project summary  (paste into the form — 1,490 characters, fits the 1,500 limit)

> **Mustahiq AI** is a decision-support layer for Al-Khidmat Foundation's beneficiary aid.
> It helps staff find, verify and fairly allocate aid — and connects micro-entrepreneurs
> to each other.
>
> **Who it's for:** Al-Khidmat field officers and managers (the eligibility side), and
> loan-financed beneficiaries running small businesses (the marketplace).
>
> **Eligibility.** A field officer enters a household's situation in conversation. The
> system checks it against every active programme across Al-Khidmat's seven areas of work
> — health, education, disaster relief, clean water, orphan care, BanoQabil, community
> services — using plain hard rules plus an XGBoost confidence score trained on 15,000
> synthetic profiles. Suggestions go to a staff worklist, never an automatic enrolment.
> Staff pool a case, verify real need on a home visit, and a bi-weekly cycle ranks
> everyone waiting on one transparent, factor-by-factor rubric so budgets reach the most
> in need. Fairness is structural: how someone was found can never affect their rank.
>
> **Marketplace.** Once a beneficiary has a business loan, they open a phone app, describe
> their business by voice in any language, and are matched to nearby suppliers, customers,
> workers or business partners. No fees, ever — Al-Khidmat only introduces.
>
> **What we built:** two web apps, a FastAPI backend, the rules-plus-ML eligibility
> engine, a retrieval layer that cites real policy text, and the full
> verify → rank → allocate workflow — all on free infrastructure, tested end to end.

---

## 3. Presentation

- `Mustahiq_AI_Presentation.pptx` — 11 slides, 16:9, editable.
- `Mustahiq_AI_Presentation.pdf` — same deck, ready to upload if PPTX conversion misbehaves.

Slide 8 carries **real screenshots** of both apps running on the synthetic demo data (staff
dashboard + the marketplace home). Swap in fresher ones any time — they're just pictures on
the slide.

### Per-slide talking points (mixed panel — keep it plain)

1. **Title** — "Al-Khidmat helps millions. The hard part isn't wanting to help — it's
   deciding who gets limited help, and being able to explain why."
2. **Problem** — one household can qualify for several programmes but only one gets
   checked; "why them?" has no written answer; a beneficiary who starts a business is left
   alone when the loan ends.
3. **What we built** — two front doors (staff / beneficiary), one engine underneath.
4. **Eligibility pipeline** — five stages, and a human decides at every gate. Rules
   *eliminate*; the model only *ranks confidence*. Nobody is auto-enrolled.
5. **Fairness** — the rubric is shown to staff, weight by weight; entry path is recorded
   but can never enter the maths; every decision has a plain-language reason.
6. **The confidence model** — XGBoost on 15,000 synthetic profiles, held-out ROC-AUC ≈ 0.76.
   No LLM in scoring, no training on real people, never decides funding. Deliberately
   narrow — that's the point.
7. **Marketplace** — loan → describe your business by voice → matched across three models
   (supply chain / employment / joint venture) → both sides notified → they deal directly.
   No fees, no commission.
8. **The product** — both screens on this slide are the real apps on synthetic demo data.
   41 + 33 automated tests, plus marketplace smoke tests.
9. **Constraints** — free tier only, every answer cited, any language in, staff-operated.
10. **Impact** — before/after: one programme → all of them in milliseconds; memory →
    a snapshotted rubric; no record → a reason for every decision.
11. **Close** — "From aid, to auditable aid, to self-reliance."

---

## What's a prototype vs. production

Honest framing for questions:

- **Real and running:** both portals, the API, the rules + XGBoost engine, the RAG /
  citation layer, discovery, verification, the ranking cycle, allocation, the marketplace
  matching pipeline, dedup, auth on both sides.
- **Wired for deploy, not yet scheduled in the cloud:** the two cron jobs (bi-weekly
  ranking, daily marketplace sweep) run from `python -m workflows.run` and are defined in
  `render.yaml`; in the demo they're triggered on demand.
- **Out of scope (whiteboarded):** production auth hardening, row-level security, real SMS
  provider, real payment rails. Synthetic data only — no model trains on real
  beneficiaries (in production, verification outcomes become the labels).
