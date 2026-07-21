const BASE = '/api';

async function req(url, opts = {}) {
  const res = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
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
