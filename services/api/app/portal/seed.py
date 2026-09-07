"""Comprehensive synthetic seed for the isolated SQLite demo.

Reuses packages/data/synthetic.py -- THE SAME generator the XGBoost
confidence model trains on (packages/eligibility/run_model_pipeline.py) --
so the demo actually varies:

  * 6 programmes with genuinely different hard rules (a district-gated
    disaster programme, a district-gated WASH programme, income+chronic
    health, income+school-child education, orphan+dependents, unemployed
    skills training), each with its own priority-weight profile, budget,
    and cycle capacity. Microfinance is deliberately NOT one of them --
    a loan is a debt, never "found eligible" for proactively; it lives
    entirely on the marketplace side (see PROGRAM_META);
  * ~85 beneficiaries with a real multivariate spread and realistic
    partial data (incomes 5k-90k, 5-25% missing fields), so discovery
    lands some people in three programmes, some in one, and some in none;
  * verified candidate pools across SEVERAL programmes, deep enough that
    running a ranking cycle produces a visibly differentiated list and
    the budget/capacity actually forces staff to cut people;
  * a mix of entry_path (direct applicants + AI-identified) and
    cycles_waited, so the rubric's factors move;
  * three deliberate near-duplicate profile pairs for the duplicate queue.

Nothing here is real Al-Khidmat data or policy. SQLite-demo only -- the
guard in seed_demo() refuses to run against anything else.
"""
import random
from datetime import date, timedelta
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.portal.rubric import DEFAULT_WEIGHTS, validate_weights
from data.synthetic import build_synthetic_programs, generate_synthetic_profiles
from eligibility.evaluator import evaluate_rules
from eligibility.models import BeneficiaryProfile

from . import service as s
from . import tables as t


def demo_id(name):
    return str(uuid5(NAMESPACE_URL, 'mustahiq-staff-demo/' + name))


def _passes(profile_row, rules):
    """True if a stored profile row passes every hard rule of a programme.
    Coerces through JSON the same way service.discover() does -- the model
    is strict (UUID / Decimal), a DB row is str / float."""
    import json

    from fastapi.encoders import jsonable_encoder
    payload = {k: v for k, v in profile_row.items() if k in BeneficiaryProfile.model_fields}
    profile = BeneficiaryProfile.model_validate_json(json.dumps(jsonable_encoder(payload)))
    return evaluate_rules(profile, rules).status == 'pass'


# Per-domain demo metadata the generator doesn't carry: a display name, a
# priority-weight profile that reflects what each programme actually cares
# about, and a budget/capacity pair tight enough that allocation bites.
PROGRAM_META = {
    'disaster_management': dict(
        name='Emergency Relief (Kasur)', budget=280_000, capacity=6, valid_days=45,
        weights={'income_inverse': .20, 'dependents': .15, 'disability': .15, 'urgency': .35, 'no_prior_assistance': .15}),
    'health_services': dict(
        name='Medical Assistance', budget=450_000, capacity=6, valid_days=90,
        weights={'income_inverse': .20, 'chronic_illness': .25, 'disability': .20, 'urgency': .20, 'dependents': .15}),
    'education': dict(
        name='Education Support', budget=200_000, capacity=10, valid_days=120,
        weights={'income_inverse': .30, 'school_age_children': .25, 'dependents': .20, 'no_prior_assistance': .25}),
    'wash': dict(
        name='Clean Water Access (Tharparkar)', budget=None, capacity=20, valid_days=180,
        weights=DEFAULT_WEIGHTS),
    'orphan_care': dict(
        name='Orphan Family Support', budget=160_000, capacity=5, valid_days=90,
        weights={'income_inverse': .25, 'dependents': .30, 'disability': .15, 'school_age_children': .15, 'no_prior_assistance': .15}),
    'bano_qabil': dict(
        name='Bano Qabil Skills Training', budget=None, capacity=25, valid_days=60,
        weights={'income_inverse': .35, 'dependents': .20, 'no_prior_assistance': .25, 'school_age_children': .20}),
    # islamic_microfinance is deliberately NOT here. A loan is a debt --
    # nobody is "found eligible" for it proactively (SRS 5.3 / CLAUDE.md).
    # It lives entirely on the marketplace side as the sign-up gate
    # (microfinance_loans + the eligibility check in packages/marketplace),
    # never as a discoverable eligibility-side programme. The generator
    # still trains the XGBoost model with it as a domain; the seed just
    # never creates a programme row for it, so discovery never scores it.
}

NAMES = [
    'Fatima Bibi', 'Muhammad Aslam', 'Rukhsana Begum', 'Ali Hassan', 'Sadia Parveen',
    'Abdul Rehman', 'Zainab Khalid', 'Usman Tariq', 'Nusrat Bibi', 'Hamza Ahmed',
    'Amina Yousaf', 'Bilal Akhtar', 'Farzana Iqbal', 'Hassan Raza', 'Maryam Asif',
    'Imran Shah', 'Kulsoom Bano', 'Naveed Anjum', 'Shabana Kausar', 'Tariq Mehmood',
    'Robina Yasmin', 'Adeel Sarwar', 'Saima Noreen', 'Kashif Latif', 'Nasreen Akhtar',
    'Waqar Younis', 'Shazia Parveen', 'Faisal Nadeem', 'Uzma Hameed', 'Rashid Minhas',
    'Yasmeen Bibi', 'Zubair Ali', 'Naila Rani', 'Danish Kamboh', 'Iqra Saleem',
    'Sabir Hussain', 'Rehana Kausar', 'Aftab Gul', 'Mehnaz Begum', 'Junaid Iqbal',
    'Parveen Akhtar', 'Shahid Mahmood', 'Bushra Naz', 'Owais Qadri', 'Tehmina Gilani',
    'Arshad Bhatti', 'Ghulam Fatima', 'Nadeem Abbas', 'Kausar Perveen', 'Sohail Ahmad',
    'Rani Bibi', 'Asif Raza', 'Musarrat Jahan', 'Zahid Hussain', 'Firdous Begum',
    'Kamran Sheikh', 'Naseem Akhtar', 'Rizwan Haider', 'Shamim Ara', 'Ghazala Yasmin',
    'Muneer Ahmed', 'Talat Mahmood', 'Nighat Sultana', 'Pervez Iqbal', 'Rukhsar Bano',
    'Shakeel Anjum', 'Tahira Kausar', 'Ejaz Ahmad', 'Samina Riaz', 'Waseem Abbas',
    'Farida Begum', 'Nasir Mehmood', 'Hina Pervaiz', 'Qamar Zaman', 'Lubna Aslam',
    'Riffat Naheed', 'Salman Ghani', 'Ambreen Fatima', 'Tanveer Hussain', 'Shaista Perveen',
    'Abrar Ahmed', 'Rubina Kausar', 'Mansoor Ali', 'Nazia Bibi', 'Irfan Ullah',
]

DISTRICT_CLUSTER = {
    'Kasur': 'KSR-01', 'Tharparkar': 'THR-01', 'Lahore': 'LHR-01', 'Multan': 'MUL-01',
    'Sukkur': 'SKR-01', 'Faisalabad': 'FSD-01', 'Rawalpindi': 'RWP-01', 'Peshawar': 'PSH-01',
    'Karachi': 'KHI-01', 'Quetta': 'QTA-01', 'Islamabad': 'ISB-01',
}


def _criteria_chunks(prog, meta):
    """One retrievable passage per rule + one overview -- gives the staff
    assistant and the public support chatbot something real to cite."""
    yield (0, f'SYNTHETIC DEMO POLICY — {meta["name"]}. Fictional hackathon criteria, not official '
              f'Al-Khidmat policy. Documents required: CNIC or B-form, a household income statement, '
              f'and programme-specific supporting records. Staff must verify actual need and confirm '
              f'the household has not already received similar assistance. No automatic enrollment. '
              f'Verification stays valid for {meta["valid_days"]} days.')
    for i, rule in enumerate(prog.rules, start=1):
        yield (i, f'{meta["name"]} eligibility rule: {rule.description}. '
                  f'(field {rule.field} {rule.operator} {rule.value})')


def seed_demo():
    if not settings.portal_demo_mode or engine.dialect.name != 'sqlite':
        raise RuntimeError('Synthetic seed is restricted to the explicitly enabled SQLite demo.')
    t.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.execute(select(t.staff_users.c.id)).first():
            db.execute(t.staff_users.update().where(t.staff_users.c.email == 'demo@mustahiq.local').values(full_name='Rayan'))
            db.commit()
            return

        rng = random.Random(7)
        staff_id = demo_id('staff')
        officer_id = demo_id('officer')

        # ---- departments + programmes (rules from the shared generator,
        #      minus islamic_microfinance -- see PROGRAM_META) ----
        programs = [p for p in build_synthetic_programs() if p.domain != 'islamic_microfinance']
        program_ids = {}
        for prog in programs:
            meta = PROGRAM_META[prog.domain]
            # id conventions kept stable for test_staff_workflow.py:
            # department -> demo_id(<domain>), programme -> demo_id(<display name>)
            dept_id = demo_id(prog.domain)
            program_ids[prog.domain] = demo_id(meta['name'])
            db.execute(t.departments.insert().values(
                id=dept_id, name=prog.domain.replace('_', ' ').title(), domain=prog.domain, created_at=s.now()))
            db.execute(t.programs.insert().values(
                id=program_ids[prog.domain], name=meta['name'], department_id=dept_id, domain=prog.domain,
                description='Synthetic hackathon programme. Criteria, budgets and capacities are illustrative examples, not Al-Khidmat policy.',
                criteria_structured={'hard_rules': [r.model_dump(mode='json') for r in prog.rules]},
                priority_weights=validate_weights(dict(meta['weights'])),
                requires_explicit_application=False,  # none of the seeded 6 are explicit-only
                active=True, has_document_criteria=True,
                budget_per_cycle=meta['budget'], capacity_per_cycle=meta['capacity'],
                cycle_frequency_days=14, verification_valid_days=meta['valid_days'],
                created_at=s.now(), updated_at=s.now()))
            for idx, text in _criteria_chunks(prog, meta):
                s.insert(db, t.criteria, program_id=program_ids[prog.domain], chunk_index=idx,
                         chunk_text=text, created_at=s.now())

        db.execute(t.staff_users.insert().values(
            id=staff_id, full_name='Rayan', email='demo@mustahiq.local', role='super_admin',
            active=True, department_id=demo_id('education'), created_at=s.now()))
        db.execute(t.staff_users.insert().values(
            id=officer_id, full_name='Ayesha Malik', email='officer@mustahiq.local', role='field_officer',
            active=True, department_id=demo_id('health_services'), created_at=s.now()))

        # ---- beneficiaries (shared generator) -> discovery + dedup per row ----
        base = generate_synthetic_profiles(len(NAMES), seed=7)
        profile_ids = []
        for i, bp in enumerate(base):
            d = bp.model_dump()
            district = d['district'] if d['district'] in DISTRICT_CLUSTER else rng.choice(list(DISTRICT_CLUSTER))
            pid = demo_id('bene-' + str(i))
            profile_ids.append(pid)
            filled = sum(1 for v in d.values() if v is not None)
            row = dict(
                id=pid, full_name=NAMES[i],
                cnic=f'3520{rng.randint(1, 9)}-{rng.randint(1000000, 9999999)}-{rng.randint(1, 9)}',
                phone=f'+9230{rng.randint(10000000, 99999999)}',
                district=district, city=district, cluster_id=DISTRICT_CLUSTER[district],
                household_size=d['household_size'], dependents=d['dependents'],
                school_age_children=d['school_age_children'], marital_status=d['marital_status'],
                monthly_income=float(d['monthly_income']) if d['monthly_income'] is not None else None,
                employment_status=d['employment_status'], owns_home=d['owns_home'],
                education_level=d['education_level'], has_disability=d['has_disability'],
                chronic_illness_flag=d['chronic_illness_flag'], date_of_birth=d['date_of_birth'],
                is_orphan=d['is_orphan'], prior_assistance_count=d['prior_assistance_count'],
                domain_attributes={}, staff_notes='Synthetic local demo case. No real beneficiary data.',
                completeness_score=round(filled / len(d) * 100),
                consent_given=True, created_by_staff_id=staff_id,
                created_at=s.now() - timedelta(days=rng.randint(1, 45)), updated_at=s.now())
            db.execute(t.profiles.insert().values(**row))
            s.discover(db, row)            # trigger 1 -- real, against every active programme
            s.detect_duplicates(db, row)   # trigger 2

        # ---- three deliberate near-duplicates for the review queue ----
        for j in range(3):
            src = s.get(db, t.profiles, profile_ids[j * 5])
            dup = dict(src)
            dup['id'] = demo_id('dup-' + str(j))
            dup['full_name'] = src['full_name'].replace('Muhammad', 'Muhamad').replace(' Bibi', ' Bi bi') or src['full_name'] + ' .'
            if dup['full_name'] == src['full_name']:
                dup['full_name'] = src['full_name'] + '.'
            dup['cnic'] = None
            dup['created_at'] = s.now() - timedelta(days=rng.randint(1, 10))
            db.execute(t.profiles.insert().values(**dup))
            s.detect_duplicates(db, dup)

        def make_verification(prof, pid, domain, outcome, elsewhere=False):
            stated = prof['monthly_income'] or rng.randint(12_000, 40_000)
            return s.insert(
                db, t.verifications, beneficiary_id=str(prof['id']), program_id=pid,
                conducted_by_staff_id=officer_id, conducted_at=s.now(), created_at=s.now(),
                outcome=outcome, need_confirmed=outcome == 'verified', assistance_elsewhere=elsewhere,
                assistance_details='Received a one-off ration pack last quarter.' if elsewhere else None,
                urgency_level=rng.choices(['low', 'medium', 'high', 'critical'], weights=[2, 4, 3, 1])[0],
                verified_income=round(float(stated) * rng.uniform(0.85, 1.12), -2),
                verified_household_size=prof['household_size'] or rng.randint(3, 8),
                valid_until=date.today() + timedelta(days=PROGRAM_META[domain]['valid_days']),
                notes='Synthetic verification for the demo.',
                program_specific_data={key: prof[key] for key in
                                       ('dependents', 'school_age_children', 'has_disability',
                                        'chronic_illness_flag', 'prior_assistance_count')})

        def make_application(prof, pid, verification_id, entry_path):
            s.insert(db, t.applications, beneficiary_id=str(prof['id']), program_id=pid,
                     entry_path=entry_path, verification_id=verification_id, status='active',
                     cycles_waited=rng.randint(0, 3),
                     amount_requested=rng.choice([15_000, 20_000, 25_000, 30_000, 40_000]),
                     applied_at=s.now() - timedelta(days=rng.randint(2, 20)),
                     created_by_staff_id=staff_id, updated_at=s.now())

        # ---- AI-identified path: pool a SLICE of each programme's pending
        #      suggestions (the rest stay in the Discovery review queue),
        #      then verify most and open applications for the verified ----
        for domain, pid in program_ids.items():
            pending = [m for m in s.rows(db, t.matches)
                       if str(m['program_id']) == pid and m['status'] == 'pending_review']
            rng.shuffle(pending)
            take = round(len(pending) * rng.uniform(0.45, 0.65))  # leave a real review backlog
            for k, m in enumerate(pending[:take]):
                s.update(db, t.matches, m['id'], status='pooled',
                         reviewed_at=s.now(), reviewed_by_staff_id=staff_id)
                outreach = rng.choices(['verified', 'in_verification', 'awaiting_outreach'], weights=[6, 2, 2])[0]
                s.insert(db, t.pool, beneficiary_id=str(m['beneficiary_id']), program_id=pid,
                         match_record_id=str(m['id']), added_at=s.now(),
                         added_by_staff_id=staff_id, outreach_status=outreach)
                if outreach != 'verified':
                    continue
                prof = s.get(db, t.profiles, m['beneficiary_id'])
                outcome = 'no_actual_need' if rng.random() < 0.16 else 'verified'   # honest fails happen
                ver = make_verification(prof, pid, domain, outcome, elsewhere=rng.random() < 0.12)
                if outcome == 'verified':
                    make_application(prof, pid, str(ver['id']),
                                     entry_path='direct' if k % 4 == 0 else 'ai_identified')

        # ---- direct-application path: people who walked into a facilitation
        #      centre and applied for a specific programme themselves. They
        #      are ranked identically to AI-identified candidates (SRS 7.4);
        #      entry_path is recorded for audit only. Pick a few per
        #      programme who pass its hard rules but were NOT AI-suggested. ----
        rules_by_domain = {p.domain: p.rules for p in programs}
        for domain, pid in program_ids.items():
            already = {str(a['beneficiary_id']) for a in s.rows(db, t.applications)
                       if str(a['program_id']) == pid}
            walk_ins = [p for p in (s.get(db, t.profiles, i) for i in profile_ids)
                        if str(p['id']) not in already and _passes(p, rules_by_domain[domain])]
            for prof in walk_ins[:rng.randint(1, 3)]:
                ver = make_verification(prof, pid, domain, 'verified')
                make_application(prof, pid, str(ver['id']), entry_path='direct')

        db.commit()
