import jwt from 'jsonwebtoken';

export const JWT_SECRET = process.env.JWT_SECRET || 'dev-insecure-secret-change-me';
const TOKEN_TTL = '7d';

// ---- 5-level role model ----
// 'owner' = action owner: sees & updates ONLY the CAs assigned to them.
export const ROLES = ['super_admin', 'admin', 'editor', 'owner', 'viewer'];

export const ROLE_LABELS = {
  super_admin: { th: 'Super Admin', en: 'Super Admin' },
  admin: { th: 'Admin', en: 'Admin' },
  editor: { th: 'Editor', en: 'Editor' },
  owner: { th: 'Owner (เจ้าของงาน)', en: 'Owner' },
  viewer: { th: 'Viewer', en: 'Viewer' },
};

// Every capability the app gates on.
export const PERMISSIONS = [
  'dashboard.view',
  'records.view',
  'records.create',
  'records.edit',       // edit any record
  'records.edit_own',   // update progress/evidence on records assigned to me
  'records.delete',
  'records.export',
  'users.manage',
  'settings.manage',
];

const ALL = new Set(PERMISSIONS);
export const ROLE_PERMS = {
  super_admin: ALL,
  admin: new Set(['dashboard.view', 'records.view', 'records.create', 'records.edit', 'records.edit_own', 'records.delete', 'records.export', 'users.manage']),
  editor: new Set(['dashboard.view', 'records.view', 'records.create', 'records.edit', 'records.edit_own', 'records.export']),
  owner: new Set(['dashboard.view', 'records.view', 'records.edit_own', 'records.export']),
  viewer: new Set(['dashboard.view', 'records.view', 'records.export']),
};

// Roles whose record visibility is scoped to their own assigned CAs.
export function isScopedToOwn(role) {
  return role === 'owner';
}

export function can(role, perm) {
  return ROLE_PERMS[role]?.has(perm) ?? false;
}

// Which roles a given actor is allowed to assign when inviting / changing roles.
export const ASSIGNABLE_ROLES = {
  super_admin: ['admin', 'editor', 'owner', 'viewer'],
  admin: ['editor', 'owner', 'viewer'],
};

// Can `actor` manage (change role / disable / delete) a user who currently holds `targetRole`?
export function canManageUser(actorRole, targetRole) {
  if (targetRole === 'super_admin') return false; // super admin is managed via .env only
  if (actorRole === 'super_admin') return true;
  if (actorRole === 'admin') return ['editor', 'owner', 'viewer'].includes(targetRole);
  return false;
}

export function permsFor(role) {
  return PERMISSIONS.filter((p) => can(role, p));
}

export function signToken(user) {
  return jwt.sign({ id: user.id, email: user.email, name: user.name, role: user.role }, JWT_SECRET, {
    expiresIn: TOKEN_TTL,
  });
}

export function verifyToken(token) {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch {
    return null;
  }
}

// ---- Express middleware ----
export function authRequired(db) {
  return (req, res, next) => {
    const h = req.headers.authorization || '';
    const token = h.startsWith('Bearer ') ? h.slice(7) : null;
    const payload = token && verifyToken(token);
    if (!payload) return res.status(401).json({ error: 'unauthorized' });
    const user = db.prepare('SELECT id, email, name, role, status FROM users WHERE id = ?').get(payload.id);
    if (!user || user.status !== 'active') return res.status(401).json({ error: 'unauthorized' });
    req.user = user;
    next();
  };
}

export function requirePerm(perm) {
  return (req, res, next) => {
    if (!can(req.user.role, perm)) return res.status(403).json({ error: 'forbidden', need: perm });
    next();
  };
}
