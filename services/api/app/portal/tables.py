"""Core-table mappings. create_all is used ONLY for the isolated SQLite demo.

Production uses the team's Supabase schema plus numbered migrations. Deliberately
no marketplace tables or automatic production schema changes here.
"""
from sqlalchemy import Boolean, Column as C, Date, DateTime, Float, Integer, JSON, MetaData, String, Table, Text

metadata = MetaData()


def table(name, *columns):
    return Table(name, metadata, C('id', String, primary_key=True), *columns)


departments = table('departments', C('name', Text), C('domain', Text), C('created_at', DateTime(timezone=True)))
staff_users = table('staff_users', C('full_name', Text), C('email', Text), C('role', Text), C('department_id', String), C('auth_user_id', String), C('active', Boolean), C('created_at', DateTime(timezone=True)))
profiles = table('beneficiary_profiles',
    C('full_name', Text), C('cnic', Text, unique=True), C('phone', Text), C('district', Text), C('city', Text), C('cluster_id', Text),
    C('household_size', Integer), C('dependents', Integer), C('school_age_children', Integer), C('monthly_income', Float),
    C('marital_status', Text), C('employment_status', Text), C('owns_home', Boolean), C('education_level', Text),
    C('has_disability', Boolean), C('chronic_illness_flag', Boolean), C('date_of_birth', Date), C('is_orphan', Boolean),
    C('prior_assistance_count', Integer), C('domain_attributes', JSON), C('staff_notes', Text), C('completeness_score', Float),
    C('consent_given', Boolean), C('created_by_staff_id', String), C('created_at', DateTime(timezone=True)), C('updated_at', DateTime(timezone=True)))
programs = table('programs', C('department_id', String), C('name', Text), C('domain', Text), C('description', Text),
    C('criteria_structured', JSON), C('priority_weights', JSON), C('requires_explicit_application', Boolean), C('has_document_criteria', Boolean),
    C('budget_per_cycle', Float), C('capacity_per_cycle', Integer), C('cycle_frequency_days', Integer), C('verification_valid_days', Integer),
    C('active', Boolean), C('created_at', DateTime(timezone=True)), C('updated_at', DateTime(timezone=True)))
matches = table('match_records', C('beneficiary_id', String), C('program_id', String), C('score', Float), C('reason', Text),
    C('source_chunk_id', String), C('status', Text), C('reviewed_by_staff_id', String), C('reviewed_at', DateTime(timezone=True)), C('staff_notes', Text), C('created_at', DateTime(timezone=True)))
pool = table('potentially_eligible_pool', C('beneficiary_id', String), C('program_id', String), C('match_record_id', String),
    C('added_at', DateTime(timezone=True)), C('added_by_staff_id', String), C('outreach_status', Text))
verifications = table('verifications', C('beneficiary_id', String), C('program_id', String), C('conducted_by_staff_id', String),
    C('conducted_at', DateTime(timezone=True)), C('outcome', Text), C('need_confirmed', Boolean), C('urgency_level', Text),
    C('assistance_elsewhere', Boolean), C('assistance_details', Text), C('verified_income', Float), C('verified_household_size', Integer),
    C('program_specific_data', JSON), C('notes', Text), C('valid_until', Date), C('created_at', DateTime(timezone=True)))
applications = table('applications', C('beneficiary_id', String), C('program_id', String), C('entry_path', Text), C('verification_id', String),
    C('status', Text), C('need_score', Float), C('score_breakdown', JSON), C('rank_in_cycle', Integer), C('cycles_waited', Integer),
    C('amount_requested', Float), C('amount_disbursed', Float), C('disbursed_at', DateTime(timezone=True)), C('applied_at', DateTime(timezone=True)),
    C('created_by_staff_id', String), C('updated_at', DateTime(timezone=True)))
cycles = table('ranking_cycles', C('program_id', String), C('run_at', DateTime(timezone=True)), C('pool_size', Integer),
    C('budget_available', Float), C('capacity_available', Integer), C('weights_snapshot', JSON), C('approved_count', Integer),
    C('disbursed_count', Integer), C('reviewed_by_staff_id', String), C('status', Text), C('created_at', DateTime(timezone=True)))
cycle_candidates = table('ranking_cycle_candidates', C('cycle_id', String), C('application_id', String), C('rank', Integer),
    C('need_score', Float), C('score_breakdown', JSON), C('status', Text), C('amount', Float), C('created_at', DateTime(timezone=True)))
duplicates = table('duplicate_flags', C('profile_a_id', String), C('profile_b_id', String), C('similarity_score', Float), C('matched_on', Text),
    C('status', Text), C('reviewed_by_staff_id', String), C('reviewed_at', DateTime(timezone=True)), C('created_at', DateTime(timezone=True)))
criteria = table('program_criteria', C('program_id', String), C('chunk_text', Text), C('chunk_index', Integer), C('created_at', DateTime(timezone=True)))
