import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import useOrderDetail from '../hooks/useOrderDetail';
import OrderHeader from '../components/order-detail/OrderHeader';
import OrderMetrics from '../components/order-detail/OrderMetrics';
import ScoreCard from '../components/order-detail/ScoreCard';
import PriceChart from '../components/order-detail/PriceChart';

const SectionCard = ({ title, children }) => (
  <div style={sectionStyles.card}>
    <h3 style={sectionStyles.title}>{title}</h3>
    <div style={sectionStyles.content}>{children}</div>
  </div>
);

const sectionStyles = {
  card: {
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    padding: '1.5rem',
  },
  title: {
    fontSize: '0.75rem',
    fontWeight: '600',
    color: 'var(--text2)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    marginBottom: '0.875rem',
  },
  content: {
    fontSize: '0.9rem',
    color: 'var(--text)',
    lineHeight: '1.7',
    whiteSpace: 'pre-wrap',
  },
};

const AlertBanner = ({ message }) => (
  <div style={{
    backgroundColor: 'rgba(255, 209, 102, 0.12)',
    border: '1px solid rgba(255, 209, 102, 0.4)',
    borderRadius: '10px',
    padding: '1rem 1.25rem',
    marginBottom: '1.5rem',
    display: 'flex',
    alignItems: 'flex-start',
    gap: '0.75rem',
    color: 'var(--yellow)',
    fontSize: '0.9rem',
    lineHeight: '1.5',
  }}>
    <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>⚠️</span>
    <span>{message}</span>
  </div>
);

const SignauxList = ({ signaux }) => {
  if (!signaux) return <p style={{ color: 'var(--text2)', fontSize: '0.875rem' }}>Aucun signal disponible.</p>;

  if (typeof signaux === 'string') {
    return <p style={{ color: 'var(--text)', fontSize: '0.875rem', lineHeight: '1.7' }}>{signaux}</p>;
  }

  if (Array.isArray(signaux)) {
    return (
      <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {signaux.map((signal, i) => (
          <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontSize: '0.875rem', color: 'var(--text)' }}>
            <span style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '0.1rem' }}>›</span>
            <span>{typeof signal === 'object' ? JSON.stringify(signal) : signal}</span>
          </li>
        ))}
      </ul>
    );
  }

  if (typeof signaux === 'object') {
    return (
      <dl style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {Object.entries(signaux).map(([key, val]) => (
          <div key={key}>
            <dt style={{ fontSize: '0.7rem', color: 'var(--text2)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '0.15rem' }}>
              {key.replace(/_/g, ' ')}
            </dt>
            <dd style={{ fontSize: '0.875rem', color: 'var(--text)', margin: 0 }}>
              {typeof val === 'object' ? JSON.stringify(val) : String(val)}
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  return null;
};

const OrderDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: order, loading, error } = useOrderDetail(id);

  const ticker = order?.ticker || order?.actif;

  const decision = order?.decision || {};
  const detailScore = decision.detail_score || order?.detail_score || null;
  const signaux = decision.signaux_techniques || order?.signaux_techniques || null;
  const contexte = decision.contexte_actualite || order?.contexte_actualite || null;
  const risques = decision.risques_identifies || order?.risques_identifies || null;
  const conclusion = decision.conclusion || order?.conclusion || null;
  const sentiment = decision.sentiment_communaute || order?.sentiment_communaute || null;

  return (
    <div style={styles.page}>
      <div style={styles.main}>
        <button style={styles.backButton} onClick={() => navigate('/')}>
          ← Retour au Dashboard
        </button>

        {loading && (
          <div className="loading-container">
            <div className="spinner" />
            <span>Chargement de l'ordre...</span>
          </div>
        )}

        {error && !loading && (
          <div className="error-container">
            Erreur de connexion au serveur: {error}
          </div>
        )}

        {!loading && !error && order && (
          <>
            <OrderHeader order={order} />

            <div style={styles.grid2}>
              <OrderMetrics order={order} />
              <ScoreCard
                scoreConfiance={order.confiance ?? order.decision?.score_confiance}
                detailScore={detailScore}
              />
            </div>

            <PriceChart
              ticker={ticker}
              prixEntree={order.prix_entree}
              stopLoss={order.stop_loss}
              takeProfit={order.take_profit}
            />

            {order.alerte && (
              <AlertBanner message={typeof order.alerte === 'string' ? order.alerte : 'Alerte active sur cette position.'} />
            )}

            {signaux && (
              <SectionCard title="Analyse Technique — Signaux">
                <SignauxList signaux={signaux} />
              </SectionCard>
            )}

            {(contexte || risques) && (
              <div style={{ ...styles.grid2, marginTop: '1.5rem' }}>
                {contexte && (
                  <SectionCard title="Contexte Actualité">
                    <SignauxList signaux={contexte} />
                  </SectionCard>
                )}
                {risques && (
                  <SectionCard title="Risques Identifiés">
                    <SignauxList signaux={risques} />
                  </SectionCard>
                )}
              </div>
            )}

            {conclusion && (
              <div style={{ marginTop: '1.5rem' }}>
                <SectionCard title="Conclusion">
                  <SignauxList signaux={conclusion} />
                </SectionCard>
              </div>
            )}

            {sentiment && (
              <div style={{ marginTop: '1.5rem' }}>
                <SectionCard title="Sentiment Communauté">
                  <SignauxList signaux={sentiment} />
                </SectionCard>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

const styles = {
  page: {
    minHeight: '100vh',
    backgroundColor: 'var(--bg)',
    paddingTop: '1.5rem',
  },
  main: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '1.5rem 2rem 4rem',
  },
  backButton: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.4rem',
    color: 'var(--accent)',
    fontSize: '0.875rem',
    fontWeight: '500',
    cursor: 'pointer',
    background: 'none',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '0.4rem 0.9rem',
    marginBottom: '1.5rem',
    transition: 'border-color 0.15s, color 0.15s',
  },
  grid2: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '1.5rem',
    marginBottom: '1.5rem',
  },
};

export default OrderDetail;
