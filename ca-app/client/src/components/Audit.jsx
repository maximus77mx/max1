import { useEffect, useState } from 'react';
import { api } from '../api';
import { useI18n } from '../i18n';

const ACTION_META = {
  'auth.login': { icon: '→', color: '#62625b' },
  'auth.change_password': { icon: '🔑', color: '#1f5bb5' },
  'auth.password_reset': { icon: '🔑', color: '#1f5bb5' },
  'user.invite': { icon: '✉', color: '#7e238b' },
  'user.accept_invite': { icon: '✓', color: '#103c25' },
  'user.role_change': { icon: '⇄', color: '#915b00' },
  'user.status_change': { icon: '◑', color: '#915b00' },
  'user.reset_password': { icon: '🔑', color: '#7e238b' },
  'user.remove': { icon: '✕', color: '#e60023' },
  'record.create': { icon: '+', color: '#103c25' },
  'record.update': { icon: '✎', color: '#915b00' },
  'record.delete': { icon: '✕', color: '#e60023' },
};

export default function Audit() {
  const { t } = useI18n();
  const [rows, setRows] = useState(null);
  const [filter, setFilter] = useState('');

  useEffect(() => { api.audit(500).then(setRows); }, []);
  if (!rows) return <div className="loading">Loading…</div>;

  const shown = filter ? rows.filter((r) =>
    [r.actor_email, r.action, r.entity_ref, r.detail].join(' ').toLowerCase().includes(filter.toLowerCase())) : rows;

  return (
    <div>
      <div className="toolbar">
        <input type="search" placeholder={t.search} value={filter} onChange={(e) => setFilter(e.target.value)} />
        <div className="spacer" style={{ flex: 1 }} />
        <span style={{ color: 'var(--ash)', fontWeight: 700, fontSize: 13 }}>{shown.length} {t.count}</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>{t.when}</th><th>{t.who}</th><th>{t.action}</th><th>{t.target}</th><th>{t.detail}</th></tr>
          </thead>
          <tbody>
            {shown.map((r) => {
              const m = ACTION_META[r.action] || { icon: '•', color: '#62625b' };
              return (
                <tr key={r.id}>
                  <td style={{ whiteSpace: 'nowrap', fontSize: 12, color: 'var(--mute)' }}>{r.ts?.replace('T', ' ').slice(0, 16)}</td>
                  <td style={{ fontWeight: 600 }}>{r.actor_email}<br /><span style={{ fontSize: 11, color: 'var(--ash)' }}>{r.actor_role}</span></td>
                  <td><span style={{ color: m.color, fontWeight: 800, fontSize: 12.5 }}>{m.icon} {r.action}</span></td>
                  <td>{r.entity_ref || '—'}</td>
                  <td style={{ fontSize: 12.5, color: 'var(--mute)' }}>{r.detail || '—'}</td>
                </tr>
              );
            })}
            {shown.length === 0 && <tr><td colSpan={5} className="empty">{t.noData}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
