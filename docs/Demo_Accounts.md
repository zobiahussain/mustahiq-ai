# Demo login accounts

The fixed cast for a live demo of the marketplace app. Created by
`packages/data/seed_demo_accounts.py` (re-runnable) — keep this file in sync
with that script's `DEMO_ACCOUNTS` list.

Every account is a **real `microfinance_loans` row**, so it works with the
real eligibility gate (`SKIP_ELIGIBILITY_CHECK=false`). None have a listing
yet — the demo is *log in → create a listing → watch matching run*, not
"look at one that already exists". The trade category is fixed per number
(decided at "loan time"); describe a business that fits it.

## Setup

```powershell
cd packages\data
..\rag\.venv\Scripts\python.exe seed_demo_accounts.py
```

## The OTP code

Not sent by SMS. After **Send code** (click once — a fast second click hits
the resend cooldown), read it from the **API server terminal**:

```
[SMS -- NOT ACTUALLY SENT ...] to +923111100005: Your Al-Khidmat marketplace code is NNNNNN
```

---

## Lahore / LHR-01 — one per trade category

LHR-01 is the densest seed cluster: every category has counterparts on every
side (hiring, job-seekers, buyers, suppliers, partners), so whatever the
listing ends up seeking, matches come back — most as **"same cluster" ×1.00**.

| Phone | Category | Loan | Describe a business like… |
|---|---|---|---|
| `+923111100001` | Trading businesses | disbursed | wholesale mixed merchandise; needs stock, or a supplier |
| `+923111100002` | Grocery / Karyana | disbursed | karyana shop; needs a wholesaler, or hiring a cashier |
| `+923111100003` | Tailoring & embroidery | **approved** | stitching shalwar kameez & uniforms; seeking work, or hiring stitchers |
| `+923111100004` | Livestock | disbursed | goat & cattle rearing; needs feed, or a dairy partner |
| `+923111100005` | Manufacturing | disbursed | stitching footballs / sports goods; needs raw material, or hiring operators |
| `+923111100006` | Services | disbursed | laundry & dry-cleaning; seeking steady customers |
| `+923111100007` | Food | disbursed | home bakery; needs flour & sugar supply, or hiring kitchen staff |
| `+923111100008` | Three-wheeler / rickshaw | disbursed | goods delivery between areas; needs spare parts |
| `+923111100009` | Agriculture | **approved** | seasonal wheat & rice; needs seed & fertilizer |
| `+923111100010` | Freelancing / technology | disbursed | freelance web development, remote; seeking work or a partner |
| `+923111100011` | Handicrafts & Artisan Crafts | disbursed | handmade jewellery / pottery; needs beads & clay, or seeking commissions |
| `+923111100012` | Construction & Home Trades | disbursed | electrician; seeking work, or a contractor hiring tradesmen |
| `+923111100013` | Beauty & Personal Care | disbursed | home salon; needs cosmetics supply, or a partner for a parlour |
| `+923111100014` | Repair & Maintenance | disbursed | mobile & appliance repair; needs spare parts |
| `+923111100015` | Education & Tutoring | disbursed | home tutoring; seeking students, or an academy partner |

## Karachi / KHI-01 — a second cluster

For cross-city stories and to show proximity weighting (a Karachi listing
matching a Lahore one comes back at **×0.70 "same province"** or lower, below
the same-cluster matches).

| Phone | Category | Loan |
|---|---|---|
| `+923111102001` | Tailoring & embroidery | **approved** |
| `+923111102002` | Handicrafts & Artisan Crafts | disbursed |
| `+923111102003` | Food | disbursed |
| `+923111102004` | Manufacturing | disbursed |
| `+923111102005` | Livestock | disbursed |
| `+923111102006` | Beauty & Personal Care | disbursed |

## Edge cases

| Phone | What it shows |
|---|---|
| `+923111109001` | **Demo Liberation** — Liberation-Loan style, no trade category. Logs in fine, but `can_create_listing: false` — never offered listing creation. |
| `+923001234573` | Sara Iqbal — loan status `defaulted` → **403 at Send code**, no OTP. |
| `+923001234575` | Nadia Parveen — loan status `rejected` → **403 at Send code**, no OTP. |
| any number not in the DB (e.g. `+923009999999`) | **403** "This number isn't recognised, or isn't yet eligible." |
| `+923001234567` | Amina Bibi (from `seed_data.py`) — the original curated eligible number, Tailoring, disbursed. |
