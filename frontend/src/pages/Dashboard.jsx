import React from 'react';
import Header from '../components/layout/Header';
import MetricsBar from '../components/dashboard/MetricsBar';
import CapitalChart from '../components/dashboard/CapitalChart';
import OrdersTable from '../components/dashboard/OrdersTable';
import useOrders from '../hooks/useOrders';

const Dashboard = () => {
  const { data, loading, error, refetch } = useOrders();

  const metriques = data?.metriques || null;
  const historiqueCapital = data?.historique_capital || [];
  const ouverts = data?.ouverts || [];
  const clotures = data?.cloturer || [];

  return (
    <div style={styles.page}>
      <Header capital={metriques?.capital_actuel} />

      <main style={styles.main}>
        <div style={styles.topBar}>
          <span style={styles.lastUpdate}>
            {data && !loading ? `Dernière mise à jour : ${metriques?.derniere_mise_a_jour || '—'}` : ''}
          </span>
          <button
            style={{ ...styles.refreshBtn, opacity: loading ? 0.6 : 1 }}
            onClick={refetch}
            disabled={loading}
            title="Actualiser les ordres"
          >
            {loading ? '⟳ Chargement...' : '⟳ Actualiser les ordres'}
          </button>
        </div>

        {loading && (
          <div className="loading-container">
            <div className="spinner" />
            <span>Chargement du portfolio...</span>
          </div>
        )}

        {error && !loading && (
          <div className="error-container">
            Erreur de connexion au serveur: {error}
          </div>
        )}

        {!loading && !error && (
          <>
            <MetricsBar metriques={metriques} />
            <CapitalChart data={historiqueCapital} />

            <h2 style={styles.sectionTitle}>Positions Ouvertes</h2>
            <OrdersTable orders={ouverts} />

            <h2 style={styles.sectionTitle}>Historique des Trades</h2>
            {clotures.length === 0 ? (
              <div style={styles.emptyHistory}>
                Aucun trade clôturé pour le moment.
              </div>
            ) : (
              <OrdersTable orders={clotures} />
            )}
          </>
        )}
      </main>
    </div>
  );
};

const styles = {
  page: {
    minHeight: '100vh',
    backgroundColor: 'var(--bg)',
  },
  main: {
    maxWidth: '1400px',
    margin: '0 auto',
    padding: '80px 2rem 3rem',
  },
  topBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '1.5rem',
  },
  lastUpdate: {
    fontSize: '0.75rem',
    color: 'var(--text2)',
  },
  refreshBtn: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.4rem',
    padding: '0.5rem 1rem',
    borderRadius: '8px',
    border: '1px solid var(--border)',
    backgroundColor: 'var(--bg2)',
    color: 'var(--accent)',
    fontSize: '0.8rem',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'background-color 0.15s, border-color 0.15s',
  },
  sectionTitle: {
    fontSize: '0.875rem',
    fontWeight: '600',
    color: 'var(--text2)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '1rem',
  },
  emptyHistory: {
    padding: '2rem',
    textAlign: 'center',
    color: 'var(--text2)',
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    fontSize: '0.875rem',
  },
};

export default Dashboard;
