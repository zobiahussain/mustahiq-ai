# Software Requirements Specification

**AI-Powered Unified Beneficiary Matching & Allocation Platform for Al-Khidmat**

## 1. Project Overview

Al-Khidmat runs programs across seven distinct domain areas, each addressing a different
kind of need — education, healthcare, financial support, vocational training, and others.
These programs are managed independently. A person who becomes a beneficiary under one
program has no simple way of finding out whether they also qualify for the others, and the
departments running those programs have no easy way of knowing that this person already
exists in their pool of potential candidates.

This project proposes an AI-powered Unified Beneficiary Matching & Allocation Platform
that builds a single profile for each beneficiary, uses it to surface the Al-Khidmat
programs they may qualify for, and then helps each department allocate its limited
resources to the people who need them most.

The platform separates three things that are usually collapsed together: discovering that
someone may qualify, verifying that they actually need the help, and deciding who receives
it when there is not enough to go around. AI does the first. People do the other two.

The goal is not to replace the systems each department already uses, and it is not an
attempt to build a full Management Information System. It is an intelligence layer sitting
on top of the existing setup — helping beneficiaries discover opportunities they didn't
know existed, and helping departments find people already sitting in their eligible pool.

The same matching engine works in the other direction: beneficiaries who've received
microfinance support can be connected to each other as customers, suppliers, or
co-founders, turning a one-time loan into an ongoing business relationship. Ventures formed
this way feed a portion of their later success back into Al-Khidmat's donation pool.

## 2. Problem Statement

When an organization runs several independent programs, two things tend to go wrong.

First, beneficiaries rarely know the full extent of what they qualify for. Someone who
registers for one scheme has no reliable way of checking whether their profile also fits
two or three others — doing it manually means chasing eligibility criteria across
departments they may not know exist.

Second, departments face the mirror version of the same problem. Each team manages its own
applicants well, but has no visibility into whether people already registered elsewhere
might also fit theirs. That information exists in the organization — it's just not
connected to where it's needed.

A centralized, AI-driven matching system closes this gap by surfacing relevant programs to
beneficiaries automatically, and by giving departments a way to identify likely candidates
from the existing beneficiary base.

## 3. Objectives

- Build a unified beneficiary profile reusable across every program.
- Automatically identify which programs a beneficiary is likely to qualify for.
- Cut down on manual searching and awareness campaigns as the primary discovery route.
- Give departments a way to find potential beneficiaries who already exist in the system.
- Improve how effectively existing Al-Khidmat programs are used.
- Provide genuine recommendations with reasoning — not just a searchable database.
- Help beneficiaries who've received microfinance support find customers, suppliers, and
  complementary business connections.
- Give successful marketplace ventures a lightweight way to give back to the donation pool.
- Keep a human in the loop on every recommendation, so nothing reaches a beneficiary
  without staff judgement.
- Verify real, current need before anyone is treated as a candidate for assistance.
- Allocate limited resources by verified need rather than by application date or who
  happened to hear about a program.
- Ensure people surfaced by cross-program matching compete on exactly the same terms as
  those who applied directly.

## 4. Target Users

On the eligibility side covered in this section, the platform is operated by Al-Khidmat
staff on a beneficiary's behalf — staff are the only ones who log in here. This is a
deliberate design position: the clientele is largely rural and may not navigate an online
system comfortably, and a system that requires them to do so would exclude the people it
exists to serve. (The marketplace, covered in §5.12, is the deliberate exception — see
§5.13 and §7.5.)

### 4.1 Field Officers

Al-Khidmat staff working directly with beneficiaries. They should be able to:

- Create and update a beneficiary's profile in conversation, skipping anything the person
  is uncomfortable answering.
- Create a store listing alongside a beneficiary who has trade or business information.
- See the programs a beneficiary appears to qualify for, with the reasoning.
- Review the match worklist and approve or dismiss what the system has found.
- Make introductions between matched businesses.
- Record fees and donation payments.

### 4.2 Department Administrators

Staff managing individual programs. In addition to everything a field officer can do, they
should be able to:

- Define and edit eligibility criteria for their program.
- View the beneficiaries recommended to their department.
- Identify people likely to qualify for their initiative.
- Review how far their program's reach extends and how well matches are performing.

### 4.3 Beneficiaries

People seeking support or opportunities through Al-Khidmat's programs. Their experience
differs by which half of the platform they're in:

**Eligibility side** — they do not log in and have no accounts here:
- Their profile is created for them by a field officer, in conversation.
- They are told in plain language what they appear to qualify for.
- They are shown only matches a staff member has approved — never a pending one.

**Marketplace** — they log in themselves (phone + SMS one-time code, §5.13) and act
without a staff intermediary:
- They create and own their own listing, via a conversational assistant, and update it
  themselves whenever they choose.
- If a business match is found, they're notified directly by SMS and email, and connect
  with the other party themselves — no staff introduction step.

On the eligibility side, the system never contacts a beneficiary directly — an automated
message announcing a match staff might have dismissed would raise hopes it shouldn't
have. The marketplace works the opposite way on purpose: matches there carry no
allocation decision, so there is nothing for a beneficiary's hopes to be raised falsely
about, and both parties are notified directly by SMS and email.

## 5. Core Features

### 5.1 Unified Beneficiary Profile

A single profile per beneficiary holding personal information, family details, education
background, employment and income information, location, assistance previously received,
and other relevant attributes. This removes the need to re-register from scratch for each
program.

### 5.2 AI Cross-Program Discovery

The system reads a beneficiary's profile and checks it against the eligibility criteria of
every active program, not just the one they applied for. Someone who applies for a health
loan may turn out to also qualify for vocational training, educational support, or
financial aid — and the system surfaces these automatically.

A cross-program match is a suggestion, not an application. It does not make the person an
applicant for that program and confers no priority. The confidence score attached to a
match measures the likelihood that someone may qualify; it is never used in need-based
prioritization.

Eligibility criteria won't always arrive as clean structured fields — some programs may
only have criteria written out in a document. Those documents are processed once, at
upload: a language model drafts the criteria as structured rules, a department
administrator confirms the draft, and the confirmed rules are stored on the program.
Scoring then reads the stored rules, never the document.

No language model and no retrieval runs during eligibility scoring. Scoring is a
deterministic rule check plus a trained classifier, so it completes in milliseconds and
returns the same result for the same person every time — which is what makes it auditable.
The same documents are separately chunked and embedded so the assistant can cite them on
demand.

### 5.3 Programs Requiring Explicit Application

Not every program can be offered proactively. Most Al-Khidmat programs are grants or
services — a department can approach someone and tell them they qualify, and the person is
free to accept or decline at no cost to themselves.

Microfinance is different. A loan creates a debt obligation. Surfacing someone as a
microfinance candidate they never asked for would be pushing a liability onto a vulnerable
person, and no amount of eligibility confidence justifies it.

Programs are therefore marked with a flag indicating whether they may be offered
proactively. For programs requiring explicit application, cross-program discovery still
evaluates the person — so the department can see who would qualify if they asked — but the
match is suppressed rather than pooled for outreach. The person must approach Al-Khidmat
and request it.

This also shapes the marketplace: a beneficiary only becomes a marketplace participant
after they have applied for and received microfinance support and started a business. The
marketplace is downstream of a loan the person chose to take, never of an eligibility
match.

### 5.4 AI Recommendation Engine

For each beneficiary, it produces a list of suitable programs, an eligibility confidence
score, and a plain-language reason behind each recommendation — for example: "You may
qualify for Program X because your income level, location, and family profile match its
requirements."

### 5.5 Beneficiary AI Assistant

A conversational assistant answering questions about what programs are available, what the
eligibility requirements are, what documents are needed, how to apply, and why a
particular recommendation was made. It is grounded in the same retrieval layer used for
eligibility matching, so answers reference actual program content rather than generic
text, and cite the passage they came from.

Its primary user is a staff member working with a beneficiary — answering questions such
as whether this person qualifies for anything else, or what documents a program requires.
It runs on demand only and is never part of an automatic workflow.

### 5.6 Potentially Eligible Pool

People surfaced by cross-program discovery are placed in the relevant program's
Potentially Eligible Pool. They are not contacted at this point and are not applicants.
They wait until that program's periodic assessment cycle reaches them.

This waiting stage is deliberate. Contacting someone the moment an algorithm flags them
would raise expectations the organisation may not be able to meet; outreach happens on the
department's schedule rather than the algorithm's.

### 5.7 Verification & Outreach

During a program's assessment cycle, staff contacts people in the potentially eligible
pool and establishes:

- Whether there is an actual, current need for this program.
- Whether they have already applied for or received similar assistance — from another
  Al-Khidmat department or elsewhere. Because the profile is unified, staff can see a
  person's history across every Al-Khidmat program in one place, which no single
  department could previously do.
- Current financial and household circumstances, re-confirmed rather than assumed from
  the original profile.
- Any program-specific eligibility information, and an urgency level.

Verification can fail, and failure removes the person from the pool rather than leaving
them in it. Recorded outcomes are: verified, no actual need, assisted elsewhere, not
eligible, unreachable, or declined.

A verification expires after a configurable window (90 days by default). Circumstances
change, and a candidate who rolls over across several cycles is re-contacted rather than
ranked on stale information.

Direct applicants pass through this same verification. It is not an extra hurdle for
AI-identified candidates — it is the single gate everyone goes through.

### 5.8 Unified Candidate Pool

Once verified, a person joins the same candidate pool as everyone who applied to that
program directly. From this point the two paths are indistinguishable: they are ranked by
identical criteria, in one list.

How a candidate entered — directly or through cross-program discovery — is recorded so the
organisation can audit whether the matching is genuinely finding people who qualify. It is
never used as an input to prioritization.

### 5.9 Periodic Need-Based Prioritization

Each program periodically evaluates its entire unified pool, bi-weekly by default and
configurable per program. A prioritization rubric scores every candidate on verified need,
urgency, vulnerability, household circumstances, and prior assistance, and ranks them
against one another.

The rubric is a transparent set of weights held as data on the program row, not a learned
model. Three reasons: there are no training labels for who most deserved assistance; the
decision must be defensible to a department head, a donor, or a rejected applicant; and a
department can retune a weight without retraining anything.

Weights are per-program. A health program may weight medical urgency heavily where an
education program weights school-age children — the same engine, different weights, owned
by the department.

Every candidate's score is stored with its factor-by-factor breakdown, so any position in
the ranking can be explained.

### 5.10 Human Review & Allocation

Staff reviews the ranked candidates and makes the final approval decision — the ranking is
a recommendation, not a verdict. Local knowledge the rubric cannot capture belongs at this
step.

Resources are then allocated in approved priority order until the cycle's budget or
capacity is exhausted. Candidates not funded roll over into the next cycle without
reapplying, and the number of cycles they have waited is tracked so anyone repeatedly
falling just below the line becomes visible.

### 5.11 Supporting Department View

A lightweight interface letting departments view matched beneficiaries, see potential
applicants, and gauge their program's reach. A supporting feature, not the core of the
project.

### 5.12 Beneficiary Marketplace

Beyond matching beneficiaries to programmes, the same infrastructure connects
beneficiaries to each other. A beneficiary who has applied for and received microfinance
support can join the marketplace on the app and create a listing describing their
business.

Three matching models operate: supply chain (a supplier of inputs with a producer who
needs them), employment (a business needing a skill with a beneficiary who has it), and
joint venture (two owners pooling into one shared business). Rickshaw and three-wheeler
operators participate as a logistics role, making distant matches workable.

The marketplace runs on the beneficiary app without staff involvement. Matches are sent
to both parties by SMS and email; they connect themselves. Nothing is charged at any
point — no registration fee, no ranking fee, and no claim on business earnings. Once
established, a beneficiary may choose to donate voluntarily.

Al-Khidmat introduces only. Terms, pricing, delivery and disputes are entirely between the
two businesses.

The module is specified in full in the accompanying
[Marketplace Specification](Marketplace_Spec.md) document, with its own schema file.

### 5.13 Platform Interfaces

The platform is presented as two separate, coded front ends, since the product itself —
not just the logic behind it — needs to be shown and used at the hackathon. They have two
different access models, deliberately:

- **Main Platform Portal** — staff-facing, sits behind staff login (email + password).
  Covers profile creation, eligibility results, the match review worklist, and the
  department view.
- **Marketplace App** — beneficiary-facing, sits behind phone + SMS one-time-code login,
  no staff involvement. Covers store listing creation, business match results, and the
  parties connecting directly.

Full UI design details are covered in the accompanying [System Architecture](Architecture.md)
document (§4.2.1 for the marketplace login flow), and every use case is traced step by
step in the [End-to-End Flows](End_to_End_Flows.md) document.

## 6. AI Components

### 6.1 Cross-Program Discovery

Surfaces programs a beneficiary may qualify for. Hard rules stated by the program
eliminate anyone who does not meet policy; a gradient-boosted classifier then estimates
confidence among those who remain. Output is a suggestion for staff review, never an
application.

Rules and the classifier are not alternatives. A policy threshold is a decision the
department made and written down, and cannot be learned from data; confidence among those
who pass it is a fuzzy pattern, which is what the classifier is for.

For this build the classifier is trained on synthetic data, since no historical decisions
are available. In operation, every verification outcome becomes a labelled training
example — the platform generates its own training data as it is used.

### 6.2 Criteria Extraction (LLM, one-off)

When a criteria document is uploaded, a language model drafts its rules as structured
JSON: hard rules that determine pass or fail, soft signals that become classifier
features, and the required documents a beneficiary must bring. A department administrator
confirms the draft before it takes effect — a human validates the model's reading once,
rather than the system trusting it on every registration.

This runs at upload time only. It is not part of the scoring path.

### 6.3 Natural Language Processing

Converts a beneficiary's free-text situation description into structured profile fields
using JSON-mode generation, so output is directly usable rather than parsed out of prose.
Staff confirms the extraction. This touches data entry, not eligibility.

### 6.4 Similarity Matching

Finds the relationship between a beneficiary's profile and a program's requirements, and —
for the marketplace — between two beneficiary profiles. Runs as vector similarity search
with SQL filtering applied in the same query, so candidates are narrowed by hard
constraints such as district or trade category before semantic ranking.

### 6.5 Duplicate Detection

Flags possible duplicate registrations of the same beneficiary across programs, using
exact CNIC matching first, then fuzzy comparison of name and phone via RapidFuzz. Profiles
carry no embedding, and CNIC catches nearly all real duplicates.

### 6.6 Conversational AI

Powers the interactive assistant, answering only from retrieved platform content.

### 6.7 Prioritization Rubric

Scores and ranks verified candidates within a program's unified pool. Implemented as a
transparent weighted rubric rather than a learned model, for the reasons given in 5.9, and
stored as data on the program row so departments can tune it without a code change.

The rubric operates only on verified data and profile attributes. It has no access to how
a candidate entered the pool.

### 6.8 Shared Retrieval (RAG) Layer

A single retrieval service serves the conversational assistant, match explanations, and
marketplace business matching. It does not participate in eligibility scoring — retrieval
answers questions and surfaces source passages; it does not decide who qualifies. It does
not scrape external websites.

The layer is built on a managed RAG framework rather than a hand-rolled retrieval script,
so chunking, embedding, retrieval, and citation of source passages are handled by tested
components instead of custom code written under time pressure.

### 6.9 Agentic Workflow Layer

Some parts of the system respond only when asked; others run automatically and surface
results without anyone asking first. Triggers are implemented as declarative, event-driven
workflow steps rather than ad-hoc callbacks, so each trigger's inputs, outputs, and failure
behaviour are explicit and independently testable.

The complete trigger inventory, with owners, is in the
[Team Work Division](Team_Work_Division.md) document, and every trigger is traced end to
end in the [End-to-End Flows](End_to_End_Flows.md) document. On-demand components — the
assistant, and eligibility matching at first registration — need only a request/response
API.

On the eligibility side, no trigger delivers anything to a beneficiary directly — every
automatic output lands in the staff review worklist first, because allocating limited
resources is a decision that needs human judgement. The marketplace is deliberately
different: it notifies both parties directly, since introducing two businesses carries no
allocation decision and routing it through staff would make the module a burden rather
than a benefit.

## 7. Non-Functional Requirements

### 7.1 Cost

The platform must run entirely on free tiers at hackathon scale — no paid infrastructure
and no GPU. Inference is rate-limited on the free tier, so embeddings are precomputed
rather than generated during a demo.

### 7.2 Language

The platform operates in English. Multilingual support is a future enhancement, not a
current requirement.

### 7.3 Explainability

- Every recommendation and match must surface a plain-language reason alongside the score.
- Assistant answers must be traceable to the source passage they were drawn from.

### 7.4 Fairness & Auditability

- Candidates surfaced by AI and candidates who applied directly must be ranked by
  identical criteria, in one pool.
- Entry path is recorded for audit and must never be an input to prioritization.
- Every ranking must be explainable to a factor-by-factor level.
- Each ranking cycle stores a snapshot of the weights used, so past decisions remain
  explainable after a rubric changes.

### 7.5 Access & Data Handling

- Only Al-Khidmat staff authenticate **on the eligibility side** — there is no
  beneficiary login, password reset, or account recovery there. The marketplace app is
  the deliberate exception: beneficiaries authenticate themselves via phone number + SMS
  one-time code (Architecture.md §4.2.1), since they own their own listing and matches
  there.
- Staff accounts carry a role — field officer, department administrator, or super
  administrator — which governs whether they can edit program criteria and which
  departments' matches they can see.
- Every profile, listing, and review decision records the staff member responsible, so
  actions taken on a beneficiary's behalf are attributable.
- Beneficiary records are held in a single managed Postgres database with row-level
  security available for production hardening.
- No beneficiary data is used to train any model.

## 8. Out of Scope

- Building a complete MIS or ERP platform
- Replacing existing Al-Khidmat databases
- Managing the internal operations of individual departments
- Building a full organization-wide reporting system
- Scraping external websites for opportunities, tenders, or listings
- Multilingual support
- Beneficiary-facing self-service accounts — a possible later addition, not part of this
  build
- Processing or holding live payments — fees and commitments are tracked as records, not
  settled by the platform

## 9. Expected Impact

- Beneficiaries discover programs they didn't know they were eligible for.
- Overall utilization of Al-Khidmat's programs increases.
- Repeated registrations and manual screening are reduced.
- Departments proactively identify people who need support, instead of waiting for them to
  apply.
- Successful marketplace ventures contribute back into the donation pool, reinforcing the
  funding cycle.

## 10. Future Enhancements

- Integration with existing Al-Khidmat systems.
- Multilingual support for Urdu and regional languages.
- A beneficiary-facing view, once the staff-operated model is established.
- Predictive models to anticipate future beneficiary needs.
- Automated application processing.
- Expanding the marketplace to more categories, with richer business profiles and real
  payment processing.
- Advanced analytics to support program planning.

## 11. Proposed System Flow (superseded — see note)

> **This section is carried over from the previous SRS revision and has not been rewritten
> for the staff-operated model.** It still describes beneficiaries reaching "a results
> screen," which contradicts §4's "beneficiaries do not log in." The
> [End-to-End Flows](End_to_End_Flows.md) document's eleven use cases are the current,
> authoritative version of this section — read that instead. Kept here only so the
> discrepancy is visible rather than silently dropped.

The platform runs one repeating pattern: something new gets added, the relevant part of
the system immediately checks it against everything already in place, and a match — if
any — gets surfaced without anyone having to search for it.

### 11.1 Beneficiary Registration

A person registers and creates their Unified Beneficiary Profile — personal, family,
income, location, and where relevant, trade or business information.

This single event fires three checks at once: eligibility matching against every active
program; duplicate detection against existing records; and, if trade information exists,
creation of a store listing that is immediately compared against every other listing.

The beneficiary lands on a results screen showing matched programs and, if relevant,
marketplace matches found right then.

For more detail on anything shown, the Beneficiary AI Assistant answers on request.

### 11.2 A Later Match

Not every match happens immediately. A cobbler might register on day one with no match; a
shoe-business owner might register on day five.

Day five's registration re-triggers the same check — and this time finds day one's
listing. Both beneficiaries are notified without either having to search.

The same applies to eligibility: a new or changed program re-triggers a scan of existing
beneficiaries, surfacing anyone who now qualifies.

### 11.3 Department Side

Departments see matched and recommended beneficiaries through the Supporting Department
View. Departments decide who to admit — the platform surfaces candidates, it never
enrolls anyone automatically.

### 11.4 Marketplace Participation

After a microfinance loan is disbursed, the beneficiary may join the marketplace on the
app when they choose to.

A conversational assistant creates the listing from voice or typed input, in whatever
language they speak.

Matching runs automatically and notifies both parties by SMS and email; they connect
themselves.

Nothing is charged. Once established, a beneficiary may choose to donate voluntarily.

## 12. Core Innovation

The innovation isn't storing beneficiary data or building another portal — organizations
already have systems for that. What's new is the intelligence layer connecting people to
opportunities: understanding a beneficiary's actual situation and automatically surfacing
the programs and business connections relevant to them, instead of leaving that discovery
to chance or manual effort.
