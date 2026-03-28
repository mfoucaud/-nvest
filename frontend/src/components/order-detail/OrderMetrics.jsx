import React from 'react';

const formatCurrency = (value) => {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 2,
  }).format(value);
};

const formatNumber = (value, decimals = 2) => {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
};

const formatDate = (dateStr) => {
  if (!dateStr) return '—';
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
};

const MetricItem = ({ label, value, color, size }) => (
  <div style={styles.item}>
    <div style={styles.label}>{label}</div>
    <div style={{ ...styles.value, color: color || 'var(--text)', fontSize: size || '1.1rem' }}>
      {value}
    </div>
  </div>
);

const OrderMetrics = ({ order }) => {
  if (!order) return null;

  const pnl = order.pnl_latent;
  const pnlColor = pnl !== null && pnl !== undefined
    ? (pnl >= 0 ? 'var(--green)' : 'var(--red)')
    : 'var(--text2)';

  const pnlFormatted = pnl !== null && pnl !== undefined
    ? new Intl.NumberFormat('fr-FR', {
        style: 'currency',
        currency: 'EUR',
        maximumFractionDigits: 2,
        signDisplay: 'always',
      }).format(pnl)
    : '—';

  const rr = order.ratio_rr || order.ratio_risque_rendement;
  const taille = order.taille_position_eur || order.taille_position || order.montant_investi;
  const confiance = order.score_confiance;

  return (
    <div style={styles.container}>
      <h3 style={styles.title}>Métriques de Position</h3>
      <div style={styles.grid}>
        <MetricItem
          label="Prix d'entrée"
          value={formatNumber(order.prix_entree, 4)}
          color="var(--text)"
        />
        <MetricItem
          label="Cours actuel"
          value={formatNumber(order.prix_actuel || order.cours_actuel, 4)}
          color="var(--accent2)"
        />
        <MetricItem
          label="Stop Loss"
          value={formatNumber(order.stop_loss, 4)}
          color="var(--red)"
        />
        <MetricItem
          label="Take Profit"
          value={formatNumber(order.take_profit, 4)}
          color="var(--green)"
        />
        <MetricItem
          label="P&L Latent (€)"
          value={pnlFormatted}
          color={pnlColor}
          size="1.2rem"
        />
        <MetricItem
          label="Ratio R/R"
          value={rr !== null && rr !== undefined ? `${formatNumber(rr, 2)}` : '—'}
          color="var(--accent)"
        />
        <MetricItem
          label="Taille (€)"
          value={formatCurrency(taille)}
          color="var(--text)"
        />
        <MetricItem
          label="Confiance"
          value={confiance !== null && confiance !== undefined ? `${confiance} / 10` : '—'}
          color={
            confiance >= 7 ? 'var(--green)'
            : confiance >= 5 ? 'var(--yellow)'
            : 'var(--red)'
          }
        />
        <MetricItem
          label="Expiration"
          value={formatDate(order.date_expiration || order.expiration)}
          color="var(--text2)"
        />
      </div>
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
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '1rem',
  },
  item: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.2rem',
  },
  label: {
    fontSize: '0.7rem',
    color: 'var(--text2)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    fontWeight: '500',
  },
  value: {
    fontWeight: '700',
    lineHeight: '1.2',
  },
};

export default OrderMetrics;
