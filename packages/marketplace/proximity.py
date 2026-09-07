
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

TWO DIFFERENT CONFIDENCE LEVELS IN THIS FILE -- READ BEFORE EXTENDING
--------------------------------------------------------------------------
PROVINCE_BY_DISTRICT below covers all of Pakistan (all four provinces +
Islamabad Capital Territory + Azad Jammu & Kashmir + Gilgit-Baltistan),
not just the demo's seven districts -- a real beneficiary can be from
anywhere, and the earlier version of this file only covering seed data
was too narrow. Province membership is stable, well-known administrative
geography, so this list is filled in with real confidence.

ADJACENT_DISTRICT_PAIRS is DELIBERATELY NOT extended the same way.
Exactly which of ~160 districts physically border which others is much
easier to get wrong from memory than "which province is X in" -- and a
wrong adjacency claim is a worse bug than a missing one: it silently
gives someone a 0.85 they shouldn't get, rather than just falling back
to the still-reasonable "same province" or "elsewhere" tiers. So this
list stays small and only grows when a pair is actually confirmed, not
guessed wholesale. New districts also get created periodically (both
lists can go stale) -- the real fix, eventually, is Al-Khidmat's own
cluster/district reference data replacing this file's guesses entirely.
"""

PROVINCE_BY_DISTRICT = {
    # Punjab
    "Attock": "Punjab", "Bahawalnagar": "Punjab", "Bahawalpur": "Punjab",
    "Bhakkar": "Punjab", "Chakwal": "Punjab", "Chiniot": "Punjab",
    "Dera Ghazi Khan": "Punjab", "Faisalabad": "Punjab", "Gujranwala": "Punjab",
    "Gujrat": "Punjab", "Hafizabad": "Punjab", "Jhang": "Punjab",
    "Jhelum": "Punjab", "Kasur": "Punjab", "Khanewal": "Punjab",
    "Khushab": "Punjab", "Lahore": "Punjab", "Layyah": "Punjab",
    "Lodhran": "Punjab", "Mandi Bahauddin": "Punjab", "Mianwali": "Punjab",
    "Multan": "Punjab", "Muzaffargarh": "Punjab", "Nankana Sahib": "Punjab",
    "Narowal": "Punjab", "Okara": "Punjab", "Pakpattan": "Punjab",
    "Rahim Yar Khan": "Punjab", "Rajanpur": "Punjab", "Rawalpindi": "Punjab",
    "Sahiwal": "Punjab", "Sargodha": "Punjab", "Sheikhupura": "Punjab",
    "Sialkot": "Punjab", "Toba Tek Singh": "Punjab", "Vehari": "Punjab",

    # Sindh
    "Badin": "Sindh", "Dadu": "Sindh", "Ghotki": "Sindh",
    "Hyderabad": "Sindh", "Jacobabad": "Sindh", "Jamshoro": "Sindh",
    "Kambar Shahdadkot": "Sindh", "Karachi": "Sindh", "Kashmore": "Sindh",
    "Khairpur": "Sindh", "Larkana": "Sindh", "Matiari": "Sindh",
    "Mirpur Khas": "Sindh", "Naushahro Feroze": "Sindh", "Sanghar": "Sindh",
    "Shaheed Benazirabad": "Sindh", "Shikarpur": "Sindh", "Sujawal": "Sindh",
    "Sukkur": "Sindh", "Tando Allahyar": "Sindh", "Tando Muhammad Khan": "Sindh",
    "Tharparkar": "Sindh", "Thatta": "Sindh", "Umerkot": "Sindh",

    # Khyber Pakhtunkhwa
    "Abbottabad": "Khyber Pakhtunkhwa", "Bajaur": "Khyber Pakhtunkhwa",
    "Bannu": "Khyber Pakhtunkhwa", "Battagram": "Khyber Pakhtunkhwa",
    "Buner": "Khyber Pakhtunkhwa", "Charsadda": "Khyber Pakhtunkhwa",
    "Chitral": "Khyber Pakhtunkhwa", "Dera Ismail Khan": "Khyber Pakhtunkhwa",
    "Hangu": "Khyber Pakhtunkhwa", "Haripur": "Khyber Pakhtunkhwa",
    "Karak": "Khyber Pakhtunkhwa", "Khyber": "Khyber Pakhtunkhwa",
    "Kohat": "Khyber Pakhtunkhwa", "Kohistan": "Khyber Pakhtunkhwa",
    "Kurram": "Khyber Pakhtunkhwa", "Lakki Marwat": "Khyber Pakhtunkhwa",
    "Lower Dir": "Khyber Pakhtunkhwa", "Malakand": "Khyber Pakhtunkhwa",
    "Mansehra": "Khyber Pakhtunkhwa", "Mardan": "Khyber Pakhtunkhwa",
    "Mohmand": "Khyber Pakhtunkhwa", "North Waziristan": "Khyber Pakhtunkhwa",
    "Nowshera": "Khyber Pakhtunkhwa", "Orakzai": "Khyber Pakhtunkhwa",
    "Peshawar": "Khyber Pakhtunkhwa", "Shangla": "Khyber Pakhtunkhwa",
    "South Waziristan": "Khyber Pakhtunkhwa", "Swabi": "Khyber Pakhtunkhwa",
    "Swat": "Khyber Pakhtunkhwa", "Tank": "Khyber Pakhtunkhwa",
    "Tor Ghar": "Khyber Pakhtunkhwa", "Upper Dir": "Khyber Pakhtunkhwa",

    # Balochistan
    "Awaran": "Balochistan", "Barkhan": "Balochistan", "Chagai": "Balochistan",
    "Dera Bugti": "Balochistan", "Duki": "Balochistan", "Gwadar": "Balochistan",
    "Harnai": "Balochistan", "Jafarabad": "Balochistan", "Jhal Magsi": "Balochistan",
    "Kalat": "Balochistan", "Kech": "Balochistan", "Kharan": "Balochistan",
    "Khuzdar": "Balochistan", "Kohlu": "Balochistan", "Lasbela": "Balochistan",
    "Loralai": "Balochistan", "Mastung": "Balochistan", "Musakhel": "Balochistan",
    "Nasirabad": "Balochistan", "Nushki": "Balochistan", "Panjgur": "Balochistan",
    "Pishin": "Balochistan", "Quetta": "Balochistan", "Sherani": "Balochistan",
    "Sibi": "Balochistan", "Sohbatpur": "Balochistan", "Surab": "Balochistan",
    "Washuk": "Balochistan", "Zhob": "Balochistan", "Ziarat": "Balochistan",

    # Islamabad Capital Territory
    "Islamabad": "Islamabad Capital Territory",

    # Azad Jammu & Kashmir
    "Bagh": "Azad Jammu & Kashmir", "Bhimber": "Azad Jammu & Kashmir",
    "Hattian Bala": "Azad Jammu & Kashmir", "Haveli": "Azad Jammu & Kashmir",
    "Kotli": "Azad Jammu & Kashmir", "Mirpur": "Azad Jammu & Kashmir",
    "Muzaffarabad": "Azad Jammu & Kashmir", "Neelum": "Azad Jammu & Kashmir",
    "Poonch": "Azad Jammu & Kashmir", "Sudhanoti": "Azad Jammu & Kashmir",

    # Gilgit-Baltistan
    "Astore": "Gilgit-Baltistan", "Diamer": "Gilgit-Baltistan",
    "Ghanche": "Gilgit-Baltistan", "Ghizer": "Gilgit-Baltistan",
    "Gilgit": "Gilgit-Baltistan", "Hunza": "Gilgit-Baltistan",
    "Kharmang": "Gilgit-Baltistan", "Nagar": "Gilgit-Baltistan",
    "Shigar": "Gilgit-Baltistan", "Skardu": "Gilgit-Baltistan",
    "Tangir": "Gilgit-Baltistan",
}

# Each pair listed once; checked both directions in is_adjacent().
# Deliberately kept small -- see file docstring "TWO DIFFERENT CONFIDENCE
# LEVELS." Only pairs actually confirmed, not guessed wholesale.
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
