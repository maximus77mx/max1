import express from 'express';
import bcrypt from 'bcryptjs';
import { signToken, permsFor, ROLE_LABELS, authRequired } from '../auth.js';
import { logAudit } from '../audit.js';

export default function authRoutes(db) {
  const r = express.Router();

  // POST /api/auth/login
  r.post('/login', (req, res) => {
    const email = (req.body.email || '').trim().toLowerCase();
    const password = req.body.password || '';
    const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
    if (!user || !user.password_hash) return res.status(401).json({ error: 'invalid_credentials' });
    if (user.status !== 'active') return res.status(403).json({ error: 'account_' + user.status });
    if (!bcrypt.compareSync(password, user.password_hash)) return res.status(401).json({ error: 'invalid_credentials' });
    db.prepare(`UPDATE users SET last_login = datetime('now') WHERE id = ?`).run(user.id);
    logAudit(db, user, 'auth.login', { entity: 'user', ref: user.email });
    res.json({
      token: signToken(user),
      user: { id: user.id, email: user.email, name: user.name, role: user.role, perms: permsFor(user.role) },
    });
  });

  // POST /api/auth/change-password  { current_password, new_password } (self-service)
  r.post('/change-password', authRequired(db), (req, res) => {
    const { current_password, new_password } = req.body;
    if (!new_password || new_password.length < 6) return res.status(400).json({ error: 'weak_password' });
    const user = db.prepare('SELECT * FROM users WHERE id = ?').get(req.user.id);
    if (!user.password_hash || !bcrypt.compareSync(current_password || '', user.password_hash))
      return res.status(400).json({ error: 'wrong_current_password' });
    db.prepare('UPDATE users SET password_hash = ? WHERE id = ?').run(bcrypt.hashSync(new_password, 10), user.id);
    logAudit(db, req.user, 'auth.change_password', { entity: 'user', ref: user.email });
    res.json({ ok: true });
  });

  // GET /api/auth/me
  r.get('/me', authRequired(db), (req, res) => {
    res.json({
      user: { ...req.user, perms: permsFor(req.user.role) },
      roleLabels: ROLE_LABELS,
    });
  });

  // GET /api/auth/invite/:token — validate an invite (used by the accept screen)
  r.get('/invite/:token', (req, res) => {
    const inv = db.prepare('SELECT * FROM invites WHERE token = ?').get(req.params.token);
    if (!inv) return res.status(404).json({ error: 'invite_not_found' });
    if (inv.accepted_at) return res.status(410).json({ error: 'invite_used' });
    if (inv.expires_at && new Date(inv.expires_at) < new Date()) return res.status(410).json({ error: 'invite_expired' });
    res.json({ email: inv.email, role: inv.role, purpose: inv.purpose || 'invite' });
  });

  // POST /api/auth/accept-invite — set name + password from an invite token
  r.post('/accept-invite', (req, res) => {
    const { token, password, name } = req.body;
    if (!password || password.length < 6) return res.status(400).json({ error: 'weak_password' });
    const inv = db.prepare('SELECT * FROM invites WHERE token = ?').get(token);
    if (!inv) return res.status(404).json({ error: 'invite_not_found' });
    if (inv.accepted_at) return res.status(410).json({ error: 'invite_used' });
    if (inv.expires_at && new Date(inv.expires_at) < new Date()) return res.status(410).json({ error: 'invite_expired' });

    const hash = bcrypt.hashSync(password, 10);
    const existing = db.prepare('SELECT * FROM users WHERE email = ?').get(inv.email);
    const isReset = inv.purpose === 'reset';
    let user;
    if (existing) {
      // A password reset keeps the existing role; an invite applies the invited role.
      const role = isReset ? existing.role : inv.role;
      db.prepare(`UPDATE users SET password_hash = ?, name = COALESCE(?, name), role = ?, status = 'active' WHERE id = ?`)
        .run(hash, name || null, role, existing.id);
      user = db.prepare('SELECT * FROM users WHERE id = ?').get(existing.id);
    } else {
      const info = db.prepare(`INSERT INTO users (email, name, password_hash, role, status) VALUES (?, ?, ?, ?, 'active')`)
        .run(inv.email, name || null, hash, inv.role);
      user = db.prepare('SELECT * FROM users WHERE id = ?').get(info.lastInsertRowid);
    }
    db.prepare(`UPDATE invites SET accepted_at = datetime('now') WHERE id = ?`).run(inv.id);
    logAudit(db, user, isReset ? 'auth.password_reset' : 'user.accept_invite', { entity: 'user', ref: user.email });
    res.json({
      token: signToken(user),
      user: { id: user.id, email: user.email, name: user.name, role: user.role, perms: permsFor(user.role) },
    });
  });

  return r;
}
