import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { useI18n } from '../i18n';

export default function Settings({ flash }) {
  const { t } = useI18n();
  const [cfg, setCfg] = useState(null);
  const [pass, setPass] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testTo, setTestTo] = useState('');
  const [roster, setRoster] = useState(null);
  const [rosterBusy, setRosterBusy] = useState(false);
  const rosterFileRef = useRef(null);

  useEffect(() => {
    api.getMailSettings().then(setCfg);
    api.rosterInfo().then(setRoster).catch(() => setRoster(null));
  }, []);
  if (!cfg) return <div className="loading">Loading…</div>;

  const onRosterFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setRosterBusy(true);
    try {
      const res = await api.uploadRoster(file);
      flash(`${t.rosterUploaded} (${res.count})`);
      api.rosterInfo().then(setRoster);
    } catch {
      flash(t.rosterUploadFailed, 'err');
    } finally {
      setRosterBusy(false);
    }
  };

  const set = (k, v) => setCfg((p) => ({ ...p, [k]: v }));

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const body = { ...cfg };
      if (pass) body.pass = pass; // only send if changed
      const updated = await api.saveMailSettings(body);
      setCfg(updated);
      setPass('');
      flash(t.settingsSaved);
    } catch (ex) {
      flash(ex.body?.error === 'invalid_sender_email' ? 'Invalid sender email' : 'Save failed', 'err');
    } finally {
      setSaving(false);
    }
  };

  const test = async () => {
    setTesting(true);
    try {
      const res = await api.testMail(testTo || undefined);
      flash(`${t.testSent} (${res.to})`);
    } catch {
      flash(t.testFailed, 'err');
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="form-shell">
      <div className="form-head">
        <h2>{t.emailSettings}</h2>
        <span className={`role-chip`} style={{ background: cfg.enabled ? '#103c25' : '#62625b' }}>
          {cfg.enabled ? t.mailStatusOn : t.mailStatusOff}
        </span>
      </div>
      <p style={{ color: 'var(--mute)', marginTop: -8, fontWeight: 600, fontSize: 13 }}>
        {t.emailSettingsHint} {cfg.source === 'env' ? t.sourceEnv : cfg.source === 'db' ? t.sourceDb : ''}
      </p>

      <form onSubmit={save}>
        <fieldset className="fieldset">
          <span className="legend">SMTP Server</span>
          <div className="grid-fields">
            <div className="field">
              <label>{t.smtpHost}</label>
              <input value={cfg.host || ''} placeholder="smtp.gmail.com" onChange={(e) => set('host', e.target.value)} />
            </div>
            <div className="field">
              <label>{t.smtpPort}</label>
              <input value={cfg.port || ''} placeholder="587" onChange={(e) => set('port', e.target.value)} />
            </div>
            <div className="field">
              <label>{t.smtpUser}</label>
              <input value={cfg.user || ''} autoComplete="off" onChange={(e) => set('user', e.target.value)} />
            </div>
            <div className="field">
              <label>{t.smtpPass} <span style={{ color: 'var(--ash)', fontWeight: 500 }}>{t.smtpPassKeep}</span></label>
              <input type="password" value={pass} autoComplete="new-password"
                placeholder={cfg.hasPassword ? '••••••••' : ''} onChange={(e) => setPass(e.target.value)} />
            </div>
            <div className="field full" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input id="secure" type="checkbox" checked={!!cfg.secure} style={{ width: 'auto' }}
                onChange={(e) => set('secure', e.target.checked)} />
              <label htmlFor="secure" style={{ margin: 0 }}>{t.smtpSecure}</label>
            </div>
          </div>
        </fieldset>

        <fieldset className="fieldset">
          <span className="legend">{t.senderName} / {t.senderEmail}</span>
          <div className="grid-fields">
            <div className="field">
              <label>{t.senderName}</label>
              <input value={cfg.sender_name || ''} placeholder="QA Corrective Action" onChange={(e) => set('sender_name', e.target.value)} />
            </div>
            <div className="field">
              <label>{t.senderEmail}</label>
              <input type="email" value={cfg.sender_email || ''} placeholder="qa@company.com" onChange={(e) => set('sender_email', e.target.value)} />
            </div>
          </div>
        </fieldset>

        <div className="form-actions" style={{ position: 'static' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginRight: 'auto' }}>
            <input type="email" placeholder={t.testTo + ' (' + t.email + ')'} value={testTo}
              onChange={(e) => setTestTo(e.target.value)}
              style={{ border: '1px solid var(--hairline)', borderRadius: 9, padding: '9px 12px', fontSize: 13.5, minWidth: 220 }} />
            <button type="button" className="cta ghost" onClick={test} disabled={testing || !cfg.enabled}>
              {testing ? t.saving : t.sendTest}
            </button>
          </div>
          <button type="submit" className="cta" disabled={saving}>{saving ? t.saving : t.saveSettings}</button>
        </div>
      </form>

      <div className="fieldset" style={{ marginTop: 22 }}>
        <span className="legend">{t.rosterTitle}</span>
        <p style={{ color: 'var(--mute)', fontSize: 13, fontWeight: 600, marginTop: 4 }}>{t.rosterHintText}</p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <div style={{ fontSize: 13.5 }}>
            <b>{roster?.count ?? 0}</b> {t.rosterCount}
            {roster?.filename && (
              <span style={{ color: 'var(--ash)', fontSize: 12, marginLeft: 8 }}>
                {roster.filename} · {roster.updated_at?.slice(0, 16).replace('T', ' ')}
              </span>
            )}
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <input type="file" accept=".xlsx,.xls" ref={rosterFileRef} style={{ display: 'none' }} onChange={onRosterFile} />
            <button type="button" className="cta ghost" disabled={rosterBusy} onClick={() => rosterFileRef.current?.click()}>
              📤 {rosterBusy ? t.uploading : t.rosterUpload}
            </button>
          </div>
        </div>

        {roster?.manual?.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div className="section-title">{t.manualEntries} ({roster.manual.length})</div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>ID</th><th>{t.name}</th><th>Sup / N-5</th><th>N-4</th><th>Section</th><th></th></tr>
                </thead>
                <tbody>
                  {roster.manual.map((m) => (
                    <tr key={m.employee_id}>
                      <td style={{ fontSize: 12, color: 'var(--mute)' }}>{m.employee_id}</td>
                      <td style={{ fontWeight: 700 }}>{m.fullname}</td>
                      <td>{m.n5_name || '—'}</td>
                      <td>{m.n4_name || '—'}</td>
                      <td>{m.section || m.division || '—'}</td>
                      <td>
                        <button type="button" className="icon-btn danger"
                          onClick={async () => {
                            if (!confirm(`${t.del}: ${m.fullname}?`)) return;
                            await api.deleteManualEmployee(m.employee_id);
                            api.rosterInfo().then(setRoster);
                          }}>
                          {t.del}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
