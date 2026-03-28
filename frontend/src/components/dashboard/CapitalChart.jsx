import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const formatCurrency = (value) => {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value);
};

const formatDateShort = (dateStr) => {
  if (!dateStr) return '';
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: '2-digit',
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
};

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div style={tooltipStyles.container}>
        <div style={tooltipStyles.date}>{formatDateShort(label)}</div>
        <div style={tooltipStyles.value}>{formatCurrency(payload[0].value)}</div>
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
  },
  date: {
    fontSize: '0.75rem',
    color: 'var(--text2)',
    marginBottom: '0.25rem',
  },
  value: {
    fontSize: '1rem',
    fontWeight: '700',
    color: '#6c63ff',
  },
};

const CapitalChart = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div style={styles.empty}>
        Aucune donnée d'historique de capital disponible.
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h3 style={styles.title}>Évolution du Capital</h3>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--border)"
            vertical={false}
          />
          <XAxis
            dataKey="date"
            tickFormatter={formatDateShort}
            tick={{ fill: 'var(--text2)', fontSize: 11 }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v) => formatCurrency(v)}
            tick={{ fill: 'var(--text2)', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={100}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="capital"
            stroke="#6c63ff"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 5, fill: '#6c63ff', stroke: 'var(--bg2)', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    padding: '1.5rem',
    marginBottom: '2rem',
  },
  header: {
    marginBottom: '1rem',
  },
  title: {
    fontSize: '0.875rem',
    fontWeight: '600',
    color: 'var(--text2)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    margin: 0,
  },
  empty: {
    padding: '2rem',
    textAlign: 'center',
    color: 'var(--text2)',
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    marginBottom: '2rem',
  },
};

export default CapitalChart;
