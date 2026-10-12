export function Badge({ kind, value }) {
  if (!value) return <span className="badge st-blank">—</span>;
  const cls = value.replace(/[^a-zA-Z]/g, '');
  return <span className={`badge ${kind}-${cls}`}>{value}</span>;
}

export function Toast({ msg, kind }) {
  if (!msg) return null;
  return <div className={`toast ${kind === 'err' ? 'err' : ''}`}>{msg}</div>;
}
