"""
get_impact_report() -- Marketplace_Spec.md section 11 ("what Al-Khidmat
gains"), schema reference query F verbatim. The only function in this
whole module aimed at staff/donors rather than a beneficiary -- worth
naming explicitly, since every other file here assumes "the caller is a
logged-in beneficiary."
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def get_impact_report() -> dict:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    cur.execute(
        """
        select
          (select count(*) from marketplace_matches where status = 'connected')
            as connections_made,
          (select count(*) from venture_lineage) as ventures_formed,
          (select count(*) from listing_participants where role = 'employee')
            as jobs_created,
          (select count(*) from graduation_events where event_type = 'became_donor')
            as beneficiaries_now_donors,
          (select count(*) from store_listings where is_women_led and active)
            as women_led_businesses
        """
    )
    columns = [d[0] for d in cur.description]
    row = dict(zip(columns, cur.fetchone()))
    cur.close()
    conn.close()
    return row
