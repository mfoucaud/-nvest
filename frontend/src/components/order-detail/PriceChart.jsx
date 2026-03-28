import React, { useState, useMemo } from 'react';
import {
  ComposedChart,
  LineChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import usePriceHistory from '../../hooks/usePriceHistory';

// ─── Période ──────────────────────────────────────────────────────────────────

const PERIODS = [
  { label: '10J', days: 10 },
  { label: '1M',  days: 30 },
  { label: '1A',  days: 252 },
];

// Période de chauffe pour calculer correctement BB(20) et RSI(14)
// On fetch WARMUP jours supplémentaires et on les exclut de l'affichage
const WARMUP = 20;

// ─── Utilitaires ──────────────────────────────────────────────────────────────

const formatDate = (dateStr, days) => {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    const opts =
      days <= 30
        ? { day: '2-digit', month: '2-digit' }
        : { month: 'short', year: '2-digit' };
    return new Intl.DateTimeFormat('fr-FR', opts).format(d);
  } catch {
    return dateStr;
  }
};

const formatPrice = (value) => {
  if (value == null) return '—';
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value);
};

// ─── Indicateurs techniques ───────────────────────────────────────────────────

/** RSI 14 périodes (Wilder) */
const calcRSI = (closes) => {
  const period = 14;
  const rsi = closes.map(() => null);
  if (closes.length < period + 1) return rsi;

  let gains = 0;
  let losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = closes[i] - closes[i - 1];
    if (diff > 0) gains += diff;
    else losses -= diff;
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;
  rsi[period] = avgLoss === 0 ? 100 : +(100 - 100 / (1 + avgGain / avgLoss)).toFixed(2);

  for (let i = period + 1; i < closes.length; i++) {
    const diff = closes[i] - closes[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
    rsi[i] = avgLoss === 0 ? 100 : +(100 - 100 / (1 + avgGain / avgLoss)).toFixed(2);
  }

  return rsi;
};

/** Bandes de Bollinger 20 périodes, 2 écarts-types */
const calcBollinger = (closes) => {
  const period = 20;
  return closes.map((_, i) => {
    if (i < period - 1) {
      return { bb_mid: null, bb_upper: null, bb_lower: null, bb_band: null };
    }
    const slice = closes.slice(i - period + 1, i + 1);
    const mean = slice.reduce((s, v) => s + v, 0) / period;
    const stdDev = Math.sqrt(
      slice.reduce((s, v) => s + (v - mean) ** 2, 0) / period
    );
    return {
      bb_mid:   +(mean).toFixed(4),
      bb_upper: +(mean + 2 * stdDev).toFixed(4),
      bb_lower: +(mean - 2 * stdDev).toFixed(4),
      bb_band:  +(4 * stdDev).toFixed(4), // largeur de la bande = bb_upper - bb_lower
    };
  });
};

// ─── Chandelles japonaises (Customized layer — utilise les échelles recharts) ──

// ─── Chandelle japonaise (custom shape pour <Bar>) ────────────────────────────

const CandlestickShape = ({ x, width, background, payload, domainMin, domainMax }) => {
  if (!payload || !background) return null;
  const { open, high, low, close } = payload;
  if (open == null || close == null || high == null || low == null) return null;

  const range = domainMax - domainMin;
  if (range === 0) return null;

  const { y: chartTop, height: chartH } = background;
  const toY = (price) => chartTop + chartH * (1 - (price - domainMin) / range);

  const highY    = toY(high);
  const lowY     = toY(low);
  const bodyTopY = toY(Math.max(open, close));
  const bodyBotY = toY(Math.min(open, close));
  const bodyH    = Math.max(bodyBotY - bodyTopY, 1);
  const color    = close >= open ? '#00c48c' : '#ff4d6d';
  const cx = x + width / 2;
  const bx = x + width * 0.15;
  const bw = Math.max(width * 0.7, 1);

  return (
    <g>
      <line x1={cx} y1={highY}    x2={cx} y2={bodyTopY}  stroke={color} strokeWidth={1.5} />
      <rect x={bx}  y={bodyTopY}  width={bw} height={bodyH} fill={color} />
      <line x1={cx} y1={bodyBotY} x2={cx} y2={lowY}      stroke={color} strokeWidth={1.5} />
    </g>
  );
};

// ─── Labels de référence ──────────────────────────────────────────────────────

const RefLabel = ({ viewBox, value, color }) => {
  const { x, y, width } = viewBox;
  return (
    <text x={x + (width || 0) - 4} y={y - 5} fill={color} fontSize={10} textAnchor="end">
      {value}
    </text>
  );
};

// ─── Tooltips ────────────────────────────────────────────────────────────────

const PriceTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div style={tt}>
      <div style={{ color: '#94a3b8', fontSize: '0.72rem', marginBottom: '0.3rem' }}>{label}</div>
      {d.open  != null && <Row label="O" value={formatPrice(d.open)}  color="#e2e8f0" />}
      {d.high  != null && <Row label="H" value={formatPrice(d.high)}  color="#00c48c" />}
      {d.low   != null && <Row label="L" value={formatPrice(d.low)}   color="#ff4d6d" />}
      {d.close != null && <Row label="C" value={formatPrice(d.close)} color="#6c63ff" />}
      {d.bb_upper != null && (
        <>
          <div style={{ borderTop: '1px solid #2d3748', margin: '0.3rem 0' }} />
          <Row label="BB+" value={formatPrice(d.bb_upper)} color="rgba(108,99,255,0.7)" />
          <Row label="BB~" value={formatPrice(d.bb_mid)}   color="rgba(108,99,255,0.5)" />
          <Row label="BB−" value={formatPrice(d.bb_lower)} color="rgba(108,99,255,0.7)" />
        </>
      )}
    </div>
  );
};

const RSITooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const rsi = payload[0]?.value;
  if (rsi == null) return null;
  const color = rsi >= 70 ? '#ff4d6d' : rsi <= 30 ? '#00c48c' : '#ffd166';
  return (
    <div style={tt}>
      <div style={{ color: '#94a3b8', fontSize: '0.72rem' }}>{label}</div>
      <Row label="RSI(14)" value={rsi.toFixed(1)} color={color} />
    </div>
  );
};

const Row = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', fontSize: '0.8rem', color }}>
    <span style={{ opacity: 0.7 }}>{label}</span>
    <span style={{ fontWeight: 600 }}>{value}</span>
  </div>
);

const tt = {
  backgroundColor: '#1a1d27',
  border: '1px solid #2d3748',
  borderRadius: '8px',
  padding: '0.55rem 0.85rem',
  minWidth: '130px',
};

// ─── Composant principal ──────────────────────────────────────────────────────

const PriceChart = ({ ticker, prixEntree, stopLoss, takeProfit }) => {
  const [period, setPeriod] = useState(PERIODS[0]);
  // On fetche period.days + WARMUP pour avoir assez de données pour RSI(14) et BB(20)
  const { data: priceData, loading, error } = usePriceHistory(ticker, period.days + WARMUP);

  const rawData = priceData?.data || [];

  const chartData = useMemo(() => {
    if (!rawData.length) return [];
    const closes = rawData.map((d) => d.close);
    const rsiArr = calcRSI(closes);
    const bbArr  = calcBollinger(closes);
    const full = rawData.map((d, i) => ({ ...d, rsi: rsiArr[i], ...bbArr[i] }));
    // N'afficher que les dernières `period.days` bougies (les données warmup sont exclues)
    return full.slice(-period.days);
  }, [rawData, period.days]);

  if (!ticker) return null;

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.state}>Chargement du graphique…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <div style={{ ...styles.state, color: '#ff4d6d' }}>
          Impossible de charger les données : {error}
        </div>
      </div>
    );
  }

  if (!chartData.length) {
    return (
      <div style={styles.container}>
        <div style={styles.state}>Aucune donnée disponible.</div>
      </div>
    );
  }

  // Domaine Y (prix + indicateurs + niveaux de référence)
  const priceLows  = chartData.map((d) => d.low).filter(Boolean);
  const priceHighs = chartData.map((d) => d.high).filter(Boolean);
  const bbLows     = chartData.map((d) => d.bb_lower).filter(Boolean);
  const bbHighs    = chartData.map((d) => d.bb_upper).filter(Boolean);
  const refPrices  = [prixEntree, stopLoss, takeProfit].filter(Boolean);
  const allVals    = [...priceLows, ...priceHighs, ...bbLows, ...bbHighs, ...refPrices];
  const domainMin  = Math.min(...allVals) * 0.998;
  const domainMax  = Math.max(...allVals) * 1.002;

  const dateFormatter = (d) => formatDate(d, period.days);

  return (
    <div style={styles.container}>
      {/* En-tête */}
      <div style={styles.header}>
        <h3 style={styles.title}>Graphique — {ticker}</h3>
        <div style={styles.periodBar}>
          {PERIODS.map((p) => (
            <button
              key={p.label}
              style={period.label === p.label ? { ...styles.btn, ...styles.btnActive } : styles.btn}
              onClick={() => setPeriod(p)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Chandelles + Bollinger ── */}
      <ResponsiveContainer width="100%" height={330}>
        <ComposedChart data={chartData} margin={{ top: 10, right: 70, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(45,55,72,0.55)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={dateFormatter}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            axisLine={{ stroke: '#2d3748' }}
            tickLine={false}
            minTickGap={30}
          />
          <YAxis
            domain={[domainMin, domainMax]}
            tickFormatter={formatPrice}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={80}
            orientation="right"
          />
          <Tooltip content={<PriceTooltip />} />

          {/* Lignes Bollinger */}
          <Line type="monotone" dataKey="bb_upper" stroke="#6c63ff" strokeWidth={1}
            strokeDasharray="4 2" dot={false} activeDot={false} isAnimationActive={false} connectNulls={false} />
          <Line type="monotone" dataKey="bb_mid"   stroke="#6c63ff" strokeWidth={1}
            strokeOpacity={0.45} dot={false} activeDot={false} isAnimationActive={false} connectNulls={false} />
          <Line type="monotone" dataKey="bb_lower" stroke="#6c63ff" strokeWidth={1}
            strokeDasharray="4 2" dot={false} activeDot={false} isAnimationActive={false} connectNulls={false} />

          {/* Chandelles japonaises */}
          <Bar
            dataKey="close"
            isAnimationActive={false}
            shape={(props) => (
              <CandlestickShape {...props} domainMin={domainMin} domainMax={domainMax} />
            )}
          />

          {/* Niveaux de référence */}
          {prixEntree && (
            <ReferenceLine y={prixEntree} stroke="#ffffff" strokeDasharray="6 3" strokeWidth={1.5}
              label={<RefLabel value={`Entrée ${formatPrice(prixEntree)}`} color="#ffffff" />} />
          )}
          {stopLoss && (
            <ReferenceLine y={stopLoss} stroke="#ff4d6d" strokeDasharray="6 3" strokeWidth={1.5}
              label={<RefLabel value={`SL ${formatPrice(stopLoss)}`} color="#ff4d6d" />} />
          )}
          {takeProfit && (
            <ReferenceLine y={takeProfit} stroke="#00c48c" strokeDasharray="6 3" strokeWidth={1.5}
              label={<RefLabel value={`TP ${formatPrice(takeProfit)}`} color="#00c48c" />} />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* ── RSI ── */}
      <div style={{ marginTop: '0.75rem' }}>
        <div style={styles.rsiTitle}>RSI (14)</div>
        <ResponsiveContainer width="100%" height={100}>
          <LineChart data={chartData} margin={{ top: 4, right: 70, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(45,55,72,0.4)" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={dateFormatter}
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              minTickGap={30}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[30, 50, 70]}
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              width={80}
              orientation="right"
            />
            <Tooltip content={<RSITooltip />} />
            <ReferenceLine y={70} stroke="#ff4d6d" strokeDasharray="3 3" strokeWidth={1} />
            <ReferenceLine y={30} stroke="#00c48c" strokeDasharray="3 3" strokeWidth={1} />
            <ReferenceLine y={50} stroke="#94a3b8" strokeDasharray="2 4" strokeWidth={0.5} strokeOpacity={0.4} />
            <Line
              type="monotone"
              dataKey="rsi"
              stroke="#ffd166"
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 3, fill: '#ffd166' }}
              isAnimationActive={false}
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* ── Légende ── */}
      <div style={styles.legend}>
        <span style={{ color: '#00c48c' }}>▲ Haussier</span>
        <span style={{ color: '#ff4d6d' }}>▼ Baissier</span>
        <span style={{ color: '#6c63ff' }}>— Bollinger (20,2)</span>
        <span style={{ color: '#ffd166' }}>— RSI (14)</span>
        {prixEntree && <span style={{ color: '#ffffff' }}>— Entrée</span>}
        {stopLoss    && <span style={{ color: '#ff4d6d' }}>— SL</span>}
        {takeProfit  && <span style={{ color: '#00c48c' }}>— TP</span>}
      </div>
    </div>
  );
};

// ─── Styles ───────────────────────────────────────────────────────────────────

const styles = {
  container: {
    backgroundColor: 'var(--bg2)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    padding: '1.5rem',
    marginBottom: '1.5rem',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '1.25rem',
    flexWrap: 'wrap',
    gap: '0.75rem',
  },
  title: {
    fontSize: '0.875rem',
    fontWeight: '600',
    color: 'var(--text2)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    margin: 0,
  },
  periodBar: {
    display: 'flex',
    gap: '0.375rem',
  },
  btn: {
    padding: '0.25rem 0.65rem',
    fontSize: '0.75rem',
    fontWeight: '600',
    borderRadius: '6px',
    border: '1px solid var(--border)',
    backgroundColor: 'transparent',
    color: 'var(--text2)',
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  btnActive: {
    backgroundColor: 'var(--accent)',
    borderColor: 'var(--accent)',
    color: '#ffffff',
  },
  rsiTitle: {
    fontSize: '0.68rem',
    fontWeight: '700',
    color: '#ffd166',
    textTransform: 'uppercase',
    letterSpacing: '0.07em',
    marginBottom: '0.15rem',
    paddingLeft: '4px',
  },
  legend: {
    display: 'flex',
    gap: '1.25rem',
    marginTop: '1rem',
    fontSize: '0.75rem',
    flexWrap: 'wrap',
    color: 'var(--text2)',
  },
  state: {
    padding: '4rem',
    textAlign: 'center',
    color: 'var(--text2)',
  },
};

export default PriceChart;
