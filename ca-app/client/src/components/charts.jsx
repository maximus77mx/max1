import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from 'recharts';

const INK = '#262622';
const RED = '#e60023';
const PALETTE = ['#e60023', '#262622', '#7e238b', '#1f5bb5', '#915b00', '#103c25', '#91918c', '#cc001f'];

// Turn a {label: count} map into sorted [{name, value}]
export function toData(obj) {
  return Object.entries(obj || {})
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
}

const tooltipStyle = {
  contentStyle: { borderRadius: 10, border: '1px solid #dadad3', fontSize: 12, fontWeight: 600 },
  cursor: { fill: 'rgba(0,0,0,0.03)' },
};

export function HBar({ data, color = RED, height }) {
  const h = height || Math.max(120, data.length * 34 + 10);
  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="name"
          width={140}
          tick={{ fontSize: 12, fill: INK, fontWeight: 600 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip {...tooltipStyle} />
        <Bar dataKey="value" radius={[0, 6, 6, 0]} label={{ position: 'right', fontSize: 11, fontWeight: 700, fill: INK }}>
          {data.map((_, i) => (
            <Cell key={i} fill={typeof color === 'function' ? color(data[i], i) : color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function VBar({ data, color = INK, height = 240 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ left: -10, right: 10, top: 10, bottom: 4 }}>
        <XAxis dataKey="name" tick={{ fontSize: 11, fill: INK, fontWeight: 600 }} axisLine={false} tickLine={false} interval={0} />
        <YAxis tick={{ fontSize: 11, fill: '#91918c' }} axisLine={false} tickLine={false} allowDecimals={false} />
        <Tooltip {...tooltipStyle} />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} label={{ position: 'top', fontSize: 11, fontWeight: 700, fill: INK }}>
          {data.map((_, i) => (
            <Cell key={i} fill={typeof color === 'function' ? color(data[i], i) : color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Donut({ data, height = 240 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip {...tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: 12, fontWeight: 600 }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export const priorityColor = (d) =>
  d.name === 'High' || d.name === 'Compliance-critical' ? RED : d.name === 'Medium' ? '#915b00' : '#91918c';

export const statusColor = (d) => {
  const m = { Closed: '#103c25', 'In-progress': '#915b00', Verifying: '#1f5bb5', Open: '#303a9e', Reopened: RED };
  return m[d.name] || '#91918c';
};

export { PALETTE };
