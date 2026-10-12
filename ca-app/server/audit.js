// Lightweight audit trail helper.
export function logAudit(db, actor, action, { entity, ref, detail } = {}) {
  try {
    db.prepare(
      'INSERT INTO audit_log (actor_email, actor_role, action, entity, entity_ref, detail) VALUES (?, ?, ?, ?, ?, ?)'
    ).run(actor?.email || null, actor?.role || null, action, entity || null, ref || null, detail || null);
  } catch (e) {
    console.error('[audit] failed:', e.message);
  }
}
