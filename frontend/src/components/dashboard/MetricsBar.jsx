import React from 'react';

const formatCurrency = (value) => {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value);
};

const formatPnl = (value) => {
  if (value === null || value === undefined) return { text: '—', color: 'var(--text2)' };
  const formatted = new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
    signDisplay: 'always',
  }).format(value);
  return {
    text: formatted,
    color: value >= 0 ? 'var(--green)' : 'var(--red)',
  };
};

const MetricCard = ({ label, value, valueColor, sub }) => (
  <div style={styles.card}>
    <div style={styles.label}>{label}</div>
    <div style={{ ...styles.value, color: valueColor || 'var(--text)' }}>{value}</div>
    {sub && <div style={styles.sub}>{sub}</div>}
  </div>
);

const MetricsBar = ({ metriques }) => {
  if (!metriques) return null;

  const {
    capital_actuel,
    pnl_latent_eur,
    pnl_total_eur,
    nb_trades_ouverts,
    nb_trades_total,
  } = metriques;

  const pnlLatent = formatPnl(pnl_latent_eur);
  const pnlRealise = formatPnl(pnl_total_eur);

  return (
    <div style={styles.bar}>
      <MetricCard
        label="Capital Actuel"
        value={formatCurrency(capital_actuel)}
        valueColor="var(--accent2)"
      />
      <MetricCard
        label="P&L Latent"
        value={pnlLatent.text}
        valueColor={pnlLatent.color}
        sub="positions ouvertes"
      />
      <MetricCard
        label="P&L Réalisé"
        value={pnlRealise.text}
        valueColor={pnlRealise.color}
        sub="total clôturé"
      />
      <MetricCard
        label="Trades"
        value={`${nb_trades_ouverts ?? '—'} / ${nb_trades_total ?? '—'}`}
        valueColor="var(--text)"
        sub="ouverts / total"
      />
    </div>
  );
};

const styles = {
  bar: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: '1rem',
    marginBottom: '1.5rem',
  },
  card: {
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    padding: '1.25rem 1.5rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.25rem',
  },
  label: {
    fontSize: '0.75rem',
    color: 'var(--text2)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    fontWeight: '500',
  },
  value: {
    fontSize: '1.5rem',
    fontWeight: '700',
    lineHeight: '1.2',
    marginTop: '0.25rem',
  },
  sub: {
    fontSize: '0.75rem',
    color: 'var(--text2)',
    marginTop: '0.125rem',
  },
};

export default MetricsBar;
