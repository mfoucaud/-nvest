import React from 'react';

const formatCapital = (value) => {
  if (value === null || value === undefined) return '—';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: 0,
  }).format(value);
};

const formatDate = (date) => {
  return new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(date);
};

const Header = ({ capital }) => {
  const today = new Date();

  return (
    <header style={styles.header}>
      <div style={styles.inner}>
        <div style={styles.left}>
          <span style={styles.title}>📈 Trading Fictif</span>
          <span style={styles.date}>{formatDate(today)}</span>
        </div>
        <div style={styles.right}>
          <span style={styles.capitalLabel}>Capital</span>
          <span style={styles.capitalBadge}>{formatCapital(capital)}</span>
        </div>
      </div>
    </header>
  );
};

const styles = {
  header: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 100,
    backgroundColor: 'var(--bg2)',
    borderBottom: '1px solid var(--border)',
    padding: '0 2rem',
    height: '64px',
    display: 'flex',
    alignItems: 'center',
  },
  inner: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    maxWidth: '1400px',
    margin: '0 auto',
  },
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: '1.5rem',
  },
  title: {
    fontSize: '1.25rem',
    fontWeight: '700',
    color: 'var(--text)',
    letterSpacing: '-0.02em',
  },
  date: {
    fontSize: '0.875rem',
    color: 'var(--text2)',
    textTransform: 'capitalize',
  },
  right: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
  },
  capitalLabel: {
    fontSize: '0.875rem',
    color: 'var(--text2)',
  },
  capitalBadge: {
    backgroundColor: 'var(--bg3)',
    border: '1px solid var(--border)',
    borderRadius: '8px',
    padding: '0.375rem 1rem',
    fontSize: '1rem',
    fontWeight: '700',
    color: 'var(--accent2)',
    letterSpacing: '0.01em',
  },
};

export default Header;
