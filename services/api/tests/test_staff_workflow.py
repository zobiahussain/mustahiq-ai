"""Offline integration tests: isolated SQLite DB, real saved XGBoost scorer.

Never opens the shared Supabase database or calls any external AI provider.
"""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import date, timedelta
from uuid import uuid4

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'services' / 'api'))
sys.path.insert(0, str(REPO / 'packages'))
_tmp = tempfile.TemporaryDirectory(prefix='mustahiq-staff-test-')
os.environ['PORTAL_DEMO_MODE'] = 'true'
os.environ['STAFF_GENERATION_ENABLED'] = 'false'
os.environ['PORTAL_DEMO_DATABASE'] = str(Path(_tmp.name) / 'tests.sqlite3')

from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal, engine
from app.portal import tables as t
from app.portal.seed import seed_demo, demo_id
from app.portal.auth import demo_token
from eligibility.prioritization import score_need, DEFAULT_WEIGHTS, validate_weights


class StaffWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        seed_demo()
        cls.token = cls.client.post('/portal/demo-session').json()['access_token']
        cls.headers = {'Authorization': 'Bearer ' + cls.token}

    def setUp(self):
        t.metadata.drop_all(engine)
        seed_demo()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        engine.dispose()
        _tmp.cleanup()

    def call(self, method, path, body=None, expected=200, headers=None):
        r = self.client.request(method, '/portal' + path, json=body, headers=headers or self.headers)
        self.assertEqual(r.status_code, expected, r.text)
        return r.json()

    def workspace(self):
        return self.call('GET', '/workspace')

    def profile_body(self, **changes):
        return {'full_name': 'Test Candidate', 'district': 'Lahore', 'monthly_income': 15000,
                'household_size': 6, 'dependents': 4, 'school_age_children': 2,
                'has_disability': False, 'chronic_illness_flag': False, 'prior_assistance_count': 0,
                'consent_given': True, **changes}

    def verification(self, profile_id, program_id, **changes):
        return {'beneficiary_id': profile_id, 'program_id': program_id, 'outcome': 'verified',
                'need_confirmed': True, 'assistance_elsewhere': False, 'verified_income': 15000,
                'verified_household_size': 6, 'notes': 'Confirmed in household assessment.',
                'urgency_level': 'high', 'amount_requested': 20000, **changes}

    def test_anonymous_access_blocked_and_demo_explicit(self):
        self.assertEqual(self.client.get('/portal/workspace').status_code, 401)
        self.assertTrue(self.client.get('/portal/config').json()['demo_mode'])

    def test_registration_to_disbursement_and_repeat_protection(self):
        created = self.call('POST', '/profiles', self.profile_body(), expected=201)
        profile_id, program_id = created['profile']['id'], demo_id('Education Support')
        self.assertTrue(any(r['status'] == 'pending_review' for r in created['discovery']))
        state = self.workspace()
        match = next(m for m in state['matches'] if m['beneficiary_id'] == profile_id and m['program_id'] == program_id)
        self.call('POST', f"/matches/{match['id']}/review", {'action': 'pooled'})
        self.call('POST', f"/matches/{match['id']}/review", {'action': 'pooled'}, expected=409)
        self.call('POST', '/verifications', self.verification(profile_id, program_id), expected=201)
        cycle = self.call('POST', f'/programs/{program_id}/cycles', expected=201)
        self.call('POST', f'/programs/{program_id}/cycles', expected=409)
        state = self.workspace()
        application = next(a for a in state['applications'] if a['beneficiary_id'] == profile_id)
        candidate = next(c for c in state['cycle_candidates'] if c['application_id'] == application['id'])
        self.assertEqual(application['entry_path'], 'ai_identified')
        self.assertTrue(candidate['score_breakdown'])
        self.call('POST', f"/cycles/{cycle['id']}/candidates/{candidate['id']}", {'approved': True, 'amount': 20000})
        self.call('POST', f"/cycles/{cycle['id']}/finalise")
        self.call('POST', f"/cycles/{cycle['id']}/finalise", expected=409)
        after = self.workspace()
        self.assertEqual(next(a for a in after['applications'] if a['id'] == application['id'])['status'], 'disbursed')
        self.assertTrue(any(a['status'] == 'rolled_over' for a in after['applications']))

    def test_direct_application_requires_verification_and_rules(self):
        profile = self.call('POST', '/profiles', self.profile_body(), expected=201)['profile']
        pid = demo_id('Education Support')
        self.call('POST', '/applications', {'beneficiary_id': profile['id'], 'program_id': pid}, expected=201)
        self.call('POST', '/applications', {'beneficiary_id': profile['id'], 'program_id': pid}, expected=409)
        self.call('POST', '/verifications', self.verification(profile['id'], pid, need_confirmed=False), expected=422)
        self.call('POST', '/verifications', self.verification(profile['id'], pid, verified_income=99000), expected=409)
        self.call('POST', '/verifications', self.verification(profile['id'], pid), expected=201)
        self.assertEqual(next(a for a in self.workspace()['applications'] if a['beneficiary_id'] == profile['id'])['entry_path'], 'direct')

    def test_suppressed_microfinance_cannot_be_pooled(self):
        match = next(m for m in self.workspace()['matches'] if m['status'] == 'suppressed')
        self.call('POST', f"/matches/{match['id']}/review", {'action': 'pooled'}, expected=409)

    def test_budget_enforced_and_atomic(self):
        pid = demo_id('Education Support')
        cycle = self.call('POST', f'/programs/{pid}/cycles', expected=201)
        candidate = self.workspace()['cycle_candidates'][0]
        self.call('POST', f"/cycles/{cycle['id']}/candidates/{candidate['id']}", {'approved': True, 'amount': 999999})
        self.call('POST', f"/cycles/{cycle['id']}/finalise", expected=409)
        self.assertFalse(any(a['status'] == 'disbursed' for a in self.workspace()['applications']))

    def test_expired_verification_excluded(self):
        with SessionLocal() as db:
            db.execute(t.verifications.update().values(valid_until=date.today() - timedelta(days=1)))
            db.commit()
        result = self.call('POST', f"/programs/{demo_id('Education Support')}/cycles", expected=201)
        self.assertEqual(result['pool_size'], 0)
        self.assertEqual(result['expired_count'], 4)
        self.assertTrue(all(a['status'] == 'expired' for a in self.workspace()['applications']))

    def test_duplicate_cnic_rejected_and_fuzzy_flagged(self):
        body = self.profile_body(cnic='3520212345671')
        self.call('POST', '/profiles', body, expected=201)
        self.call('POST', '/profiles', body, expected=409)
        body['cnic'] = '3520212345672'
        self.call('POST', '/profiles', body, expected=201)
        self.assertTrue(any(d['status'] == 'pending' for d in self.workspace()['duplicates']))

    def test_department_scope_and_admin_role_enforced(self):
        staff_id = str(uuid4())
        with SessionLocal() as db:
            db.execute(t.staff_users.insert().values(id=staff_id, full_name='Limited Officer', email='officer@example.test', role='area_manager', department_id=demo_id('health_services'), active=True))
            db.commit()
        headers = {'Authorization': 'Bearer ' + demo_token(staff_id)}
        state = self.call('GET', '/workspace', headers=headers)
        self.assertTrue(all(p['domain'] == 'health_services' for p in state['programs']))
        self.call('POST', f"/programs/{demo_id('Medical Assistance')}/cycles", expected=403, headers=headers)
        match = next(m for m in self.workspace()['matches'] if m['program_id'] == demo_id('Education Support'))
        self.call('POST', f"/matches/{match['id']}/review", {'action': 'pooled'}, expected=403, headers=headers)

    def test_documents_and_assistant_use_sources(self):
        result = self.call('POST', '/assistant', {'question': 'What documents are required?', 'program_id': demo_id('Education Support')})
        self.assertTrue(result['sources'])
        self.assertTrue(all(s['program_id'] == demo_id('Education Support') for s in result['sources']))
        result = self.call('POST', '/assistant', {'question': 'quantum entanglement mars cryptocurrency'})
        self.assertEqual(result['sources'], [])

    def test_profile_validation_and_consent(self):
        for changes in [{'monthly_income': -1}, {'consent_given': False}, {'cnic': 'abc'}, {'household_size': 2, 'dependents': 8}]:
            self.call('POST', '/profiles', self.profile_body(**changes), expected=422)

    def test_same_need_same_score_and_forbidden_factors(self):
        arguments = dict(verified_income=15000, dependents=4, has_disability=False, prior_assistance_count=0,
                         school_age_children=2, urgency_level='high', chronic_illness_flag=False, cycles_waited=0, weights=DEFAULT_WEIGHTS)
        self.assertEqual(score_need(**arguments), score_need(**arguments))
        with self.assertRaises(ValueError):
            validate_weights({'entry_path': 1.0})
        with self.assertRaises(ValueError):
            validate_weights({'income_inverse': float('nan')})
        with self.assertRaises(TypeError):
            score_need(**arguments, entry_path='direct')
        with self.assertRaises(ValueError):
            score_need(**{**arguments, 'dependents': None})


if __name__ == '__main__':
    unittest.main()
