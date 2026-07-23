import Database from 'better-sqlite3';
import bcrypt from 'bcryptjs';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { FIELD_KEYS } from './fields.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');
const DB_PATH = process.env.DB_PATH || path.join(DATA_DIR, 'ca.db');

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

// Build the table dynamically from the field definitions so schema stays in sync.
const columnDefs = FIELD_KEYS.map((k) => `"${k}" TEXT`).join(',\n  ');
db.exec(`
CREATE TABLE IF NOT EXISTS ca_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ${columnDefs},
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ca_id ON ca_records(ca_id);
`);

// Seed once, only if the table is empty.
const count = db.prepare('SELECT COUNT(*) AS n FROM ca_records').get().n;
if (count === 0) {
  const seedPath = path.join(DATA_DIR, 'seed.json');
  if (fs.existsSync(seedPath)) {
    const rows = JSON.parse(fs.readFileSync(seedPath, 'utf-8'));
    const cols = FIELD_KEYS;
    const stmt = db.prepare(
      `INSERT INTO ca_records (${cols.map((c) => `"${c}"`).join(',')}) VALUES (${cols.map((c) => `@${c}`).join(',')})`
    );
    const insertMany = db.transaction((records) => {
      for (const r of records) {
        const clean = {};
        for (const c of cols) clean[c] = r[c] ?? null;
        stmt.run(clean);
      }
    });
    insertMany(rows);
    console.log(`[db] Seeded ${rows.length} CA records`);
  }
}

// ---- Auth tables ----
db.exec(`
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  password_hash TEXT,
  role TEXT NOT NULL DEFAULT 'viewer',
  status TEXT NOT NULL DEFAULT 'invited',   -- invited | active | disabled
  created_at TEXT DEFAULT (datetime('now')),
  last_login TEXT
);
CREATE TABLE IF NOT EXISTS invites (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  role TEXT NOT NULL,
  token TEXT UNIQUE NOT NULL,
  invited_by TEXT,
  purpose TEXT DEFAULT 'invite',            -- invite | reset
  created_at TEXT DEFAULT (datetime('now')),
  expires_at TEXT,
  accepted_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT DEFAULT (datetime('now')),
  actor_email TEXT,
  actor_role TEXT,
  action TEXT NOT NULL,                      -- e.g. record.create, user.invite
  entity TEXT,                               -- record | user
  entity_ref TEXT,                           -- CA ID / email
  detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE IF NOT EXISTS ca_updates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id INTEGER NOT NULL,
  ca_id TEXT,
  user_email TEXT,
  user_name TEXT,
  kind TEXT NOT NULL DEFAULT 'note',        -- note | status | file
  note TEXT,
  old_status TEXT,
  new_status TEXT,
  ts TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_updates_record ON ca_updates(record_id);
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id INTEGER NOT NULL,
  ca_id TEXT,
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL,
  size INTEGER,
  mime TEXT,
  uploaded_by TEXT,
  ts TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_evidence_record ON evidence(record_id);
`);

// Upgrade older DBs: link a CA record to the user account responsible for it.
try { db.exec('ALTER TABLE ca_records ADD COLUMN owner_user_id INTEGER'); } catch { /* already present */ }
// Link a user account to an employee in the org roster.
try { db.exec('ALTER TABLE users ADD COLUMN employee_id TEXT'); } catch { /* already present */ }

// ---- Org roster (division / section / team per employee) ----
db.exec(`
CREATE TABLE IF NOT EXISTS org_roster (
  employee_id TEXT PRIMARY KEY,
  fullname TEXT,
  n5_name TEXT,
  n4_name TEXT,
  n3_name TEXT,
  division TEXT,
  section TEXT,
  sub_section TEXT,
  agent_type TEXT,
  emp_status TEXT
);
CREATE INDEX IF NOT EXISTS idx_roster_name ON org_roster(fullname);
`);

export function replaceRoster(records) {
  const ins = db.prepare(`INSERT OR REPLACE INTO org_roster
    (employee_id, fullname, n5_name, n4_name, n3_name, division, section, sub_section, agent_type, emp_status)
    VALUES (@employee_id, @fullname, @n5_name, @n4_name, @n3_name, @division, @section, @sub_section, @agent_type, @emp_status)`);
  const txn = db.transaction((rows) => {
    db.prepare('DELETE FROM org_roster').run();
    let n = 0;
    for (const r of rows) {
      if (!r.employee_id && !r.fullname) continue;
      ins.run({
        employee_id: r.employee_id || `NAME:${r.fullname}`,
        fullname: r.fullname || null,
        n5_name: r.n5_name || null,
        n4_name: r.n4_name || null,
        n3_name: r.n3_name || null,
        division: r.division || null,
        section: r.section || null,
        sub_section: r.sub_section || null,
        agent_type: r.agent_type || null,
        emp_status: r.emp_status || null,
      });
      n++;
    }
    return n;
  });
  return txn(records);
}

// Seed roster once from data/org.json if the table is empty.
const rosterCount = db.prepare('SELECT COUNT(*) AS n FROM org_roster').get().n;
if (rosterCount === 0) {
  const orgPath = path.join(DATA_DIR, 'org.json');
  if (fs.existsSync(orgPath)) {
    const n = replaceRoster(JSON.parse(fs.readFileSync(orgPath, 'utf-8')));
    console.log(`[db] Seeded org roster: ${n} employees`);
  }
}

// Add purpose column if upgrading an older DB (ignore if it already exists).
try { db.exec("ALTER TABLE invites ADD COLUMN purpose TEXT DEFAULT 'invite'"); } catch { /* already present */ }

// ---- Bootstrap the Super Admin from .env ----
// SUPER_ADMIN_EMAIL is required; SUPER_ADMIN_PASSWORD sets/updates the password.
const superEmail = (process.env.SUPER_ADMIN_EMAIL || '').trim().toLowerCase();
if (superEmail) {
  const existing = db.prepare('SELECT * FROM users WHERE email = ?').get(superEmail);
  const pw = process.env.SUPER_ADMIN_PASSWORD;
  if (!existing) {
    const hash = pw ? bcrypt.hashSync(pw, 10) : null;
    db.prepare(
      `INSERT INTO users (email, name, password_hash, role, status) VALUES (?, ?, ?, 'super_admin', ?)`
    ).run(superEmail, process.env.SUPER_ADMIN_NAME || 'Super Admin', hash, pw ? 'active' : 'invited');
    console.log(`[db] Super admin created: ${superEmail}${pw ? '' : ' (no password set — set SUPER_ADMIN_PASSWORD in .env)'}`);
  } else {
    // Keep the env account as super_admin & active; refresh password if provided.
    const hash = pw ? bcrypt.hashSync(pw, 10) : existing.password_hash;
    db.prepare(`UPDATE users SET role = 'super_admin', status = 'active', password_hash = ? WHERE email = ?`).run(hash, superEmail);
  }
} else {
  console.warn('[db] SUPER_ADMIN_EMAIL not set in .env — no super admin bootstrapped. See .env.example');
}

export default db;
