import { useEffect, useState } from 'react';
import { api } from '../api';
import { useI18n } from '../i18n';
import { Badge } from './ui';
import { HBar, VBar, Donut, toData, priorityColor, statusColor } from './charts';

function Kpi({ val, label, kind }) {
  return (
    <div className={`kpi ${kind || ''}`}>
      <div className="val">{val}</div>
      <div className="label">{label}</div>
    </div>
  );
}

export default function Dashboard() {
  const { t } = useI18n();
  const [s, setS] = useState(null);
  const [teamMode, setTeamMode] = useState('n4');

  useEffect(() => {
    api.stats().then(setS);
  }, []);

  if (!s) return <div className="loading">Loading…</div>;

  const teams = (teamMode === 'n4' ? s.teamN4 : s.teamN3) || [];

  const errData = toData(s.byErrorType);
  const priData = toData(s.byPriority);
  const aging = ['1-7', '8-14', '15-30', '30+'].map((k) => ({ name: k, value: s.agingBuckets[k] }));

  return (
    <div>
      <div className="kpi-grid">
        <Kpi val={s.total} label={t.total} />
        <Kpi val={s.overdueCount} label={t.overdue} kind="alert" />
        <Kpi val={s.dueSoonCount} label={t.dueSoon} />
        <Kpi val={s.complianceOpen} label={t.complianceOpen} kind="alert" />
        <Kpi val={s.closedNotSustained} label={t.closedNotSustained} />
        <Kpi val={`${s.onTimeClosure.pct}%`} label={t.onTime} kind="good" />
      </div>

      <div className="panel-grid">
        <div className="panel">
          <h3>{t.byStatus}</h3>
          <VBar data={toData(s.byStatus)} color={statusColor} />
        </div>
        <div className="panel">
          <h3>{t.byLevel}</h3>
          <Donut data={toData(s.byLevel)} />
        </div>
        <div className="panel">
          <h3>{t.byProduct}</h3>
          <HBar data={toData(s.byProduct)} color="#262622" />
        </div>
        <div className="panel">
          <h3>{t.byCause}</h3>
          <Donut data={toData(s.byCause)} />
        </div>
        <div className="panel">
          <h3>{t.byPriorityErr}</h3>
          <div className="section-title">{t.priority}</div>
          <HBar data={priData} color={priorityColor} height={priData.length * 34 + 10} />
          <div className="section-title" style={{ marginTop: 14 }}>{t.errorType}</div>
          <HBar data={errData} color="#7e238b" height={errData.length * 34 + 10} />
        </div>
        <div className="panel">
          <h3>{t.byLever}</h3>
          <HBar data={toData(s.byLever)} color="#1f5bb5" />
        </div>

        <div className="panel wide">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
            <h3 style={{ margin: 0 }}>{t.byTeam}</h3>
            <div className="seg">
              <button className={teamMode === 'n4' ? 'active' : ''} onClick={() => setTeamMode('n4')}>N-4</button>
              <button className={teamMode === 'n3' ? 'active' : ''} onClick={() => setTeamMode('n3')}>N-3</button>
            </div>
            {s.teamUnattributed > 0 && (
              <span style={{ fontSize: 12, color: 'var(--ash)', fontWeight: 600 }}>
                · {t.unattributed}: {s.teamUnattributed}
              </span>
            )}
          </div>
          {teams.length === 0 ? (
            <div className="empty">{t.noData}</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 24, alignItems: 'start' }}>
              <HBar data={teams.map((x) => ({ name: x.name, value: x.total }))} color="#262622" />
              <div className="table-wrap" style={{ maxHeight: 340, overflowY: 'auto' }}>
                <table>
                  <thead>
                    <tr><th>{t.teamCol}</th><th>{t.total}</th><th>{t.openCol}</th><th>{t.overdue}</th></tr>
                  </thead>
                  <tbody>
                    {teams.map((x) => (
                      <tr key={x.name}>
                        <td style={{ fontWeight: 700, fontSize: 12.5 }}>{x.name}</td>
                        <td>{x.total}</td>
                        <td>{x.open}</td>
                        <td style={{ color: x.overdue ? '#e60023' : 'var(--ash)', fontWeight: 800 }}>{x.overdue}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        <div className="panel wide">
          <h3>{t.overdueAging}</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 24, alignItems: 'center' }}>
            <VBar data={aging} color={(d) => (d.name === '30+' ? '#e60023' : d.name === '15-30' ? '#cc001f' : '#915b00')} height={200} />
            <div className="table-wrap" style={{ maxHeight: 300, overflowY: 'auto' }}>
              <table>
                <thead>
                  <tr>
                    <th>CA ID</th>
                    <th>{t.priority}</th>
                    <th>Product</th>
                    <th>Due date</th>
                    <th>{t.daysOverdue}</th>
                  </tr>
                </thead>
                <tbody>
                  {s.overdueList.slice(0, 40).map((r) => (
                    <tr key={r.id}>
                      <td style={{ fontWeight: 700 }}>{r.ca_id}</td>
                      <td><Badge kind="pr" value={r.priority} /></td>
                      <td>{r.product}</td>
                      <td>{r.due_date}</td>
                      <td style={{ color: '#e60023', fontWeight: 800 }}>{r.overdue_days}</td>
                    </tr>
                  ))}
                  {s.overdueList.length === 0 && (
                    <tr><td colSpan={5} className="empty">—</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
