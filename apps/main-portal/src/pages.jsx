import { useMemo, useState } from 'react';
import { ArrowRight, ArrowUpRight, Users, ScanSearch, ClipboardCheck, Plus, Search, Filter, Check, X, FileCheck, Clock, ShieldCheck, Download, Info, BarChart3 } from 'lucide-react';
import { Alert, Avatar, Badge, Empty, Field, FormActions, LinkButton, Modal, PageHeading, Panel, Person, SearchBox, Table, dateLabel, money, titleCase } from './components';
import { api } from './api';

const lookups = data => ({ person: id => data.profiles.find(p => p.id === id), program: id => data.programs.find(p => p.id === id) });
const isAdmin = data => ['department_admin', 'super_admin'].includes(data.staff.role);
const profileButton = (person, open) => <Person person={person} onClick={() => open({ type: 'profile', id: person.id })}/>;
const filterRows = (rows, data, search, program) => {
  const { person, program: getProgram } = lookups(data);
  return rows.filter(r => (!program || r.program_id === program) && `${person(r.beneficiary_id)?.full_name} ${person(r.beneficiary_id)?.district} ${getProgram(r.program_id)?.name}`.toLowerCase().includes(search.toLowerCase()));
};
function ProgramFilter({ data, value, onChange }) { return <label className="filter-select"><Filter size={15}/><select aria-label="Filter by program" value={value} onChange={e => onChange(e.target.value)}><option value="">All programs</option>{data.programs.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>; }

export function Dashboard({ data, navigate, open }) {
  const { person, program } = lookups(data);
  const pending = data.matches.filter(r => r.status === 'pending_review');
  const outreach = data.pool.filter(r => ['awaiting_outreach', 'in_verification'].includes(r.outreach_status));
  const verified = data.applications.filter(r => r.verification_id && ['active', 'rolled_over', 'ranked', 'approved'].includes(r.status));
  const disbursed = data.applications.filter(r => r.status === 'disbursed');
  const metrics = [
    ['Registered beneficiaries', data.profiles.length, Users, 'Across your accessible casework', 'beneficiaries'],
    ['Suggestions to review', pending.length, ScanSearch, 'Discovery matches awaiting a staff decision', 'discovery'],
    ['Awaiting outreach', outreach.length, ClipboardCheck, 'Ready for a verification visit', 'outreach'],
    ['Verified candidates', verified.length, ShieldCheck, 'In the shared candidate pool', 'candidates'],
  ];
  return <><PageHeading eyebrow="OVERVIEW" title="Welcome back." description="What needs your team’s attention today."><span className="date-label">{dateLabel(new Date())}</span><button className="button primary" onClick={() => open({ type: 'profile-form' })}><Plus size={17}/> Register beneficiary</button></PageHeading>
    <div className="metric-grid">{metrics.map(([label, count, Icon, subtitle, target], i) => <button key={label} className={`metric metric-${i}`} onClick={() => navigate(target)}><div><span className="metric-icon"><Icon size={21}/></span><ArrowUpRight size={16}/></div><strong>{count.toLocaleString()}</strong><h3>{label}</h3><p>{subtitle}</p></button>)}</div>
    <div className="dashboard-grid"><Panel title="Your next steps" subtitle="Where cases are waiting on a staff action." action={<LinkButton onClick={() => navigate('discovery')}>View worklist</LinkButton>}>
      <div className="action-list">{[[ScanSearch, 'Review discovery matches', `${pending.length} suggestions need a staff decision`, 'discovery', pending.length], [ClipboardCheck, 'Reach out and verify need', `${outreach.length} cases are ready for assessment`, 'outreach', outreach.length], [FileCheck, 'Review the candidate pool', `${verified.length} verified candidates across programs`, 'candidates', verified.length]].map(([Icon, title, sub, target, count]) => <button key={title} className="action-row" onClick={() => navigate(target)}><span className="action-icon"><Icon size={21}/></span><span><strong>{title}</strong><small>{sub}</small></span><span className="count-chip">{count}</span><ArrowRight size={17}/></button>)}</div>
      <div className="panel-note"><ShieldCheck size={16}/> Discovery is a suggestion. Verification comes before allocation.</div></Panel>
      <Panel title="Pipeline" subtitle="Where each case sits, from registration to support."><div className="care-journey">{[['Registered', data.profiles.length], ['Awaiting review', pending.length], ['In outreach', outreach.length], ['Verified pool', verified.length], ['Supported', disbursed.length]].map(([label, count], i) => <div key={label}><span className={`step-number step-${i}`}>{i + 1}</span><span>{label}</span><strong>{count}</strong></div>)}</div></Panel>
    </div>
    <Panel title="Recently registered" subtitle="The latest beneficiary profiles added." action={<LinkButton onClick={() => navigate('beneficiaries')}>All beneficiaries</LinkButton>}><Table rows={[...data.profiles].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5)} columns={[
      { label: 'Beneficiary', render: p => profileButton(p, open) }, { label: 'Household', render: p => `${p.household_size ?? '—'} members` },
      { label: 'Monthly income', render: p => money(p.monthly_income) }, { label: 'Added on', render: p => dateLabel(p.created_at) },
      { label: 'Case status', render: p => <Badge status={data.applications.some(a => a.beneficiary_id === p.id && a.verification_id) ? 'verified' : 'pending_review'}/> },
      { label: '', render: p => <button aria-label={`View ${p.full_name}`} className="icon-button" onClick={() => open({ type: 'profile', id: p.id })}><ArrowUpRight size={18}/></button> },
    ]}/></Panel></>;
}

export function Beneficiaries({ data, open }) {
  const [search, setSearch] = useState(''), [district, setDistrict] = useState('');
  const rows = data.profiles.filter(p => (!district || p.district === district) && `${p.full_name} ${p.district} ${p.cnic || ''} ${p.phone || ''}`.toLowerCase().includes(search.toLowerCase()));
  return <><PageHeading title="Beneficiaries" eyebrow="REGISTER" description="Every registered household. Staff enter each profile in conversation, across a desk."><button className="button secondary" onClick={() => open({ type: 'application' })}><Plus size={16}/> Direct application</button><button className="button primary" onClick={() => open({ type: 'profile-form' })}><Plus size={17}/> Register beneficiary</button></PageHeading><section className="panel"><div className="toolbar"><SearchBox value={search} onChange={setSearch}/><select aria-label="District filter" value={district} onChange={e => setDistrict(e.target.value)}><option value="">All districts</option>{[...new Set(data.profiles.map(p => p.district))].sort().map(d => <option key={d}>{d}</option>)}</select><span className="result-count">{rows.length} beneficiaries</span></div><Table rows={rows} empty="No beneficiaries found" columns={[
    { label: 'Beneficiary', render: p => profileButton(p, open) }, { label: 'Household', render: p => <><strong>{p.household_size ?? '—'} members</strong><small>{p.dependents ?? '—'} dependents</small></> },
    { label: 'Monthly income', render: p => money(p.monthly_income) }, { label: 'Employment', render: p => titleCase(p.employment_status) },
    { label: 'Registered', render: p => dateLabel(p.created_at) }, { label: '', render: p => <button className="text-button" onClick={() => open({ type: 'profile', id: p.id })}>View case <ArrowRight size={15}/></button> },
  ]}/></section></>;
}

export function Discovery({ data, open, mutate, pending }) {
  const [search, setSearch] = useState(''), [program, setProgram] = useState(''), [status, setStatus] = useState('pending_review'), [review, setReview] = useState(null), [notes, setNotes] = useState(''), [error, setError] = useState('');
  const lookup = lookups(data);
  const rows = filterRows(data.matches.filter(r => r.status === status), data, search, program).sort((a, b) => b.score - a.score);
  async function submit(e) { e.preventDefault(); setError(''); try { await mutate(`/matches/${review.row.id}/review`, { action: review.action, notes }, review.action === 'pooled' ? 'Added to the outreach list. No beneficiary has been contacted automatically.' : 'Suggestion dismissed.'); setReview(null); } catch (err) { setError(err.message); } }
  return <><PageHeading eyebrow="DISCOVERY REVIEW" title="Suggested program matches" description="Review why a program was suggested. Your decision starts the next step."/><div className="information-line"><Info size={17}/><span>Confidence estimates verification likelihood; it is never an allocation priority. The model is trained on synthetic data.</span></div><section className="panel"><div className="tabs">{['pending_review', 'pooled', 'dismissed', 'suppressed'].map(s => <button key={s} className={status === s ? 'selected' : ''} onClick={() => setStatus(s)}>{titleCase(s)} <span>{data.matches.filter(r => r.status === s).length}</span></button>)}</div><div className="toolbar"><SearchBox value={search} onChange={setSearch}/><ProgramFilter data={data} value={program} onChange={setProgram}/></div><Table rows={rows} empty="No suggestions in this view" columns={[
    { label: 'Beneficiary', render: r => profileButton(lookup.person(r.beneficiary_id), open) }, { label: 'Suggested program', render: r => <><strong>{lookup.program(r.program_id)?.name}</strong><small>{titleCase(lookup.program(r.program_id)?.domain)}</small></> },
    { label: 'Why this match', render: r => <div className="reason-cell">{r.reason}</div> }, { label: 'Confidence', render: r => <Badge status="confidence">{r.score >= .7 ? 'High' : r.score >= .4 ? 'Medium' : 'Low'}</Badge> },
    { label: 'Review', render: r => status === 'pending_review' ? <div className="row-actions"><button className="button small primary" disabled={pending} onClick={() => { setReview({ row: r, action: 'pooled' }); setNotes(''); setError(''); }}>Pool <ArrowRight size={14}/></button><button className="icon-button" aria-label={`Dismiss suggestion for ${lookup.person(r.beneficiary_id)?.full_name}`} onClick={() => { setReview({ row: r, action: 'dismissed' }); setNotes(''); setError(''); }}><X size={17}/></button></div> : <Badge status={r.status}/> },
  ]}/>{status === 'suppressed' && <div className="panel-note">These programs require an explicit application. They cannot be pooled for unsolicited outreach.</div>}</section>{review && <Modal title={review.action === 'pooled' ? 'Add to outreach' : 'Dismiss suggestion'} subtitle={`${lookup.person(review.row.beneficiary_id)?.full_name} · ${lookup.program(review.row.program_id)?.name}`} onClose={() => !pending && setReview(null)}><form onSubmit={submit}>{error && <Alert type="error">{error}</Alert>}<p>{review.action === 'pooled' ? 'This puts the person on your team’s assessment list. They are not yet an applicant and will not be contacted automatically.' : 'Record your judgment. This does not change the beneficiary’s other opportunities.'}</p><Field label="Review note"><textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}/></Field><FormActions busy={pending} onCancel={() => setReview(null)} label={review.action === 'pooled' ? 'Add to outreach' : 'Dismiss suggestion'}/></form></Modal>}</>;
}

export function Outreach({ data, open }) {
  const [search, setSearch] = useState(''), [program, setProgram] = useState(''), [history, setHistory] = useState(false);
  const lookup = lookups(data);
  const direct = data.applications.filter(a => (!a.verification_id || a.status === 'expired') && !['withdrawn', 'disbursed'].includes(a.status));
  const active = data.pool.filter(r => ['awaiting_outreach', 'in_verification'].includes(r.outreach_status));
  const combined = [...active.map(r => ({ ...r, entry_path: 'ai_identified' })), ...direct.filter(a => !active.some(p => p.beneficiary_id === a.beneficiary_id && p.program_id === a.program_id)).map(a => ({ ...a, outreach_status: 'awaiting_outreach' }))];
  const rows = filterRows(history ? data.verifications : combined, data, search, program);
  return <><PageHeading title="Outreach & verification" eyebrow="OUTREACH" description="Confirm real need, check for assistance elsewhere, and record the assessment."/><section className="panel"><div className="tabs"><button className={!history ? 'selected' : ''} onClick={() => setHistory(false)}>Needs verification <span>{combined.length}</span></button><button className={history ? 'selected' : ''} onClick={() => setHistory(true)}>Verification history <span>{data.verifications.length}</span></button></div><div className="toolbar"><SearchBox value={search} onChange={setSearch}/><ProgramFilter data={data} value={program} onChange={setProgram}/></div><Table rows={rows} empty={history ? 'No assessments recorded yet' : 'No cases awaiting verification'} columns={[
    { label: 'Beneficiary', render: r => profileButton(lookup.person(r.beneficiary_id), open) }, { label: 'Program', render: r => lookup.program(r.program_id)?.name },
    { label: history ? 'Outcome' : 'Entry path · audit only', render: r => <Badge status={history ? r.outcome : r.entry_path}/> },
    { label: history ? 'Valid until' : 'Contact', render: r => history ? dateLabel(r.valid_until) : lookup.person(r.beneficiary_id)?.phone || 'Not recorded' },
    { label: history ? 'Caseworker notes' : 'Next step', render: r => history ? <span className="reason-cell">{r.notes}</span> : <button className="button small primary" onClick={() => open({ type: 'verify', record: r })}>Record assessment <ArrowRight size={14}/></button> },
  ]}/></section></>;
}

export function Candidates({ data, open, mutate, pending }) {
  const [programId, setProgramId] = useState(data.programs[0]?.id || ''), [cycleId, setCycleId] = useState(''), [approval, setApproval] = useState(null), [finalise, setFinalise] = useState(false), [amount, setAmount] = useState(''), [error, setError] = useState(''), [showPolicy, setShowPolicy] = useState(false), [confirmRank, setConfirmRank] = useState(false);
  const lookup = lookups(data), program = lookup.program(programId);
  const cycles = data.cycles.filter(c => c.program_id === programId).sort((a, b) => b.run_at.localeCompare(a.run_at));
  const cycle = cycles.find(c => c.id === cycleId) || cycles[0];
  const candidates = data.cycle_candidates.filter(c => c.cycle_id === cycle?.id).sort((a, b) => a.rank - b.rank);
  const apps = data.applications.filter(a => a.program_id === programId && !['withdrawn', 'disbursed'].includes(a.status));
  const canRank = isAdmin(data) && !cycles.some(c => c.status !== 'finalised');
  const approved = candidates.filter(c => c.status === 'approved');
  async function run() { setError(''); try { const c = await mutate(`/programs/${programId}/cycles`, undefined, 'Ranking cycle created with a saved factor-by-factor breakdown.'); setCycleId(c.id); setConfirmRank(false); } catch (e) { setError(e.message); } }
  async function approve(e) { e.preventDefault(); setError(''); try { await mutate(`/cycles/${cycle.id}/candidates/${approval.id}`, { approved: approval.status !== 'approved', amount: amount === '' ? null : Number(amount) }, 'Candidate review saved.'); setApproval(null); } catch (e) { setError(e.message); } }
  async function finish() { setError(''); try { await mutate(`/cycles/${cycle.id}/finalise`, undefined, 'Cycle finalised. Approved support recorded; remaining candidates rolled over.'); setFinalise(false); } catch (e) { setError(e.message); } }
  return <><PageHeading eyebrow="RANKING & ALLOCATION" title="Rank verified need, allocate within budget" description="One pool, identical criteria. Verified candidates are ranked by a transparent, program-specific rubric."><button className="button secondary" onClick={() => setShowPolicy(!showPolicy)}><Info size={16}/> {showPolicy ? 'Hide rubric' : 'View rubric'}</button></PageHeading>
    <div className="cycle-toolbar"><Field label="Program"><select value={programId} onChange={e => { setProgramId(e.target.value); setCycleId(''); }}>{data.programs.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field><Field label="Ranking cycle"><select value={cycle?.id || ''} onChange={e => setCycleId(e.target.value)}><option value="" disabled>No ranking cycles yet</option>{cycles.map(c => <option key={c.id} value={c.id}>{dateLabel(c.run_at)} · {titleCase(c.status)}</option>)}</select></Field><button className="button primary" disabled={!canRank || pending || !program} onClick={() => { setError(''); setConfirmRank(true); }}><ListOrderedIcon/> Run ranking cycle</button></div>
    {error && <Alert type="error">{error}</Alert>}{showPolicy && <Panel title="Transparent need rubric" subtitle="Normalization v1 is an illustrative example for administrator review, not official Al-Khidmat policy."><div className="rubric-grid">{Object.entries(program?.priority_weights || {}).map(([key, value]) => <div key={key}><strong>{titleCase(key)} <b>{Math.round(value * 100)}%</b></strong><p>{data.factor_definitions[key]}</p></div>)}</div><div className="panel-note">Entry path and AI confidence are excluded. Equal scores use application time, then application ID.</div></Panel>}
    <div className="allocation-summary"><div><small>Cycle budget</small><strong>{money(cycle?.budget_available ?? program?.budget_per_cycle)}</strong></div><div><small>Capacity</small><strong>{cycle?.capacity_available ?? program?.capacity_per_cycle ?? 'Uncapped'} <span>people</span></strong></div><div><small>Approved this cycle</small><strong>{approved.length} <span>/ {candidates.length}</span></strong></div><div><small>Approved amount</small><strong>{money(approved.reduce((sum, c) => sum + Number(c.amount || 0), 0))}</strong></div></div>
    {cycle && <Panel title="Ranked candidates" subtitle={`${dateLabel(cycle.run_at)} · ${titleCase(cycle.status)} · Each score has an immutable cycle snapshot.`} action={isAdmin(data) && cycle.status !== 'finalised' && <button className="button primary small" disabled={pending} onClick={() => { setError(''); setFinalise(true); }}>Finalize allocation <ArrowRight size={15}/></button>}><Table rows={candidates} empty="No verified candidates qualified for this cycle" columns={[
      { label: 'Rank', render: c => <span className="rank-number">{String(c.rank).padStart(2, '0')}</span> },
      { label: 'Beneficiary', render: c => profileButton(lookup.person(data.applications.find(a => a.id === c.application_id)?.beneficiary_id), open) },
      { label: 'Need score', render: c => <div className="score"><strong>{Number(c.need_score).toFixed(1)}<small>/100</small></strong><div><i style={{ width: `${c.need_score}%` }}/></div></div> },
      { label: 'Score breakdown', render: c => <details className="breakdown"><summary>View {Object.keys(c.score_breakdown || {}).length} factors</summary>{Object.entries(c.score_breakdown || {}).map(([key, value]) => <div key={key}>{titleCase(key)}<strong>{Number(value.points).toFixed(1)}</strong></div>)}</details> },
      { label: 'Allocation', render: c => money(c.amount) }, { label: 'Status', render: c => <Badge status={c.status}/> },
      { label: '', render: c => isAdmin(data) && cycle.status !== 'finalised' && <button className="button small secondary" disabled={pending} onClick={() => { setApproval(c); setAmount(c.amount ?? ''); setError(''); }}>{c.status === 'approved' ? 'Undo approval' : 'Review & approve'}</button> },
    ]}/></Panel>}
    <Panel title="Unified candidate pool" subtitle="Direct applicants and AI-identified candidates share the same verification gate."><Table rows={apps} empty="No applications in this program yet" columns={[
      { label: 'Beneficiary', render: a => profileButton(lookup.person(a.beneficiary_id), open) }, { label: 'Verification', render: a => <Badge status={a.verification_id ? 'verified' : 'awaiting_outreach'}>{a.verification_id ? dateLabel(data.verifications.find(v => v.id === a.verification_id)?.valid_until) : 'Required'}</Badge> },
      { label: 'Status', render: a => <Badge status={a.status}/> }, { label: 'Cycles waited', render: a => a.cycles_waited || 0 }, { label: 'Requested', render: a => money(a.amount_requested) },
      { label: 'Assessment', render: a => ['active', 'rolled_over', 'expired'].includes(a.status) && <button className="text-button" onClick={() => open({ type: 'verify', record: a })}>{a.verification_id ? 'Reassess' : 'Verify'} <ArrowRight size={14}/></button> },
    ]}/></Panel>
    {approval && <Modal title={approval.status === 'approved' ? 'Remove approval' : 'Approve this candidate'} onClose={() => !pending && setApproval(null)}><form onSubmit={approve}>{error && <Alert type="error">{error}</Alert>}<p>Approval records your review. Allocation is recorded only when the cycle is finalized.</p>{approval.status !== 'approved' && <Field label="Allocation amount (PKR)" hint={cycle.budget_available == null ? 'Optional for in-kind support.' : 'Required for a budgeted program.'}><input type="number" min="1" required={cycle.budget_available != null} value={amount} onChange={e => setAmount(e.target.value)}/></Field>}<FormActions busy={pending} onCancel={() => setApproval(null)} label={approval.status === 'approved' ? 'Remove approval' : 'Approve candidate'}/></form></Modal>}
    {confirmRank && <Modal title="Run a new ranking cycle" onClose={() => !pending && setConfirmRank(false)}><p>Rank verified candidates for <strong>{program.name}</strong> using the current rubric. Expired verifications return to outreach. Scores and weights are saved for audit.</p><Alert>Review the rubric first: its normalization caps are an illustrative policy and need your department’s agreement.</Alert>{error && <Alert type="error">{error}</Alert>}<div className="form-actions"><button className="button secondary" onClick={() => setConfirmRank(false)}>Cancel</button><button className="button primary" disabled={pending} onClick={run}>{pending ? 'Ranking…' : 'Run ranking'}</button></div></Modal>}
    {finalise && <Modal title="Finalize this allocation cycle" onClose={() => !pending && setFinalise(false)}><p>Record support for <strong>{approved.length} approved candidates</strong>, totaling <strong>{money(approved.reduce((sum, c) => sum + Number(c.amount || 0), 0))}</strong>. The remaining {candidates.length - approved.length} candidates will roll into the next cycle.</p><Alert>This records allocations in the case-management system. It does not transfer money. Finalized cycles cannot be edited here.</Alert>{error && <Alert type="error">{error}</Alert>}<div className="form-actions"><button className="button secondary" onClick={() => setFinalise(false)}>Cancel</button><button className="button primary" disabled={pending} onClick={finish}>{pending ? 'Finalizing…' : 'Confirm & finalize'}</button></div></Modal>}
  </>;
}
function ListOrderedIcon() { return <FileCheck size={17}/>; }

export function Duplicates({ data, open, mutate, pending }) {
  const lookup = lookups(data), [history, setHistory] = useState(false);
  async function review(id, status) { try { await mutate(`/duplicates/${id}?status=${status}`, undefined, status === 'confirmed' ? 'Duplicate confirmed for manual follow-up. No profiles were merged.' : 'Flag dismissed.'); } catch { /* Shared error banner shows the failure. */ } }
  return <><PageHeading eyebrow="DATA QUALITY" title="Duplicate review" description="Review suspected duplicates. Confirmation never merges or deletes profiles automatically."/><section className="panel"><div className="tabs"><button className={!history ? 'selected' : ''} onClick={() => setHistory(false)}>Pending review</button><button className={history ? 'selected' : ''} onClick={() => setHistory(true)}>Reviewed</button></div><Table rows={data.duplicates.filter(r => history ? r.status !== 'pending' : r.status === 'pending')} empty="No duplicate flags to review" columns={[
    { label: 'Profile A', render: r => profileButton(lookup.person(r.profile_a_id), open) }, { label: 'Profile B', render: r => profileButton(lookup.person(r.profile_b_id), open) },
    { label: 'Similarity', render: r => `${Number(r.similarity_score).toFixed(0)}%` }, { label: 'Detected by', render: r => titleCase(r.matched_on) },
    { label: 'Review', render: r => history ? <Badge status={r.status}/> : <div className="row-actions"><button disabled={pending} className="button small primary" onClick={() => review(r.id, 'confirmed')}>Confirm duplicate</button><button disabled={pending} className="button small secondary" onClick={() => review(r.id, 'dismissed')}>Dismiss</button></div> },
  ]}/></section></>;
}

export function Reports({ data }) {
  const summary = data.programs.map(p => ({ ...p, discovered: data.matches.filter(m => m.program_id === p.id && m.status !== 'suppressed').length,
    verified: data.applications.filter(a => a.program_id === p.id && a.verification_id).length,
    supported: data.applications.filter(a => a.program_id === p.id && a.status === 'disbursed').length,
    amount: data.applications.filter(a => a.program_id === p.id && a.status === 'disbursed').reduce((sum, a) => sum + Number(a.amount_disbursed || 0), 0),
  }));
  function download() {
    const cell = value => `"${String(value ?? '').replace(/^[=+@-]/, "'$&").replaceAll('"', '""')}"`;
    const csv = [['Program', 'Discovered', 'Verified applications', 'Supported', 'Recorded allocation PKR'], ...summary.map(p => [p.name, p.discovered, p.verified, p.supported, p.amount])].map(r => r.map(cell).join(',')).join('\r\n');
    const link = document.createElement('a'), url = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })); link.href = url; link.download = 'mustahiq-department-summary.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <><PageHeading eyebrow="DEPARTMENT REPORTS" title="Department reports" description="Discovery, verification, and recorded allocations across your programs."><button className="button secondary" onClick={download}><Download size={17}/> Export summary</button></PageHeading><div className="report-banner"><BarChart3 size={34}/><div><strong>{data.applications.filter(a => a.status === 'disbursed').length}</strong><span>allocations recorded</span></div><div><strong>{money(summary.reduce((sum, p) => sum + p.amount, 0))}</strong><span>support recorded across programs</span></div><p>Current workspace only,<br/>not organization-wide.</p></div><Panel title="Program overview" subtitle="Counts reflect the current accessible workspace, not organization-wide impact."><Table rows={summary} columns={[
    { label: 'Program', render: p => <><strong>{p.name}</strong><small>{titleCase(p.domain)}</small></> }, { label: 'Discovered', render: p => p.discovered }, { label: 'Verified', render: p => p.verified },
    { label: 'Supported', render: p => p.supported }, { label: 'Recorded allocation', render: p => money(p.amount) },
  ]}/></Panel><Panel title="Ranking audit trail" subtitle="Each cycle preserves its weights and candidate breakdowns."><Table rows={[...data.cycles].sort((a, b) => b.run_at.localeCompare(a.run_at))} empty="Run your first ranking cycle to start the audit trail" columns={[
    { label: 'Program', render: c => data.programs.find(p => p.id === c.program_id)?.name }, { label: 'Run date', render: c => dateLabel(c.run_at) }, { label: 'Pool', render: c => c.pool_size }, { label: 'Approved', render: c => c.approved_count }, { label: 'Supported', render: c => c.disbursed_count }, { label: 'Status', render: c => <Badge status={c.status}/> },
  ]}/></Panel></>;
}
