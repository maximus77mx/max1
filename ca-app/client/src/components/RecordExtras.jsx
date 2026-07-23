import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { useI18n } from '../i18n';
import { useAuth } from '../auth';
import { Badge } from './ui';

function fmtSize(n) {
  if (n == null) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

const KIND_ICON = { note: '✎', status: '⇄', file: '📎' };

// Progress panel (for the record's owner), evidence attachments, and activity
// timeline — shown under the CA form when viewing/editing an existing record.
export default function RecordExtras({ record, onRecordChanged, flash }) {
  const { t } = useI18n();
  const { user, can } = useAuth();
  const [evidence, setEvidence] = useState([]);
  const [updates, setUpdates] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  // progress form
  const [note, setNote] = useState('');
  const [resultAfter, setResultAfter] = useState(record.result_after || '');
  const [newStatus, setNewStatus] = useState('');
  const [saving, setSaving] = useState(false);

  const isOwnerOfRecord = record.owner_user_id != null && record.owner_user_id === user.id;
  const canTouch = can('records.edit') || (can('records.edit_own') && isOwnerOfRecord);
  const showProgressPanel = isOwnerOfRecord && can('records.edit_own') && record.status !== 'Closed';

  const load = () => {
    api.evidenceList(record.id).then(setEvidence);
    api.updates(record.id).then(setUpdates);
  };
  useEffect(load, [record.id]); // eslint-disable-line

  const pickFile = () => fileRef.current?.click();
  const onFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadEvidence(record.id, file);
      flash(t.savedOk);
      load();
    } catch (ex) {
      flash(ex.status === 413 ? t.fileTooLarge : 'Upload failed', 'err');
    } finally {
      setUploading(false);
    }
  };

  const removeFile = async (ev) => {
    if (!confirm(`${t.del}: ${ev.original_name}?`)) return;
    await api.deleteEvidence(ev.id);
    load();
  };

  const submitProgress = async (e) => {
    e.preventDefault();
    if (!note && resultAfter === (record.result_after || '') && !newStatus) return;
    setSaving(true);
    try {
      const body = {};
      if (note) body.note = note;
      if (resultAfter !== (record.result_after || '')) body.result_after = resultAfter;
      if (newStatus) body.status = newStatus;
      const updated = await api.progress(record.id, body);
      setNote('');
      setNewStatus('');
      flash(t.progressSaved);
      onRecordChanged?.(updated);
      load();
    } catch {
      flash('Update failed', 'err');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="extras">
      {showProgressPanel && (
        <form className="fieldset no-print" onSubmit={submitProgress}>
          <span className="legend legend-red">{t.progressTitle}</span>
          <div className="grid-fields">
            <div className="field full">
              <label>{t.progressNote}</label>
              <textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
            </div>
            <div className="field">
              <label>{t.resultAfterLabel}</label>
              <input value={resultAfter} onChange={(e) => setResultAfter(e.target.value)} />
            </div>
            <div className="field">
              <label>Status</label>
              <select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                <option value="">{t.statusKeep}</option>
                <option value="In-progress">{t.markInProgress}</option>
                <option value="Verifying">{t.sendVerify}</option>
              </select>
            </div>
          </div>
          <div style={{ textAlign: 'right', marginTop: 10 }}>
            <button className="cta" type="submit" disabled={saving}>{saving ? t.saving : t.submitProgress}</button>
          </div>
        </form>
      )}

      <div className="fieldset">
        <span className="legend">{t.evidence} ({evidence.length})</span>
        {canTouch && (
          <div className="no-print" style={{ marginBottom: 10 }}>
            <input type="file" ref={fileRef} style={{ display: 'none' }} onChange={onFile} />
            <button type="button" className="cta ghost" onClick={pickFile} disabled={uploading}>
              📎 {uploading ? t.uploading : t.uploadFile}
            </button>
            <span style={{ fontSize: 11.5, color: 'var(--ash)', marginLeft: 10 }}>≤ 15 MB</span>
          </div>
        )}
        {evidence.length === 0 ? (
          <div style={{ color: 'var(--ash)', fontWeight: 600, fontSize: 13 }}>{t.noFiles}</div>
        ) : (
          <div className="evidence-list">
            {evidence.map((ev) => (
              <div className="evidence-row" key={ev.id}>
                <span className="ev-icon">📄</span>
                <div className="ev-meta">
                  <button type="button" className="link" onClick={() => api.downloadEvidence(ev.id, ev.original_name)}>
                    {ev.original_name}
                  </button>
                  <div className="ev-sub">{fmtSize(ev.size)} · {t.uploadedBy} {ev.uploaded_by} · {ev.ts?.slice(0, 16).replace('T', ' ')}</div>
                </div>
                <div className="row-actions no-print">
                  <button type="button" className="icon-btn" onClick={() => api.downloadEvidence(ev.id, ev.original_name)}>{t.download}</button>
                  {(ev.uploaded_by === user.email || can('records.edit')) && (
                    <button type="button" className="icon-btn danger" onClick={() => removeFile(ev)}>{t.del}</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="fieldset">
        <span className="legend">{t.timeline} ({updates.length})</span>
        {updates.length === 0 ? (
          <div style={{ color: 'var(--ash)', fontWeight: 600, fontSize: 13 }}>{t.noUpdates}</div>
        ) : (
          <div className="timeline">
            {updates.map((u) => (
              <div className="tl-row" key={u.id}>
                <span className="tl-icon">{KIND_ICON[u.kind] || '•'}</span>
                <div className="tl-body">
                  <div className="tl-head">
                    <b>{u.user_name || u.user_email}</b>
                    <span className="tl-ts">{u.ts?.slice(0, 16).replace('T', ' ')}</span>
                  </div>
                  {u.kind === 'status' ? (
                    <div className="tl-status">
                      {t.statusChanged}: <Badge kind="st" value={u.old_status} /> → <Badge kind="st" value={u.new_status} />
                    </div>
                  ) : u.kind === 'file' ? (
                    <div>{t.attachedFile}: <b>{u.note}</b></div>
                  ) : (
                    <div style={{ whiteSpace: 'pre-wrap' }}>{u.note}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
