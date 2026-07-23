import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { useI18n } from '../i18n';
import { useAuth } from '../auth';
import RecordExtras from './RecordExtras';

function Field({ f, lang, value, error, onChange, readOnly }) {
  const label = lang === 'th' ? f.th : f.en;
  const { t } = useI18n();
  const common = {
    id: f.key,
    value: value ?? '',
    disabled: readOnly,
    onChange: (e) => onChange(f.key, e.target.value),
  };
  return (
    <div className={`field ${f.type === 'ta' ? 'full' : ''} ${error ? 'err' : ''}`}>
      <label htmlFor={f.key}>
        {label}
        {f.required && <span className="req">*</span>}
      </label>
      {f.type === 'select' ? (
        <select {...common}>
          <option value="">{t.selectPlaceholder}</option>
          {f.options.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      ) : f.type === 'ta' ? (
        <textarea {...common} rows={2} />
      ) : (
        <input type={f.type === 'date' ? 'date' : 'text'} {...common} />
      )}
      {error && <div className="msg">{error}</div>}
    </div>
  );
}

export default function RegisterForm({ meta, editId, onSaved, onCancel, flash }) {
  const { lang, t } = useI18n();
  const { can } = useAuth();
  const readOnly = !!editId && !can('records.edit');
  const [form, setForm] = useState({});
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [userOpts, setUserOpts] = useState(null);

  // Load the user list for the Owner picker (editors+ only).
  useEffect(() => {
    if (can('records.create') || can('records.edit')) {
      api.userOptions().then(setUserOpts).catch(() => setUserOpts(null));
    }
  }, []); // eslint-disable-line

  // Attach dropdown options to each field from meta.lists
  const fields = useMemo(
    () => meta.fields.map((f) => ({ ...f, options: f.list ? meta.lists[f.list] : null })),
    [meta]
  );

  useEffect(() => {
    if (editId) {
      api.get(editId).then((r) => setForm(r));
    } else {
      api.nextId().then(({ next_id }) =>
        setForm({ ca_id: next_id, raise_date: new Date().toISOString().slice(0, 10), status: 'Open' })
      );
    }
  }, [editId]);

  const isIndividual = form.level === 'Individual';

  const change = (k, v) => {
    setForm((p) => ({ ...p, [k]: v }));
    setErrors((p) => ({ ...p, [k]: undefined }));
  };

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setErrors({});
    try {
      if (editId) await api.update(editId, form);
      else await api.create(form);
      onSaved();
    } catch (err) {
      if (err.body?.errors) {
        const map = {};
        for (const e of err.body.errors) map[e.field] = e.msg;
        setErrors(map);
        onSaved(null, 'err');
      } else {
        onSaved(null, 'err');
      }
      // scroll to first error
      const first = err.body?.errors?.[0]?.field;
      if (first) document.getElementById(first)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="form-shell" onSubmit={submit}>
      <div className="form-head">
        <h2>{readOnly ? `${form.ca_id || ''}` : editId ? t.editTitle : t.formTitle}</h2>
        <div style={{ display: 'flex', gap: 10 }} className="no-print">
          {editId && <button type="button" className="cta ghost" onClick={() => window.print()}>🖨 {t.printPdf}</button>}
          <button type="button" className="cta ghost" onClick={onCancel}>{readOnly ? t.records : t.cancel}</button>
          {!readOnly && <button type="submit" className="cta" disabled={saving}>{saving ? t.saving : t.save}</button>}
        </div>
      </div>

      {meta.groups.map((g) => {
        if (g.key === 'individual' && !isIndividual) return null;
        const gfields = fields.filter((f) => f.group === g.key);
        if (!gfields.length) return null;
        return (
          <fieldset className="fieldset" key={g.key}>
            <span className="legend">{lang === 'th' ? g.th : g.en}</span>
            <div className="grid-fields">
              {gfields.map((f) => (
                <Field key={f.key} f={f} lang={lang} value={form[f.key]} error={errors[f.key]} onChange={change} readOnly={readOnly} />
              ))}
              {g.key === 'action' && userOpts && (
                <div className="field">
                  <label htmlFor="owner_user_id">{t.ownerUser}</label>
                  <select id="owner_user_id" value={form.owner_user_id ?? ''} disabled={readOnly}
                    onChange={(e) => change('owner_user_id', e.target.value ? Number(e.target.value) : null)}>
                    <option value="">{t.selectOwner}</option>
                    {userOpts.map((u) => (
                      <option key={u.id} value={u.id}>{u.name ? `${u.name} (${u.email})` : u.email}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </fieldset>
        );
      })}

      {editId && form.id && (
        <RecordExtras record={form} onRecordChanged={(updated) => setForm(updated)} flash={flash} />
      )}

      {!readOnly && (
        <div className="form-actions">
          <button type="button" className="cta ghost" onClick={onCancel}>{t.cancel}</button>
          <button type="submit" className="cta" disabled={saving}>{saving ? t.saving : t.save}</button>
        </div>
      )}
    </form>
  );
}
