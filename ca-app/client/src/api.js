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
  // users
  users: () => req('/users'),
  inviteUser: (email, role) => req('/users/invite', { method: 'POST', body: JSON.stringify({ email, role }) }),
  resendInvite: (id) => req(`/users/${id}/resend`, { method: 'POST' }),
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
