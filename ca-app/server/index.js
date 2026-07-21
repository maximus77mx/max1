import './env.js'; // must be first — loads server/.env before db bootstrap
import express from 'express';
import cors from 'cors';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import db from './db.js';
import { FIELDS, FIELD_KEYS, GROUPS, LISTS, SLA_DAYS } from './fields.js';
import { authRequired, requirePerm } from './auth.js';
import authRoutes from './routes/authRoutes.js';
import userRoutes from './routes/userRoutes.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors());
app.use(express.json({ limit: '2mb' }));

// ---- Auth & user management ----
app.use('/api/auth', authRoutes(db));
app.use('/api/users', userRoutes(db));

const api = express.Router();
// Everything below requires a logged-in user.
api.use(authRequired(db));

// --- Metadata: field schema, groups, dropdown lists, SLA matrix ---
api.get('/meta', (_req, res) => {
  res.json({ fields: FIELDS, groups: GROUPS, lists: LISTS, sla: SLA_DAYS });
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

// --- List records (optional filters) ---
api.get('/records', requirePerm('records.view'), (req, res) => {
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
  const sql = `SELECT * FROM ca_records ${where.length ? 'WHERE ' + where.join(' AND ') : ''} ORDER BY ca_id`;
  res.json(db.prepare(sql).all(params));
});

api.get('/records/:id', requirePerm('records.view'), (req, res) => {
  const row = db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id);
  if (!row) return res.status(404).json({ error: 'not found' });
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

api.post('/records', requirePerm('records.create'), (req, res) => {
  const data = pickFields(req.body);
  const errors = validate(data);
  if (errors.length) return res.status(400).json({ errors });
  const dup = db.prepare('SELECT id FROM ca_records WHERE ca_id = ?').get(data.ca_id);
  if (dup) return res.status(409).json({ errors: [{ field: 'ca_id', msg: 'CA ID already exists' }] });
  const cols = FIELD_KEYS;
  const info = db
    .prepare(`INSERT INTO ca_records (${cols.map((c) => `"${c}"`).join(',')}) VALUES (${cols.map((c) => `@${c}`).join(',')})`)
    .run(data);
  res.status(201).json(db.prepare('SELECT * FROM ca_records WHERE id = ?').get(info.lastInsertRowid));
});

api.put('/records/:id', requirePerm('records.edit'), (req, res) => {
  const existing = db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id);
  if (!existing) return res.status(404).json({ error: 'not found' });
  const data = pickFields(req.body);
  const errors = validate(data);
  if (errors.length) return res.status(400).json({ errors });
  const dup = db.prepare('SELECT id FROM ca_records WHERE ca_id = ? AND id != ?').get(data.ca_id, req.params.id);
  if (dup) return res.status(409).json({ errors: [{ field: 'ca_id', msg: 'CA ID already exists' }] });
  const setClause = FIELD_KEYS.map((c) => `"${c}" = @${c}`).join(', ');
  db.prepare(`UPDATE ca_records SET ${setClause}, updated_at = datetime('now') WHERE id = @id`).run({ ...data, id: req.params.id });
  res.json(db.prepare('SELECT * FROM ca_records WHERE id = ?').get(req.params.id));
});

api.delete('/records/:id', requirePerm('records.delete'), (req, res) => {
  const info = db.prepare('DELETE FROM ca_records WHERE id = ?').run(req.params.id);
  if (!info.changes) return res.status(404).json({ error: 'not found' });
  res.json({ ok: true });
});

// --- Dashboard aggregations ---
function countBy(rows, key) {
  const m = {};
  for (const r of rows) {
    const v = r[key] || '(blank)';
    m[v] = (m[v] || 0) + 1;
  }
  return m;
}

const OPEN_STATUSES = ['Open', 'In-progress', 'Verifying', 'Reopened'];

api.get('/stats', requirePerm('dashboard.view'), (_req, res) => {
  const rows = db.prepare('SELECT * FROM ca_records').all();
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

app.use('/api', api);

// --- Serve built frontend in production (single-port localhost) ---
const clientDist = path.join(__dirname, '..', 'client', 'dist');
if (fs.existsSync(clientDist)) {
  app.use(express.static(clientDist));
  app.get('*', (_req, res) => res.sendFile(path.join(clientDist, 'index.html')));
}

app.listen(PORT, () => {
  console.log(`[server] CA Register API on http://localhost:${PORT}`);
});
