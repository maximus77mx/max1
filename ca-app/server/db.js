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
`);

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
