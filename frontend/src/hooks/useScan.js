import { useState, useEffect, useRef, useCallback } from 'react';
import { runScan, fetchScanStatus } from '../services/api';

const today = () => new Date().toISOString().slice(0, 10);

const useScan = (onDone) => {
  const [status, setStatus]   = useState(null); // dernier scan connu
  const [running, setRunning] = useState(false);
  const [error, setError]     = useState(null);
  const pollRef = useRef(null);

  const stopPoll = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const pollStatus = useCallback(async () => {
    try {
      const s = await fetchScanStatus();
      setStatus(s);
      if (s.status !== 'en_cours') {
        stopPoll();
        setRunning(false);
        if (onDone) onDone();
      }
    } catch { /* silencieux */ }
  }, [onDone]);

  // Charge le statut initial au montage
  useEffect(() => {
    fetchScanStatus().then(setStatus).catch(() => {});
    return stopPoll;
  }, []);

  const launch = useCallback(async () => {
    setError(null);
    setRunning(true);
    try {
      const res = await runScan();
      if (res.status === 'already_running') {
        // déjà en cours, on poll quand même
      }
      pollRef.current = setInterval(pollStatus, 3000);
    } catch (e) {
      setError(e.message);
      setRunning(false);
    }
  }, [pollStatus]);

  // Le scan du jour a déjà généré le max d'ordres ?
  const todayDone = status &&
    status.started_at?.slice(0, 10) === today() &&
    status.status === 'termine' &&
    status.nb_ordres_generes >= 2;

  return { status, running, error, launch, todayDone };
};

export default useScan;
