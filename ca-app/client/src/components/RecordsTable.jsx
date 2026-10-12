import { useEffect, useState } from 'react';
import { api } from '../api';
import { useI18n } from '../i18n';
import { useAuth } from '../auth';
import { Badge } from './ui';

export default function RecordsTable({ meta, onEdit, onNew, refreshKey, onChanged }) {
  const { lang, t } = useI18n();
  const { can } = useAuth();
  const canEdit = can('records.edit');
  const canDelete = can('records.delete');
  const canCreate = can('records.create');
  const canExport = can('records.export');
  const [exporting, setExporting] = useState(false);
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState({ q: '', status: '', level: '', product: '', priority: '' });
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.list(filters).then((r) => { setRows(r); setLoading(false); });
  };

  useEffect(() => {
    const id = setTimeout(load, filters.q ? 250 : 0);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, refreshKey]);

  const del = async (r) => {
    if (!confirm(t.confirmDel + `\n${r.ca_id}`)) return;
    await api.remove(r.id);
    onChanged?.();
    load();
  };

  const set = (k, v) => setFilters((p) => ({ ...p, [k]: v }));

  const opts = (list) => meta.lists[list].map((o) => <option key={o} value={o}>{o}</option>);

  return (
    <div>
      <div className="toolbar">
        <input type="search" placeholder={t.search} value={filters.q} onChange={(e) => set('q', e.target.value)} />
        <select value={filters.status} onChange={(e) => set('status', e.target.value)}>
          <option value="">{t.all} · Status</option>{opts('status')}
        </select>
        <select value={filters.level} onChange={(e) => set('level', e.target.value)}>
          <option value="">{t.all} · Level</option>{opts('level')}
        </select>
        <select value={filters.product} onChange={(e) => set('product', e.target.value)}>
          <option value="">{t.all} · Product</option>{opts('product')}
        </select>
        <select value={filters.priority} onChange={(e) => set('priority', e.target.value)}>
          <option value="">{t.all} · Priority</option>{opts('priority')}
        </select>
        <div className="spacer" style={{ flex: 1 }} />
        <span style={{ color: 'var(--ash)', fontWeight: 700, fontSize: 13 }}>{rows.length} {t.count}</span>
        {canExport && (
          <button className="cta ghost" disabled={exporting}
            onClick={async () => { setExporting(true); try { await api.exportCsv(filters, lang); } finally { setExporting(false); } }}>
            ⬇ {t.downloadCsv}
          </button>
        )}
        {canCreate && <button className="cta" onClick={onNew}>{t.newCA}</button>}
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>CA ID</th>
              <th>Level</th>
              <th>Product</th>
              <th>Nonconformity</th>
              <th>Priority</th>
              <th>Status</th>
              <th>Owner</th>
              <th>Due</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td><button className="link" onClick={() => onEdit(r.id)}>{r.ca_id}</button></td>
                <td>{r.level}</td>
                <td>{r.product}</td>
                <td className="desc">{r.nonconformity}</td>
                <td><Badge kind="pr" value={r.priority} /></td>
                <td><Badge kind="st" value={r.status} /></td>
                <td>{r.action_owner}</td>
                <td style={{ whiteSpace: 'nowrap' }}>{r.due_date}</td>
                <td>
                  <div className="row-actions">
                    <button className="icon-btn" onClick={() => onEdit(r.id)}>{canEdit ? t.edit : t.view}</button>
                    {canDelete && <button className="icon-btn danger" onClick={() => del(r)}>{t.del}</button>}
                  </div>
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={9} className="empty">{t.noData}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
