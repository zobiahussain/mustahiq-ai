import { useCallback, useEffect, useState } from 'react';
import { LayoutDashboard, Users, ScanSearch, ClipboardCheck, ListOrdered, Layers, BarChart3, MessagesSquare, ShieldCheck, LogOut, Menu, Plus, ArrowRight, RefreshCw, ExternalLink, X } from 'lucide-react';
import { api, hasSession, setSession } from './api';
import { Alert, Avatar, Loading, Submit, Field, titleCase } from './components';
import { Dashboard, Beneficiaries, Discovery, Outreach, Candidates, Reports, Duplicates } from './pages';
import { ProfileForm, ProfileDetail, VerificationForm, ApplicationForm } from './forms';
import { Programs, Assistant } from './programs';

const navigation = [
  ['dashboard', 'Overview', LayoutDashboard], ['beneficiaries', 'Beneficiaries', Users], ['discovery', 'Discovery review', ScanSearch],
  ['outreach', 'Outreach & verification', ClipboardCheck], ['candidates', 'Ranking & allocation', ListOrdered],
  ['programs', 'Programs & criteria', Layers], ['duplicates', 'Duplicate review', ShieldCheck], ['reports', 'Department reports', BarChart3], ['assistant', 'Staff assistant', MessagesSquare],
];
function currentRoute() { const value = location.hash.slice(1); return navigation.some(n => n[0] === value) ? value : 'dashboard'; }

function Login({ config, error, onLogin, retry }) {
  const [busy, setBusy] = useState(false), [localError, setError] = useState('');
  async function submit(event, demo = false) {
    event?.preventDefault(); setBusy(true); setError('');
    try { const body = event ? Object.fromEntries(new FormData(event.currentTarget)) : undefined; await onLogin(demo ? '/demo-session' : '/session', body); }
    catch (err) { setError(err.message); } finally { setBusy(false); }
  }
  return <div className="login-page"><div className="login-story"><img className="login-logo" src="/alkhidmat-logo.svg" alt="Alkhidmat Foundation Pakistan"/><div className="story-content"><div className="eyebrow">MUSTAHIQ AI · STAFF PORTAL</div><h1>Beneficiary casework,<br/><span>start to finish.</span></h1><p>Register households, review who may qualify for support, verify need, and allocate within budget.</p><div className="story-steps"><span>01 <b>Discover potential matches</b></span><span>02 <b>Verify need</b></span><span>03 <b>Rank and allocate</b></span></div></div><div className="story-footer">Alkhidmat Foundation Pakistan · established 1990</div></div><main className="login-main"><div className="login-card"><span className="overline">SIGN IN</span><h2>Staff sign in</h2><p>Use your Alkhidmat staff account to manage beneficiary casework.</p>{(error || localError) && <Alert type="error">{localError || error}</Alert>}{!config && <button className="button secondary" onClick={retry}>Retry connection</button>}{config?.demo_mode ? <><div className="demo-intro"><BadgeDemo/><h3>Demo workspace</h3><p>This local workspace uses fictional beneficiaries and demonstration policies. Changes are saved only to the isolated demo database.</p></div><button disabled={busy} onClick={() => submit(null, true)} className="button primary full">{busy ? 'Opening workspace…' : 'Enter demo workspace'}<ArrowRight size={18}/></button></> : config && <form onSubmit={submit}><Field label="Staff email"><input type="email" name="email" required autoComplete="username" placeholder="you@alkhidmat.org"/></Field><Field label="Password"><input name="password" type="password" required autoComplete="current-password" placeholder="Enter your password"/></Field><Submit busy={busy}>Sign in to workspace <ArrowRight size={18}/></Submit><p className="fine-print">Use your existing staff account. Contact your administrator if you need access.</p></form>}<div className="login-trust"><ShieldCheck size={17}/> Staff-operated · Human-reviewed · Explainable</div></div><footer>Alkhidmat Foundation Pakistan <span>Mustahiq AI / Hackathon project</span></footer></main></div>;
}
function BadgeDemo() { return <span className="badge demo">LOCAL DEMO</span>; }

export default function App() {
  const [route, setRoute] = useState(currentRoute), [config, setConfig] = useState(null), [data, setData] = useState(null);
  const [error, setError] = useState(''), [loading, setLoading] = useState(hasSession()), [notice, setNotice] = useState('');
  const [modal, setModal] = useState(null), [menu, setMenu] = useState(false), [pending, setPending] = useState(false);
  const load = useCallback(async () => { setError(''); try { setData(await api('/workspace')); } catch (e) { setError(e.message); throw e; } finally { setLoading(false); } }, []);
  const init = useCallback(async () => { try { setError(''); setConfig(await api('/config')); if (hasSession()) await load(); } catch (e) { setError(e.message); setLoading(false); } }, [load]);
  useEffect(() => { init(); const hash = () => setRoute(currentRoute()); const logout = () => { setData(null); setLoading(false); setModal(null); setNotice(''); setError('Your session ended. Please sign in again.'); }; window.addEventListener('hashchange', hash); window.addEventListener('staff-session-expired', logout); return () => { window.removeEventListener('hashchange', hash); window.removeEventListener('staff-session-expired', logout); }; }, [init]);
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(''), 6000); return () => clearTimeout(timer); }, [notice]);
  function navigate(next) { location.hash = next; setRoute(next); setMenu(false); setError(''); }
  async function mutate(path, body, message = 'Changes saved.', method = 'POST') {
    setPending(true); setError('');
    try { const result = await api(path, { method, body }); await load(); setNotice(message); return result; }
    catch (e) { setError(e.message); throw e; } finally { setPending(false); }
  }
  async function login(path, body) { setSession(await api(path, { method: 'POST', body })); try { await load(); } catch (e) { setSession(null); throw e; } }
  if (loading && !data) return <Loading/>;
  if (!data) return <Login config={config} error={error} onLogin={login} retry={init}/>;
  const shared = { data, navigate, open: setModal, mutate, pending };
  const counts = { discovery: data.matches.filter(r => r.status === 'pending_review').length, outreach: data.pool.filter(r => ['awaiting_outreach', 'in_verification'].includes(r.outreach_status)).length, duplicates: data.duplicates.filter(r => r.status === 'pending').length };
  const pages = { dashboard: Dashboard, beneficiaries: Beneficiaries, discovery: Discovery, outreach: Outreach, candidates: Candidates, programs: Programs, duplicates: Duplicates, reports: Reports, assistant: Assistant };
  const Page = pages[route] || Dashboard;
  return <div className="app"><a href="#main-content" className="skip-link">Skip to content</a><div className="utility"><span>Alkhidmat Foundation Pakistan <i/> Serving humanity since 1990</span><span>{data.demo_mode ? 'SYNTHETIC DATA · LOCAL DEMO' : 'AUTHORIZED STAFF WORKSPACE'}</span></div><header className="topbar"><div className="brand"><button className="icon-button mobile-only" aria-label="Toggle navigation" onClick={() => setMenu(!menu)}><Menu/></button><img src="/alkhidmat-logo.svg" alt="Alkhidmat Foundation Pakistan"/><span className="brand-divider"/><div className="product-name">Mustahiq<span>AI</span><small>BENEFICIARY CARE PLATFORM</small></div></div><div className="topbar-right"><span className="workspace-tag"><span className="status-dot"/>{data.demo_mode ? 'Demo workspace' : 'Staff workspace'}</span><div className="staff-mini"><Avatar name={data.staff.full_name} small/><span><strong>{data.staff.full_name}</strong><small>{titleCase(data.staff.role)}</small></span></div></div></header>
    <div className="workspace-layout">{menu && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setMenu(false)}/>}<aside className={`sidebar ${menu ? 'open' : ''}`}><span className="nav-label">YOUR WORKSPACE</span><nav aria-label="Main navigation">{navigation.map(([key, label, Icon], i) => <div key={key}>{i === 5 && <span className="nav-label second">MANAGEMENT & INSIGHTS</span>}<a href={`#${key}`} onClick={() => navigate(key)} className={`nav-item ${route === key ? 'active' : ''}`} aria-current={route === key ? 'page' : undefined}><Icon size={19}/><span>{label}</span>{counts[key] > 0 && <b>{counts[key]}</b>}</a></div>)}</nav><div className="sidebar-bottom"><div className="care-note"><ShieldCheck size={22}/><strong>Discovery is a suggestion.</strong><p>Rules and a confidence model surface possible matches. Staff make every decision.</p></div><a className="external-link" href="https://alkhidmat.org/" target="_blank" rel="noreferrer">Alkhidmat Foundation <ExternalLink size={14}/></a><button className="nav-item signout" onClick={() => { setSession(null); setData(null); setModal(null); setError(''); }}><LogOut size={18}/> Sign out</button></div></aside>
    <main id="main-content" className="main-content"><div className="breadcrumb"><span>Staff portal</span><span>/</span><strong>{navigation.find(n => n[0] === route)?.[1]}</strong><button className="icon-button" disabled={pending} aria-label="Refresh workspace" onClick={() => load().catch(() => {})}><RefreshCw size={16}/></button></div>{data.demo_mode && <div className="demo-strip"><ShieldCheck size={14}/><span>Demonstration workspace. People, budgets, and program policies are fictional.</span></div>}{error && <Alert type="error">{error}</Alert>}<Page {...shared}/><footer className="page-footer"><span>Alkhidmat Foundation Pakistan · Mustahiq AI</span><span>AI-assisted discovery. Human-led decisions.</span></footer></main></div>
    {notice && <div role="status" className="toast"><ShieldCheck size={19}/>{notice}<button className="icon-button" aria-label="Dismiss notification" onClick={() => setNotice('')}><X size={16}/></button></div>}
    {modal?.type === 'profile-form' && <ProfileForm {...shared} profile={modal.profile} onClose={() => setModal(null)}/>}
    {modal?.type === 'profile' && <ProfileDetail {...shared} profile={data.profiles.find(p => p.id === modal.id)} onClose={() => setModal(null)}/>}
    {modal?.type === 'verify' && <VerificationForm {...shared} record={modal.record} onClose={() => setModal(null)}/>}
    {modal?.type === 'application' && <ApplicationForm {...shared} profileId={modal.profileId} onClose={() => setModal(null)}/>}
  </div>;
}
