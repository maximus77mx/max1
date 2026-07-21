import nodemailer from 'nodemailer';

// If SMTP_* env vars are present we send real email; otherwise we run in
// "dev mode" where the invite link is returned to the caller (and logged),
// so invites work on localhost with zero setup.
const hasSmtp = !!(process.env.SMTP_HOST && process.env.SMTP_PORT);

let transporter = null;
if (hasSmtp) {
  transporter = nodemailer.createTransport({
    host: process.env.SMTP_HOST,
    port: Number(process.env.SMTP_PORT),
    secure: process.env.SMTP_SECURE === 'true',
    auth: process.env.SMTP_USER ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASS } : undefined,
  });
}

export const mailEnabled = hasSmtp;

export async function sendInviteEmail({ to, link, inviterName, role, reset = false }) {
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

  if (!transporter) {
    console.log(`\n[mailer:dev] Invite link for ${to}:\n${link}\n`);
    return { delivered: false, link };
  }
  await transporter.sendMail({
    from: process.env.SMTP_FROM || process.env.SMTP_USER,
    to,
    subject,
    html,
  });
  console.log(`[mailer] Invite email sent to ${to}`);
  return { delivered: true };
}
