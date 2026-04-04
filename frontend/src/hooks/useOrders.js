import { useState, useEffect, useCallback } from 'react';
import { fetchOrders, refreshOrders } from '../services/api';

const useOrders = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      await refreshOrders();
    } catch {
      // refresh échoue silencieusement — on re-fetch quand même
    }
    setTick((t) => t + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await fetchOrders();
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
  }, [tick]);

  return { data, loading, error, refetch };
};

export default useOrders;
