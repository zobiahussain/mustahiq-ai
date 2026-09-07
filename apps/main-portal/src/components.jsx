import { useEffect, useRef, useState } from 'react';
import { X, Search, ChevronLeft, ChevronRight, Inbox, ArrowUpRight, LoaderCircle } from 'lucide-react';

export const titleCase = value => (value || 'Not recorded').replaceAll('_', ' ').replace(/\b\w/g, x => x.toUpperCase());
export const money = value => value == null ? '—' : `PKR ${Number(value).toLocaleString('en-PK', { maximumFractionDigits: 0 })}`;
export const dateLabel = value => value ? new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
export function Badge({ children, status = '' }) { return <span className={`badge ${status}`}>{children || titleCase(status)}</span>; }
export function Avatar({ name = '', small = false }) { return <span className={`avatar ${small ? 'small' : ''}`}>{name.split(' ').slice(0, 2).map(x => x[0]).join('')}</span>; }
export function Person({ person, onClick }) { return <button className="person" onClick={onClick}><Avatar name={person?.full_name}/><span><strong>{person?.full_name || 'Unknown profile'}</strong><small>{person?.district} · {person?.cnic ? `CNIC •••• ${person.cnic.slice(-4)}` : 'CNIC not recorded'}</small></span></button>; }
export function PageHeading({ eyebrow, title, description, children }) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow || 'STAFF WORKSPACE'}</div><h1>{title}</h1><p>{description}</p></div><div className="heading-actions">{children}</div></div>; }
export function Empty({ title = 'Nothing here yet', children }) { return <div className="empty"><Inbox size={30}/><h3>{title}</h3><p>{children || 'New records will appear here as your team works through cases.'}</p></div>; }
export function Loading() { return <div className="loading" role="status"><LoaderCircle className="spin"/> Loading your workspace…</div>; }
export function Alert({ children, type = 'info' }) { return <div className={`alert ${type}`} role={type === 'error' ? 'alert' : 'status'}>{children}</div>; }
export function SearchBox({ value, onChange, placeholder = 'Search names, districts, or CNIC…' }) { return <label className="search-box"><Search size={17}/><input aria-label={placeholder} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}/></label>; }
export function Modal({ title, subtitle, children, onClose, wide = false }) {
  const ref = useRef();
  useEffect(() => { const dialog = ref.current; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} className={`modal ${wide ? 'wide' : ''}`} onCancel={e => { e.preventDefault(); onClose(); }} onClick={e => { if (e.target === ref.current) onClose(); }}><header><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={20}/></button></header><div className="modal-body">{children}</div></dialog>;
}
export function Field({ label, hint, children, className = '' }) { return <label className={`field ${className}`}><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>; }
export function Table({ columns, rows, empty, pageSize = 8 }) {
  const [page, setPage] = useState(0);
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const current = Math.min(page, pages - 1);
  useEffect(() => setPage(0), [rows.length]);
  return <><div className="table-scroll"><table><thead><tr>{columns.map(c => <th key={c.label}>{c.label}</th>)}</tr></thead><tbody>{rows.slice(current * pageSize, (current + 1) * pageSize).map((row, i) => <tr key={row.id || i}>{columns.map(c => <td key={c.label}>{c.render(row)}</td>)}</tr>)}</tbody></table>{!rows.length && <Empty title={empty}/>}</div>{rows.length > pageSize && <div className="pagination"><span>Showing {current * pageSize + 1}–{Math.min((current + 1) * pageSize, rows.length)} of {rows.length}</span><div><button className="icon-button" aria-label="Previous page" disabled={!current} onClick={() => setPage(current - 1)}><ChevronLeft size={17}/></button><span>{current + 1} / {pages}</span><button className="icon-button" aria-label="Next page" disabled={current === pages - 1} onClick={() => setPage(current + 1)}><ChevronRight size={17}/></button></div></div>}</>;
}
export function Panel({ title, subtitle, action, children, className = '' }) { return <section className={`panel ${className}`}><div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</section>; }
export function LinkButton({ children, onClick }) { return <button className="text-button" onClick={onClick}>{children}<ArrowUpRight size={16}/></button>; }
export function Submit({ busy, children = 'Save changes', ...props }) { return <button className="button primary" type="submit" disabled={busy} {...props}>{busy && <LoaderCircle size={16} className="spin"/>}{busy ? 'Saving…' : children}</button>; }
export function FormActions({ busy, onCancel, label }) { return <div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={onCancel}>Cancel</button><Submit busy={busy}>{label}</Submit></div>; }
