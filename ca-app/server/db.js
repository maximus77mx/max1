import Database from 'better-sqlite3';
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

export default db;
