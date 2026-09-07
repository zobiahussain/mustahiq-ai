// DOM interaction checks; no network or shared beneficiary data is used.
// Backend workflow semantics are covered separately by the real-model API tests.
// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

const mock = vi.hoisted(() => ({ api: vi.fn(), streamApi: vi.fn(), hasSession: vi.fn(() => false), setSession: vi.fn() }));
vi.mock('./api', () => mock);
let state;
const programId = '11111111-1111-4111-8111-111111111111';
const profileId = '22222222-2222-4222-8222-222222222222';
const definitions = { income_inverse: '1 − min(verified income / PKR 50,000, 1)', dependents: 'min(dependents / 10, 1)', disability: 'Confirmed disability', no_prior_assistance: 'Prior assistance factor', school_age_children: 'School-age children factor' };
function fixture() {
  return { demo_mode: true, staff: { full_name: 'Rayan', role: 'super_admin' }, factor_definitions: definitions,
    departments: [{ id: '33333333-3333-4333-8333-333333333333', name: 'Education' }],
    profiles: [{ id: profileId, full_name: 'Fatima Bibi', district: 'Lahore', monthly_income: 15000, household_size: 5, dependents: 3, school_age_children: 2, created_at: '2026-09-07T10:00:00Z', consent_given: true }],
    programs: [{ id: programId, name: 'Education Support', domain: 'education', description: 'Synthetic program', active: true, department_id: '33333333-3333-4333-8333-333333333333', budget_per_cycle: 150000, capacity_per_cycle: 6, cycle_frequency_days: 14, verification_valid_days: 90,
      criteria_structured: { hard_rules: [{ rule_id: 'income', field: 'monthly_income', operator: '<=', value: 35000, description: 'Income cap' }] }, priority_weights: { income_inverse: 1 } }],
    matches: [{ id: 'm1', beneficiary_id: profileId, program_id: programId, status: 'pending_review', score: .8, reason: 'Income cap passed.' }],
    pool: [], applications: [], cycles: [], cycle_candidates: [], duplicates: [], verifications: [],
    criteria: [{ id: 'c1', program_id: programId, chunk_text: 'Required documents include CNIC and an income statement.' }],
  };
}
beforeEach(() => {
  location.hash = ''; state = fixture(); vi.clearAllMocks(); mock.hasSession.mockReturnValue(false);
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
  Element.prototype.scrollIntoView = vi.fn();
  mock.api.mockImplementation(async (path, options) => {
    if (path === '/config') return { demo_mode: true };
    if (path === '/demo-session') return { access_token: 'demo-test' };
    if (path === '/workspace') return structuredClone(state);
    if (path === '/profiles') { const profile = { ...options.body, id: 'new-profile', created_at: '2026-09-07T11:00:00Z' }; state.profiles.push(profile); return { profile, discovery: [] }; }
    if (path === '/assistant') return { answer: 'These documents support the answer.', mode: 'source_lookup', sources: [{ id: 'c1', program_id: programId, program_name: 'Education Support', text: state.criteria[0].chunk_text }] };
    return {};
  });
  mock.streamApi.mockImplementation(async (path, { onEvent }) => {
    if (path === '/support/chat/stream') {
      onEvent({ type: 'meta', sources: [{ id: 'c1', program_id: programId, program_name: 'Education Support', text: state.criteria[0].chunk_text }] });
      onEvent({ type: 'token', text: 'Education Support requires ' });
      onEvent({ type: 'token', text: 'CNIC and an income statement.' });
      onEvent({ type: 'done' });
    }
  });
});
afterEach(cleanup);
async function login() {
  const user = userEvent.setup(); render(<App/>);
  await user.click(await screen.findByRole('button', { name: /Enter demo workspace/i }));
  await screen.findByRole('heading', { name: 'Welcome back.' }); return user;
}

describe('staff portal interactions', () => {
  it('opens a clearly labeled demo with real workspace counts', async () => {
    await login();
    expect(screen.getByText(/People, budgets, and program policies are fictional/)).toBeTruthy();
    expect(screen.getByRole('button', { name: /Registered beneficiaries/ }).textContent).toContain('1');
  });
  it('does not show the public support chatbot option', async () => {
    render(<App/>);
    expect(screen.queryByRole('button', { name: /Open Alkhidmat support chatbot/i })).toBeNull();
  });
  it('renders every primary route without a runtime error', async () => {
    const user = await login();
    for (const [label, heading] of [
      ['Beneficiaries', 'Every person. One profile.'], ['Discovery review', 'Potential support, ready for review.'],
      ['Outreach & verification', 'Conversations that confirm care.'], ['Ranking & allocation', 'Prioritize need. Allocate with care.'],
      ['Programs & criteria', 'Clear criteria. Consistent care.'], ['Duplicate review', 'One person, one clear record.'],
      ['Department reports', 'See the support taking shape.'], ['Staff assistant', 'A helping hand for your casework.'],
    ]) {
      const nav = screen.getByRole('navigation', { name: 'Main navigation' });
      await user.click(within(nav).getByRole('link', { name: new RegExp(label.replace('&', '&')) }));
      expect(await screen.findByRole('heading', { name: heading })).toBeTruthy();
    }
  });
  it('registers a partial profile with explicit consent and preserves unknown fields', async () => {
    const user = await login(); await user.click(screen.getByRole('button', { name: /Register beneficiary/ }));
    await user.type(screen.getByLabelText('Full name *'), 'Test Beneficiary');
    await user.type(screen.getByLabelText('District *'), 'Multan');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.type(screen.getByLabelText('Monthly income (PKR)'), '18000');
    await user.click(screen.getByRole('button', { name: 'Continue' }));
    await user.click(screen.getByRole('checkbox'));
    await user.click(screen.getByRole('button', { name: /Register & discover support/ }));
    await screen.findByRole('heading', { name: 'Beneficiary case file' });
    const payload = mock.api.mock.calls.find(([path]) => path === '/profiles')[1].body;
    expect(payload.monthly_income).toBe(18000); expect(payload.has_disability).toBeNull(); expect(payload.consent_given).toBe(true);
  });
  it('shows API validation errors inside the active form', async () => {
    const user = await login();
    await user.click(screen.getByRole('link', { name: /Beneficiaries/ }));
    await user.click(screen.getByRole('button', { name: /Direct application/ }));
    await user.selectOptions(screen.getByLabelText('Beneficiary'), profileId);
    await user.selectOptions(screen.getByLabelText('Requested program'), programId);
    const original = mock.api.getMockImplementation();
    mock.api.mockImplementation((path, options) => path === '/applications' ? Promise.reject(new Error('An application already exists.')) : original(path, options));
    await user.click(screen.getByRole('button', { name: 'Record application' }));
    expect(await within(screen.getByRole('dialog')).findByRole('alert')).toBeTruthy();
    expect(screen.getByRole('dialog').textContent).toContain('An application already exists.');
  });
  it('asks the source assistant and displays inspectable citations', async () => {
    const user = await login(); await user.click(screen.getByRole('link', { name: 'Staff assistant' }));
    await user.click(screen.getByRole('button', { name: 'What documents are required for education support?' }));
    expect(await screen.findByText('SOURCE LOOKUP · NO GENERATED CLAIMS')).toBeTruthy();
    expect(screen.getByText('Required documents include CNIC and an income statement.')).toBeTruthy();
  });
  it('clears protected casework when a session expires', async () => {
    await login(); window.dispatchEvent(new Event('staff-session-expired'));
    expect(await screen.findByRole('button', { name: /Enter demo workspace/ })).toBeTruthy();
    expect(screen.queryByText('Fatima Bibi')).toBeNull();
  });
});
