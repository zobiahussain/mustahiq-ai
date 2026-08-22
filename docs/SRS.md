# Software Requirements Specification

**AI-Powered Unified Beneficiary Matching Platform for Al-Khidmat**

## 1. Project Overview

Al-Khidmat runs programs across seven distinct domain areas, each addressing a different
kind of need — education, healthcare, financial support, vocational training, and others.
These programs are managed independently. A person who becomes a beneficiary under one
program has no simple way of finding out whether they also qualify for the others, and the
departments running those programs have no easy way of knowing that this person already
exists in their pool of potential candidates.

This project proposes an AI-powered Unified Beneficiary Matching Platform that builds a
single profile for each beneficiary and uses it to intelligently match individuals with
the Al-Khidmat programs they are eligible for.

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

## 4. Target Users

### 4.1 Beneficiaries

People seeking support or opportunities through Al-Khidmat's programs. They should be
able to:

- Create and update their profile.
- Provide personal, family, educational, financial, and location details.
- View the programs they may qualify for.
- Receive recommendations and notifications as new matches appear.
- See why they were matched to a particular program.
- Track the status of their applications.

### 4.2 Al-Khidmat Departments

Authorized staff managing individual programs. They should be able to:

- Define eligibility criteria for their program.
- View the beneficiaries recommended to them.
- Identify people likely to qualify for their initiative.
- Review how far their program's reach extends and how well matches are performing.

## 5. Core Features

### 5.1 Unified Beneficiary Profile

A single profile per beneficiary holding personal information, family details, education
background, employment and income information, location, assistance previously received,
and other relevant attributes. This removes the need to re-register from scratch for each
program.

### 5.2 AI-Based Eligibility Matching

The system reads a beneficiary's profile and checks it against the eligibility criteria of
every active program, not just the one they applied for. Someone who registers for one
initiative may turn out to also qualify for vocational training, educational support,
healthcare assistance, financial aid, or a community program — and the system flags these
automatically.

Eligibility criteria won't always arrive as clean structured fields — some programs may
only have criteria written out in a document. For those cases the system uses
Retrieval-Augmented Generation to pull the relevant criteria at matching time. Retrieval
runs over documents uploaded to the platform or prepared as mock program documents; the
system does not scrape external websites.

### 5.3 AI Recommendation Engine

For each beneficiary, it produces a list of suitable programs, an eligibility confidence
score, and a plain-language reason behind each recommendation — for example: "You may
qualify for Program X because your income level, location, and family profile match its
requirements."

### 5.4 Beneficiary AI Assistant

A conversational assistant that helps beneficiaries understand what programs are
available, what the eligibility requirements are, what documents they'll need, how to
apply, and why a particular recommendation was made. It is grounded in the same retrieval
layer used for eligibility matching, so answers reference actual program content rather
than generic text.

### 5.5 Supporting Department View

A lightweight interface letting departments view matched beneficiaries, see potential
applicants, and gauge their program's reach. A supporting feature, not the core of the
project.

### 5.6 Beneficiary Marketplace

Beyond matching beneficiaries to Al-Khidmat's programs, the same profile and matching
infrastructure connects beneficiaries to each other. A beneficiary who has received
microfinance financing — or simply has relevant trade or business information on their
profile — can opt in to create a store listing: their trade or business, product or
service, location, capacity, and pricing.

This reuses the same matching AI built for eligibility matching — beneficiary-to-program
and beneficiary-to-beneficiary matching are structurally the same problem, pointed at a
different pair of profiles.

#### 5.6.1 Marketplace Business Models

| Model | How it works | Example |
|---|---|---|
| 1. Supply-chain pairing | A beneficiary supplying a raw material or input is matched with a beneficiary running the end-product business that needs it. | A leather/fabric supplier matched to a cobbler |
| 2. Joint-venture formation | Two beneficiaries with complementary skills are matched to combine into a new business rather than a supplier relationship. | A tailor and a fabric/garment shop owner matched to jointly open a boutique |
| 3. Competitive ranking | A beneficiary offering goods or services similar to others can pay a premium fee to rank above unboosted competitors in match results. | Two shoe sellers on the marketplace; one pays to rank first |

#### 5.6.2 Venture Lifecycle & Fee Structure

- A flat, one-time registration fee is charged when a store listing is first created.
- A grace period of roughly six months to a year follows, during which no earnings-based
  commitment applies.
- Once earning, a recurring donation commitment begins — periodic payments over the
  following year — flowing into Al-Khidmat's donation pool.
- Premium ranking fees route into the same donation pool rather than being kept as
  platform revenue.
- Exact fee amounts and the donation-commitment cadence are placeholders — confirm the
  figures before finalizing.
- The platform tracks these fees and commitments as records rather than processing live
  payments.

### 5.7 Platform Interfaces

The platform is presented as two separate, coded portals, since the product itself — not
just the logic behind it — needs to be shown and used at the hackathon.

- **Main Platform Portal** — for beneficiaries and departments: profile creation,
  recommendations view, department view.
- **Marketplace Portal** — for the business-matching side: store listing creation, match
  results, and alerts.

Full UI design details are covered in [Architecture.md](Architecture.md).

## 6. AI Components

### 6.1 Recommendation System

Matches beneficiaries to programs using rule-based eligibility cutoffs combined with a
gradient-boosted classifier for soft-match probability.

### 6.2 Natural Language Processing

Interprets beneficiary descriptions, program descriptions, and eligibility criteria.
Free-text input is converted into structured profile fields using JSON-mode generation, so
output is directly usable rather than parsed out of prose.

### 6.3 Similarity Matching

Finds the relationship between a beneficiary's profile and a program's requirements, and —
for the marketplace — between two beneficiary profiles. Runs as vector similarity search
with SQL filtering applied in the same query, so candidates are narrowed by hard
constraints such as district or trade category before semantic ranking.

### 6.4 Duplicate Detection

Flags possible duplicate registrations of the same beneficiary across programs, combining
fuzzy string comparison on identity fields with vector similarity on the wider profile.

### 6.5 Conversational AI

Powers the interactive assistant, answering only from retrieved platform content.

### 6.6 Shared Retrieval (RAG) Layer

A single retrieval service sits behind both the eligibility engine and the conversational
assistant, pulling relevant passages from uploaded or mock program and business documents
at matching or answer time. This is one shared service rather than a separate pipeline per
component, and it does not scrape external websites.

The layer is built on a managed RAG framework rather than a hand-rolled retrieval script,
so chunking, embedding, retrieval, and citation of source passages are handled by tested
components instead of custom code written under time pressure.

### 6.7 Agentic Workflow Layer

Some parts of the system respond only when asked; others run automatically and surface
results without anyone asking first. Triggers are implemented as declarative, event-driven
workflow steps rather than ad-hoc callbacks, so each trigger's inputs, outputs, and failure
behaviour are explicit and independently testable.

The complete trigger inventory, with owners, is in
[Team_Work_Division.md](Team_Work_Division.md). On-demand components — the Beneficiary AI
Assistant, and eligibility matching at first registration — need only a request/response
API.

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

### 7.4 Data Handling

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
- Predictive models to anticipate future beneficiary needs.
- Automated application processing.
- Expanding the marketplace to more categories, with richer business profiles and real
  payment processing.
- Advanced analytics to support program planning.

## 11. Proposed System Flow

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

### 11.4 Venture Lifecycle

1. A store listing is created and the one-time registration fee is recorded.
2. For a grace period of roughly six months to a year, no earnings-based commitment
   applies.
3. Once earning, a recurring donation commitment begins, recorded and routed toward the
   donation pool.
4. If the beneficiary opts into competitive ranking, the premium fee is recorded and
   routed to the same pool.

## 12. Core Innovation

The innovation isn't storing beneficiary data or building another portal — organizations
already have systems for that. What's new is the intelligence layer connecting people to
opportunities: understanding a beneficiary's actual situation and automatically surfacing
the programs and business connections relevant to them, instead of leaving that discovery
to chance or manual effort.
