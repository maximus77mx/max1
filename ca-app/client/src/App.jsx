import { useEffect, useState } from 'react';
import { api, getToken, setToken } from './api';
import { I18nContext, STR } from './i18n';
import { AuthContext, ROLE_BADGE } from './auth';
import { Toast } from './components/ui';
import Dashboard from './components/Dashboard';
import RecordsTable from './components/RecordsTable';
import RegisterForm from './components/RegisterForm';
import Login from './components/Login';
import AcceptInvite from './components/AcceptInvite';
import Users from './components/Users';
import Audit from './components/Audit';
import Settings from './components/Settings';
import ChangePassword from './components/ChangePassword';

function inviteTokenFromUrl() {
  return new URLSearchParams(window.location.search).get('invite');
}

export default function App() {
  const [lang, setLang] = useState('th');
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [meta, setMeta] = useState(null);
  const [view, setView] = useState('dashboard');
  const [editId, setEditId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [toast, setToast] = useState(null);
  const [showChangePw, setShowChangePw] = useState(false);
  const [inviteToken] = useState(inviteTokenFromUrl());

  const t = STR[lang];
  const can = (perm) => user?.perms?.includes(perm);

  // Restore session on load
  useEffect(() => {
    if (inviteToken) { setAuthChecked(true); return; }
    if (getToken()) {
      api.me().then((d) => setUser({ ...d.user, perms: d.user.perms })).catch(() => setToken(null)).finally(() => setAuthChecked(true));
    } else {
      setAuthChecked(true);
    }
  }, [inviteToken]);

  // Load CA metadata once authenticated
  useEffect(() => {
    if (user) api.meta().then(setMeta);
  }, [user]);

  // Global 401 handler
  useEffect(() => {
    const h = () => { setUser(null); };
    window.addEventListener('ca-unauthorized', h);
    return () => window.removeEventListener('ca-unauthorized', h);
  }, []);

  // Pick a landing view the user is allowed to see
  useEffect(() => {
    if (user) setView(can('dashboard.view') ? 'dashboard' : 'records');
  }, [user]); // eslint-disable-line

  const flash = (msg, kind) => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 2600);
  };

  const clearInviteUrl = () => window.history.replaceState({}, '', '/');
  const onAuthed = (u) => { setUser(u); clearInviteUrl(); };
  const logout = () => { setToken(null); setUser(null); };

  const openNew = () => { setEditId(null); setView('form'); };
  const openEdit = (id) => { setEditId(id); setView('form'); };
  const onSaved = (_r, kind) => {
    if (kind === 'err') return;
    flash(t.savedOk);
    setRefreshKey((k) => k + 1);
    setView('records');
  };

  // ---- Routing ----
  if (inviteToken) {
    return (
      <I18nContext.Provider value={{ lang, t, setLang }}>
        <AcceptInvite token={inviteToken} onAccepted={onAuthed} />
      </I18nContext.Provider>
    );
  }
  if (!authChecked) return <div className="loading">Loading…</div>;
  if (!user) {
    return (
      <I18nContext.Provider value={{ lang, t, setLang }}>
        <Login onLoggedIn={onAuthed} />
      </I18nContext.Provider>
    );
  }
  if (!meta) return <div className="loading">Loading…</div>;

  const navItem = (key, label, perm) =>
    (!perm || can(perm)) && (
      <button className={view === key ? 'active' : ''} onClick={() => setView(key)}>{label}</button>
    );

  const rb = ROLE_BADGE[user.role];

  return (
    <I18nContext.Provider value={{ lang, t, setLang }}>
      <AuthContext.Provider value={{ user, can, logout }}>
        <div className="app">
          <header className="topbar">
            <div className="brand">
              <span className="logo"><b>QA</b> Corrective Action</span>
              <span className="sub">True Corporation · COPC / ISO</span>
            </div>
            <nav className="nav">
              {navItem('dashboard', t.dashboard, 'dashboard.view')}
              {navItem('records', t.records, 'records.view')}
              {navItem('users', t.users, 'users.manage')}
              {navItem('audit', t.auditLog, 'users.manage')}
              {navItem('settings', t.settings, 'settings.manage')}
            </nav>
            <div className="spacer" />
            <button className="lang-btn" onClick={() => setLang(lang === 'th' ? 'en' : 'th')}>{t.lang}</button>
            <div className="user-chip">
              <span className="role-chip" style={{ background: rb.color }}>{rb.label}</span>
              <span className="user-name">{user.name || user.email}</span>
              <button className="lang-btn" onClick={() => setShowChangePw(true)}>{t.changePassword}</button>
              <button className="lang-btn" onClick={logout}>{t.logout}</button>
            </div>
            {can('records.create') && <button className="cta" onClick={openNew}>{t.newCA}</button>}
          </header>

          <main className="wrap">
            {view === 'dashboard' && (can('dashboard.view') ? <Dashboard key={refreshKey} /> : <div className="empty">{t.noPermission}</div>)}
            {view === 'records' && (can('records.view') ? (
              <RecordsTable
                meta={meta}
                refreshKey={refreshKey}
                onEdit={openEdit}
                onNew={openNew}
                onChanged={() => { setRefreshKey((k) => k + 1); flash(t.savedOk); }}
              />
            ) : <div className="empty">{t.noPermission}</div>)}
            {view === 'users' && (can('users.manage') ? <Users flash={flash} /> : <div className="empty">{t.noPermission}</div>)}
            {view === 'audit' && (can('users.manage') ? <Audit /> : <div className="empty">{t.noPermission}</div>)}
            {view === 'settings' && (can('settings.manage') ? <Settings flash={flash} /> : <div className="empty">{t.noPermission}</div>)}
            {view === 'form' && (
              <RegisterForm
                meta={meta}
                editId={editId}
                onSaved={onSaved}
                onCancel={() => setView(editId ? 'records' : 'dashboard')}
              />
            )}
          </main>

          {showChangePw && <ChangePassword onClose={() => setShowChangePw(false)} flash={flash} />}
          <Toast msg={toast?.msg} kind={toast?.kind} />
        </div>
      </AuthContext.Provider>
    </I18nContext.Provider>
  );
}
