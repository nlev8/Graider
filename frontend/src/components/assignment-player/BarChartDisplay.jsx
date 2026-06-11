/**
 * BarChartDisplay - Renders an SVG bar chart from data
 */
export default function BarChartDisplay({ data, title }) {
  if (!data || !data.labels || !data.values) {
    return <div style={{ color: '#ef4444', padding: '10px' }}>Missing chart data</div>;
  }

  const { labels, values, y_label } = data;
  const maxVal = Math.max(...values);
  const chartWidth = 400;
  const chartHeight = 200;
  const barWidth = Math.min(50, (chartWidth - 60) / labels.length - 10);
  const padding = { top: 30, right: 20, bottom: 40, left: 50 };

  return (
    <div style={{ marginBottom: '15px' }}>
      <svg width={chartWidth} height={chartHeight + padding.top + padding.bottom}>
        <rect x={0} y={0} width={chartWidth} height={chartHeight + padding.top + padding.bottom} style={{ fill: 'var(--input-bg)' }} rx={8} />
        {title && (
          <text x={chartWidth / 2} y={20} textAnchor="middle" fontSize={14} fontWeight="600" style={{ fill: 'var(--text-primary)' }}>{title}</text>
        )}
        {y_label && (
          <text x={15} y={chartHeight / 2 + padding.top} textAnchor="middle" fontSize={11} style={{ fill: 'var(--text-muted)' }} transform={`rotate(-90, 15, ${chartHeight / 2 + padding.top})`}>{y_label}</text>
        )}
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={chartHeight + padding.top} style={{ stroke: 'var(--glass-border)' }} strokeWidth={1} />
        <line x1={padding.left} y1={chartHeight + padding.top} x2={chartWidth - padding.right} y2={chartHeight + padding.top} style={{ stroke: 'var(--glass-border)' }} strokeWidth={1} />
        {[0, 0.25, 0.5, 0.75, 1].map((tick, i) => {
          const y = padding.top + chartHeight * (1 - tick);
          return (
            <g key={i}>
              <line x1={padding.left - 5} y1={y} x2={padding.left} y2={y} style={{ stroke: 'var(--text-muted)' }} />
              <text x={padding.left - 10} y={y + 4} textAnchor="end" fontSize={10} style={{ fill: 'var(--text-muted)' }}>{Math.round(maxVal * tick)}</text>
            </g>
          );
        })}
        {values.map((val, idx) => {
          const barHeight = (val / maxVal) * chartHeight;
          const x = padding.left + 20 + idx * ((chartWidth - padding.left - padding.right - 40) / labels.length);
          const y = padding.top + chartHeight - barHeight;
          const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
          return (
            <g key={idx}>
              <rect x={x} y={y} width={barWidth} height={barHeight} fill={colors[idx % colors.length]} rx={3} />
              <text x={x + barWidth / 2} y={y - 5} textAnchor="middle" fontSize={10} style={{ fill: 'var(--text-primary)' }} fontWeight="500">{val}</text>
              <text x={x + barWidth / 2} y={chartHeight + padding.top + 15} textAnchor="middle" fontSize={10} style={{ fill: 'var(--text-primary)' }}>{labels[idx]}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
