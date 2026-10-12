import { useState } from 'react';
import { api } from '../api';
import { useI18n } from '../i18n';

// Manually add an employee who isn't in the monthly roster yet.
export default function AddEmployeeModal({ initialName, onSaved, onClose, flash }) {
  const { t } = useI18n();
  const [f, setF] = useState({
    fullname: initialName || '', employee_id: '', n5_name: '', n4_name: '',
    division: '', section: '', sub_section: '', agent_type: '',
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (!f.fullname.trim()) return setErr(t.empNameRequired);
    setBusy(true);
    setErr('');
    try {
      const emp = await api.addRosterEmployee(f);
      flash?.(t.empAdded);
      onSaved(emp);
    } catch (ex) {
      setErr(ex.body?.error === 'employee_exists' ? t.empIdExists : t.empAddFailed);
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <form className="modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h3 style={{ marginTop: 0 }}>{t.addEmployee}</h3>
        <div className="grid-fields">
          <div className="field">
            <label>{t.empFullname} <span className="req">*</span></label>
            <input value={f.fullname} autoFocus onChange={set('fullname')} required />
          </div>
          <div className="field">
            <label>{t.empId}</label>
            <input value={f.employee_id} placeholder={t.empIdAuto} onChange={set('employee_id')} />
          </div>
          <div className="field">
            <label>Sup / N-5</label>
            <input value={f.n5_name} onChange={set('n5_name')} />
          </div>
          <div className="field">
            <label>N-4</label>
            <input value={f.n4_name} onChange={set('n4_name')} />
          </div>
          <div className="field">
            <label>Division</label>
            <input value={f.division} onChange={set('division')} />
          </div>
          <div className="field">
            <label>Section</label>
            <input value={f.section} onChange={set('section')} />
          </div>
          <div className="field">
            <label>Sub-section</label>
            <input value={f.sub_section} onChange={set('sub_section')} />
          </div>
          <div className="field">
            <label>Agent type</label>
            <input value={f.agent_type} onChange={set('agent_type')} />
          </div>
        </div>
        {err && <div className="auth-err" style={{ marginTop: 12 }}>{err}</div>}
        <div className="form-actions" style={{ position: 'static', padding: 0, marginTop: 14 }}>
          <button type="button" className="cta ghost" onClick={onClose}>{t.cancel}</button>
          <button type="submit" className="cta" disabled={busy}>{busy ? t.saving : t.save}</button>
        </div>
      </form>
    </div>
  );
}
