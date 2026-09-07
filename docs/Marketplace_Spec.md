# Beneficiary Marketplace — Module Specification

**AI-Powered Unified Beneficiary Matching & Allocation Platform — Al-Khidmat**

Al-Khidmat gives interest-free loans to people starting small businesses. Those
businesses currently operate alone: a cobbler buys leather from whoever he can find,
while another beneficiary two districts away sells leather, and neither knows the other
exists.

The marketplace connects them. It is a separate module from eligibility matching, running
on the beneficiary app, and it operates without staff involvement.

> **This is the authoritative source for the marketplace module.** The eligibility side
> and the marketplace are two front ends with two different, deliberate access models —
> Architecture.md §4 lays out both side by side.

## 1. Operating Principles

- The marketplace runs on the app, not through staff. Al-Khidmat staff run microfinance
  and read reports; they do not create listings, approve matches, or make introductions.
  The module must not add to their workload.
- Nothing is charged at any point. No registration fee, no premium ranking, no claim on
  business earnings. The only money flow is a voluntary donation a beneficiary may choose
  to make once established.
- Al-Khidmat introduces; it does not broker. Terms, pricing, delivery and disputes are
  entirely between the two businesses.
- Participation is never automatic. A person joins the marketplace when they choose to,
  once their loan is **approved** — they don't have to wait for disbursement, since the
  trade category (and so the eligibility decision) is already settled by then.
- Premium ranking was considered and deliberately rejected. Charging for visibility in a
  charity marketplace means the poorest are seen least, which contradicts the purpose —
  and routing the fee to donations does not fix it.

## 2. Entry

1. A person applies for a microfinance loan at a facilitation centre. They must ask;
   microfinance is never offered proactively, because a loan creates a debt obligation.
2. Staff takes the application on the portal and records which of Al-Khidmat's four loan
   products funds it — **and now also picks a trade category** (one of the fifteen in
   `trade_categories` — see `packages/data/reference_lists.md` for the full list and what
   each one means — or "Not a business" for bail/medical/debt-relief loans, including
   the Liberation Loan) at the same moment they already record what the loan is for. This
   is a new field on the loan application, proposed by this module specifically to make
   the gate below possible — it doesn't exist in Al-Khidmat's process today.
   Expanded from ten categories to fifteen on 6 Sep 2026 — real listings weren't finding
   a natural home (bulk jewelry making read as neither "Handicrafts" nor comfortably
   "Trading"; a beauty parlour, a home electrician, and a phone-repair shop were all
   being flattened into one catch-all "Services" bucket, which was quietly defeating the
   employment same-category matching rule described in §5.3's quality floor below, since
   two completely unrelated trades would share a category and be treated as a safe
   same-trade employment match). Expanding the list to fifteen changed how many options
   there are to choose from; **7 Sep 2026 a second change moved WHO chooses**: the
   loan's `trade_category_id` is now only the eligibility gate ("financed into a
   business at all"), and the listing's own category is picked when the listing is
   created — `FULL_DRAFT_PROMPT` proposes one, the review screen shows it pre-selected
   and changeable (§3.2). A beneficiary whose real trade differs from the loan-desk
   record — or anyone testing — was otherwise stuck with a mis-filed listing.
3. The loan is **approved** — Al-Khidmat's loan system records the outcome, in this
   schema a row in `microfinance_loans` (`loan_reference`, `loan_product`,
   `trade_category_id`, `stated_purpose_text`, `status`, `amount_disbursed`,
   `disbursed_on`), created with `status = 'approved'`, `amount_disbursed`/`disbursed_on`
   still null. The row is later updated to `status = 'disbursed'` once money actually
   moves — that update doesn't change marketplace eligibility, since approval already did.
4. Whenever they're ready — from the moment they're approved onward — the beneficiary
   joins the marketplace on the app themselves.

**Eligibility gate.** The marketplace is not public — the app is not the eligibility
side, so it cannot re-run the assessment that already happened. What it checks instead:
does a `microfinance_loans` row exist for this beneficiary with `status` `approved` or
`disbursed`, and does that row have a `trade_category_id` set. Not income, not household
size, not programme criteria — just "did Al-Khidmat decide to finance them into one of the
fifteen trade categories."

`trade_category_id` being `null` is what excludes a loan that doesn't lead to a business —
this covers the Liberation Loan, but also bail, medical, or debt-relief loans generally,
without any logic needing to check the loan product's name specifically. That beneficiary
can still log in — the gate isn't about denying them the app — but they're never offered
the listing-creation flow, since there's nothing to list.

`status` matters on the other end too: `defaulted` or `rejected` don't pass the gate — no
longer eligible, or never was. `defaulted` is stronger than just closing the gate to new
signups — an *existing* listing gets deactivated too (see the schema's reference query J),
since a defaulted loan is a reputational fact the marketplace can't just ignore for
someone already listed.

A phone number with no matching beneficiary record at all is rejected before an OTP is
even sent — the marketplace only ever authenticates people already on file from a loan
application, never a fresh signup from the general public.

**The invitation problem.** A background eligibility check tells the *system* someone
qualifies, but nothing tells the *person* the app exists — staff mentioning it at the
loan desk is not something the system can rely on. So the moment a `microfinance_loans`
row is written with a `trade_category_id` set, an SMS goes out automatically with a short
signup code (`marketplace_invitations`). That code is a convenience and an invitation,
**never a requirement** — if it's lost or never arrives, phone + OTP alone still gets
someone in, because the real gate is the eligibility check above, not the code. It also
gives a genuine adoption metric: invitations sent versus signups completed.

### 2.1 Login — Phone + SMS One-Time Code

There is no password, no email, no account-recovery flow. Login is a phone number plus a
one-time code sent by SMS.

- The number is already captured on the loan application, so login links straight to the
  existing `beneficiary_profiles` row via `beneficiary_app_accounts`.
- It's the same channel already used for match notifications (§7) — no new delivery
  mechanism to build.
- The pattern mirrors Easypaisa / JazzCash login, so it's already familiar.
- Changing a registered number is staff-assisted at a facilitation centre, not
  self-service — self-service recovery without email isn't realistic for this clientele.

Full schema (`beneficiary_app_accounts`, `login_otps`) is in Architecture.md §4.2.1 and
`packages/data/schema/al_khidmat_marketplace_schema.sql`.

**Resend cooldown, added 6 Sep 2026.** A phone number can request a new code only once
every 30 seconds — not a security feature against guessing (`verify_otp()`'s
`MAX_OTP_ATTEMPTS` already covers that), but protection against the SEND itself being
hammered. Harmless today, since no real SMS provider is wired up yet (`auth.py`'s
`_send_sms()` just prints), but the moment one is, an unthrottled resend is a way to run
up a real bill against any number, correct or not — cheaper to close now than to retrofit
once a bill exists. A number still inside its cooldown gets
`{"otp_sent": false, "reason": "cooldown", "retry_after_seconds": N}` — an expected
outcome, the same way "not eligible" already is, not an error.

Loan product and trade category are independent. A tailor funded under a Small Business
Loan and a tailor funded under Loan for Orphan's Mother are identical to the marketplace —
it reads what the business does and ignores which product financed it.

One exception: any loan recorded with no trade category — a Liberation Loan being the
clearest example — does not lead to a business, so it produces no listing.

## 3. Creating a Listing

The person opens the app, already known to it (`GET /me/context` returns their name,
district, cluster, trade category and stated purpose from the loan record — never asked
again).

**Voice-first, two screens — rebuilt 5 Sep 2026, replacing an earlier five-card
tap-through form.** The five-card version (role, then seeking flags, then one text box,
then two questions, then details — each its own screen) shipped first and is still
worth understanding *why it changed*: direct feedback was that tapping through five
screens is real friction for someone using an app like this for the first time, often
with low literacy — and once nearly every field became a tap, semantic search stopped
doing much real work, since almost everything could already be filtered structurally.
"Someone just talks, in whatever words, and the system figures out the rest" is what
actually justifies the embedding architecture existing at all — you cannot pre-build a
structured filter for something you don't know the shape of in advance. So the design
went back to that:

1. **Screen 1 — record or type.** One free-text box, filled by typing *or* by voice (a
   record button transcribes via Groq's hosted Whisper, and the transcript lands in the
   same editable box typing would have).
2. **Screen 2 — review everything the AI drafted, plus what it's never allowed to
   guess.** One richer LLM call (replacing the old enrichment-only call) reads the raw
   text and drafts the *whole* listing at once — role, all four seeking flags, business
   name, the bilingual description, skills, women-led (only if explicitly said),
   capacity, and price range — every one of them shown back and editable, never silently
   trusted. Beneath that, in a visually separate card, two questions are asked directly
   every single time, with no AI-suggested default: see §3.1.

There is no separate path based on assumptions about literacy or loan size — everyone
gets the same two screens.

### 3.1 The one LLM call, and what it's deliberately never allowed to draft

Its job isn't translation — it's *enrichment for matching*. A thin phrase like "سلائی"
makes a thin embedding. Expanded into "tailoring, stitching shalwar kameez and uniforms,
garment production," it actually matches a fabric supplier searching in English.

```python
prompt = f"""
A small-business owner in Pakistan recorded (or typed) a description of
their business, in their own words, in whatever language felt natural.

What they said: "{raw_text}"

Read it and draft a marketplace listing. Return JSON:
{{
  "trade_category": "the single best fit from this list, verbatim: {trade_categories}",
  "role": "exactly one of: supplier, producer, retailer, service, logistics",
  "seeking_inputs" / "seeking_workers" / "seeking_partner" / "seeking_work": true/false,
  "business_name": "... or null",
  "product_or_service_en": "expanded English description for semantic
     matching — include the craft, typical outputs, and related terms a
     supplier or employer would search for",
  "product_or_service_original": "their exact words, only lightly cleaned
     up — never invent detail they didn't say",
  "skills_en": "comma-separated, or null",
  "is_women_led": true/false — ONLY true if they explicitly said so,
  "monthly_capacity": "... or null",
  "price_range": "... or null"
}}
"""
```

`is_remote_capable` and `output_is_physical` are deliberately **never** in this prompt.
An earlier draft had the LLM suggest `is_remote_capable` as a pre-filled default;
reverted, because this field silently controls whether an entire distance/proximity
filter runs for the listing at all (see §5.3) — too much to hang on a model guess when a
plain, mandatory tap costs almost nothing. Both are asked directly, every time, in their
own card on the review screen, with no default that lets someone skip past them
un-answered.

**On `will_partner_outside_district` — this needed fixing, not just noting.** The gate
described in §3.3 below is a genuine *filter*, not just a ranking penalty: a candidate who
hasn't opted into cross-cluster matching is excluded from appearing at all, the same way
an unwilling supplier or worker is (§5, step 2, "Distance eligibility"). An earlier version
of the five-card design skipped its travel-question card entirely for partner-only
listings, which meant `will_partner_outside_district` could never be asked and would
silently stay `false` forever — permanently excluding that listing from every
cross-cluster joint-venture match, not merely ranking it lower. Fixed, and preserved in
this rebuild: the travel question(s) relevant to whichever seeking flags are checked
always appear on the review screen, including partner-only.

**English internally, their language everywhere they see it.** The platform-wide "English
only" rule (SRS §7.2) governs the *matching* pipeline, not what a beneficiary is required
to speak. `product_or_service` and `skills` are each stored as an `_en` version (what gets
embedded and matched) and an `_original` version (what they actually wrote, shown back to
them and to whoever they match with). Nobody has to read or write English to use this app.

### 3.2 What a listing captures

| Field | Purpose |
|---|---|
| Trade category | AI-drafted from the free text, shown pre-selected and changeable on the review screen (7 Sep 2026 — was inherited from the loan record). The loan still gates whether someone can list at all |
| Product or service | `_en` (embedded, matched) + `_original` (shown to people) — AI-drafted, editable |
| Skills | Same `_en`/`_original` split — from the same LLM call as product/service |
| Role | supplier, producer, retailer, service, or logistics — AI-drafted, editable |
| Capacity and price range | Optional, can stay blank — AI-drafted, editable |
| Cluster and district | Proximity signal; already known from the loan record |
| Seeking flags | inputs, workers, a partner, or work — AI-drafted, editable |
| Remote-capable | Plain tap, always asked, no model involved — §3.1 |
| Physical output | Plain tap, always asked, no model involved — §3.1 |
| Travel willingness | Shown for whichever seeking flag(s) are checked — asks only what's relevant |
| Women-led | A flag, not a category — AI-drafted (only if explicitly said), editable |

### 3.3 Two gates before travel willingness, not one

**Remote-capable** and **physical output** are independent, because a person's presence
and a good's movement don't always travel together:

| | Proximity filter | Distance penalty |
|---|---|---|
| Remote-capable (work) | None | None on relocation/partnering — full score (×1.0) |
| No physical output (goods) | None | None on delivery — full score (×1.0) |
| Physical, willing to travel | None | Applies (see §5, proximity weighting) |
| Physical, not willing | Own cluster only | n/a |

The clearest single-flag example is freelancing/technology: a web developer in Lahore and
a client in Karachi never meet at all, so relocating doesn't apply, and there's no
physical output either. But the two can also split: a remote consultant who ships physical
sample kits is remote-capable *and* has a physical output — the work needs no travel, the
kits still need delivery. A supplier selling design files needs neither.

| Model | What has to move | Gate | Question |
|---|---|---|---|
| Supply chain | Goods | Physical output = true | Card 5, if materials selected |
| Employment | The person | Remote-capable = false | Card 5, if work selected |
| Joint venture | Both parties, permanently | Remote-capable = false | Card 5, if partner selected |

Relocation willingness is a plain yes or no, never a declared radius. Someone might accept
Lahore to Islamabad but not Lahore to Karachi, and that depends on the pay, the city, and
their family — none of which can be answered in the abstract. Distant matches surface if
they said yes; the real decision is made when they see the actual city and offer.

## 4. The Three Matching Models

| Model | What it connects | Example |
|---|---|---|
| Supply chain | A supplier of inputs with a producer who needs them | A leather supplier and a cobbler |
| Employment | A business needing a skill with a beneficiary who has it | A growing boutique and a tailor without steady work |
| Joint venture | Two owners pooling into one shared business | A shoe seller and a fabric seller opening a combined shop |

### 4.1 Employment is structurally different

In the other two models both sides are businesses. In employment, one side is a person
offering skill and the other is a business offering work. They are not peers, and the
outcome differs: a joint venture makes two owners, employment makes one employer and one
employee.

It is also the model that most directly serves what Al-Khidmat gets from this. One loan
funds a business; that business hires another beneficiary; one loan produces two
livelihoods.

## 5. Matching Logic

Fires whenever a listing is created or edited — but see §5.2 on WHEN the results actually
appear, changed 6 Sep 2026.

1. **Complementary role filter** — a producer looks for suppliers, not other producers. A
   joint venture candidate looks only at others who opted in.
2. **Distance eligibility** — a goods match needs willingness to deliver; an employment
   match needs willingness to relocate. Applied as a filter, so nobody is shown matches
   they have already ruled out. Skipped for a supply-chain match when the listing's
   output isn't physical, and for an employment or joint-venture match when the listing
   is remote-capable (§3.3) — in each case, nothing to check distance against.
3. **Quality floor** — added 5 Sep 2026, see §5.3. Two thresholds, applied as filters in
   the same query as step 2, not a ranking penalty: a global floor every candidate must
   clear, and a stricter same-trade-or-strong-similarity gate specific to employment.
4. **Vector similarity** over the listing text ranks whatever survives the filters.
5. **Proximity weighting** reorders the result: same cluster × 1.00, adjacent district ×
   0.85, same province × 0.70, elsewhere × 0.50 — except where step 2's gate was open,
   which stays at × 1.00 regardless of where the other side is.

The matching pool always covers every existing listing, not only recent ones.

Proximity is a weight, not a filter. A strong cross-cluster match can outrank a weak local
one — a well-suited leather supplier two districts away is worth more than a poor one
nearby.

### 5.1 Why cross-cluster matters

Al-Khidmat operates 53 clusters. Within a cluster, people often already know each other,
so matching adds little. The platform's real value is between clusters: a leather
supplier in Sukkur and a cobbler in Hyderabad currently have no way to find one another.

Each match is labelled with its proximity so the practical difference is visible — a
same-cluster introduction is straightforward, while a cross-cluster one means goods
physically move and transport has to be arranged.

### 5.2 The delayed match

A cobbler lists on Monday and no supplier exists yet, so nothing happens. A supplier lists
on Friday, matching runs against everything already stored, and finds Monday's cobbler.
The trigger is Friday's listing, not a scheduled scan — which is why matching always
runs against the full pool rather than only new arrivals.

**When the results actually appear, changed 6 Sep 2026.** Matching itself is fast (one
indexed vector query per applicable model), but writing a plain-language reason for each
surviving match is a real LLM call *per match* — up to 8-10 sequential Groq calls for a
listing with several matches. Running that inline, inside the same request that saves the
listing, is what made saving feel frozen for a minute or two. It now runs as a background
task instead: the person sees their listing saved immediately, and the app polls for match
results behind the scenes, showing a genuine "still looking" state rather than either a
frozen screen or a falsely-empty one. See Marketplace_Technical_Flow.md §3 for the
mechanism.

**A genuinely empty result now explains itself.** Rather than a dead "no opportunities
yet" regardless of cause, the system names the actual reason — nobody nearby offers this
yet, or candidates exist but none are close enough or willing to travel, or (for
employment specifically) nearby candidates exist but none share the trade category and
none cleared the strong-similarity bar in §5.3. Computed from the same real counts the
filters themselves use, not guessed.

### 5.3 Quality floor

Added 5 Sep 2026, direct feedback: a clay-jewelry maker seeking employment was once shown
"Fatima Farms" (needs field workers) as a match, with a perfectly plausible-sounding
reason attached — because matching always returned the top candidates from whatever
passed the filters, even when none of them were genuinely a good fit. Two thresholds fix
this, applied as SQL filters (never fetch-then-filter in Python):

- **A global floor, deliberately low.** Checked directly against real data before picking
  a number: genuinely good supply-chain matches scored as low as 0.28 on this dataset's
  short, template-heavy text, while the bad farm/jewelry match scored 0.41-0.50 — *higher*
  than the good one. Raw similarity alone doesn't reliably separate good from bad here, so
  the floor is set safely below every good match measured, catching only the truly
  degenerate, near-unrelated tail — not a confident "this line separates good from bad."
- **A stricter, employment-only gate.** Unlike supply chain (where crossing trades is the
  whole point — a leather supplier matching a shoemaker in a different category is exactly
  how that model works), an employer hiring for their own trade overwhelmingly wants
  someone in that *same* declared trade category — a cheap, reliable signal this dataset's
  short descriptions don't reliably encode into the embedding alone. So an employment
  candidate must either share the source's trade category, or clear a meaningfully higher
  similarity bar to prove a genuine cross-trade connection. Calibrated from real evidence,
  not a first guess: an initial bar caught the Fatima Farms case but two more real
  "this shouldn't have matched" examples surfaced independently at the same level
  (an electrician matched to graphic designers; a potter matched to a beauty parlour and a
  repair shop) — three examples clustered in the same band was treated as a pattern, not
  noise, and the bar was raised well above it. Still explicitly revisable: if a genuinely
  good cross-trade employment match is ever blocked by it, that's real evidence to loosen
  it again, the same way these examples were evidence to tighten it.

This is also why the category expansion in §2 mattered beyond taxonomy: a same-category
check is only a meaningful signal if the categories are narrow enough that two genuinely
unrelated trades don't share one.

### 5.4 Search is a separate thing from matching, and deliberately unfiltered

Everything above (§5–5.3) is *automatic* matching — the system pushing candidates at a
listing when it's created or edited. A beneficiary can also search directly, at any time,
for something they need — a supplier for their next batch of leather, a rickshaw operator,
a tailor to hire.

**Search covers every cluster, with no proximity filter and no willingness check at all —
even for a listing that isn't remote-capable and never said it would travel or deliver.**
This is a deliberate difference from automatic matching, not an oversight:

- Search is intent-driven. Someone searching already knows what they need and is
  prepared to judge the distance themselves — a Sukkur cobbler searching for leather
  suppliers wants to see every supplier that exists, including a strong one in Hyderabad,
  and decide for himself whether the trip or delivery cost is worth it.
- Automatic matching is push-driven — the system is choosing what to interrupt someone
  with unprompted, which is exactly where the willingness/remote-capable flags earn their
  keep: they keep the system from pushing a cross-country match at someone who has
  already said, in advance, that they wouldn't take it.

In short: **the flags constrain what gets pushed automatically, never what a person can
find by looking for it themselves.**

## 6. Logistics as a Service

Rickshaw and three-wheeler operators are a distinct role. They are not supplying or
producing — they are what makes a distant match workable, and they answer the
transport-cost question by being present in the match rather than leaving it unresolved.

A logistics listing carries routes rather than a single location, since an operator
covers a corridor, plus vehicle type and what will actually fit.

### 6.1 Two ways logistics surfaces

- **Automatically** — attached to a cross-cluster goods match, suggesting an operator who
  runs that route.
- **By direct search** — any beneficiary needing transport can look for an operator,
  including for business that has nothing to do with the marketplace. A tailor moving
  garments to an outside buyer has a real need, and restricting logistics to internal
  matches would be arbitrary.

This also gives operators something a supplier-and-producer marketplace would not: repeat
work on a known route, rather than whoever flags them down.

## 7. Notification and Connection

- Matches are sent to every party involved, by SMS and email. No phone calls — that would
  put the burden back on staff.
- Everyone matched can see and act. People weigh their options and choose the best one,
  as in any real market.
- The parties connect themselves and visit a facilitation centre if they wish. Staff is
  not part of this step.
- Either side may dismiss a match, and that pair never resurfaces.
- Matches expire after seven days without response, so nobody waits indefinitely.

## 8. Availability and Rate Limiting

A listing carries an availability status the person controls:

| Status | Meaning |
|---|---|
| seeking | Actively looking; surfaces normally in matching |
| open_to_offers | Not looking, but will hear a good one; ranks lower and is flagged |
| committed | Capacity is spoken for; does not surface in new matches |

In practice nobody marks themselves busy voluntarily — few people turn away sales — so
there is an automatic backstop. Once a listing has more than five open, unanswered
requests it stops surfacing until some are answered or expire. This protects both sides: a
supplier buried in forty requests answers none of them, and forty people get silence.

## 9. Ventures, Participants and Independence

### 9.1 A venture is a listing

When two listings combine, the venture becomes its own listing and re-enters the pool as
a participant. A venture is simply a business, and businesses keep needing suppliers,
keep expanding into new districts, and keep partnering. There is no terminal state.

The venture declares its own cluster, district, trade category and role — nothing is
inherited from the parents, because the combined shop may be somewhere neither parent was,
selling something neither sold alone.

### 9.2 Lineage

Which listings formed a venture is recorded separately. This prevents re-matching people
who have already partnered, and it produces a genuine outcome to report: a venture that
grew from three beneficiaries across two clusters and now employs two more.

### 9.3 A person keeps their own identity

Ownership lives in a participants table, never on the listing, so a listing may have any
number of owners plus employees.

A person may hold more than one listing. A tailor who joins a boutique still has his own
tailoring listing — joining a venture does not erase him. Working somewhere does not stop
anyone looking for other opportunities.

| Situation | Own listing becomes | Why |
|---|---|---|
| Became a venture co-owner | committed | His capacity now belongs to the venture |
| Employed at another business | stays seeking | A job does not tie up his own trade |
| Wants both | his choice | He sets it himself; the system does not decide |

### 9.4 Transparency

Every listing publicly shows where else that person is confirmed to be involved — also a
partner in one venture, also employed at another. In a network where nobody has ratings
yet, existing involvement is real signal, and it lets someone judge availability before
asking.

Only confirmed involvement is shown. Pending or in-discussion involvement is never
displayed, since nothing has actually happened yet.

## 10. Housekeeping and Boundaries

- Listings expire after six months unless confirmed, so dead listings clean themselves up
  rather than accumulating.
- Al-Khidmat introduces only. Terms, pricing, delivery, transport costs, and any dispute
  are entirely between the two businesses. This must be displayed at listing creation and
  again at introduction, not buried in a policy page.
- Nothing is charged. Once a business is established, the app may offer a gentle,
  voluntary donation option. There is no schedule, no amount owed, and no overdue state.

## 11. What Al-Khidmat Gains

The marketplace charges nothing, so the return to Al-Khidmat is not financial. It is
larger than a fee would have been.

### 11.1 Zakat graduation

Al-Khidmat's own stated objective is to transform beneficiaries into future donors. In
Islamic terms this is the move from *mustahiq* — eligible to receive zakat — to someone
who pays it. A beneficiary whose business succeeds crosses that line.

Tracking it turns a narrative into a reportable metric: not only how many people were
helped, but how many no longer need help and now contribute. For an organisation whose
most prominent call to action is *Give Zakat*, that is worth considerably more than any
fee this module could have charged.

### 11.2 A mobilisable supply network

Al-Khidmat runs disaster response. The marketplace is, incidentally, a live register of
local businesses by district and trade — who can supply food, materials, or transport, in
which area, right now.

During a flood or earthquake that is operational infrastructure rather than a
convenience, and it exists as a byproduct of the marketplace running normally.

### 11.3 Verified linkage stories

Lineage and participant data produce traceable outcomes rather than anecdotes: this
venture grew from three beneficiaries across two clusters and now employs two more
people.

Institutional donors and grant committees fund measurable outcomes. "We disbursed 866
million" is a spending figure; "we disbursed 866 million and created N verified business
linkages and M jobs" is an effectiveness figure, and it is generated automatically.

### 11.4 Employment beyond the borrower

A business with reliable supply and steady customers hires. That is a livelihood created
for someone who never took a loan at all — the clearest possible answer to what the
marketplace produces.

None of these take anything from beneficiaries, which is what makes them safe to present.
A charity marketplace that generates profit for the charity invites exactly the question
you do not want asked.

## 12. Scope Boundaries

- **Out:** payment processing, escrow, delivery tracking, ratings and reviews, any fee of
  any kind.
- **Out:** staff-mediated listing creation, staff approval of matches, staff-made
  introductions.
- **Out:** any obligation on a beneficiary's business income.
- **In:** listing creation by assistant, three matching models, logistics as both match
  participant and searchable service, SMS and email notification, participant and
  lineage tracking, voluntary donations, graduation tracking.
