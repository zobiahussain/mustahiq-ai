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
  after their loan is disbursed.
- Premium ranking was considered and deliberately rejected. Charging for visibility in a
  charity marketplace means the poorest are seen least, which contradicts the purpose —
  and routing the fee to donations does not fix it.

## 2. Entry

1. A person applies for a microfinance loan at a facilitation centre. They must ask;
   microfinance is never offered proactively, because a loan creates a debt obligation.
2. Staff takes the application on the portal and records which of Al-Khidmat's four loan
   products funds it.
3. The loan is approved and disbursed.
4. Later, when they are ready, the beneficiary joins the marketplace on the app
   themselves. This is not tied to disbursement.

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

Loan product and trade category are independent. A tailor funded under a Small Business
Loan and a tailor funded under Loan for Orphan's Mother are identical to the marketplace —
it reads what the business does and ignores which product financed it.

One exception: a Liberation Loan does not lead to a business, so it produces no listing.

## 3. Creating a Listing

The person opens the app. A conversational assistant asks what they do, in plain
language. They answer by voice or keyboard, in whatever language they speak. The model
structures the answer into a listing and reads back what it understood for confirmation.

There is no form. This is the whole onboarding, and it is the same experience for
everyone — there is no separate path based on assumptions about literacy or loan size.

### 3.1 What a listing captures

| Field | Purpose |
|---|---|
| Trade category | One of ten reference categories; drives matching |
| Product or service | Free text, embedded for semantic matching |
| Skills | What this business can do — used for employment matching |
| Role | supplier, producer, retailer, service, or logistics |
| Capacity and price range | Context for whether a match is workable |
| Cluster and district | Proximity signal; cluster is Al-Khidmat's own operating unit |
| Seeking flags | inputs, workers, a partner, or work — which models this listing joins |
| Travel willingness | Asked per model; see 3.2 |
| Women-led | A flag, not a category — it cuts across all ten |

### 3.2 Travel willingness is asked per model

A single transportability flag does not work, because a different thing moves in each
model.

| Model | What has to move | Question asked |
|---|---|---|
| Supply chain | Goods | Will you deliver outside your area? |
| Employment | The person | Would you relocate for work? |
| Joint venture | Both parties, permanently | Would you partner outside your district? |

There is no transportability lookup table by trade category. The person is asked
directly, because they know and a table would only guess — tailoring is local as a
service but its finished garments travel fine, and grocery splits by product rather than
by category.

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

Fires whenever a listing is created or edited.

1. **Complementary role filter** — a producer looks for suppliers, not other producers. A
   joint venture candidate looks only at others who opted in.
2. **Distance eligibility** — a goods match needs willingness to deliver; an employment
   match needs willingness to relocate. Applied as a filter, so nobody is shown matches
   they have already ruled out.
3. **Vector similarity** over the listing text ranks whatever survives the filters.
4. **Proximity weighting** reorders the result: same cluster × 1.00, adjacent district ×
   0.85, same province × 0.70, elsewhere × 0.50.

The search always covers the entire existing pool, not only recent listings.

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
on Friday, the search runs against everything already stored, and finds Monday's cobbler.
The trigger is Friday's listing, not a scheduled scan — which is why matching always
searches the full pool rather than only new arrivals.

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
