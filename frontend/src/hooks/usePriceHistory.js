import { useState, useEffect } from 'react';
import { fetchPriceHistory } from '../services/api';

const usePriceHistory = (ticker, days = 10) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!ticker) return;

    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await fetchPriceHistory(ticker, days);
        if (!cancelled) {
          setData(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Erreur de connexion au serveur');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [ticker, days]);

  return { data, loading, error };
};

export default usePriceHistory;
