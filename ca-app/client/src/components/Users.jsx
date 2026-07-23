import { useEffect, useState } from 'react';
import { api } from '../api';
import { useI18n } from '../i18n';
import { useAuth, ROLE_BADGE } from '../auth';
import RosterPicker from './RosterPicker';
import AddEmployeeModal from './AddEmployeeModal';

function RoleChip({ role }) {
  const rb = ROLE_BADGE[role] || { label: role, color: '#62625b' };
  return <span className="role-chip" style={{ background: rb.color }}>{rb.label}</span>;
}

export default function Users({ flash }) {
  const { t } = useI18n();
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('viewer');
  const [linkBox, setLinkBox] = useState(null); // { email, link }
  const [copied, setCopied] = useState(false);

  const load = () => api.users().then((d) => { setData(d); setRole(d.assignableRoles[d.assignableRoles.length - 1] || 'viewer'); });
  useEffect(() => { load(); }, []); // eslint-disable-line

  if (!data) return <div className="loading">Loading…</div>;

  const invite = async (e) => {
    e.preventDefault();
    try {
      const res = await api.inviteUser(email.trim(), role);
      setEmail('');
      if (res.link) { setLinkBox({ email: res.email, link: res.link }); setCopied(false); }
      else flash(t.emailSent);
      load();
    } catch (ex) {
      flash(ex.body?.error === 'user_exists' ? 'User already exists' : 'Invite failed', 'err');
    }
  };

  const copy = () => {
    navigator.clipboard?.writeText(linkBox.link);
    setCopied(true);
  };

  const changeRole = async (u, newRole) => { await api.setUserRole(u.id, newRole); load(); };
  const toggle = async (u) => { await api.setUserStatus(u.id, u.status === 'disabled' ? 'active' : 'disabled'); load(); };
  const resend = async (u) => {
    const res = await api.resendInvite(u.id);
    if (res.link) { setLinkBox({ email: u.email, link: res.link }); setCopied(false); }
    else flash(t.emailSent);
  };
  const reset = async (u) => {
    const res = await api.resetUserPassword(u.id);
    if (res.link) { setLinkBox({ email: u.email, link: res.link }); setCopied(false); }
    else flash(t.emailSent);
  };
  const remove = async (u) => {
    if (!confirm(`${t.remove}: ${u.email}?`)) return;
    await api.removeUser(u.id); load();
  };

  const manageable = (u) =>
    u.role !== 'super_admin' && u.id !== user.id &&
    (user.role === 'super_admin' || ['editor', 'owner', 'viewer'].includes(u.role));

  // Linking a user to the org roster: self, super admin, or a manageable user.
  const canLink = (u) => u.id === user.id || user.role === 'super_admin' || manageable(u);
  const [linkDraft, setLinkDraft] = useState({}); // user id → typed text
  const [addEmpFor, setAddEmpFor] = useState(null); // { user, name } → show add-employee modal

  const linkEmployee = async (u, emp) => {
    await api.setUserEmployee(u.id, emp.employee_id);
    setLinkDraft((p) => ({ ...p, [u.id]: undefined }));
    flash(t.savedOk);
    load();
  };
  const unlinkEmployee = async (u) => {
    await api.setUserEmployee(u.id, null);
    load();
  };

  return (
    <div>
      {/* Invite */}
      <div className="panel" style={{ marginBottom: 18 }}>
        <h3>{t.inviteByEmail}</h3>
        <form onSubmit={invite} className="toolbar" style={{ marginBottom: 0 }}>
          <input type="email" required placeholder={t.email} value={email}
            onChange={(e) => setEmail(e.target.value)} style={{ minWidth: 260 }} />
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {data.assignableRoles.map((r) => <option key={r} value={r}>{ROLE_BADGE[r].label}</option>)}
          </select>
          <button className="cta" type="submit">{t.sendInvite}</button>
          {!data.mailEnabled && <span style={{ color: 'var(--ash)', fontSize: 12, fontWeight: 600 }}>
            · dev mode: {t.inviteLinkCopy}</span>}
        </form>
        {linkBox && (
          <div className="link-box">
            <div style={{ fontSize: 12, color: 'var(--mute)', fontWeight: 700, marginBottom: 6 }}>
              {t.inviteLinkCopy} — {linkBox.email}
            </div>
            <div className="link-row">
              <input readOnly value={linkBox.link} onFocus={(e) => e.target.select()} />
              <button className="cta ghost" type="button" onClick={copy}>{copied ? t.copied : t.copy}</button>
            </div>
          </div>
        )}
      </div>

      {/* Pending invites */}
      {data.pendingInvites.length > 0 && (
        <div className="panel" style={{ marginBottom: 18 }}>
          <h3>{t.pendingInvites} ({data.pendingInvites.length})</h3>
          <div className="table-wrap">
            <table>
              <thead><tr><th>{t.email}</th><th>{t.role}</th><th>Invited by</th></tr></thead>
              <tbody>
                {data.pendingInvites.map((i) => (
                  <tr key={i.id}><td>{i.email}</td><td><RoleChip role={i.role} /></td><td>{i.invited_by}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* All users */}
      <div className="panel">
        <h3>{t.allUsers} ({data.users.length})</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>{t.email}</th><th>{t.name}</th><th>{t.role}</th><th>{t.orgTeam}</th><th>{t.status}</th><th>{t.lastLogin}</th><th>{t.actions}</th></tr>
            </thead>
            <tbody>
              {data.users.map((u) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 700 }}>{u.email}{u.id === user.id && ' (you)'}</td>
                  <td>{u.name || '—'}</td>
                  <td>
                    {manageable(u) ? (
                      <select value={u.role} onChange={(e) => changeRole(u, e.target.value)}
                        style={{ borderRadius: 8, padding: '4px 8px', fontSize: 12 }}>
                        {data.assignableRoles.map((r) => <option key={r} value={r}>{ROLE_BADGE[r].label}</option>)}
                      </select>
                    ) : <RoleChip role={u.role} />}
                  </td>
                  <td style={{ minWidth: 220 }}>
                    {u.employee_id ? (
                      <div className="org-cell">
                        <div style={{ fontWeight: 700, fontSize: 12.5 }}>{u.emp_name}
                          {canLink(u) && (
                            <button type="button" className="link" style={{ marginLeft: 6, fontSize: 11 }} onClick={() => unlinkEmployee(u)}>✕</button>
                          )}
                        </div>
                        <div style={{ fontSize: 11.5, color: 'var(--mute)' }}>
                          {[u.division, u.section].filter(Boolean).join(' › ')}
                        </div>
                      </div>
                    ) : canLink(u) ? (
                      <RosterPicker
                        value={linkDraft[u.id]}
                        placeholder={t.linkEmployee}
                        canAdd
                        addLabel={t.addEmployee}
                        onAdd={(name) => setAddEmpFor({ user: u, name })}
                        onChange={(v) => setLinkDraft((p) => ({ ...p, [u.id]: v }))}
                        onPick={(emp) => linkEmployee(u, emp)}
                      />
                    ) : (
                      <span style={{ color: 'var(--ash)' }}>—</span>
                    )}
                  </td>
                  <td><span className={`badge st-${u.status === 'active' ? 'Closed' : u.status === 'invited' ? 'Inprogress' : 'Reopened'}`}>{t['st_' + u.status]}</span></td>
                  <td style={{ whiteSpace: 'nowrap', fontSize: 12, color: 'var(--mute)' }}>{u.last_login?.slice(0, 16) || '—'}</td>
                  <td>
                    {manageable(u) && (
                      <div className="row-actions">
                        {u.status === 'invited' && <button className="icon-btn" onClick={() => resend(u)}>{t.resend}</button>}
                        {u.status !== 'invited' && <button className="icon-btn" onClick={() => toggle(u)}>{u.status === 'disabled' ? t.enable : t.disable}</button>}
                        {u.status === 'active' && <button className="icon-btn" onClick={() => reset(u)}>{t.resetPassword}</button>}
                        <button className="icon-btn danger" onClick={() => remove(u)}>{t.remove}</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {addEmpFor && (
        <AddEmployeeModal
          initialName={addEmpFor.name}
          flash={flash}
          onClose={() => setAddEmpFor(null)}
          onSaved={(emp) => {
            const u = addEmpFor.user;
            setAddEmpFor(null);
            linkEmployee(u, emp);
          }}
        />
      )}
    </div>
  );
}
