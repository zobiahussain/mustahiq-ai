# Demo login accounts

A fixed set of beneficiaries for a live demo of the marketplace app. All are
**Lahore / LHR-01** (the densest seed cluster — every trade category has
counterpart listings on every side: hiring, job-seekers, buyers, suppliers,
partners), all `disbursed` with a real trade category, and **none have a
listing yet** — so you log in, create a listing on the spot, and matching
runs against the seeded Lahore businesses.

Requires `SKIP_ELIGIBILITY_CHECK=false` in `.env` (the real gate — these are
real `microfinance_loans` rows, not the bypass). The trade category is fixed
per number (set at "loan time"); describe a business that fits it.

| Phone | Trade category | Describe a business like… |
|---|---|---|
| `+923111110001` | Manufacturing | stitching footballs / sports goods, needs raw material, or hiring machine operators |
| `+923111110002` | Tailoring & embroidery | stitching shalwar kameez & uniforms; seeking work, or hiring stitchers |
| `+923111110003` | Handicrafts & Artisan Crafts | handmade jewellery / pottery; needs beads & clay, or seeking commissions |
| `+923111110004` | Food | home bakery; needs flour & sugar supply, or hiring kitchen staff |
| `+923111110005` | Grocery / Karyana | karyana shop; needs a wholesale supplier, or hiring a cashier |
| `+923111110006` | Livestock | goat & cattle rearing; needs feed, or a dairy partner |
| `+923111110007` | Beauty & Personal Care | home salon; needs cosmetics supply, or a partner to open a parlour |
| `+923111110008` | Construction & Home Trades | electrician; seeking work, or a contractor hiring tradesmen |

## The OTP code

Not sent by SMS. After "Send code", read it from the **API server terminal**:

```
[SMS -- NOT ACTUALLY SENT ...] to +923111110001: Your Al-Khidmat marketplace code is NNNNNN
```

Click **Send code once** — a fast second click hits the resend cooldown and
returns no new code.

## Re-seeding these accounts

```powershell
cd packages\data
..\rag\.venv\Scripts\python.exe create_test_customer.py --phone "+923111110001" --name "Demo Sportswear" --district "Lahore" --category "Manufacturing" --status disbursed
# …one line per row above. --cluster defaults to LHR-01 via proximity.cluster_for("Lahore").
```
