import React from 'react';
import { useNavigate } from 'react-router-dom';

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
      year: '2-digit',
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
      padding: '0.2rem 0.6rem',
      borderRadius: '4px',
      fontSize: '0.7rem',
      fontWeight: '700',
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
      backgroundColor: isAchat ? 'rgba(0, 196, 140, 0.15)' : 'rgba(255, 77, 109, 0.15)',
      color: isAchat ? 'var(--green)' : 'var(--red)',
      border: `1px solid ${isAchat ? 'rgba(0, 196, 140, 0.3)' : 'rgba(255, 77, 109, 0.3)'}`,
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
      padding: '0.2rem 0.6rem',
      borderRadius: '4px',
      fontSize: '0.7rem',
      fontWeight: '700',
      textTransform: 'uppercase',
      letterSpacing: '0.05em',
      backgroundColor: style.bg,
      color: style.color,
      border: `1px solid ${style.border}`,
    }}>
      {statut || '—'}
    </span>
  );
};

const PnlCell = ({ value }) => {
  if (value === null || value === undefined) return <td style={styles.td}>—</td>;
  const color = value >= 0 ? 'var(--green)' : 'var(--red)';
  const formatted = new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 2,
    signDisplay: 'always',
  }).format(value);
  return (
    <td style={{ ...styles.td, color, fontWeight: '600' }}>{formatted}</td>
  );
};

const OrdersTable = ({ orders }) => {
  const navigate = useNavigate();

  if (!orders || orders.length === 0) {
    return (
      <div style={styles.empty}>
        Aucune position à afficher.
      </div>
    );
  }

  return (
    <div style={styles.wrapper}>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>ID</th>
            <th style={styles.th}>Actif</th>
            <th style={styles.th}>Classe</th>
            <th style={styles.th}>Direction</th>
            <th style={styles.th}>Entrée</th>
            <th style={styles.th}>Actuel</th>
            <th style={styles.th}>SL</th>
            <th style={styles.th}>TP</th>
            <th style={styles.th}>P&L Latent</th>
            <th style={styles.th}>Conf.</th>
            <th style={styles.th}>Expiration</th>
            <th style={styles.th}>Statut</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr
              key={order.id_ordre || order.id}
              style={styles.row}
              onClick={() => navigate(`/orders/${order.id_ordre || order.id}`)}
              title="Voir le détail"
            >
              <td style={styles.td}>
                <span style={styles.idCell}>
                  {order.alerte && <span title="Alerte active" style={{ marginRight: '0.25rem' }}>⚠️</span>}
                  {order.id_ordre || order.id}
                </span>
              </td>
              <td style={{ ...styles.td, fontWeight: '600', color: 'var(--text)' }}>
                {order.ticker || order.actif || '—'}
              </td>
              <td style={{ ...styles.td, color: 'var(--text2)' }}>
                {order.classe_actif || order.classe || '—'}
              </td>
              <td style={styles.td}>
                <DirectionBadge direction={order.direction} />
              </td>
              <td style={styles.td}>{formatNumber(order.prix_entree)}</td>
              <td style={{ ...styles.td, color: 'var(--accent2)' }}>
                {formatNumber(order.prix_actuel || order.cours_actuel)}
              </td>
              <td style={{ ...styles.td, color: 'var(--red)' }}>
                {formatNumber(order.stop_loss)}
              </td>
              <td style={{ ...styles.td, color: 'var(--green)' }}>
                {formatNumber(order.take_profit)}
              </td>
              <PnlCell value={order.pnl_latent} />
              <td style={styles.td}>
                {order.confiance !== undefined && order.confiance !== null
                  ? `${order.confiance}%`
                  : order.score_confiance !== undefined && order.score_confiance !== null
                  ? `${order.score_confiance}/10`
                  : '—'}
              </td>
              <td style={{ ...styles.td, color: 'var(--text2)' }}>
                {formatDate(order.date_expiration || order.expiration)}
              </td>
              <td style={styles.td}>
                <StatusBadge statut={order.statut} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const styles = {
  wrapper: {
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    overflow: 'hidden',
    marginBottom: '2rem',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    padding: '0.875rem 1rem',
    textAlign: 'left',
    fontSize: '0.7rem',
    fontWeight: '600',
    color: 'var(--text2)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    backgroundColor: 'var(--bg3)',
    borderBottom: '1px solid var(--border)',
    whiteSpace: 'nowrap',
  },
  td: {
    padding: '0.875rem 1rem',
    fontSize: '0.875rem',
    color: 'var(--text)',
    borderBottom: '1px solid var(--border)',
    whiteSpace: 'nowrap',
  },
  row: {
    cursor: 'pointer',
    transition: 'background-color 0.15s',
  },
  idCell: {
    fontFamily: 'monospace',
    fontSize: '0.8rem',
    color: 'var(--text2)',
  },
  empty: {
    padding: '3rem',
    textAlign: 'center',
    color: 'var(--text2)',
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    marginBottom: '2rem',
  },
};

export default OrdersTable;
