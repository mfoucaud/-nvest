import React from 'react';

const formatDate = (dateStr) => {
  if (!dateStr) return '—';
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(dateStr));
  } catch {
    return dateStr;
  }
};

const DirectionBadge = ({ direction }) => {
  const isAchat = direction?.toUpperCase() === 'ACHAT' || direction?.toUpperCase() === 'BUY' || direction?.toUpperCase() === 'LONG';
  return (
    <span style={{
      display: 'inline-block',
      padding: '0.3rem 0.9rem',
      borderRadius: '6px',
      fontSize: '0.8rem',
      fontWeight: '700',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      backgroundColor: isAchat ? 'rgba(0, 196, 140, 0.15)' : 'rgba(255, 77, 109, 0.15)',
      color: isAchat ? 'var(--green)' : 'var(--red)',
      border: `1px solid ${isAchat ? 'rgba(0, 196, 140, 0.4)' : 'rgba(255, 77, 109, 0.4)'}`,
    }}>
      {direction || '—'}
    </span>
  );
};

const StatusBadge = ({ statut }) => {
  const colors = {
    OUVERT: { bg: 'rgba(108, 99, 255, 0.15)', color: 'var(--accent)', border: 'rgba(108, 99, 255, 0.3)' },
    FERME: { bg: 'rgba(148, 163, 184, 0.15)', color: 'var(--text2)', border: 'rgba(148, 163, 184, 0.3)' },
    CLOTURE: { bg: 'rgba(148, 163, 184, 0.15)', color: 'var(--text2)', border: 'rgba(148, 163, 184, 0.3)' },
    EN_ATTENTE: { bg: 'rgba(255, 209, 102, 0.15)', color: 'var(--yellow)', border: 'rgba(255, 209, 102, 0.3)' },
  };
  const key = statut?.toUpperCase().replace(/ /g, '_') || '';
  const style = colors[key] || { bg: 'rgba(148, 163, 184, 0.15)', color: 'var(--text2)', border: 'rgba(148, 163, 184, 0.3)' };
  return (
    <span style={{
      display: 'inline-block',
      padding: '0.3rem 0.9rem',
      borderRadius: '6px',
      fontSize: '0.8rem',
      fontWeight: '700',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      backgroundColor: style.bg,
      color: style.color,
      border: `1px solid ${style.border}`,
    }}>
      {statut || '—'}
    </span>
  );
};

const OrderHeader = ({ order }) => {
  if (!order) return null;

  const ticker = order.ticker || order.actif || '—';
  const nom = order.nom || order.nom_actif || '';
  const classe = order.classe_actif || order.classe || '';

  return (
    <div style={styles.container}>
      <div style={styles.left}>
        <div style={styles.tickerRow}>
          <h1 style={styles.ticker}>{ticker}</h1>
          <div style={styles.badges}>
            <DirectionBadge direction={order.direction} />
            <StatusBadge statut={order.statut} />
          </div>
        </div>
        {(nom || classe) && (
          <div style={styles.subtitle}>
            {nom && <span>{nom}</span>}
            {nom && classe && <span style={styles.dot}>•</span>}
            {classe && <span style={{ color: 'var(--text2)' }}>{classe}</span>}
          </div>
        )}
        <div style={styles.meta}>
          <span style={styles.metaLabel}>Ouvert le:</span>
          <span style={styles.metaValue}>{formatDate(order.date_ouverture || order.date_ordre)}</span>
          {(order.id_ordre || order.id) && (
            <>
              <span style={styles.dot}>•</span>
              <span style={styles.metaLabel}>ID:</span>
              <span style={{ ...styles.metaValue, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                {order.id_ordre || order.id}
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    padding: '1.5rem 2rem',
    marginBottom: '1.5rem',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  left: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  tickerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
    flexWrap: 'wrap',
  },
  ticker: {
    fontSize: '2rem',
    fontWeight: '800',
    color: 'var(--text)',
    letterSpacing: '-0.02em',
    margin: 0,
  },
  badges: {
    display: 'flex',
    gap: '0.5rem',
    alignItems: 'center',
  },
  subtitle: {
    fontSize: '0.9rem',
    color: 'var(--text)',
    display: 'flex',
    gap: '0.5rem',
    alignItems: 'center',
  },
  meta: {
    display: 'flex',
    gap: '0.5rem',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  metaLabel: {
    fontSize: '0.8rem',
    color: 'var(--text2)',
  },
  metaValue: {
    fontSize: '0.8rem',
    color: 'var(--text)',
  },
  dot: {
    color: 'var(--border)',
  },
};

export default OrderHeader;
