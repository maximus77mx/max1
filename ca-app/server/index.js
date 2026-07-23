import './env.js'; // must be first — loads server/.env before db bootstrap
import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import crypto from 'crypto';
import multer from 'multer';
import { fileURLToPath } from 'url';
import db from './db.js';
import { FIELDS, FIELD_KEYS, GROUPS, LISTS, SLA_DAYS } from './fields.js';
import { authRequired, requirePerm, can, isScopedToOwn } from './auth.js';
import { logAudit } from './audit.js';
import authRoutes from './routes/authRoutes.js';
import userRoutes from './routes/userRoutes.js';
import settingsRoutes from './routes/settingsRoutes.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors());
app.use(express.json({ limit: '2mb' }));

// ---- Evidence upload storage ----
const UPLOAD_DIR = path.join(__dirname, 'data', 'uploads');
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });
const upload = multer({
  storage: multer.diskStorage({
    destination: UPLOAD_DIR,
    filename: (_req, file, cb) => cb(null, crypto.randomBytes(10).toString('hex') + path.extname(file.originalname)),
  }),
  limits: { fileSize: 15 * 1024 * 1024 }, // 15 MB per file
});
// Multer decodes original filenames as latin1 — restore UTF-8 (Thai names).
const fixName = (n) => Buffer.from(n, 'latin1').toString('utf8');

// ---- Auth & user management ----
app.use('/api/auth', authRoutes(db));
app.use('/api/users', userRoutes(db));
app.use('/api/settings', settingsRoutes(db));

const api = express.Router();
// Everything below requires a logged-in user.
api.use(authRequired(db));

// --- Metadata: field schema, groups, dropdown lists, SLA matrix ---
api.get('/meta', (_req, res) => {
  res.json({ fields: FIELDS, groups: GROUPS, lists: LISTS, sla: SLA_DAYS });
});

// --- User options for the Owner picker (editors+ only) ---
api.get('/user-options', (req, res) => {
  if (!can(req.user.role, 'records.create') && !can(req.user.role, 'records.edit'))
    return res.status(403).json({ error: 'forbidden' });
  const rows = db
    .prepare("SELECT id, email, name, role FROM users WHERE status != 'disabled' ORDER BY name, email")
    .all();
  res.json(rows);
});

// --- Suggest next CA ID like CA-2026-091 ---
api.get('/next-id', (_req, res) => {
  const rows = db.prepare('SELECT ca_id FROM ca_records').all();
  const year = new Date().getFullYear();
  let max = 0;
  for (const r of rows) {
    const m = /^CA-(\d{4})-(\d+)/.exec(r.ca_id || '');
    if (m && Number(m[1]) === year) max = Math.max(max, Number(m[2]));
  }
  const next = `CA-${year}-${String(max + 1).padStart(3, '0')}`;
  res.json({ next_id: next });
});

// ---- Shared record filtering (list + CSV export) ----
// Owner-role users are scoped server-side to records assigned to them.
function buildWhere(req) {
  const { status, level, product, priority, q } = req.query;
  const where = [];
  const params = {};
  if (status) { where.push('status = @status'); params.status = status; }
  if (level) { where.push('level = @level'); params.level = level; }
  if (product) { where.push('product = @product'); params.product = product; }
  if (priority) { where.push('priority = @priority'); params.priority = priority; }
  if (q) {
    where.push('(ca_id LIKE @q OR nonconformity LIKE @q OR corrective_action LIKE @q OR root_cause LIKE @q)');
    params.q = `%${q}%`;
  }
  if (isScopedToOwn(req.user.role)) {
    where.push('owner_user_id = @uid');
    params.uid = req.user.id;
  }
  return { where, params };
}

// Can this user see this specific record?
function canSeeRecord(req, rec) {
  if (!isScopedToOwn(req.user.role)) return true;
  return rec.owner_user_id === req.user.id;
}

// Can this user modify/attach on this record?
function canTouchRecord(req, rec) {
  if (can(req.user.role, 'records.edit')) return true;
  return can(req.user.role, 'records.edit_own') && rec.owner_user_id === req.user.id;
}

// --- List records (optional filters; owner-scoped) ---
api.get('/records', requirePerm('records.view'), (req, res) => {
  const { where, params } = buildWhere(req);
  const sql = `SELECT * FROM ca_records ${where.length ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY ca_id`;
  res.json(db.prepare(sql).all(params));
});

api.get('/records/:id', requirePerm('records.view'), (req, res) => {
  const row = db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id);
  if (!row || !canSeeRecord(req, row)) return res.status(404).json({ error: 'not found' });
  res.json(row);
});

function pickFields(body) {
  const clean = {};
  for (const k of FIELD_KEYS) {
    let v = body[k];
    if (v === '' || v === undefined) v = null;
    clean[k] = v;
  }
  return clean;
}

function validate(data) {
  const errors = [];
  for (const f of FIELDS) {
    if (f.required && !data[f.key]) errors.push({ field: f.key, msg: `${f.en} is required` });
    if (f.type === 'select' && data[f.key] && !LISTS[f.list].includes(data[f.key])) {
      errors.push({ field: f.key, msg: `Invalid value for ${f.en}` });
    }
  }
  return errors;
}

// Validate & normalize the owner_user_id assignment (null = unassigned).
function normalizeOwnerId(body) {
  const v = body.owner_user_id;
  if (v === undefined || v === null || v === '') return { ok: true, value: null };
  const u = db.prepare('SELECT id FROM users WHERE id = ?').get(v);
  if (!u) return { ok: false };
  return { ok: true, value: u.id };
}

api.post('/records', requirePerm('records.create'), (req, res) => {
  const data = pickFields(req.body);
  const errors = validate(data);
  if (errors.length) return res.status(400).json({ errors });
  const owner = normalizeOwnerId(req.body);
  if (!owner.ok) return res.status(400).json({ errors: [{ field: 'owner_user_id', msg: 'Unknown owner user' }] });
  const dup = db.prepare('SELECT id FROM ca_records WHERE ca_id = ?').get(data.ca_id);
  if (dup) return res.status(409).json({ errors: [{ field: 'ca_id', msg: 'CA ID already exists' }] });
  const cols = [...FIELD_KEYS, 'owner_user_id'];
  const info = db
    .prepare(`INSERT INTO ca_records (${cols.map((c) => `"${c}"`).join(',')}) VALUES (${cols.map((c) => `@${c}`).join(',')})`)
    .run({ ...data, owner_user_id: owner.value });
  logAudit(db, req.user, 'record.create', { entity: 'record', ref: data.ca_id });
  res.status(201).json(db.prepare('SELECT * FROM ca_records WHERE id = ?').get(info.lastInsertRowid));
});

api.put('/records/:id', requirePerm('records.edit'), (req, res) => {
  const existing = db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id);
  if (!existing) return res.status(404).json({ error: 'not found' });
  const data = pickFields(req.body);
  const errors = validate(data);
  if (errors.length) return res.status(400).json({ errors });
  const owner = normalizeOwnerId(req.body);
  if (!owner.ok) return res.status(400).json({ errors: [{ field: 'owner_user_id', msg: 'Unknown owner user' }] });
  const dup = db.prepare('SELECT id FROM ca_records WHERE ca_id = ? AND id != ?').get(data.ca_id, req.params.id);
  if (dup) return res.status(409).json({ errors: [{ field: 'ca_id', msg: 'CA ID already exists' }] });
  const setClause = [...FIELD_KEYS.map((c) => `"${c}" = @${c}`), 'owner_user_id = @owner_user_id'].join(', ');
  db.prepare(`UPDATE ca_records SET ${setClause}, updated_at = datetime('now') WHERE id = @id`)
    .run({ ...data, owner_user_id: owner.value, id: req.params.id });
  const changed = FIELD_KEYS.filter((k) => (existing[k] ?? null) !== (data[k] ?? null));
  logAudit(db, req.user, 'record.update', { entity: 'record', ref: data.ca_id, detail: changed.length ? `fields: ${changed.join(', ')}` : null });
  // Status changes go on the record's timeline too.
  if (existing.status !== data.status) {
    db.prepare(
      "INSERT INTO ca_updates (record_id, ca_id, user_email, user_name, kind, old_status, new_status) VALUES (?, ?, ?, ?, 'status', ?, ?)"
    ).run(existing.id, data.ca_id, req.user.email, req.user.name, existing.status, data.status);
  }
  res.json(db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id));
});

api.delete('/records/:id', requirePerm('records.delete'), (req, res) => {
  const existing = db.prepare('SELECT ca_id FROM ca_records WHERE id = ?').get(req.params.id);
  const info = db.prepare('DELETE FROM ca_records WHERE id = ?').run(req.params.id);
  if (!info.changes) return res.status(404).json({ error: 'not found' });
  // Clean up attached evidence files + timeline.
  for (const ev of db.prepare('SELECT * FROM evidence WHERE record_id = ?').all(req.params.id)) {
    try { fs.unlinkSync(path.join(UPLOAD_DIR, ev.stored_name)); } catch { /* already gone */ }
  }
  db.prepare('DELETE FROM evidence WHERE record_id = ?').run(req.params.id);
  db.prepare('DELETE FROM ca_updates WHERE record_id = ?').run(req.params.id);
  logAudit(db, req.user, 'record.delete', { entity: 'record', ref: existing?.ca_id });
  res.json({ ok: true });
});

// ---- Owner progress update (limited scope, no closing) ----
api.patch('/records/:id/progress', (req, res) => {
  const rec = db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id);
  if (!rec || !canSeeRecord(req, rec)) return res.status(404).json({ error: 'not found' });
  if (!canTouchRecord(req, rec)) return res.status(403).json({ error: 'forbidden' });
  const { note, result_after, status } = req.body;
  if (!note && result_after === undefined && !status) return res.status(400).json({ error: 'nothing_to_update' });
  // Owners may only move work forward to In-progress / Verifying — closing stays with QA.
  if (status && !['In-progress', 'Verifying'].includes(status)) return res.status(400).json({ error: 'status_not_allowed' });
  if (status && rec.status === 'Closed') return res.status(400).json({ error: 'record_closed' });

  const sets = [];
  const params = { id: rec.id };
  if (result_after !== undefined) { sets.push('result_after = @result_after'); params.result_after = result_after || null; }
  if (status) { sets.push('status = @status'); params.status = status; }
  if (sets.length) db.prepare(`UPDATE ca_records SET ${sets.join(', ')}, updated_at = datetime('now') WHERE id = @id`).run(params);

  if (note || result_after !== undefined) {
    db.prepare(
      "INSERT INTO ca_updates (record_id, ca_id, user_email, user_name, kind, note) VALUES (?, ?, ?, ?, 'note', ?)"
    ).run(rec.id, rec.ca_id, req.user.email, req.user.name, note || `ผลหลังแก้: ${result_after}`);
  }
  if (status && status !== rec.status) {
    db.prepare(
      "INSERT INTO ca_updates (record_id, ca_id, user_email, user_name, kind, old_status, new_status) VALUES (?, ?, ?, ?, 'status', ?, ?)"
    ).run(rec.id, rec.ca_id, req.user.email, req.user.name, rec.status, status);
  }
  logAudit(db, req.user, 'record.progress', { entity: 'record', ref: rec.ca_id, detail: status ? `status → ${status}` : 'progress note' });
  res.json(db.prepare('SELECT * FROM ca_records WHERE id = ?').get(rec.id));
});

// ---- Timeline ----
api.get('/records/:id/updates', requirePerm('records.view'), (req, res) => {
  const rec = db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id);
  if (!rec || !canSeeRecord(req, rec)) return res.status(404).json({ error: 'not found' });
  res.json(db.prepare('SELECT * FROM ca_updates WHERE record_id = ? ORDER BY id DESC').all(rec.id));
});

// ---- Evidence attachments ----
api.get('/records/:id/evidence', requirePerm('records.view'), (req, res) => {
  const rec = db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id);
  if (!rec || !canSeeRecord(req, rec)) return res.status(404).json({ error: 'not found' });
  res.json(db.prepare('SELECT id, record_id, ca_id, original_name, size, mime, uploaded_by, ts FROM evidence WHERE record_id = ? ORDER BY id DESC').all(rec.id));
});

api.post('/records/:id/evidence', upload.single('file'), (req, res) => {
  const rec = db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id);
  if (!rec || !canSeeRecord(req, rec)) return res.status(404).json({ error: 'not found' });
  if (!canTouchRecord(req, rec)) return res.status(403).json({ error: 'forbidden' });
  if (!req.file) return res.status(400).json({ error: 'no_file' });
  const original = fixName(req.file.originalname);
  const info = db.prepare(
    'INSERT INTO evidence (record_id, ca_id, original_name, stored_name, size, mime, uploaded_by) VALUES (?, ?, ?, ?, ?, ?, ?)'
  ).run(rec.id, rec.ca_id, original, req.file.filename, req.file.size, req.file.mimetype, req.user.email);
  db.prepare(
    "INSERT INTO ca_updates (record_id, ca_id, user_email, user_name, kind, note) VALUES (?, ?, ?, ?, 'file', ?)"
  ).run(rec.id, rec.ca_id, req.user.email, req.user.name, original);
  logAudit(db, req.user, 'evidence.upload', { entity: 'record', ref: rec.ca_id, detail: original });
  res.status(201).json(db.prepare('SELECT id, record_id, ca_id, original_name, size, mime, uploaded_by, ts FROM evidence WHERE id = ?').get(info.lastInsertRowid));
});

api.get('/evidence/:id/download', requirePerm('records.view'), (req, res) => {
  const ev = db.prepare('SELECT * FROM evidence WHERE id = ?').get(req.params.id);
  if (!ev) return res.status(404).json({ error: 'not found' });
  const rec = db.prepare('SELECT * FROM ca_records WHERE id = ?').get(ev.record_id);
  if (!rec || !canSeeRecord(req, rec)) return res.status(404).json({ error: 'not found' });
  const full = path.join(UPLOAD_DIR, ev.stored_name);
  if (!fs.existsSync(full)) return res.status(410).json({ error: 'file_missing' });
  res.download(full, ev.original_name);
});

api.delete('/evidence/:id', (req, res) => {
  const ev = db.prepare('SELECT * FROM evidence WHERE id = ?').get(req.params.id);
  if (!ev) return res.status(404).json({ error: 'not found' });
  const isUploader = ev.uploaded_by === req.user.email;
  if (!isUploader && !can(req.user.role, 'records.edit')) return res.status(403).json({ error: 'forbidden' });
  try { fs.unlinkSync(path.join(UPLOAD_DIR, ev.stored_name)); } catch { /* already gone */ }
  db.prepare('DELETE FROM evidence WHERE id = ?').run(ev.id);
  logAudit(db, req.user, 'evidence.delete', { entity: 'record', ref: ev.ca_id, detail: ev.original_name });
  res.json({ ok: true });
});

// ---- CSV export (respects filters + owner scoping) ----
api.get('/export/records.csv', requirePerm('records.export'), (req, res) => {
  const { where, params } = buildWhere(req);
  const rows = db.prepare(`SELECT * FROM ca_records ${where.length ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY ca_id`).all(params);
  const lang = req.query.lang === 'en' ? 'en' : 'th';
  const esc = (v) => (v == null ? '' : `"${String(v).replace(/"/g, '""')}"`);
  const header = FIELDS.map((f) => esc(f[lang])).join(',');
  const lines = rows.map((r) => FIELD_KEYS.map((k) => esc(r[k])).join(','));
  const csv = '﻿' + [header, ...lines].join('\r\n'); // BOM so Thai opens correctly in Excel
  logAudit(db, req.user, 'record.export_csv', { entity: 'record', detail: `${rows.length} rows` });
  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename="ca-register.csv"');
  res.send(csv);
});

// --- Dashboard aggregations (owner-scoped for owner role) ---
function countBy(rows, key) {
  const m = {};
  for (const r of rows) {
    const v = r[key] || '(blank)';
    m[v] = (m[v] || 0) + 1;
  }
  return m;
}

const OPEN_STATUSES = ['Open', 'In-progress', 'Verifying', 'Reopened'];

api.get('/stats', requirePerm('dashboard.view'), (req, res) => {
  const rows = isScopedToOwn(req.user.role)
    ? db.prepare('SELECT * FROM ca_records WHERE owner_user_id = ?').all(req.user.id)
    : db.prepare('SELECT * FROM ca_records').all();
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const parse = (d) => (d ? new Date(d + 'T00:00:00') : null);
  const isOpen = (r) => OPEN_STATUSES.includes(r.status);

  const overdue = [];
  const dueSoon = [];
  let complianceOpen = 0;
  let closedNotSustained = 0;
  const agingBuckets = { '1-7': 0, '8-14': 0, '15-30': 0, '30+': 0 };

  for (const r of rows) {
    const due = parse(r.due_date);
    if (isOpen(r) && due) {
      const diffDays = Math.round((today - due) / 86400000);
      if (diffDays > 0) {
        overdue.push({ ...r, overdue_days: diffDays });
        if (diffDays <= 7) agingBuckets['1-7']++;
        else if (diffDays <= 14) agingBuckets['8-14']++;
        else if (diffDays <= 30) agingBuckets['15-30']++;
        else agingBuckets['30+']++;
      } else if (diffDays >= -7) {
        dueSoon.push({ ...r, days_left: -diffDays });
      }
    }
    if (isOpen(r) && r.priority === 'Compliance-critical') complianceOpen++;
    if (r.status === 'Closed' && r.sustained === 'Not yet') closedNotSustained++;
  }

  const closed = rows.filter((r) => r.status === 'Closed');
  let onTime = 0;
  for (const r of closed) {
    const due = parse(r.due_date);
    const done = parse(r.sent_to_owner) || due;
    if (due && done && done <= due) onTime++;
  }

  overdue.sort((a, b) => b.overdue_days - a.overdue_days);

  res.json({
    total: rows.length,
    byStatus: countBy(rows, 'status'),
    byLevel: countBy(rows, 'level'),
    byProduct: countBy(rows, 'product'),
    byPriority: countBy(rows, 'priority'),
    byErrorType: countBy(rows, 'error_type'),
    byLever: countBy(rows, 'lever'),
    byCause: countBy(rows, 'cause_agent_non'),
    overdueCount: overdue.length,
    overdueList: overdue,
    dueSoonCount: dueSoon.length,
    dueSoonList: dueSoon,
    complianceOpen,
    closedNotSustained,
    agingBuckets,
    onTimeClosure: { onTime, closed: closed.length, pct: closed.length ? Math.round((onTime / closed.length) * 100) : 0 },
  });
});

// --- Audit log (users.manage) ---
api.get('/audit', requirePerm('users.manage'), (req, res) => {
  const limit = Math.min(Number(req.query.limit) || 200, 1000);
  const rows = db.prepare('SELECT * FROM audit_log ORDER BY id DESC LIMIT ?').all(limit);
  res.json(rows);
});

app.use('/api', api);

// Friendly errors for upload limits & anything unexpected on the API.
app.use('/api', (err, _req, res, _next) => {
  if (err?.code === 'LIMIT_FILE_SIZE') return res.status(413).json({ error: 'file_too_large' });
  console.error('[api]', err);
  res.status(500).json({ error: 'server_error' });
});

// --- Serve built frontend in production (single-port localhost) ---
const clientDist = path.join(__dirname, '..', 'client', 'dist');
if (fs.existsSync(clientDist)) {
  app.use(express.static(clientDist));
  app.get('*', (_req, res) => res.sendFile(path.join(clientDist, 'index.html')));
}

app.listen(PORT, () => {
  console.log(`[server] CA Register API on http://localhost:${PORT}`);
});
