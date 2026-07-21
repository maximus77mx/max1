import { useEffect, useState } from 'react';
import { api } from './api';
import { I18nContext, STR } from './i18n';
import { Toast } from './components/ui';
import Dashboard from './components/Dashboard';
import RecordsTable from './components/RecordsTable';
import RegisterForm from './components/RegisterForm';

export default function App() {
  const [lang, setLang] = useState('th');
  const [meta, setMeta] = useState(null);
  const [view, setView] = useState('dashboard'); // dashboard | records | form
  const [editId, setEditId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [toast, setToast] = useState(null);

  const t = STR[lang];

  useEffect(() => {
    api.meta().then(setMeta);
  }, []);

  const flash = (msg, kind) => {
    setToast({ msg, kind });
    setTimeout(() => setToast(null), 2600);
  };

  const openNew = () => { setEditId(null); setView('form'); };
  const openEdit = (id) => { setEditId(id); setView('form'); };

  const onSaved = (_r, kind) => {
    if (kind === 'err') return; // stay on form, errors are shown inline
    flash(t.savedOk);
    setRefreshKey((k) => k + 1);
    setView('records');
  };

  if (!meta) return <div className="loading">Loading…</div>;

  const navItem = (key, label) => (
    <button className={view === key ? 'active' : ''} onClick={() => setView(key)}>{label}</button>
  );

  return (
    <I18nContext.Provider value={{ lang, t, setLang }}>
      <div className="app">
        <header className="topbar">
          <div className="brand">
            <span className="logo"><b>QA</b> Corrective Action</span>
            <span className="sub">True Corporation · COPC / ISO</span>
          </div>
          <nav className="nav">
            {navItem('dashboard', t.dashboard)}
            {navItem('records', t.records)}
          </nav>
          <div className="spacer" />
          <button className="lang-btn" onClick={() => setLang(lang === 'th' ? 'en' : 'th')}>{t.lang}</button>
          <button className="cta" onClick={openNew}>{t.newCA}</button>
        </header>

        <main className="wrap">
          {view === 'dashboard' && <Dashboard key={refreshKey} />}
          {view === 'records' && (
            <RecordsTable
              meta={meta}
              refreshKey={refreshKey}
              onEdit={openEdit}
              onNew={openNew}
              onChanged={() => { setRefreshKey((k) => k + 1); flash(t.savedOk); }}
            />
          )}
          {view === 'form' && (
            <RegisterForm
              meta={meta}
              editId={editId}
              onSaved={onSaved}
              onCancel={() => setView(editId ? 'records' : 'dashboard')}
            />
          )}
        </main>

        <Toast msg={toast?.msg} kind={toast?.kind} />
      </div>
    </I18nContext.Provider>
  );
}
