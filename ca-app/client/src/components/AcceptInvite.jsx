import { useEffect, useState } from 'react';
import { api, setToken } from '../api';
import { useI18n } from '../i18n';
import { ROLE_BADGE } from '../auth';

export default function AcceptInvite({ token, onAccepted }) {
  const { lang, t, setLang } = useI18n();
  const [invite, setInvite] = useState(null);
  const [invalid, setInvalid] = useState(false);
  const [name, setName] = useState('');
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.invite(token).then(setInvite).catch(() => setInvalid(true));
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    setErr('');
    if (pw.length < 6) return setErr(t.pwTooShort);
    if (pw !== pw2) return setErr(t.pwMismatch);
    setBusy(true);
    try {
      const { token: jwt, user } = await api.acceptInvite({ token, password: pw, name });
      setToken(jwt);
      onAccepted(user);
    } catch (ex) {
      setErr(ex.body?.error === 'weak_password' ? t.pwTooShort : t.inviteInvalid);
      setBusy(false);
    }
  };

  if (invalid) {
    return (
      <div className="auth-screen">
        <div className="auth-card"><div className="auth-logo"><b>QA</b> Corrective Action</div>
          <div className="auth-err" style={{ marginTop: 12 }}>{t.inviteInvalid}</div>
          <button className="cta auth-submit" onClick={() => (window.location.href = '/')}>{t.login}</button>
        </div>
      </div>
    );
  }
  if (!invite) return <div className="loading">Loading…</div>;
  const rb = ROLE_BADGE[invite.role];
  const isReset = invite.purpose === 'reset';

  return (
    <div className="auth-screen">
      <button className="lang-btn auth-lang" onClick={() => setLang(lang === 'th' ? 'en' : 'th')}>{t.lang}</button>
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-logo"><b>QA</b> Corrective Action</div>
        <div className="auth-sub">{isReset ? t.resetTitle : t.acceptTitle}</div>
        <div className="invite-meta">
          <span>{invite.email}</span>
          <span className="role-chip" style={{ background: rb.color }}>{rb.label}</span>
        </div>
        {!isReset && (
          <div className="field">
            <label>{t.name}</label>
            <input value={name} autoFocus onChange={(e) => setName(e.target.value)} />
          </div>
        )}
        <div className="field">
          <label>{t.setPassword}</label>
          <input type="password" value={pw} autoComplete="new-password" onChange={(e) => setPw(e.target.value)} required />
        </div>
        <div className="field">
          <label>{t.confirmPassword}</label>
          <input type="password" value={pw2} autoComplete="new-password" onChange={(e) => setPw2(e.target.value)} required />
        </div>
        {err && <div className="auth-err">{err}</div>}
        <button className="cta auth-submit" type="submit" disabled={busy}>
          {busy ? t.signingIn : t.createAccount}
        </button>
      </form>
    </div>
  );
}
