import { useState } from 'react';
import { api } from '../api';
import { useI18n } from '../i18n';

export default function ChangePassword({ onClose, flash }) {
  const { t } = useI18n();
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [next2, setNext2] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr('');
    if (next.length < 6) return setErr(t.pwTooShort);
    if (next !== next2) return setErr(t.pwMismatch);
    setBusy(true);
    try {
      await api.changePassword(cur, next);
      flash(t.changePwOk);
      onClose();
    } catch (ex) {
      setErr(ex.body?.error === 'weak_password' ? t.pwTooShort : t.wrongCurrent);
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h3 style={{ marginTop: 0 }}>{t.changePassword}</h3>
        <div className="field">
          <label>{t.currentPassword}</label>
          <input type="password" value={cur} autoFocus autoComplete="current-password" onChange={(e) => setCur(e.target.value)} required />
        </div>
        <div className="field">
          <label>{t.newPassword}</label>
          <input type="password" value={next} autoComplete="new-password" onChange={(e) => setNext(e.target.value)} required />
        </div>
        <div className="field">
          <label>{t.confirmPassword}</label>
          <input type="password" value={next2} autoComplete="new-password" onChange={(e) => setNext2(e.target.value)} required />
        </div>
        {err && <div className="auth-err">{err}</div>}
        <div className="form-actions" style={{ position: 'static', padding: 0, marginTop: 6 }}>
          <button type="button" className="cta ghost" onClick={onClose}>{t.cancel}</button>
          <button type="submit" className="cta" disabled={busy}>{busy ? t.saving : t.save}</button>
        </div>
      </form>
    </div>
  );
}
