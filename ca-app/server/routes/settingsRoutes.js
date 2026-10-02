import express from 'express';
import multer from 'multer';
import * as XLSX from 'xlsx';
import { authRequired, requirePerm } from '../auth.js';
import { getMailConfigSafe, saveMailConfig, getSetting, setSetting } from '../settings.js';
import { sendTestEmail } from '../mailer.js';
import { logAudit } from '../audit.js';
import { replaceRoster } from '../db.js';

const memUpload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 20 * 1024 * 1024 } });

// Map the True/Dtac roster Excel headers → org_roster columns.
const HEADER_MAP = {
  'EMPLOYEE_ID(TEXT)': 'employee_id',
  EMPLOYEE_ID: 'employee_id_num',
  FULLNAME: 'fullname',
  'N5-Name': 'n5_name',
  'N-4 Name': 'n4_name',
  'N-3 Name': 'n3_name',
  DIVISION_NAME: 'division',
  SECTION_NAME: 'section',
  SUB_SECTION_NAME: 'sub_section',
  AGENT_TYPE: 'agent_type',
  EMPLOYEE_STATUS: 'emp_status',
};

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

  // GET /api/settings/roster — roster status (count, last upload, manual entries)
  r.get('/roster', (_req, res) => {
    const count = db.prepare('SELECT COUNT(*) AS n FROM org_roster').get().n;
    const manual = db.prepare("SELECT employee_id, fullname, n5_name, n4_name, division, section FROM org_roster WHERE source = 'manual' ORDER BY fullname").all();
    res.json({
      count,
      manual,
      updated_at: getSetting(db, 'roster.updated_at'),
      filename: getSetting(db, 'roster.filename'),
    });
  });

  // DELETE /api/settings/roster/manual/:employeeId — remove a manually-added employee
  r.delete('/roster/manual/:employeeId', (req, res) => {
    const row = db.prepare("SELECT * FROM org_roster WHERE employee_id = ? AND source = 'manual'").get(req.params.employeeId);
    if (!row) return res.status(404).json({ error: 'not_found' });
    db.prepare('DELETE FROM org_roster WHERE employee_id = ?').run(row.employee_id);
    logAudit(db, req.user, 'roster.remove_manual', { entity: 'roster', ref: row.employee_id, detail: row.fullname });
    res.json({ ok: true });
  });

  // POST /api/settings/roster — upload a new roster Excel (replaces the table)
  r.post('/roster', memUpload.single('file'), (req, res) => {
    if (!req.file) return res.status(400).json({ error: 'no_file' });
    let rows;
    try {
      const wb = XLSX.read(req.file.buffer, { type: 'buffer' });
      const ws = wb.Sheets[wb.SheetNames[0]];
      const raw = XLSX.utils.sheet_to_json(ws, { defval: null });
      rows = raw.map((rec) => {
        const out = {};
        for (const [h, key] of Object.entries(HEADER_MAP)) {
          if (rec[h] !== undefined && rec[h] !== null && key !== 'employee_id_num') {
            out[key] = String(rec[h]).trim() || null;
          }
        }
        // Fall back to the numeric EMPLOYEE_ID column if the text one is absent.
        if (!out.employee_id && rec.EMPLOYEE_ID != null) out.employee_id = String(rec.EMPLOYEE_ID).trim();
        return out;
      }).filter((x) => x.employee_id || x.fullname);
    } catch (e) {
      return res.status(400).json({ error: 'parse_failed', detail: e.message });
    }
    if (!rows.length || !rows.some((x) => x.fullname)) {
      return res.status(400).json({ error: 'no_valid_rows' });
    }
    const n = replaceRoster(rows);
    const original = Buffer.from(req.file.originalname, 'latin1').toString('utf8');
    setSetting(db, 'roster.updated_at', new Date().toISOString());
    setSetting(db, 'roster.filename', original);
    logAudit(db, req.user, 'settings.roster_upload', { entity: 'settings', ref: original, detail: `${n} employees` });
    res.json({ ok: true, count: n });
  });

  return r;
}
