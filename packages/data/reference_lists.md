# Reference Lists — don't re-derive these, just look here

Pulled straight from the schema so this file can't drift out of sync with what's
actually in the database. If you change one of these, change it in the schema first,
then update this file to match.

## The 10 trade categories (`trade_categories`)

Source: `packages/data/schema/al_khidmat_marketplace_schema.sql`, section 2.

1. Trading businesses
2. Grocery / Karyana
3. Tailoring & embroidery
4. Livestock
5. Manufacturing
6. Services
7. Food
8. Three-wheeler / rickshaw
9. Agriculture
10. Freelancing / technology

A `microfinance_loans` row with `trade_category_id` set to one of these = eligible to
create a marketplace listing. `trade_category_id = null` = not a business (Liberation
Loan and similar) = can log in, never offered listing creation.

## The 4 loan products (`microfinance_loans.loan_product`)

Stored as free text, loosely — **no logic hangs off which one it is**. Trade category
(above) is the real signal, independent of loan product.

1. Small Business Loan — 150,000 PKR
2. Loan for Orphan's Mother — 100,000 PKR
3. Liberation Loan — 100,000 PKR (always `trade_category_id = null`, no listing)
4. Income Generating Project — 150,000 PKR

## Loan status lifecycle (`microfinance_loans.status`)

| Status | Marketplace-eligible? |
|---|---|
| `approved` | **Yes** — decided, not yet disbursed. Eligibility starts here. |
| `disbursed` | Yes |
| `defaulted` | No — and deactivates any existing listing (schema ref query J) |
| `rejected` | No |

## The 5 listing roles (`store_listings.role`)

supplier · producer · retailer · service · logistics

## The 3 matching models

| Model | Connects |
|---|---|
| Supply chain | supplier ↔ producer needing inputs |
| Employment | business needing a skill ↔ beneficiary who has it |
| Joint venture | two owners pooling into one new business |

## The 4 "seeking" flags (`store_listings`) — which model(s) a listing joins

`seeking_inputs` (materials) · `seeking_workers` · `seeking_partner` · `seeking_work`

## The 2 travel/distance gates (independent of each other)

- `is_remote_capable` — does the WORK need someone physically present
- `output_is_physical` — does a GOOD need transporting

Full reasoning for all of the above: `docs/Marketplace_Spec.md`.
