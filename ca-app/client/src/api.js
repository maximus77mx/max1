const BASE = '/api';

let token = localStorage.getItem('ca_token') || null;
export function setToken(t) {
  token = t;
  if (t) localStorage.setItem('ca_token', t);
  else localStorage.removeItem('ca_token');
}
export function getToken() {
  return token;
}

async function req(url, opts = {}) {
  const res = await fetch(BASE + url, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...opts,
  });
  if (res.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event('ca-unauthorized'));
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.error || 'Request failed');
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return res.json();
}

export const api = {
  // auth
  login: (email, password) => req('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => req('/auth/me'),
  invite: (t) => req(`/auth/invite/${t}`),
  acceptInvite: (data) => req('/auth/accept-invite', { method: 'POST', body: JSON.stringify(data) }),
  changePassword: (current_password, new_password) =>
    req('/auth/change-password', { method: 'POST', body: JSON.stringify({ current_password, new_password }) }),
  // users
  users: () => req('/users'),
  inviteUser: (email, role) => req('/users/invite', { method: 'POST', body: JSON.stringify({ email, role }) }),
  resendInvite: (id) => req(`/users/${id}/resend`, { method: 'POST' }),
  resetUserPassword: (id) => req(`/users/${id}/reset`, { method: 'POST' }),
  audit: (limit = 200) => req(`/audit?limit=${limit}`),
  // settings (super admin)
  getMailSettings: () => req('/settings/mail'),
  saveMailSettings: (data) => req('/settings/mail', { method: 'PUT', body: JSON.stringify(data) }),
  testMail: (to) => req('/settings/mail/test', { method: 'POST', body: JSON.stringify({ to }) }),
  // owner workflow / evidence / export
  userOptions: () => req('/user-options'),
  progress: (id, data) => req(`/records/${id}/progress`, { method: 'PATCH', body: JSON.stringify(data) }),
  updates: (id) => req(`/records/${id}/updates`),
  evidenceList: (id) => req(`/records/${id}/evidence`),
  uploadEvidence: async (id, file) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`${BASE}/records/${id}/evidence`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const err = new Error(body.error || 'Upload failed');
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return res.json();
  },
  downloadEvidence: async (id, filename) => {
    const res = await fetch(`${BASE}/evidence/${id}/download`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('download failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
  deleteEvidence: (id) => req(`/evidence/${id}`, { method: 'DELETE' }),
  exportCsv: async (params = {}, lang = 'th') => {
    const qs = new URLSearchParams({ ...Object.fromEntries(Object.entries(params).filter(([, v]) => v)), lang }).toString();
    const res = await fetch(`${BASE}/export/records.csv?${qs}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ca-register.csv';
    a.click();
    URL.revokeObjectURL(url);
  },
  setUserRole: (id, role) => req(`/users/${id}/role`, { method: 'PATCH', body: JSON.stringify({ role }) }),
  setUserStatus: (id, status) => req(`/users/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  removeUser: (id) => req(`/users/${id}`, { method: 'DELETE' }),
  // CA records
  meta: () => req('/meta'),
  stats: () => req('/stats'),
  nextId: () => req('/next-id'),
  list: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
    return req('/records' + (qs ? `?${qs}` : ''));
  },
  get: (id) => req(`/records/${id}`),
  create: (data) => req('/records', { method: 'POST', body: JSON.stringify(data) }),
  update: (id, data) => req(`/records/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  remove: (id) => req(`/records/${id}`, { method: 'DELETE' }),
};
