import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const val = payload[0].value;
    return (
      <div style={tooltipStyles.container}>
        <div style={tooltipStyles.label}>{label}</div>
        <div style={{ color: val >= 0 ? '#00c48c' : '#ff4d6d', fontWeight: '700' }}>
          {val > 0 ? '+' : ''}{val}
        </div>
      </div>
    );
  }
  return null;
};

const tooltipStyles = {
  container: {
    backgroundColor: 'var(--bg3)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '0.75rem 1rem',
    maxWidth: '200px',
  },
  label: {
    fontSize: '0.75rem',
    color: 'var(--text2)',
    marginBottom: '0.25rem',
    wordBreak: 'break-word',
  },
};

const ScoreGauge = ({ score }) => {
  const pct = Math.min(100, Math.max(0, score));
  const color = score >= 70 ? '#00c48c' : score >= 50 ? '#ffd166' : '#ff4d6d';
  return (
    <div style={gaugeStyles.container}>
      <div style={{ ...gaugeStyles.bar, width: `${pct}%`, backgroundColor: color }} />
    </div>
  );
};

const gaugeStyles = {
  container: {
    height: '8px',
    backgroundColor: 'var(--bg3)',
    borderRadius: '4px',
    overflow: 'hidden',
    marginBottom: '0.5rem',
  },
  bar: {
    height: '100%',
    borderRadius: '4px',
    transition: 'width 0.4s ease',
  },
};

const ScoreCard = ({ scoreConfiance, detailScore }) => {
  const score = scoreConfiance;

  const chartData = detailScore
    ? Object.entries(detailScore).map(([key, value]) => ({
        name: key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
        value: typeof value === 'number' ? value : parseFloat(value) || 0,
      }))
    : [];

  const scoreColor =
    score >= 70 ? 'var(--green)' : score >= 50 ? 'var(--yellow)' : 'var(--red)';

  return (
    <div style={styles.container}>
      <h3 style={styles.title}>Score de Confiance</h3>

      <div style={styles.scoreRow}>
        <div style={{ ...styles.scoreValue, color: scoreColor }}>
          {score !== null && score !== undefined ? `${score}` : '—'}
          <span style={styles.scoreMax}>/100</span>
        </div>
        <div style={styles.scoreLabel}>
          {score >= 70 ? 'Forte conviction' : score >= 50 ? 'Conviction modérée' : 'Faible conviction'}
        </div>
      </div>

      {score !== null && score !== undefined && (
        <ScoreGauge score={score} />
      )}

      {chartData.length > 0 && (
        <>
          <div style={styles.subTitle}>Détail des sous-scores</div>
          <ResponsiveContainer width="100%" height={Math.max(150, chartData.length * 30)}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(45,55,72,0.5)" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                dataKey="name"
                type="category"
                tick={{ fill: '#94a3b8', fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                width={130}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(108,99,255,0.08)' }} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={18}>
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.value >= 0 ? '#00c48c' : '#ff4d6d'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    padding: '1.5rem',
  },
  title: {
    fontSize: '0.875rem',
    fontWeight: '600',
    color: 'var(--text2)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    margin: '0 0 1.25rem 0',
  },
  scoreRow: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '0.75rem',
    marginBottom: '0.75rem',
  },
  scoreValue: {
    fontSize: '2.5rem',
    fontWeight: '800',
    lineHeight: '1',
  },
  scoreMax: {
    fontSize: '1.25rem',
    fontWeight: '400',
    color: 'var(--text2)',
  },
  scoreLabel: {
    fontSize: '0.875rem',
    color: 'var(--text2)',
  },
  subTitle: {
    fontSize: '0.7rem',
    color: 'var(--text2)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginTop: '1.25rem',
    marginBottom: '0.5rem',
  },
};

export default ScoreCard;
