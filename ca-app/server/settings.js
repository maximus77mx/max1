// Key/value settings stored in DB, used for runtime-configurable SMTP.
// DB values take precedence over .env; .env acts as the fallback default.

export function getSetting(db, key) {
  return db.prepare('SELECT value FROM settings WHERE key = ?').get(key)?.value ?? null;
}

export function setSetting(db, key, value) {
  db.prepare(
    'INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value'
  ).run(key, value == null ? null : String(value));
}

const MAIL_KEYS = ['host', 'port', 'secure', 'user', 'pass', 'sender_name', 'sender_email'];

// Merge DB settings over .env defaults into a single mail config.
export function getMailConfig(db) {
  const g = (k) => getSetting(db, `mail.${k}`);
  const cfg = {
    host: g('host') || process.env.SMTP_HOST || '',
    port: g('port') || process.env.SMTP_PORT || '',
    secure: (g('secure') ?? (process.env.SMTP_SECURE === 'true' ? 'true' : 'false')) === 'true',
    user: g('user') || process.env.SMTP_USER || '',
    pass: g('pass') || process.env.SMTP_PASS || '',
    sender_name: g('sender_name') || 'QA Corrective Action',
    sender_email: g('sender_email') || process.env.SMTP_FROM || g('user') || process.env.SMTP_USER || '',
  };
  return cfg;
}

// Save the SMTP settings the super admin submits. Password left blank = keep existing.
export function saveMailConfig(db, body) {
  const map = {
    host: body.host,
    port: body.port,
    secure: body.secure ? 'true' : 'false',
    user: body.user,
    sender_name: body.sender_name,
    sender_email: body.sender_email,
  };
  for (const [k, v] of Object.entries(map)) setSetting(db, `mail.${k}`, v ?? '');
  if (body.pass) setSetting(db, 'mail.pass', body.pass); // only overwrite when a new one is given
}

// Client-safe view — never returns the stored password, just whether one exists.
export function getMailConfigSafe(db) {
  const c = getMailConfig(db);
  return {
    host: c.host,
    port: c.port,
    secure: c.secure,
    user: c.user,
    sender_name: c.sender_name,
    sender_email: c.sender_email,
    hasPassword: !!c.pass,
    enabled: !!(c.host && c.port),
    source: getSetting(db, 'mail.host') ? 'db' : (process.env.SMTP_HOST ? 'env' : 'none'),
  };
}
