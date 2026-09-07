"""
explain_no_matches(listing_id) -- direct response to real feedback: an
empty "No opportunities yet" screen tells a beneficiary NOTHING about why,
or what would need to change. This runs the same funnel matching.py's
_search_* functions already apply -- role/seeking filter -> geography
eligibility -> similarity floor -> (employment only) same-category-or-
strong-similarity gate -- but instead of stopping at the first empty
result, it counts how many candidates survive EACH stage, so it can name
the specific stage where the count hit zero. That's a real, honest reason
("3 businesses need what you offer, but none are near you or willing to
deliver"), not a generic "nothing found."

WHY THIS IS A TEMPLATE, NOT A GROQ CALL
--------------------------------------------------------------------------
Every number here comes straight out of a SQL count -- there's no
ambiguity to resolve, no language to generate freely, just which of five
fixed situations applies. Same reasoning CLAUDE.md already states for
eligibility match reasons ("templated, not LLM-generated" -- deterministic,
auditable, no rate limit, no chance of the LLM inventing a reason that
doesn't match the real numbers). Groq already sits on the critical path
for match REASONS (a match that DID happen); this deliberately doesn't
add a second LLM dependency for the case where nothing happened at all.

ONLY CALLED WHEN find_matches() GENUINELY RETURNED EMPTY, ON PURPOSE
--------------------------------------------------------------------------
Every query below re-runs parts of the same filtering find_matches()
already did. Fine for the empty-result case (rare enough, and only
computed once, right when someone opens their own results) -- would be
wasteful to run on every listing regardless of outcome, so callers should
only reach for this after confirming there's actually nothing to explain.
"""

import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

from matching import _fetch_listing, MIN_SIMILARITY, EMPLOYMENT_STRONG_SIMILARITY

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def _funnel(cur, source: dict, *, base_where: str, base_params: dict,
            geo_clause: str, strong_gate: bool) -> dict:
    """
    Runs the same WHERE clause in three (or four) increasingly strict
    forms and returns the count at each stage -- the shared machinery
    behind every direction below.
    """
    vec_params = {
        **base_params,
        "vec": source["embedding"],
        "max_distance_floor": 1 - MIN_SIMILARITY,
        "max_distance_strong": 1 - EMPLOYMENT_STRONG_SIMILARITY,
        "source_category": source["trade_category_id"],
    }

    cur.execute(f"select count(*) from store_listings where {base_where}", base_params)
    total = cur.fetchone()[0]

    cur.execute(
        f"select count(*) from store_listings where {base_where} and ({geo_clause})",
        base_params,
    )
    after_geo = cur.fetchone()[0]

    cur.execute(
        f"select count(*) from store_listings where {base_where} and ({geo_clause}) "
        f"and (embedding <=> %(vec)s) <= %(max_distance_floor)s",
        vec_params,
    )
    after_floor = cur.fetchone()[0]

    after_strong = None
    if strong_gate:
        cur.execute(
            f"select count(*) from store_listings where {base_where} and ({geo_clause}) "
            f"and (embedding <=> %(vec)s) <= %(max_distance_floor)s "
            f"and (trade_category_id = %(source_category)s "
            f"     or (embedding <=> %(vec)s) <= %(max_distance_strong)s)",
            vec_params,
        )
        after_strong = cur.fetchone()[0]

    return {"total": total, "after_geo": after_geo, "after_floor": after_floor,
            "after_strong": after_strong}


def _reason_for(funnel: dict, *, none_exist_en, none_exist_ur,
                 too_far_en, too_far_ur, no_close_match_en, no_close_match_ur,
                 wrong_trade_en=None, wrong_trade_ur=None) -> dict:
    """Picks the template for whichever stage's count first hit zero."""
    if funnel["total"] == 0:
        return {"reason_en": none_exist_en, "reason_ur": none_exist_ur}
    if funnel["after_geo"] == 0:
        return {
            "reason_en": too_far_en.format(n=funnel["total"]),
            "reason_ur": too_far_ur.format(n=funnel["total"]),
        }
    if funnel["after_floor"] == 0:
        return {"reason_en": no_close_match_en, "reason_ur": no_close_match_ur}
    if funnel["after_strong"] == 0:
        return {
            "reason_en": wrong_trade_en.format(n=funnel["after_floor"]),
            "reason_ur": wrong_trade_ur.format(n=funnel["after_floor"]),
        }
    return None  # some stage always empties out if find_matches() returned nothing for this direction


def explain_no_matches(listing_id: str) -> list[dict]:
    """
    Returns one {"direction", "reason_en", "reason_ur"} dict per seeking
    flag this listing has active AND that find_matches() found nothing
    for. Empty list if the listing has no active seeking flags at all
    (shouldn't happen -- save_listing() requires at least one) or if,
    unexpectedly, every direction had a real reason to be non-empty
    (caller's job to only call this when find_matches() was empty).
    """
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    dict_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    source = _fetch_listing(dict_cur, listing_id)
    dict_cur.close()

    # A separate PLAIN cursor for the funnel's count(*) queries below --
    # RealDictCursor (used for _fetch_listing above, since matching.py's
    # _fetch_listing expects one) returns dict-like rows keyed by column
    # name, not position, so cur.fetchone()[0] would KeyError on an
    # unaliased `count(*)` result. _funnel() only ever reads a single
    # positional count, so a plain cursor is both correct and simpler here.
    cur = conn.cursor()

    explanations = []

    if source["seeking_inputs"]:
        funnel = _funnel(
            cur, source,
            base_where="active = true and availability in ('seeking', 'open_to_offers') "
                       "and role = 'supplier' and open_request_count < max_open_requests "
                       "and id <> %(source_id)s",
            base_params={"source_id": source["id"], "cluster": source["cluster_id"]},
            geo_clause="output_is_physical = false or cluster_id = %(cluster)s "
                       "or will_deliver_outside_area = true",
            strong_gate=False,
        )
        r = _reason_for(
            funnel,
            none_exist_en="No one on the marketplace is currently listed as a supplier for materials like this.",
            none_exist_ur="فی الحال مارکیٹ پلیس پر ایسا سامان فراہم کرنے والا کوئی دستیاب نہیں۔",
            too_far_en="{n} supplier(s) offer materials like this, but none are near you or willing to deliver outside their area yet.",
            too_far_ur="{n} فراہم کنندہ ایسا سامان رکھتے ہیں، لیکن کوئی بھی آپ کے قریب یا آپ کے علاقے میں ترسیل کے لیے تیار نہیں۔",
            no_close_match_en="Suppliers exist nearby, but what they offer doesn't closely match what you described.",
            no_close_match_ur="قریب فراہم کنندگان موجود ہیں، لیکن ان کا سامان آپ کی تفصیل سے میل نہیں کھاتا۔",
        )
        if r:
            explanations.append({"direction": "supply_chain_needs_materials", **r})

    if source["role"] == "supplier":
        funnel = _funnel(
            cur, source,
            base_where="active = true and availability in ('seeking', 'open_to_offers') "
                       "and seeking_inputs = true and open_request_count < max_open_requests "
                       "and id <> %(source_id)s",
            base_params={
                "source_id": source["id"], "cluster": source["cluster_id"],
                "source_output_physical": source["output_is_physical"],
                "source_will_deliver": source.get("will_deliver_outside_area", False),
            },
            geo_clause="%(source_output_physical)s = false or cluster_id = %(cluster)s "
                       "or %(source_will_deliver)s = true",
            strong_gate=False,
        )
        r = _reason_for(
            funnel,
            none_exist_en="No one on the marketplace is currently looking for materials like what you supply.",
            none_exist_ur="فی الحال کوئی بھی آپ جیسے سامان کی تلاش میں نہیں ہے۔",
            too_far_en="{n} business(es) need materials like yours, but none are near you or reachable given your delivery range yet.",
            too_far_ur="{n} کاروبار آپ جیسے سامان کی ضرورت رکھتے ہیں، لیکن کوئی بھی آپ کے قریب یا ترسیل کی حد میں نہیں۔",
            no_close_match_en="Businesses needing materials exist nearby, but none closely match what you supply.",
            no_close_match_ur="قریب کاروبار سامان کی ضرورت رکھتے ہیں، لیکن وہ آپ کے سامان سے میل نہیں کھاتے۔",
        )
        if r:
            explanations.append({"direction": "supply_chain_is_supplier", **r})

    if source["seeking_workers"]:
        funnel = _funnel(
            cur, source,
            base_where="active = true and seeking_work = true and availability = 'seeking' "
                       "and open_request_count < max_open_requests and id <> %(source_id)s",
            base_params={"source_id": source["id"], "cluster": source["cluster_id"]},
            geo_clause="is_remote_capable = true or cluster_id = %(cluster)s "
                       "or will_relocate_for_work = true",
            strong_gate=True,
        )
        r = _reason_for(
            funnel,
            none_exist_en="No one on the marketplace is currently looking for work in this line of business.",
            none_exist_ur="فی الحال کوئی بھی اس شعبے میں کام کی تلاش میں نہیں ہے۔",
            too_far_en="{n} person/people are looking for work like this, but none are near you, remote-capable, or willing to relocate yet.",
            too_far_ur="{n} افراد ایسا کام تلاش کر رہے ہیں، لیکن کوئی بھی آپ کے قریب، دور سے کام کرنے کے قابل، یا منتقل ہونے کو تیار نہیں۔",
            no_close_match_en="People seeking work exist nearby, but what they described doesn't closely match what you need.",
            no_close_match_ur="قریب کام کے متلاشی افراد موجود ہیں، لیکن ان کی مہارت آپ کی ضرورت سے میل نہیں کھاتی۔",
            wrong_trade_en="{n} nearby candidate(s) exist, but none are in your exact trade category -- "
                           "we hold back cross-trade employment suggestions unless the match is very strong, "
                           "so as not to suggest a poor fit.",
            wrong_trade_ur="{n} قریبی امیدوار موجود ہیں، لیکن کوئی بھی آپ کے شعبے سے نہیں -- "
                           "ہم مختلف شعبوں کے درمیان ملازمت کی تجویز صرف مضبوط مطابقت پر دیتے ہیں تاکہ غلط تجویز نہ دی جائے۔",
        )
        if r:
            explanations.append({"direction": "employment_hiring", **r})

    if source["seeking_work"]:
        funnel = _funnel(
            cur, source,
            base_where="active = true and seeking_workers = true "
                       "and availability in ('seeking', 'open_to_offers') "
                       "and open_request_count < max_open_requests and id <> %(source_id)s",
            base_params={
                "source_id": source["id"], "cluster": source["cluster_id"],
                "source_remote": source["is_remote_capable"],
                "source_relocate": source.get("will_relocate_for_work", False),
            },
            geo_clause="%(source_remote)s = true or cluster_id = %(cluster)s "
                       "or %(source_relocate)s = true",
            strong_gate=True,
        )
        r = _reason_for(
            funnel,
            none_exist_en="No one on the marketplace is currently hiring in this line of business.",
            none_exist_ur="فی الحال اس شعبے میں کوئی بھی ملازم نہیں رکھ رہا۔",
            too_far_en="{n} business(es) are hiring for work like this, but none are near you, remote-friendly, or reachable if you relocate yet.",
            too_far_ur="{n} کاروبار ایسے کام کے لیے بھرتی کر رہے ہیں، لیکن کوئی بھی آپ کے قریب یا رسائی میں نہیں۔",
            no_close_match_en="Businesses hiring exist nearby, but what they need doesn't closely match your skills.",
            no_close_match_ur="قریب بھرتی کرنے والے کاروبار موجود ہیں، لیکن ان کی ضرورت آپ کی مہارت سے میل نہیں کھاتی۔",
            wrong_trade_en="{n} nearby opportunity/opportunities exist, but none are in your exact trade category -- "
                           "we hold back cross-trade employment suggestions unless the match is very strong, "
                           "so as not to suggest a poor fit.",
            wrong_trade_ur="{n} قریبی مواقع موجود ہیں، لیکن کوئی بھی آپ کے شعبے سے نہیں -- "
                           "ہم مختلف شعبوں کے درمیان ملازمت کی تجویز صرف مضبوط مطابقت پر دیتے ہیں تاکہ غلط تجویز نہ دی جائے۔",
        )
        if r:
            explanations.append({"direction": "employment_seeking_work", **r})

    if source["seeking_partner"]:
        funnel = _funnel(
            cur, source,
            base_where="active = true and seeking_partner = true "
                       "and availability in ('seeking', 'open_to_offers') "
                       "and open_request_count < max_open_requests and id <> %(source_id)s",
            base_params={"source_id": source["id"], "cluster": source["cluster_id"]},
            geo_clause="is_remote_capable = true or cluster_id = %(cluster)s "
                       "or will_partner_outside_district = true",
            strong_gate=False,
        )
        r = _reason_for(
            funnel,
            none_exist_en="No one on the marketplace is currently looking for a business partner.",
            none_exist_ur="فی الحال کوئی بھی کاروباری شراکت دار کی تلاش میں نہیں ہے۔",
            too_far_en="{n} business(es) are looking for a partner, but none are near you or open to partnering outside your district yet.",
            too_far_ur="{n} کاروبار شراکت دار تلاش کر رہے ہیں، لیکن کوئی بھی آپ کے قریب یا ضلع سے باہر شراکت کے لیے تیار نہیں۔",
            no_close_match_en="Businesses seeking a partner exist nearby, but none closely complement what you do.",
            no_close_match_ur="قریب شراکت دار تلاش کرنے والے کاروبار موجود ہیں، لیکن وہ آپ کے کام سے میل نہیں کھاتے۔",
        )
        if r:
            explanations.append({"direction": "joint_venture", **r})

    cur.close()
    conn.close()
    return explanations
