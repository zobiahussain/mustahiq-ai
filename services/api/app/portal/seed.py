"""Synthetic, idempotent seed, restricted to the isolated SQLite demo."""
from datetime import date, timedelta
from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import select
from app.core.config import settings
from app.core.db import engine, SessionLocal
from eligibility.prioritization import DEFAULT_WEIGHTS
from . import tables as t
from . import service as s


def demo_id(name):
    return str(uuid5(NAMESPACE_URL, 'mustahiq-staff-demo/' + name))


def seed_demo():
    if not settings.portal_demo_mode or engine.dialect.name != 'sqlite':
        raise RuntimeError('Synthetic seed is restricted to the explicitly enabled SQLite demo.')
    t.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.execute(select(t.staff_users.c.id)).first():
            return
        specs = [
            ('Education Support', 'education', 'school_age_children', '>=', 1, 'At least one school-age child', 150000, 6),
            ('Medical Assistance', 'health_services', 'chronic_illness_flag', '==', True, 'Chronic illness reported', 200000, 8),
            ('Orphan Family Support', 'orphan_care', 'is_orphan', '==', True, 'Orphan status confirmed', 100000, 5),
            ('Bano Qabil Skills Training', 'bano_qabil', 'age', '>=', 16, 'Age 16 or older', None, 20),
            ('Mawakhat Business Loan', 'islamic_microfinance', 'age', '>=', 18, 'Applicant is an adult', 300000, 3),
            ('Emergency Relief', 'disaster_management', 'district', 'in', ['Multan', 'Sukkur'], 'Resident of a demo relief district', 250000, 10),
            ('Clean Water Access', 'wash', 'district', 'in', ['Multan', 'Sukkur', 'Lahore'], 'Resident of a supported demo district', None, 25),
        ]
        for name, domain, field, operator, value, description, budget, capacity in specs:
            db.execute(t.departments.insert().values(id=demo_id(domain), name=domain.replace('_', ' ').title(), domain=domain, created_at=s.now()))
            rules = [{'rule_id': 'income', 'field': 'monthly_income', 'operator': '<=', 'value': 35000, 'description': 'Household income at or below PKR 35,000'},
                     {'rule_id': 'requirement', 'field': field, 'operator': operator, 'value': value, 'description': description}]
            db.execute(t.programs.insert().values(id=demo_id(name), name=name, department_id=demo_id(domain), domain=domain,
                description='Synthetic hackathon program. Criteria and budgets are examples, not official Al-Khidmat policy.',
                criteria_structured={'hard_rules': rules}, priority_weights=DEFAULT_WEIGHTS, requires_explicit_application=domain == 'islamic_microfinance',
                active=True, has_document_criteria=True, budget_per_cycle=budget, capacity_per_cycle=capacity,
                cycle_frequency_days=14, verification_valid_days=90, created_at=s.now(), updated_at=s.now()))
            s.insert(db, t.criteria, program_id=demo_id(name), chunk_index=0, created_at=s.now(),
                chunk_text=f'SYNTHETIC DEMO POLICY — {name}. Household income must be at or below PKR 35,000. {description}. Documents required: CNIC or B-form, household income statement, and program-specific supporting records. Staff must verify actual need and confirm similar assistance has not already been received. Verification remains valid for 90 days. No automatic enrollment. These are fictional criteria for the hackathon.')
        staff_id = demo_id('staff')
        db.execute(t.staff_users.insert().values(id=staff_id, full_name='Ayesha Khan', email='demo@mustahiq.local', role='super_admin', active=True, department_id=demo_id('education'), created_at=s.now()))
        names = ['Fatima Bibi', 'Muhammad Aslam', 'Rukhsana Begum', 'Ali Hassan', 'Sadia Parveen', 'Abdul Rehman', 'Zainab Khalid', 'Usman Tariq', 'Nusrat Bibi', 'Hamza Ahmed', 'Amina Yousaf', 'Bilal Akhtar', 'Farzana Iqbal', 'Hassan Raza', 'Maryam Asif', 'Muhammad Aslam']
        for i, name in enumerate(names):
            profile = dict(id=demo_id('profile-' + str(i)), full_name=name, district=['Lahore', 'Multan', 'Sukkur'][i % 3],
                cnic=None, phone=None, household_size=4 + i % 5, dependents=2 + i % 4, school_age_children=1 + i % 3,
                monthly_income=10000 + i * 1300, marital_status='widowed' if i % 4 == 0 else 'married',
                employment_status='daily_wage', owns_home=False, education_level='primary', has_disability=i % 5 == 0,
                chronic_illness_flag=i % 3 == 0, is_orphan=i % 7 == 0, date_of_birth=date(1984 + i, 3, 12),
                prior_assistance_count=i % 3, domain_attributes={}, staff_notes='Synthetic local demo case. No real beneficiary data.',
                completeness_score=86, consent_given=True, created_by_staff_id=staff_id, created_at=s.now() - timedelta(days=16-i), updated_at=s.now())
            db.execute(t.profiles.insert().values(**profile))
            s.discover(db, profile)
            s.detect_duplicates(db, profile)
        education_id = demo_id('Education Support')
        for i in range(8):
            profile = s.get(db, t.profiles, demo_id('profile-' + str(i)))
            match = s.pair(db, t.matches, profile['id'], education_id)
            s.update(db, t.matches, match['id'], status='pooled', reviewed_at=s.now(), reviewed_by_staff_id=staff_id)
            s.insert(db, t.pool, beneficiary_id=profile['id'], program_id=education_id, match_record_id=match['id'],
                     added_at=s.now(), added_by_staff_id=staff_id, outreach_status='verified' if i < 4 else 'awaiting_outreach')
            if i < 4:
                verification = s.insert(db, t.verifications, beneficiary_id=profile['id'], program_id=education_id, conducted_by_staff_id=staff_id,
                    conducted_at=s.now(), created_at=s.now(), outcome='verified', need_confirmed=True, assistance_elsewhere=False,
                    urgency_level='high', verified_income=profile['monthly_income'], verified_household_size=profile['household_size'],
                    valid_until=date.today() + timedelta(days=90), notes='Synthetic verification for the demo.',
                    program_specific_data={k: profile[k] for k in ['dependents', 'school_age_children', 'has_disability', 'chronic_illness_flag', 'prior_assistance_count']})
                s.insert(db, t.applications, beneficiary_id=profile['id'], program_id=education_id, entry_path='direct' if i % 2 else 'ai_identified',
                    verification_id=verification['id'], status='active', cycles_waited=i, amount_requested=25000,
                    applied_at=s.now() - timedelta(days=10-i), created_by_staff_id=staff_id, updated_at=s.now())
        db.commit()
