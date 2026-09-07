"""Transactional staff workflow over the team's existing core tables."""
from datetime import date, datetime, timedelta, timezone
import json
from functools import lru_cache
from uuid import uuid4

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, select
from rapidfuzz import fuzz

from app.core.config import REPO_ROOT
from eligibility.discovery import DiscoveryProgram, discover_profile
from eligibility.models import BeneficiaryProfile
from eligibility.persistence import load_scorer
from eligibility.prioritization import score_need
from . import tables as t
from .auth import check_department


def now():
    return datetime.now(timezone.utc)


def rows(db, table):
    return [dict(r) for r in db.execute(select(table)).mappings()]


def get(db, table, record_id, lock=False):
    query = select(table).where(table.c.id == str(record_id))
    if lock:
        query = query.with_for_update()
    row = db.execute(query).mappings().first()
    if row is None:
        raise HTTPException(404, 'Record not found.')
    return dict(row)


def insert(db, table, **values):
    record_id = str(uuid4())
    db.execute(table.insert().values(id=record_id, **values))
    return get(db, table, record_id)


def update(db, table, record_id, **values):
    db.execute(table.update().where(table.c.id == str(record_id)).values(**values))
    return get(db, table, record_id)


def pair(db, table, beneficiary_id, program_id):
    row = db.execute(select(table).where(and_(table.c.beneficiary_id == str(beneficiary_id), table.c.program_id == str(program_id)))).mappings().first()
    return dict(row) if row else None


def canonical_policy(program):
    return json.dumps({
        'active': bool(program['active']),
        'hard_rules': (program['criteria_structured'] or {}).get('hard_rules', []),
        'priority_weights': program['priority_weights'] or {},
        'requires_explicit_application': bool(program['requires_explicit_application']),
        'verification_valid_days': program['verification_valid_days'],
    }, sort_keys=True, separators=(',', ':'))


def expire_active_applications_for_policy_change(db, program_id):
    expired = 0
    for app in rows(db, t.applications):
        if str(app['program_id']) != str(program_id) or app['status'] not in ('active', 'rolled_over'):
            continue
        update(db, t.applications, app['id'], status='expired', updated_at=now())
        outreach = pair(db, t.pool, app['beneficiary_id'], program_id)
        if outreach:
            update(db, t.pool, outreach['id'], outreach_status='awaiting_outreach')
        expired += 1
    return expired


def program_for(db, staff, program_id, lock=False):
    program = get(db, t.programs, program_id, lock)
    check_department(staff, program['department_id'])
    return program


def profile_for(db, staff, profile_id):
    profile = get(db, t.profiles, profile_id)
    if staff['role'] == 'super_admin' or str(profile['created_by_staff_id']) == str(staff['id']):
        return profile
    visible_programs = select(t.programs.c.id).where(t.programs.c.department_id == str(staff['department_id']))
    for table in [t.matches, t.pool, t.applications]:
        if db.execute(select(table.c.id).where(table.c.beneficiary_id == str(profile_id), table.c.program_id.in_(visible_programs))).first():
            return profile
    creator = db.execute(select(t.staff_users.c.department_id).where(t.staff_users.c.id == str(profile['created_by_staff_id']))).scalar()
    if creator is not None and str(creator) == str(staff['department_id']):
        return profile
    raise HTTPException(403, 'This profile is outside your department casework.')


@lru_cache(maxsize=1)
def scorer():
    return load_scorer(REPO_ROOT / 'artifacts' / 'eligibility-scorer')


def discover(db, profile, program_list=None):
    """No LLM in this path. Save suggestions without undoing staff review."""
    from pydantic import ValidationError
    available = program_list if program_list is not None else rows(db, t.programs)
    active = [p for p in available if p['active']]
    parsed = []
    errors = []
    for p in active:
        try:
            parsed.append(DiscoveryProgram.model_validate_json(__import__('json').dumps({
                'program_id': str(p['id']), 'name': p['name'], 'domain': p['domain'],
                'rules': (p['criteria_structured'] or {}).get('hard_rules', []),
                'requires_explicit_application': bool(p['requires_explicit_application']),
            })))
        except ValidationError:
            errors.append({'program_id': str(p['id']), 'program_name': p['name'], 'status': 'configuration_required', 'reason': 'Administrator must confirm valid structured rules.', 'score': None})
    payload = {key: value for key, value in profile.items() if key in BeneficiaryProfile.model_fields}
    beneficiary = BeneficiaryProfile.model_validate_json(__import__('json').dumps(jsonable_encoder(payload)))
    results = discover_profile(beneficiary, parsed, scorer()) if parsed else []
    names = {str(p['id']): p['name'] for p in active}
    output = []
    for result in results:
        data = result.model_dump()
        previous = pair(db, t.matches, profile['id'], result.program_id)
        if result.status in ('pending_review', 'suppressed'):
            if previous:
                status = result.status if result.status == 'suppressed' or previous['status'] == 'suppressed' else previous['status']
                update(db, t.matches, previous['id'], score=result.score, reason=result.reason, status=status)
            else:
                insert(db, t.matches, beneficiary_id=str(profile['id']), program_id=result.program_id,
                       score=result.score, reason=result.reason, status=result.status, created_at=now())
        elif previous:
            update(db, t.matches, previous['id'], status='dismissed', reason=result.reason)
            old_pool = pair(db, t.pool, profile['id'], result.program_id)
            if old_pool and old_pool['outreach_status'] in ('awaiting_outreach', 'in_verification'):
                update(db, t.pool, old_pool['id'], outreach_status='exited')
        output.append({**data, 'program_name': names[result.program_id]})
    return output + errors


def detect_duplicates(db, profile):
    for candidate in rows(db, t.profiles):
        if str(candidate['id']) == str(profile['id']):
            continue
        score = max(fuzz.token_sort_ratio(profile['full_name'], candidate['full_name']),
                    fuzz.ratio(profile['phone'], candidate['phone']) if profile.get('phone') and candidate.get('phone') else 0)
        if score < 85:
            continue
        existing = db.execute(select(t.duplicates.c.id).where(
            ((t.duplicates.c.profile_a_id == str(profile['id'])) & (t.duplicates.c.profile_b_id == str(candidate['id']))) |
            ((t.duplicates.c.profile_b_id == str(profile['id'])) & (t.duplicates.c.profile_a_id == str(candidate['id']))))).first()
        if not existing:
            insert(db, t.duplicates, profile_a_id=str(profile['id']), profile_b_id=str(candidate['id']),
                   similarity_score=score, matched_on='name_phone_fuzzy', status='pending', created_at=now())


def review_match(db, staff, match_id, body):
    match = get(db, t.matches, match_id, True)
    program = program_for(db, staff, match['program_id'])
    if match['status'] != 'pending_review':
        raise HTTPException(409, 'This suggestion has already been reviewed or is suppressed.')
    if body.action == 'pooled' and (program['requires_explicit_application'] or not program['active']):
        raise HTTPException(409, 'This program cannot be pooled for proactive outreach.')
    update(db, t.matches, match_id, status=body.action, staff_notes=body.notes, reviewed_by_staff_id=str(staff['id']), reviewed_at=now())
    if body.action == 'pooled':
        old = pair(db, t.pool, match['beneficiary_id'], match['program_id'])
        if not old:
            insert(db, t.pool, beneficiary_id=str(match['beneficiary_id']), program_id=str(match['program_id']), match_record_id=str(match_id),
                   added_at=now(), added_by_staff_id=str(staff['id']), outreach_status='awaiting_outreach')


def verify(db, staff, body):
    program = program_for(db, staff, body.program_id, True)
    profile = profile_for(db, staff, body.beneficiary_id)
    app = pair(db, t.applications, body.beneficiary_id, body.program_id)
    outreach = pair(db, t.pool, body.beneficiary_id, body.program_id)
    if not app and not outreach:
        raise HTTPException(409, 'Register a direct application or pool a suggestion before verification.')
    if app and app['status'] in ('ranked', 'approved', 'disbursed', 'withdrawn'):
        raise HTTPException(409, 'This application is already in a ranking cycle or has closed.')
    if not program['active']:
        raise HTTPException(409, 'This program is inactive.')
    if body.outcome == 'verified':
        from eligibility.evaluator import evaluate_rules
        from eligibility.models import ProgramRule
        import json
        candidate = {**profile, 'monthly_income': body.verified_income, 'household_size': body.verified_household_size}
        parsed = BeneficiaryProfile.model_validate_json(json.dumps(jsonable_encoder(candidate)))
        try:
            rules = [ProgramRule.model_validate_json(json.dumps(r)) for r in (program['criteria_structured'] or {}).get('hard_rules', [])]
        except ValueError:
            raise HTTPException(409, 'Program criteria need administrator confirmation.')
        if not rules or evaluate_rules(parsed, rules).status != 'pass':
            raise HTTPException(409, 'Verified figures do not pass all program rules. Update missing profile fields or record a non-eligible outcome.')
    record = insert(db, t.verifications, beneficiary_id=str(body.beneficiary_id), program_id=str(body.program_id),
        conducted_by_staff_id=str(staff['id']), conducted_at=now(), created_at=now(),
        **body.model_dump(exclude={'beneficiary_id', 'program_id', 'amount_requested'}),
        valid_until=date.today() + timedelta(days=program['verification_valid_days'] or 90) if body.outcome == 'verified' else None,
        program_specific_data={key: profile.get(key) for key in ['dependents', 'school_age_children', 'has_disability', 'chronic_illness_flag', 'prior_assistance_count']})
    if outreach:
        update(db, t.pool, outreach['id'], outreach_status='verified' if body.outcome == 'verified' else 'exited')
    if body.outcome == 'verified':
        values = dict(verification_id=record['id'], status='active', updated_at=now())
        if body.amount_requested is not None:
            values['amount_requested'] = body.amount_requested
        if app:
            update(db, t.applications, app['id'], **values)
        else:
            insert(db, t.applications, beneficiary_id=str(body.beneficiary_id), program_id=str(body.program_id), entry_path='ai_identified',
                cycles_waited=0, applied_at=now(), created_by_staff_id=str(staff['id']), **values)
        changed = update(db, t.profiles, body.beneficiary_id, monthly_income=body.verified_income,
                         household_size=body.verified_household_size, updated_at=now())
        discover(db, changed)
    elif app:
        update(db, t.applications, app['id'], status='withdrawn', verification_id=record['id'], updated_at=now())
    return record


def run_cycle(db, staff, program_id):
    program = program_for(db, staff, program_id, True)
    if not program['active']:
        raise HTTPException(409, 'This program is inactive.')
    if db.execute(select(t.cycles.c.id).where(t.cycles.c.program_id == str(program_id), t.cycles.c.status != 'finalised')).first():
        raise HTTPException(409, 'Finalise the open cycle before starting another.')
    scored, expired = [], 0
    for app in rows(db, t.applications):
        if str(app['program_id']) != str(program_id) or app['status'] not in ('active', 'rolled_over'):
            continue
        verification = get(db, t.verifications, app['verification_id']) if app['verification_id'] else None
        if not verification or verification['outcome'] != 'verified' or not verification['valid_until'] or verification['valid_until'] < date.today():
            update(db, t.applications, app['id'], status='expired', updated_at=now())
            outreach = pair(db, t.pool, app['beneficiary_id'], program_id)
            if outreach:
                update(db, t.pool, outreach['id'], outreach_status='awaiting_outreach')
            expired += 1
            continue
        facts = verification['program_specific_data'] or {}
        try:
            score, breakdown = score_need(verified_income=float(verification['verified_income']),
                dependents=facts.get('dependents'), has_disability=facts.get('has_disability'),
                prior_assistance_count=facts.get('prior_assistance_count'), school_age_children=facts.get('school_age_children'),
                urgency_level=verification['urgency_level'], chronic_illness_flag=facts.get('chronic_illness_flag'),
                cycles_waited=app['cycles_waited'] or 0, weights=program['priority_weights'] or {})
        except (ValueError, TypeError) as error:
            raise HTTPException(409, f"Re-verify candidate {app['id']} before ranking: {error}")
        scored.append((app, score, breakdown))
    # Equal need scores use application timestamp then ID, never arrival channel.
    scored.sort(key=lambda item: (-item[1], str(item[0]['applied_at']), str(item[0]['id'])))
    cycle = insert(db, t.cycles, program_id=str(program_id), run_at=now(), pool_size=len(scored),
        budget_available=program['budget_per_cycle'], capacity_available=program['capacity_per_cycle'],
        weights_snapshot={'weights': program['priority_weights'], 'normalization_version': 'demo-v1',
                          'tie_break': 'applied_at, application_id; entry_path excluded'},
        approved_count=0, disbursed_count=0, reviewed_by_staff_id=str(staff['id']), status='ranked', created_at=now())
    for rank, (app, score, breakdown) in enumerate(scored, 1):
        update(db, t.applications, app['id'], status='ranked', need_score=score, score_breakdown=breakdown, rank_in_cycle=rank, updated_at=now())
        insert(db, t.cycle_candidates, cycle_id=cycle['id'], application_id=str(app['id']), rank=rank,
            need_score=score, score_breakdown=breakdown, status='ranked', amount=app['amount_requested'], created_at=now())
    return {**cycle, 'expired_count': expired}


def approve_candidate(db, staff, cycle_id, candidate_id, body):
    cycle = get(db, t.cycles, cycle_id, True)
    program_for(db, staff, cycle['program_id'])
    if cycle['status'] == 'finalised':
        raise HTTPException(409, 'This cycle is already finalised.')
    candidate = get(db, t.cycle_candidates, candidate_id)
    if str(candidate['cycle_id']) != str(cycle_id):
        raise HTTPException(404, 'Candidate does not belong to this cycle.')
    app = get(db, t.applications, candidate['application_id'])
    verification = get(db, t.verifications, app['verification_id'])
    if body.approved and verification['valid_until'] < date.today():
        raise HTTPException(409, 'Verification expired. Finalise without approving this candidate, then re-verify.')
    if body.approved and cycle['budget_available'] is not None and body.amount is None:
        raise HTTPException(422, 'Enter an allocation amount for this budgeted program.')
    update(db, t.cycle_candidates, candidate_id, status='approved' if body.approved else 'ranked', amount=body.amount if body.approved else None)
    update(db, t.applications, app['id'], status='approved' if body.approved else 'ranked', updated_at=now())
    count = len([r for r in rows(db, t.cycle_candidates) if str(r['cycle_id']) == str(cycle_id) and r['status'] == 'approved'])
    update(db, t.cycles, cycle_id, status='under_review', approved_count=count, reviewed_by_staff_id=str(staff['id']))


def finalise_cycle(db, staff, cycle_id):
    cycle = get(db, t.cycles, cycle_id, True)
    program_for(db, staff, cycle['program_id'], True)
    if cycle['status'] == 'finalised':
        raise HTTPException(409, 'This cycle has already been finalised; no allocation was repeated.')
    candidates = sorted([r for r in rows(db, t.cycle_candidates) if str(r['cycle_id']) == str(cycle_id)], key=lambda r: r['rank'])
    approved = [r for r in candidates if r['status'] == 'approved']
    for c in approved:
        app = get(db, t.applications, c['application_id'])
        verification = get(db, t.verifications, app['verification_id'])
        if verification['valid_until'] < date.today():
            raise HTTPException(409, 'An approved verification has expired. Remove its approval before finalising.')
    total = sum(float(c['amount'] or 0) for c in approved)
    if cycle['budget_available'] is not None and total > float(cycle['budget_available']):
        raise HTTPException(409, 'Approved amounts exceed the cycle budget. Adjust approvals first.')
    if cycle['capacity_available'] is not None and len(approved) > cycle['capacity_available']:
        raise HTTPException(409, 'Approved candidates exceed the cycle capacity. Adjust approvals first.')
    for candidate in candidates:
        app = get(db, t.applications, candidate['application_id'])
        funded = candidate['status'] == 'approved'
        status = 'disbursed' if funded else 'rolled_over'
        update(db, t.cycle_candidates, candidate['id'], status=status)
        values = {'status': status, 'updated_at': now()}
        if funded:
            values.update(amount_disbursed=candidate['amount'], disbursed_at=now())
        else:
            values['cycles_waited'] = (app['cycles_waited'] or 0) + 1
        update(db, t.applications, app['id'], **values)
    return update(db, t.cycles, cycle_id, status='finalised', approved_count=len(approved), disbursed_count=len(approved), reviewed_by_staff_id=str(staff['id']))
