import express from 'express';
import crypto from 'crypto';
import { authRequired, requirePerm, canManageUser, ASSIGNABLE_ROLES, ROLES } from '../auth.js';
import { sendInviteEmail, mailEnabled } from '../mailer.js';
import { logAudit } from '../audit.js';

function inviteBase(req) {
  return process.env.APP_URL || req.headers.origin || `${req.protocol}://${req.get('host')}`;
}

export default function userRoutes(db) {
  const r = express.Router();
  r.use(authRequired(db), requirePerm('users.manage'));

  // GET /api/users — list users + pending invites
  r.get('/', (req, res) => {
    const users = db
      .prepare('SELECT id, email, name, role, status, created_at, last_login FROM users ORDER BY id')
      .all();
    const invites = db
      .prepare("SELECT id, email, role, invited_by, created_at, expires_at FROM invites WHERE accepted_at IS NULL ORDER BY id DESC")
      .all()
      .filter((i) => !i.expires_at || new Date(i.expires_at) >= new Date());
    res.json({
      users,
      pendingInvites: invites,
      assignableRoles: ASSIGNABLE_ROLES[req.user.role] || [],
      mailEnabled,
    });
  });

  // POST /api/users/invite  { email, role }
  r.post('/invite', async (req, res) => {
    const email = (req.body.email || '').trim().toLowerCase();
    const role = req.body.role;
    if (!email || !/^\S+@\S+\.\S+$/.test(email)) return res.status(400).json({ error: 'invalid_email' });
    const allowed = ASSIGNABLE_ROLES[req.user.role] || [];
    if (!allowed.includes(role)) return res.status(403).json({ error: 'role_not_allowed' });

    const existing = db.prepare('SELECT * FROM users WHERE email = ?').get(email);
    if (existing && existing.status === 'active') return res.status(409).json({ error: 'user_exists' });

    const token = crypto.randomBytes(24).toString('hex');
    const expires = new Date(Date.now() + 7 * 86400000).toISOString();
    db.prepare('INSERT INTO invites (email, role, token, invited_by, expires_at) VALUES (?, ?, ?, ?, ?)')
      .run(email, role, token, req.user.email, expires);
    // Create a placeholder "invited" user row so it shows in the list.
    if (!existing) {
      db.prepare("INSERT INTO users (email, role, status) VALUES (?, ?, 'invited')").run(email, role);
    } else {
      db.prepare("UPDATE users SET role = ?, status = 'invited' WHERE id = ?").run(role, existing.id);
    }

    const link = `${inviteBase(req)}/?invite=${token}`;
    const result = await sendInviteEmail({ to: email, link, inviterName: req.user.name || req.user.email, role });
    logAudit(db, req.user, 'user.invite', { entity: 'user', ref: email, detail: `role: ${role}` });
    res.status(201).json({ email, role, delivered: result.delivered, link: result.delivered ? undefined : link });
  });

  // POST /api/users/:id/reset — admin-initiated password reset (creates a reset link)
  r.post('/:id/reset', async (req, res) => {
    const target = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
    if (!target) return res.status(404).json({ error: 'not_found' });
    if (!canManageUser(req.user.role, target.role)) return res.status(403).json({ error: 'forbidden' });
    const token = crypto.randomBytes(24).toString('hex');
    const expires = new Date(Date.now() + 7 * 86400000).toISOString();
    db.prepare('INSERT INTO invites (email, role, token, invited_by, purpose, expires_at) VALUES (?, ?, ?, ?, ?, ?)')
      .run(target.email, target.role, token, req.user.email, 'reset', expires);
    const link = `${inviteBase(req)}/?invite=${token}`;
    const result = await sendInviteEmail({ to: target.email, link, inviterName: req.user.name || req.user.email, role: target.role, reset: true });
    logAudit(db, req.user, 'user.reset_password', { entity: 'user', ref: target.email });
    res.json({ delivered: result.delivered, link: result.delivered ? undefined : link });
  });

  // POST /api/users/:id/resend
  r.post('/:id/resend', async (req, res) => {
    const target = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
    if (!target) return res.status(404).json({ error: 'not_found' });
    if (!canManageUser(req.user.role, target.role)) return res.status(403).json({ error: 'forbidden' });
    const token = crypto.randomBytes(24).toString('hex');
    const expires = new Date(Date.now() + 7 * 86400000).toISOString();
    db.prepare('INSERT INTO invites (email, role, token, invited_by, expires_at) VALUES (?, ?, ?, ?, ?)')
      .run(target.email, target.role, token, req.user.email, expires);
    db.prepare("UPDATE users SET status = 'invited' WHERE id = ?").run(target.id);
    const link = `${inviteBase(req)}/?invite=${token}`;
    const result = await sendInviteEmail({ to: target.email, link, inviterName: req.user.name || req.user.email, role: target.role });
    res.json({ delivered: result.delivered, link: result.delivered ? undefined : link });
  });

  // PATCH /api/users/:id/role  { role }
  r.patch('/:id/role', (req, res) => {
    const target = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
    if (!target) return res.status(404).json({ error: 'not_found' });
    if (!canManageUser(req.user.role, target.role)) return res.status(403).json({ error: 'forbidden' });
    const role = req.body.role;
    const allowed = ASSIGNABLE_ROLES[req.user.role] || [];
    if (!allowed.includes(role)) return res.status(403).json({ error: 'role_not_allowed' });
    db.prepare('UPDATE users SET role = ? WHERE id = ?').run(role, target.id);
    logAudit(db, req.user, 'user.role_change', { entity: 'user', ref: target.email, detail: `${target.role} → ${role}` });
    res.json({ ok: true });
  });

  // PATCH /api/users/:id/status  { status: active|disabled }
  r.patch('/:id/status', (req, res) => {
    const target = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
    if (!target) return res.status(404).json({ error: 'not_found' });
    if (!canManageUser(req.user.role, target.role)) return res.status(403).json({ error: 'forbidden' });
    if (target.id === req.user.id) return res.status(400).json({ error: 'cannot_change_self' });
    const status = req.body.status === 'disabled' ? 'disabled' : 'active';
    if (status === 'active' && !target.password_hash) return res.status(400).json({ error: 'not_accepted_yet' });
    db.prepare('UPDATE users SET status = ? WHERE id = ?').run(status, target.id);
    logAudit(db, req.user, 'user.status_change', { entity: 'user', ref: target.email, detail: status });
    res.json({ ok: true });
  });

  // DELETE /api/users/:id
  r.delete('/:id', (req, res) => {
    const target = db.prepare('SELECT * FROM users WHERE id = ?').get(req.params.id);
    if (!target) return res.status(404).json({ error: 'not_found' });
    if (!canManageUser(req.user.role, target.role)) return res.status(403).json({ error: 'forbidden' });
    if (target.id === req.user.id) return res.status(400).json({ error: 'cannot_delete_self' });
    db.prepare('DELETE FROM users WHERE id = ?').run(target.id);
    db.prepare('DELETE FROM invites WHERE email = ?').run(target.email);
    logAudit(db, req.user, 'user.remove', { entity: 'user', ref: target.email });
    res.json({ ok: true });
  });

  return r;
}
