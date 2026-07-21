import express from 'express';
import { authRequired, requirePerm } from '../auth.js';
import { getMailConfigSafe, saveMailConfig } from '../settings.js';
import { sendTestEmail } from '../mailer.js';
import { logAudit } from '../audit.js';

export default function settingsRoutes(db) {
  const r = express.Router();
  r.use(authRequired(db), requirePerm('settings.manage'));

  // GET /api/settings/mail — current SMTP config (password never returned)
  r.get('/mail', (_req, res) => {
    res.json(getMailConfigSafe(db));
  });

  // PUT /api/settings/mail — save SMTP config
  r.put('/mail', (req, res) => {
    const { host, port, sender_email } = req.body;
    if (host && port && sender_email && !/^\S+@\S+\.\S+$/.test(sender_email))
      return res.status(400).json({ error: 'invalid_sender_email' });
    saveMailConfig(db, req.body);
    logAudit(db, req.user, 'settings.mail_update', { entity: 'settings', ref: host || '(cleared)' });
    res.json(getMailConfigSafe(db));
  });

  // POST /api/settings/mail/test — send a test email to the current user
  r.post('/mail/test', async (req, res) => {
    const to = req.body.to || req.user.email;
    try {
      await sendTestEmail(db, to);
      logAudit(db, req.user, 'settings.mail_test', { entity: 'settings', ref: to });
      res.json({ ok: true, to });
    } catch (e) {
      res.status(400).json({ error: e.message === 'smtp_not_configured' ? 'smtp_not_configured' : 'send_failed', detail: e.message });
    }
  });

  return r;
}
