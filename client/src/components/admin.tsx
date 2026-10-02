'use client';

import { FormEvent, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { LockKeyhole, Plus, Search, ShieldAlert, UserRoundCheck, UserRoundX, UsersRound, X } from 'lucide-react';
import { api } from '@/lib/api';
import type { Page, StaffUser } from '@/lib/types';
import { useShop } from './providers';
import { Empty, ErrorState, Field, Loading, Status } from './ui';

export function AdminStaffPage() {
  const { user, sessionLoading, notify } = useShop();
  const client = useQueryClient();
  const [search, setSearch] = useState('');
  const [adding, setAdding] = useState(false);
  const staff = useQuery({
    queryKey: ['admin', 'staff', search],
    queryFn: () => api<Page<StaffUser>>(`admin/staff${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ''}`),
    enabled: !!user?.is_superuser,
  });
  const statusAction = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'block' | 'unblock' }) => api<StaffUser>(`admin/staff/${id}/${action}`, 'POST', {}),
    onSuccess: async (_, variables) => {
      await client.invalidateQueries({ queryKey: ['admin', 'staff'] });
      notify(`Staff member ${variables.action === 'block' ? 'blocked' : 'unblocked'}`);
    },
    onError: error => notify((error as Error).message, true),
  });

  if (sessionLoading) return <Loading />;
  if (!user) return <Empty title="Admin sign-in required" text="Sign in with an administrator account to manage staff." href="/login?next=/admin/staff" label="Sign in" icon={<LockKeyhole size={36} />} />;
  if (!user.is_superuser) return <Empty title="Administrator access only" text="Your account does not have permission to add, block, or unblock staff." href="/account" label="Back to your account" icon={<ShieldAlert size={36} />} />;

  const rows = staff.data?.results || [];
  return <div className="container admin-staff-page section">
    <div className="admin-staff-heading"><div><span className="eyebrow green">ADMINISTRATION</span><h1>Staff management</h1><p>Add trusted team members and control their access.</p></div><button className="button" onClick={() => setAdding(true)}><Plus size={17} />Add staff</button></div>
    <div className="admin-staff-toolbar"><div className="search-box"><Search size={17} /><input aria-label="Search staff" placeholder="Search by name or email…" value={search} onChange={event => setSearch(event.target.value)} /></div><span>{staff.data?.count || 0} staff account{staff.data?.count === 1 ? '' : 's'}</span></div>
    {staff.isLoading ? <Loading /> : staff.error ? <ErrorState error={staff.error} retry={() => staff.refetch()} /> : rows.length ? <div className="admin-staff-table table-scroll"><table><thead><tr><th>Staff member</th><th>Joined</th><th>Status</th><th>Access</th></tr></thead><tbody>{rows.map(member => <tr key={member.id}><td><div className="admin-staff-person"><span>{member.first_name?.[0] || member.email[0]}</span><div><strong>{`${member.first_name} ${member.last_name}`.trim() || 'Staff member'}</strong><small>{member.email}</small></div></div></td><td>{new Date(member.date_joined).toLocaleDateString('en-NG', { day: 'numeric', month: 'short', year: 'numeric' })}</td><td><Status value={member.is_active ? 'active' : 'blocked'} /></td><td><button className={`button secondary ${member.is_active ? 'danger' : ''}`} disabled={statusAction.isPending} onClick={() => statusAction.mutate({ id: member.id, action: member.is_active ? 'block' : 'unblock' })}>{member.is_active ? <UserRoundX size={16} /> : <UserRoundCheck size={16} />}{member.is_active ? 'Block' : 'Unblock'}</button></td></tr>)}</tbody></table></div> : <div className="admin-staff-empty"><UsersRound size={36} /><h2>{search ? 'No staff found' : 'No staff accounts yet'}</h2><p>{search ? 'Try a different name or email address.' : 'Add your first staff member to give them access.'}</p>{!search && <button className="button" onClick={() => setAdding(true)}>Add staff</button>}</div>}
    {adding && <StaffDialog onClose={() => setAdding(false)} onCreated={async () => { setAdding(false); await client.invalidateQueries({ queryKey: ['admin', 'staff'] }); notify('Staff account created'); }} />}
  </div>;
}

function StaffDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      await api('admin/staff', 'POST', Object.fromEntries(form.entries()));
      await onCreated();
    } catch (caught) { setError((caught as Error).message); setBusy(false); }
  }
  return <div className="admin-dialog-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><section className="admin-dialog" role="dialog" aria-modal="true" aria-labelledby="add-staff-title"><div className="admin-dialog-head"><div><span className="eyebrow green">NEW TEAM MEMBER</span><h2 id="add-staff-title">Add staff</h2></div><button className="icon-button" aria-label="Close" onClick={onClose}><X size={19} /></button></div><form className="form-stack" onSubmit={submit}><div className="form-row"><Field label="First name"><input name="first_name" required maxLength={30} autoComplete="given-name" /></Field><Field label="Last name"><input name="last_name" required maxLength={30} autoComplete="family-name" /></Field></div><Field label="Email address"><input name="email" type="email" required autoComplete="email" /></Field><div className="form-row"><Field label="Phone number"><input name="phone1" type="tel" required placeholder="+234 801 234 5678" autoComplete="tel" /></Field><Field label="Gender"><select name="gender" required defaultValue=""><option value="" disabled>Select</option><option value="female">Female</option><option value="male">Male</option></select></Field></div><Field label="Temporary password"><input name="password" type="password" required minLength={8} maxLength={90} autoComplete="new-password" /></Field>{error && <p className="form-error" role="alert">{error}</p>}<div className="form-actions"><button type="button" className="button secondary" onClick={onClose}>Cancel</button><button className="button" disabled={busy}>{busy ? 'Creating…' : 'Create staff account'}</button></div></form></section></div>;
}
