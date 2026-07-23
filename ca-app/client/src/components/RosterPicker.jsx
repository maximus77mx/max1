import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

// Autocomplete against the org roster. Renders an input; typing ≥2 chars
// searches employees, and choosing one calls onPick(employee).
export default function RosterPicker({ value, onChange, onPick, placeholder, disabled, id }) {
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState([]);
  const [hi, setHi] = useState(-1);
  const boxRef = useRef(null);
  const timer = useRef(null);

  useEffect(() => {
    const close = (e) => { if (!boxRef.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const search = (q) => {
    clearTimeout(timer.current);
    if (!q || q.trim().length < 2) { setResults([]); setOpen(false); return; }
    timer.current = setTimeout(async () => {
      try {
        const r = await api.rosterSearch(q.trim());
        setResults(r);
        setOpen(r.length > 0);
        setHi(-1);
      } catch { /* ignore */ }
    }, 220);
  };

  const pick = (emp) => {
    onPick?.(emp);
    setOpen(false);
  };

  const onKey = (e) => {
    if (!open) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setHi((h) => Math.min(h + 1, results.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
    else if (e.key === 'Enter' && hi >= 0) { e.preventDefault(); pick(results[hi]); }
    else if (e.key === 'Escape') setOpen(false);
  };

  return (
    <div className="roster-picker" ref={boxRef}>
      <input
        id={id}
        value={value ?? ''}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete="off"
        onChange={(e) => { onChange?.(e.target.value); search(e.target.value); }}
        onKeyDown={onKey}
        onFocus={(e) => search(e.target.value)}
      />
      {open && (
        <div className="roster-dd">
          {results.map((emp, i) => (
            <button
              type="button"
              key={emp.employee_id}
              className={`roster-item ${i === hi ? 'hi' : ''}`}
              onMouseEnter={() => setHi(i)}
              onClick={() => pick(emp)}
            >
              <div className="ri-name">{emp.fullname} <span className="ri-id">{emp.employee_id}</span></div>
              <div className="ri-org">{[emp.division, emp.section].filter(Boolean).join(' › ')}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
