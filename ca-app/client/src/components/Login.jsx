import { useState } from 'react';
import { api, setToken } from '../api';
import { useI18n } from '../i18n';

export default function Login({ onLoggedIn }) {
  const { lang, t, setLang } = useI18n();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const { token, user } = await api.login(email, password);
      setToken(token);
      onLoggedIn(user);
    } catch (ex) {
      setErr(ex.body?.error?.startsWith('account_') ? t.accountDisabled : t.loginError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen">
      <button className="lang-btn auth-lang" onClick={() => setLang(lang === 'th' ? 'en' : 'th')}>{t.lang}</button>
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-logo"><b>QA</b> Corrective Action</div>
        <div className="auth-sub">{t.welcome}</div>
        <div className="field">
          <label>{t.email}</label>
          <input type="email" value={email} autoFocus autoComplete="username"
            onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label>{t.password}</label>
          <input type="password" value={password} autoComplete="current-password"
            onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {err && <div className="auth-err">{err}</div>}
        <button className="cta auth-submit" type="submit" disabled={busy}>
          {busy ? t.signingIn : t.signIn}
        </button>
      </form>
    </div>
  );
}
