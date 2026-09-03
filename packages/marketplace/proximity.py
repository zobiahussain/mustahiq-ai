"""
The proximity re-weighting step (Marketplace_Spec.md section 5, step 4):
same cluster x1.00, adjacent district x0.85, same province x0.70,
elsewhere x0.50.

WHY THIS FILE EXISTS SEPARATELY, AND A GAP IT'S FILLING IN
--------------------------------------------------------------
Nothing in the delivered schema records which province a district is in,
or which districts border each other. store_listings.district is just
free text. So this data has to live SOMEWHERE for the four-tier weighting
to be computable at all -- this file is that somewhere, for now.

THIS IS BEST-EFFORT DEMO DATA, NOT AN AUTHORITATIVE SOURCE. It only
covers the districts actually used in packages/data/seed_data.py.
Province groupings are solid (well-known, low risk of being wrong).
District ADJACENCY is real Pakistani geography but hand-typed from
memory -- verify before relying on it for anything beyond the demo. A
real version of this would come from Al-Khidmat's own cluster/district
reference data, not a Python dict.
"""

PROVINCE_BY_DISTRICT = {
    "Lahore": "Punjab",
    "Faisalabad": "Punjab",
    "Multan": "Punjab",
    "Sheikhupura": "Punjab",
    "Hyderabad": "Sindh",
    "Sukkur": "Sindh",
    "Karachi": "Sindh",
}

# Each pair listed once; checked both directions in is_adjacent().
# Deliberately small and honest about what it covers -- see file docstring.
ADJACENT_DISTRICT_PAIRS = {
    frozenset({"Lahore", "Sheikhupura"}),
}


def is_adjacent(district_a: str, district_b: str) -> bool:
    return frozenset({district_a, district_b}) in ADJACENT_DISTRICT_PAIRS


def proximity_multiplier(
    cluster_a: str | None,
    district_a: str,
    cluster_b: str | None,
    district_b: str,
) -> tuple[float, str]:
    """
    Returns (multiplier, human_label) -- the label is what
    marketplace_matches.proximity_label stores, e.g. "same cluster" or
    "Lahore -> Sukkur", per the schema comment on that column.
    """
    if cluster_a and cluster_b and cluster_a == cluster_b:
        return 1.00, "same cluster"

    if is_adjacent(district_a, district_b):
        return 0.85, f"{district_a} -> {district_b}"

    province_a = PROVINCE_BY_DISTRICT.get(district_a)
    province_b = PROVINCE_BY_DISTRICT.get(district_b)
    if province_a and province_a == province_b:
        return 0.70, f"{district_a} -> {district_b} (same province)"

    return 0.50, f"{district_a} -> {district_b}"
