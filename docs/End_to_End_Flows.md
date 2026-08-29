# End-to-End Flows

**AI-Powered Unified Beneficiary Matching & Allocation Platform — Al-Khidmat**

## The Core Principle

AI discovers potential beneficiaries. It does not make them applicants, and it does not
give them priority.

Every candidate — whether they walked in and applied directly, or were surfaced by
cross-program matching — passes through the same verification step and then enters the
same candidate pool, where they are ranked by identical criteria. How someone was found is
recorded for audit, but never influences their position.

This is what keeps the platform fair. If AI-identified candidates went straight into the
ranked pool, the system would quietly create two classes of applicant. The verification
gate is what prevents that.

## The Five Stages

| Stage | What happens | Who decides | Writes to |
|---|---|---|---|
| 1. Discovery | Profile scored against all active programs | The system | match_records |
| 2. Potential pool | Flagged people wait for the assessment cycle | Area manager | potentially_eligible_pool |
| 3. Verification | Outreach confirms real need and circumstances | Staff, with the beneficiary | verifications |
| 4. Prioritization | Whole unified pool ranked by need | A transparent rubric | applications, ranking_cycles |
| 5. Allocation | Top-ranked funded within budget | Department staff | applications |

Stages 1 and 4 are automated. Stages 2, 3, and 5 are human decisions. Nothing moves from
one stage to the next without a person, except the scoring itself.

## Use Case 1 — Beneficiary Applies for a Program

**Starts when:** a person comes to Al-Khidmat to apply for a specific program — say a
health loan.

**Flow**

1. The area manager opens the portal and enters or updates the person's unified profile,
   in conversation. Only name and district are required; anything the person is
   uncomfortable answering is skipped and can be filled in later.
2. Free-text notes about their situation are parsed into structured fields by a Groq
   JSON-mode call; the manager confirms or corrects the extraction.
3. The profile is saved with `created_by_staff_id` and a `completeness_score`. The
   profile is purely structured — nothing on it is embedded.
4. A direct application is created for the program they actually came for, with
   `entry_path = 'direct'`.
5. Saving the profile also fires cross-program matching — Use Case 2.

**Tables touched:** `beneficiary_profiles` (insert/update), `applications` (insert,
entry_path = direct), `duplicate_flags` (insert if flagged)

## Use Case 2 — AI Cross-Program Matching

**Starts when:** a profile is created or updated, or a program is added or its criteria
change.

**Flow**

1. The system loads every active row from `programs` and scores the profile against each
   one — structured rules where they exist, retrieved criteria passages via RAG where
   they only exist as prose.
2. Each program the person may qualify for produces a `match_records` row with a
   confidence score and a plain-language reason, at `status = pending_review`.
3. Programs flagged as requiring an explicit application are evaluated but SUPPRESSED —
   the match is not pooled and the person is not approached. Microfinance carries this
   flag: a loan is a debt, and nobody should be offered one they did not ask for.
4. The area manager sees immediately that the health-loan applicant may also qualify for,
   say, an education program.
5. The manager reviews and either dismisses the suggestion or pools it.

A match is a suggestion. It does not make the person an applicant for that program and
confers no priority whatsoever. The match score measures confidence that someone may
qualify — it is never used in need-based ranking.

**Tables touched:** `programs` (read), `program_criteria` (read), `match_records`
(insert, update)

## Use Case 3 — The Potentially Eligible Pool

**Starts when:** an area manager pools a match rather than dismissing it.

**Flow**

1. A `potentially_eligible_pool` row is created linking the beneficiary, the program, and
   the originating match record, at `outreach_status = 'awaiting_outreach'`.
2. The person is NOT contacted at this point and is NOT an applicant. They wait here
   until that program's periodic assessment cycle reaches them.
3. The department sees them on an outreach list, ordered by how long they have been
   waiting.

This waiting room exists because contacting someone the moment an algorithm flags them
would raise expectations the organisation may not be able to meet. Outreach happens on the
department's schedule, not the algorithm's.

**Tables touched:** `potentially_eligible_pool` (insert), `match_records` (update to
status = pooled)

## Use Case 4 — Verification & Outreach

**Starts when:** the program's periodic assessment cycle begins and staff works through
the outreach list. Direct applicants are verified on this same form.

**Flow**

1. Staff contacts the person and works through the verification: is there an actual,
   current need for this program?
2. Have they already applied for or received similar assistance — from another
   Al-Khidmat department, or from another organisation? Because the profile is unified,
   staff can see the person's history across every Al-Khidmat program in one place, which
   no single department could previously do.
3. Current financial and household circumstances are re-confirmed rather than assumed
   from the original profile.
4. Any program-specific eligibility information is collected into `program_specific_data`.
5. An urgency level is recorded: low, medium, high, or critical.
6. A `verifications` row is written with the outcome, and `valid_until` is set from the
   program's `verification_valid_days`.

Verification can fail — and failure exits the pool:

| Outcome | Meaning | What happens |
|---|---|---|
| verified | Real, current need confirmed | Enters the unified candidate pool |
| no_actual_need | Flagged, but does not actually need this | Exits the pool |
| assisted_elsewhere | Already received similar assistance | Exits the pool; recorded for future reference |
| not_eligible | Fails program-specific criteria discovered at outreach | Exits the pool |
| unreachable | Contact details stale or no response | Exits the pool; can be re-pooled if contact is updated |
| declined | Does not wish to proceed | Exits the pool |

`'unreachable'` matters more than it looks. Rural contact details go stale, and without
this outcome those people would sit in the pool indefinitely, inflating pool size and
distorting every cycle's statistics.

**Tables touched:** `verifications` (insert), `potentially_eligible_pool` (update
outreach_status), `beneficiary_profiles` (update with verified figures)

## Use Case 5 — The Unified Candidate Pool

**Starts when:** a verification returns `'verified'`.

**Flow**

1. An `applications` row is created — or, for a direct applicant, the existing row is
   linked to the verification.
2. `entry_path` records how the person arrived: `'direct'` or `'ai_identified'`.
3. Status is set to `'active'`. They are now a candidate, indistinguishable from anyone
   else in the pool.

Both paths converge here:

```
Direct applicants        ----+
                             |--> verification --> UNIFIED POOL
AI-identified candidates ----+
```

`entry_path` exists solely so the organisation can audit whether cross-program matching is
genuinely finding people who turn out to qualify. It must never appear in a program's
`priority_weights` or in any ranking computation. If it did, the fairness this whole
design protects would be undone at the last step.

**Tables touched:** `applications` (insert or update), `verifications` (read)

## Use Case 6 — Periodic Need-Based Prioritization

**Starts when:** the program's ranking cycle runs — bi-weekly by default, set per program
by `cycle_frequency_days`. Not daily, and not on every registration.

**Flow**

1. Applications whose verification has expired are moved to `status = 'expired'` and
   returned to outreach for re-contact, since circumstances change and stale
   verification cannot be ranked.
2. The remaining pool is loaded: everyone with status `'active'` or `'rolled_over'` and a
   still-valid verification. No filter or ordering by `entry_path` is applied anywhere in
   this query.
3. Each candidate is scored using that program's `priority_weights` — a transparent
   weighted rubric over verified need, urgency, vulnerability, household circumstances,
   and prior assistance.
4. The per-factor contribution of every candidate's score is stored in
   `score_breakdown`, so any ranking can be explained to staff, to the beneficiary, or to
   a donor.
5. Candidates are ranked and `rank_in_cycle` is written.
6. A `ranking_cycles` row records the run: pool size, budget available, and a snapshot of
   the weights used — so a past decision remains explainable even after a department
   later changes its rubric.

**Why a rubric and not a machine-learning model**

- There are no training labels. Machine learning needs examples of correct past
  decisions, and no dataset exists of who most deserved assistance.
- The decision must be defensible. "The model decided" is not an answer a charity can
  give a department head, a donor, or a rejected applicant.
- A rubric is tunable without retraining. If a department decides dependents should
  outweigh income, they change a weight.
- Machine learning stays where it belongs — estimating eligibility probability at the
  discovery stage, where fuzzy matching is genuinely the task. Allocation is explainable
  arithmetic.

**Weights are per-program.** A health program may weight medical urgency and chronic
illness heavily; an education program may weight school-age children and dependents. Same
engine, different weights, owned by the department and stored as data on the program row —
no code change to adjust them.

**Tables touched:** `applications` (read, update), `verifications` (read), `programs`
(read), `ranking_cycles` (insert)

## Use Case 7 — Human Review

**Starts when:** a ranking cycle completes and staff opens the ranked list.

**Flow**

1. Staff sees candidates in priority order, each with their need score and the
   factor-by-factor breakdown behind it.
2. Staff can see how long each candidate has waited (`cycles_waited`), which surfaces
   anyone repeatedly just below the funding line.
3. Staff reviews and approves — the ranking is a recommendation, not a decision. Local
   knowledge the rubric cannot capture belongs here.
4. Approved candidates move to `status = 'approved'`; the cycle moves to `'under_review'`
   then `'finalised'`.

**Tables touched:** `applications` (read, update), `ranking_cycles` (update)

## Use Case 8 — Allocation & Disbursement

**Starts when:** staff finalises an approved priority order.

**Flow**

1. Resources are allocated down the approved order until `budget_per_cycle` or
   `capacity_per_cycle` is exhausted.
2. Funded candidates move to `status = 'disbursed'`.
3. Everyone not funded moves to `'rolled_over'`, and `cycles_waited` increments — they are
   automatically in the next cycle without reapplying.
4. The cycle's `approved_count` and `disbursed_count` are recorded.

Rolling over rather than rejecting is deliberate: someone narrowly missing out three
cycles running is visible in the data, and a department can choose to weight waiting time
in its rubric.

**Tables touched:** `applications` (update), `ranking_cycles` (update)

## Use Case 9 — Duplicate Detection

**Flow**

1. On every new profile, the system compares against existing records: exact CNIC match,
   then fuzzy name and phone comparison via RapidFuzz.
2. Suspected pairs are written to `duplicate_flags` at `status = 'pending'`.
3. The flag goes to a staff queue, not to the beneficiary. A duplicate is a data-quality
   problem for Al-Khidmat, not something to raise with the person in front of you.
4. Staff confirms or dismisses; merging is a manual decision and never automatic.

**Tables touched:** `beneficiary_profiles` (read), `duplicate_flags` (insert, update)

## Use Case 10 — Marketplace (Separate Module)

A beneficiary who has applied for and received microfinance support may join the
marketplace on the app. Three models operate: supply chain, employment, and joint
venture, with rickshaw operators participating as logistics.

The marketplace runs WITHOUT staff involvement — listings are created by a conversational
assistant on the app, matching is automatic, and both parties are notified directly by
SMS and email. Nothing is charged at any point.

Specified in full in [Marketplace_Spec.md](Marketplace_Spec.md), with its own schema
file.

## Use Case 11 — Conversational Assistant

**Flow**

1. A staff member asks a question while working with a beneficiary.
2. The question is embedded and relevant passages retrieved from `program_criteria` via
   the shared RAG layer.
3. Groq generates an answer only from what was retrieved, citing the passage it came from
   so staff can verify it against the actual program document.

Its primary user is staff — answering questions such as whether this person qualifies for
anything else, or what documents a program requires. On-demand only; never part of an
automatic workflow.

## Trigger Summary

| # | Fires when | Type | What runs | Use case |
|---|---|---|---|---|
| 1 | Profile created or updated | Event | Cross-program eligibility matching | 2 |
| 2 | Profile created | Event | Duplicate detection | 9 |
| 3 | Match pooled by staff | Event | Add to potentially eligible pool | 3 |
| 4 | Verification recorded | Event | Create or link the application | 5 |
| 5 | New program added | Event | Re-scan all existing beneficiaries | 2 |
| 6 | Criteria edited | Event | Re-scan all existing beneficiaries | 2 |
| 7 | Listing created or edited | Event | Marketplace matching, notify both parties directly | 10 |
| 8 | Ranking cycle due | Scheduled (bi-weekly) | Expire stale verifications, then score and rank the pool | 6 |
| 9 | Daily | Scheduled | Expire stale marketplace matches and listings | 10 |

Triggers 8 and 9 are both scheduled but run on different clocks: ranking is per-programme
and bi-weekly; the marketplace expiry sweep is daily and platform-wide.

## What a Beneficiary Actually Experiences

- They talk to a person, not a screen. An area manager enters their details in
  conversation.
- They are told they may qualify for other programs, with the caveat that it still needs
  verification.
- They are contacted during that program's assessment cycle, not the moment an algorithm
  flags them.
- They are asked to confirm their situation, including whether they have received help
  elsewhere.
- If verified, they compete for resources on exactly the same terms as anyone who applied
  directly.
- If not funded this cycle, they carry over without reapplying.
- On this, the eligibility side, they never log in — Al-Khidmat staff are the only
  authenticated users. If they later join the marketplace (a separate module, Use Case
  10), that's the deliberate exception: they authenticate themselves there by phone + SMS
  one-time code, since they own their own listing and matches. See
  [Marketplace_Spec.md](Marketplace_Spec.md) and Architecture.md §4.2.1.
