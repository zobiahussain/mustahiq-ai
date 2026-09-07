import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.db import get_db
from app.portal.rubric import DEFAULT_WEIGHTS, FACTOR_DEFINITIONS
from . import tables as t
from . import service as s
from .auth import auth_request, current_staff, demo_token, require_admin, check_department
from .contracts import Login, Refresh, ProfileInput, ProgramInput, Review, ApplicationInput, VerificationInput, Approval, DocumentInput, AssistantInput, SupportChatInput

router = APIRouter(prefix='/portal', tags=['staff portal'])


@router.get('/config')
def config():
    return {'demo_mode': settings.portal_demo_mode, 'factor_definitions': FACTOR_DEFINITIONS, 'default_weights': DEFAULT_WEIGHTS}


@router.get('/support/programs')
def support_programs(db=Depends(get_db)):
    programs = [p for p in s.rows(db, t.programs) if p['active']]
    return {'programs': [{'id': str(p['id']), 'name': p['name'], 'domain': p['domain'], 'description': p['description'],
                          'requires_explicit_application': p['requires_explicit_application']} for p in programs]}


@router.post('/support/chat')
def support_chat(body: SupportChatInput, db=Depends(get_db)):
    from .assistant import answer_support_question
    programs = [p for p in s.rows(db, t.programs) if p['active']]
    program_ids = {str(p['id']) for p in programs}
    chunks = [c for c in s.rows(db, t.criteria) if str(c['program_id']) in program_ids]
    return answer_support_question(body.question, programs, chunks)


@router.post('/support/chat/stream')
def support_chat_stream(body: SupportChatInput, db=Depends(get_db)):
    from .assistant import build_support_chat, stream_qwen, support_llm_enabled
    programs = [p for p in s.rows(db, t.programs) if p['active']]
    program_ids = {str(p['id']) for p in programs}
    chunks = [c for c in s.rows(db, t.criteria) if str(c['program_id']) in program_ids]
    active_programs, sources, fallback, prompt = build_support_chat(body.question, programs, chunks)

    def events():
        yield json.dumps({'type': 'meta', 'mode': 'support_stream', 'sources': sources}) + '\n'
        if not prompt or not support_llm_enabled():
            yield json.dumps({'type': 'token', 'text': fallback}) + '\n'
            yield json.dumps({'type': 'done'}) + '\n'
            return
        try:
            for token in stream_qwen(prompt, active_programs):
                yield json.dumps({'type': 'token', 'text': token}) + '\n'
            yield json.dumps({'type': 'done'}) + '\n'
        except Exception:
            yield json.dumps({'type': 'token', 'text': 'The support assistant is taking too long to respond. Please try a shorter question, or ask about a specific Alkhidmat program.'}) + '\n'
            yield json.dumps({'type': 'done'}) + '\n'

    return StreamingResponse(events(), media_type='application/x-ndjson')


@router.post('/session')
def login(body: Login):
    if settings.portal_demo_mode:
        raise HTTPException(409, 'Use the clearly labeled demo entry on this local instance.')
    data = auth_request('token?grant_type=password', body=body.model_dump())
    return {key: data.get(key) for key in ['access_token', 'refresh_token', 'expires_in']}


@router.post('/session/refresh')
def refresh(body: Refresh):
    if settings.portal_demo_mode:
        raise HTTPException(401, 'Reopen the demo to start a new session.')
    data = auth_request('token?grant_type=refresh_token', body=body.model_dump())
    return {key: data.get(key) for key in ['access_token', 'refresh_token', 'expires_in']}


@router.post('/demo-session')
def demo_login(db=Depends(get_db)):
    if not settings.portal_demo_mode:
        raise HTTPException(404, 'Not found.')
    staff = next(r for r in s.rows(db, t.staff_users) if r['role'] == 'super_admin')
    return {'access_token': demo_token(staff['id']), 'expires_in': 28800}


@router.get('/me')
def me(staff=Depends(current_staff)):
    return staff


@router.get('/workspace')
def workspace(db=Depends(get_db), staff=Depends(current_staff)):
    """One coherent snapshot for a hackathon-sized casework workspace."""
    programs = [p for p in s.rows(db, t.programs) if staff['role'] == 'super_admin' or str(p['department_id']) == str(staff['department_id'])]
    program_ids = {str(p['id']) for p in programs}
    matching = [r for r in s.rows(db, t.matches) if str(r['program_id']) in program_ids]
    applications = [r for r in s.rows(db, t.applications) if str(r['program_id']) in program_ids]
    pool = [r for r in s.rows(db, t.pool) if str(r['program_id']) in program_ids]
    assigned = {str(r['beneficiary_id']) for r in matching + applications + pool}
    staff_ids = {str(r['id']) for r in s.rows(db, t.staff_users) if str(r['department_id']) == str(staff['department_id'])}
    profiles = [r for r in s.rows(db, t.profiles) if staff['role'] == 'super_admin' or str(r['id']) in assigned or str(r['created_by_staff_id']) in staff_ids or str(r['created_by_staff_id']) == str(staff['id'])]
    profile_ids = {str(p['id']) for p in profiles}
    cycles = [r for r in s.rows(db, t.cycles) if str(r['program_id']) in program_ids]
    cycle_ids = {str(c['id']) for c in cycles}
    return {'staff': staff, 'demo_mode': settings.portal_demo_mode, 'profiles': profiles, 'programs': programs,
        'departments': [r for r in s.rows(db, t.departments) if staff['role'] == 'super_admin' or str(r['id']) == str(staff['department_id'])],
        'matches': matching, 'pool': pool, 'applications': applications, 'cycles': cycles,
        'cycle_candidates': [r for r in s.rows(db, t.cycle_candidates) if str(r['cycle_id']) in cycle_ids],
        'verifications': [r for r in s.rows(db, t.verifications) if str(r['program_id']) in program_ids],
        'duplicates': [r for r in s.rows(db, t.duplicates) if str(r['profile_a_id']) in profile_ids and str(r['profile_b_id']) in profile_ids],
        'criteria': [r for r in s.rows(db, t.criteria) if str(r['program_id']) in program_ids],
        'factor_definitions': FACTOR_DEFINITIONS}


@router.post('/profiles', status_code=201)
def create_profile(body: ProfileInput, db=Depends(get_db), staff=Depends(current_staff)):
    if body.cnic and db.execute(select(t.profiles.c.id).where(t.profiles.c.cnic == body.cnic)).first():
        raise HTTPException(409, 'A profile with this CNIC already exists. Find and update the existing record.')
    values = body.model_dump()
    values['completeness_score'] = round(sum(v is not None and v != '' for v in values.values()) / len(values) * 100)
    profile = s.insert(db, t.profiles, **values, created_by_staff_id=str(staff['id']), created_at=s.now(), updated_at=s.now())
    s.detect_duplicates(db, profile)
    discovery = s.discover(db, profile)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A profile with this CNIC already exists.')
    visible_programs = {str(p['id']) for p in s.rows(db, t.programs) if staff['role'] == 'super_admin' or str(p['department_id']) == str(staff['department_id'])}
    return {'profile': profile, 'discovery': [r for r in discovery if r['program_id'] in visible_programs]}


@router.put('/profiles/{profile_id}')
def edit_profile(profile_id: UUID, body: ProfileInput, db=Depends(get_db), staff=Depends(current_staff)):
    s.profile_for(db, staff, profile_id)
    if body.cnic and db.execute(select(t.profiles.c.id).where(t.profiles.c.cnic == body.cnic, t.profiles.c.id != str(profile_id))).first():
        raise HTTPException(409, 'A different profile already uses this CNIC.')
    profile = s.update(db, t.profiles, profile_id, **body.model_dump(), updated_at=s.now())
    s.detect_duplicates(db, profile)
    s.discover(db, profile)
    db.commit()
    return profile


@router.post('/profiles/{profile_id}/discover')
def discovery(profile_id: UUID, db=Depends(get_db), staff=Depends(current_staff)):
    profile = s.profile_for(db, staff, profile_id)
    programs = [p for p in s.rows(db, t.programs) if staff['role'] == 'super_admin' or str(p['department_id']) == str(staff['department_id'])]
    results = s.discover(db, profile, programs)
    db.commit()
    return results


@router.post('/matches/{match_id}/review')
def review_match(match_id: UUID, body: Review, db=Depends(get_db), staff=Depends(current_staff)):
    s.review_match(db, staff, match_id, body)
    db.commit()
    return {'reviewed': True}


@router.post('/applications', status_code=201)
def direct_application(body: ApplicationInput, db=Depends(get_db), staff=Depends(current_staff)):
    program = s.program_for(db, staff, body.program_id, True)
    s.profile_for(db, staff, body.beneficiary_id)
    if not program['active']:
        raise HTTPException(409, 'This program is inactive.')
    if s.pair(db, t.applications, body.beneficiary_id, body.program_id):
        raise HTTPException(409, 'An application already exists for this person and program.')
    record = s.insert(db, t.applications, beneficiary_id=str(body.beneficiary_id), program_id=str(body.program_id),
        entry_path='direct', status='active', amount_requested=body.amount_requested, cycles_waited=0, applied_at=s.now(), updated_at=s.now(), created_by_staff_id=str(staff['id']))
    db.commit()
    return record


@router.post('/verifications', status_code=201)
def verification(body: VerificationInput, db=Depends(get_db), staff=Depends(current_staff)):
    result = s.verify(db, staff, body)
    db.commit()
    return result


@router.post('/programs', status_code=201)
def create_program(body: ProgramInput, db=Depends(get_db), staff=Depends(current_staff)):
    require_admin(staff)
    check_department(staff, body.department_id)
    s.get(db, t.departments, body.department_id)
    values = body.model_dump(mode='json', exclude={'hard_rules'})
    values['criteria_structured'] = {'hard_rules': [r.model_dump(mode='json') for r in body.hard_rules]}
    program = s.insert(db, t.programs, **values, created_at=s.now(), updated_at=s.now(), has_document_criteria=False)
    # Hackathon datasets are bounded; this explicit, transactional rescan avoids
    # pretending an untracked BackgroundTask is a durable job queue.
    for profile in s.rows(db, t.profiles):
        s.discover(db, profile, [program])
    db.commit()
    return program


@router.put('/programs/{program_id}')
def edit_program(program_id: UUID, body: ProgramInput, db=Depends(get_db), staff=Depends(current_staff)):
    require_admin(staff)
    current = s.program_for(db, staff, program_id, True)
    if db.execute(select(t.cycles.c.id).where(t.cycles.c.program_id == str(program_id), t.cycles.c.status != 'finalised')).first():
        raise HTTPException(409, 'Finalise the open ranking cycle before changing this program policy.')
    check_department(staff, body.department_id)
    s.get(db, t.departments, body.department_id)
    values = body.model_dump(mode='json', exclude={'hard_rules'})
    values['criteria_structured'] = {'hard_rules': [r.model_dump(mode='json') for r in body.hard_rules]}
    program = s.update(db, t.programs, program_id, **values, updated_at=s.now())
    expired_count = 0
    if s.canonical_policy(current) != s.canonical_policy(program):
        expired_count = s.expire_active_applications_for_policy_change(db, program_id)
    for profile in s.rows(db, t.profiles):
        s.discover(db, profile, [program])
    db.commit()
    return {**program, 'expired_applications': expired_count}


@router.post('/programs/{program_id}/cycles', status_code=201)
def rank(program_id: UUID, db=Depends(get_db), staff=Depends(current_staff)):
    require_admin(staff)
    record = s.run_cycle(db, staff, program_id)
    db.commit()
    return record


@router.post('/cycles/run-due')
def run_due_cycles(db=Depends(get_db), staff=Depends(current_staff)):
    """Trigger 8, on demand. Ranks every program whose bi-weekly cycle is due
    and leaves each at 'ranked' for review. The same job runs unattended via
    packages/workflows (Render cron); this endpoint is for the demo and for a
    super-admin who wants to run the batch now."""
    if staff['role'] != 'super_admin':
        raise HTTPException(403, 'Only a super administrator can run the scheduled ranking batch.')
    result = s.run_due_cycles(db, actor=staff)
    db.commit()
    return result


@router.post('/cycles/{cycle_id}/candidates/{candidate_id}')
def approve(cycle_id: UUID, candidate_id: UUID, body: Approval, db=Depends(get_db), staff=Depends(current_staff)):
    require_admin(staff)
    s.approve_candidate(db, staff, cycle_id, candidate_id, body)
    db.commit()
    return {'updated': True}


@router.post('/cycles/{cycle_id}/finalise')
def finalise(cycle_id: UUID, db=Depends(get_db), staff=Depends(current_staff)):
    require_admin(staff)
    result = s.finalise_cycle(db, staff, cycle_id)
    db.commit()
    return result


@router.post('/duplicates/{flag_id}')
def review_duplicate(flag_id: UUID, status: str = Query(pattern='^(confirmed|dismissed)$'), db=Depends(get_db), staff=Depends(current_staff)):
    flag = s.get(db, t.duplicates, flag_id, True)
    s.profile_for(db, staff, flag['profile_a_id'])
    s.profile_for(db, staff, flag['profile_b_id'])
    if flag['status'] != 'pending':
        raise HTTPException(409, 'This flag has already been reviewed.')
    result = s.update(db, t.duplicates, flag_id, status=status, reviewed_by_staff_id=str(staff['id']), reviewed_at=s.now())
    db.commit()
    return result


@router.post('/programs/{program_id}/criteria')
def add_criteria(program_id: UUID, body: DocumentInput, db=Depends(get_db), staff=Depends(current_staff)):
    require_admin(staff)
    s.program_for(db, staff, program_id)
    chunks = []
    # Paragraph-aware bounded chunks, preserving source text for exact citations.
    for offset in range(0, len(body.text), 1200):
        chunks.append(s.insert(db, t.criteria, program_id=str(program_id), chunk_text=body.text[offset:offset + 1200], chunk_index=offset // 1200, created_at=s.now()))
    if not settings.portal_demo_mode:
        try:
            from rag.criteria import index_passages
            index_passages(db, chunks)
        except Exception:
            db.rollback()
            raise HTTPException(503, 'Could not index the document. Check the shared embedding dependencies and model cache, then retry.')
    s.update(db, t.programs, program_id, has_document_criteria=True)
    db.commit()
    return {'chunks_added': len(chunks), 'message': 'Source passages saved. Eligibility rules are unchanged until an administrator edits and confirms them.'}


@router.post('/criteria/draft')
def draft_criteria(body: DocumentInput, staff=Depends(current_staff)):
    require_admin(staff)
    from .assistant import extract_rules
    return extract_rules(body.text)


@router.post('/assistant')
def assistant(body: AssistantInput, db=Depends(get_db), staff=Depends(current_staff)):
    from .assistant import answer_question
    program_ids = [str(p['id']) for p in s.rows(db, t.programs) if staff['role'] == 'super_admin' or str(p['department_id']) == str(staff['department_id'])]
    if body.program_id:
        s.program_for(db, staff, body.program_id)
        program_ids = [str(body.program_id)]
    if settings.portal_demo_mode:
        chunks = [c for c in s.rows(db, t.criteria) if str(c['program_id']) in program_ids]
    else:
        try:
            from rag.criteria import retrieve_passages
            chunks = retrieve_passages(db, body.question, program_ids)
        except Exception:
            raise HTTPException(503, 'Program-document retrieval is unavailable. Check the shared embedding dependencies and pgvector database.')
    return answer_question(body.question, chunks, s.rows(db, t.programs), semantic=not settings.portal_demo_mode)
