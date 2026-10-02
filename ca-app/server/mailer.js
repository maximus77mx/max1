import nodemailer from 'nodemailer';
import { getMailConfig } from './settings.js';

// Build a transporter from the current (DB-or-env) mail config.
function buildTransport(cfg) {
  return nodemailer.createTransport({
    host: cfg.host,
    port: Number(cfg.port),
    secure: cfg.secure,
    auth: cfg.user ? { user: cfg.user, pass: cfg.pass } : undefined,
    // Fail fast instead of hanging the request if the SMTP host is unreachable.
    connectionTimeout: 10000,
    greetingTimeout: 10000,
    socketTimeout: 15000,
  });
}

export function isMailEnabled(db) {
  const c = getMailConfig(db);
  return !!(c.host && c.port);
}

function fromLine(cfg) {
  const email = cfg.sender_email || cfg.user;
  return cfg.sender_name ? `${cfg.sender_name} <${email}>` : email;
}

// Sends the invite/reset email if SMTP is configured; otherwise runs in
// "dev mode" and returns the link for manual sharing.
export async function sendInviteEmail(db, { to, link, inviterName, role, reset = false }) {
  const cfg = getMailConfig(db);
  const subject = reset
    ? 'รีเซ็ตรหัสผ่าน QA Corrective Action / Password reset'
    : 'คุณได้รับเชิญให้ใช้งาน QA Corrective Action / You have been invited';
  const intro = reset
    ? `${inviterName || 'ผู้ดูแลระบบ'} เริ่มการรีเซ็ตรหัสผ่านให้บัญชีของคุณ`
    : `${inviterName || 'ผู้ดูแลระบบ'} เชิญคุณเข้าใช้งานระบบในสิทธิ์ <b>${role}</b>`;
  const cta = reset ? 'ตั้งรหัสผ่านใหม่ / Reset password' : 'ตั้งรหัสผ่าน / Accept invite';
  const html = `
    <div style="font-family:Arial,'Noto Sans Thai',sans-serif;max-width:520px;margin:auto;color:#33332e">
      <h2 style="color:#e60023;margin:0 0 8px">QA Corrective Action</h2>
      <p>${intro}</p>
      <p>คลิกปุ่มด้านล่างเพื่อตั้งรหัสผ่าน${reset ? 'ใหม่' : 'และเริ่มใช้งาน'} (ลิงก์หมดอายุใน 7 วัน)</p>
      <p style="text-align:center;margin:26px 0">
        <a href="${link}" style="background:#e60023;color:#fff;text-decoration:none;padding:12px 28px;border-radius:999px;font-weight:bold">
          ${cta}
        </a>
      </p>
      <p style="font-size:12px;color:#91918c">หากปุ่มไม่ทำงาน วางลิงก์นี้ในเบราว์เซอร์:<br>${link}</p>
    </div>`;

  if (!cfg.host || !cfg.port) {
    console.log(`\n[mailer:dev] Invite link for ${to}:\n${link}\n`);
    return { delivered: false, link };
  }
  try {
    await buildTransport(cfg).sendMail({ from: fromLine(cfg), to, subject, html });
    console.log(`[mailer] Invite email sent to ${to}`);
    return { delivered: true };
  } catch (e) {
    // Delivery failed (bad SMTP / unreachable) — fall back to returning the link
    // so the admin can still share it manually instead of the whole action failing.
    console.error(`[mailer] send failed for ${to}: ${e.message} — falling back to link`);
    return { delivered: false, link, error: e.message };
  }
}

// Send a test email to verify SMTP settings.
export async function sendTestEmail(db, to) {
  const cfg = getMailConfig(db);
  if (!cfg.host || !cfg.port) throw new Error('smtp_not_configured');
  await buildTransport(cfg).sendMail({
    from: fromLine(cfg),
    to,
    subject: 'ทดสอบการส่งอีเมล — QA Corrective Action / SMTP test',
    html: `<div style="font-family:Arial,'Noto Sans Thai',sans-serif">
      <h2 style="color:#e60023">SMTP test OK ✓</h2>
      <p>ระบบส่งอีเมลของ QA Corrective Action ตั้งค่าถูกต้องแล้ว</p>
      <p style="font-size:12px;color:#91918c">Host: ${cfg.host}:${cfg.port} · From: ${fromLine(cfg)}</p>
    </div>`,
  });
  return { delivered: true };
}
