import { describe, it, expect } from 'vitest';

// ─── Copie des fonctions depuis PriceChart.jsx ────────────────────────────────
// (extraites pour être testées indépendamment)

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

const calcBollinger = (closes) => {
  const period = 20;
  return closes.map((_, i) => {
    if (i < period - 1) {
      return { bb_mid: null, bb_upper: null, bb_lower: null, bb_band: null };
    }
    const slice = closes.slice(i - period + 1, i + 1);
    const mean = slice.reduce((s, v) => s + v, 0) / period;
    const stdDev = Math.sqrt(slice.reduce((s, v) => s + (v - mean) ** 2, 0) / period);
    return {
      bb_mid:   +(mean).toFixed(4),
      bb_upper: +(mean + 2 * stdDev).toFixed(4),
      bb_lower: +(mean - 2 * stdDev).toFixed(4),
      bb_band:  +(4 * stdDev).toFixed(4),
    };
  });
};

// ─── Données de test ──────────────────────────────────────────────────────────

// 30 prix synthétiques autour de 100
const makePrices = (n, base = 100, amplitude = 5) =>
  Array.from({ length: n }, (_, i) =>
    +(base + amplitude * Math.sin(i * 0.4)).toFixed(2)
  );

// ─── RSI ─────────────────────────────────────────────────────────────────────

describe('calcRSI', () => {
  it('retourne null pour les 14 premières valeurs (pas assez de données)', () => {
    const closes = makePrices(20);
    const rsi = calcRSI(closes);
    for (let i = 0; i < 14; i++) {
      expect(rsi[i]).toBeNull();
    }
  });

  it('produit la première valeur RSI à l\'index 14', () => {
    const closes = makePrices(20);
    const rsi = calcRSI(closes);
    expect(rsi[14]).not.toBeNull();
    expect(typeof rsi[14]).toBe('number');
  });

  it('RSI est toujours compris entre 0 et 100', () => {
    const closes = makePrices(50);
    const rsi = calcRSI(closes);
    rsi.filter(v => v !== null).forEach(v => {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(100);
    });
  });

  it('RSI = 100 quand tous les mouvements sont haussiers', () => {
    const closes = Array.from({ length: 20 }, (_, i) => 100 + i);
    const rsi = calcRSI(closes);
    expect(rsi[14]).toBe(100);
  });

  it('RSI proche de 0 quand tous les mouvements sont baissiers', () => {
    const closes = Array.from({ length: 20 }, (_, i) => 200 - i);
    const rsi = calcRSI(closes);
    // avgGain = 0 → RSI = 0
    expect(rsi[14]).toBe(0);
  });

  it('retourne tout null si moins de 15 points', () => {
    const closes = makePrices(14);
    const rsi = calcRSI(closes);
    expect(rsi.every(v => v === null)).toBe(true);
  });

  it('calcule correctement avec warmup (30 points → RSI valide sur les 16 derniers)', () => {
    const closes = makePrices(30);
    const rsi = calcRSI(closes);
    const validValues = rsi.filter(v => v !== null);
    expect(validValues.length).toBe(16); // 30 - 14 = 16 valeurs
  });
});

// ─── Bollinger Bands ──────────────────────────────────────────────────────────

describe('calcBollinger', () => {
  it('retourne null pour les 19 premières valeurs', () => {
    const closes = makePrices(25);
    const bb = calcBollinger(closes);
    for (let i = 0; i < 19; i++) {
      expect(bb[i].bb_mid).toBeNull();
      expect(bb[i].bb_upper).toBeNull();
      expect(bb[i].bb_lower).toBeNull();
    }
  });

  it('produit la première valeur à l\'index 19', () => {
    const closes = makePrices(25);
    const bb = calcBollinger(closes);
    expect(bb[19].bb_mid).not.toBeNull();
    expect(bb[19].bb_upper).not.toBeNull();
    expect(bb[19].bb_lower).not.toBeNull();
  });

  it('bb_upper > bb_mid > bb_lower', () => {
    const closes = makePrices(30);
    const bb = calcBollinger(closes);
    bb.filter(v => v.bb_mid !== null).forEach(v => {
      expect(v.bb_upper).toBeGreaterThan(v.bb_mid);
      expect(v.bb_mid).toBeGreaterThan(v.bb_lower);
    });
  });

  it('bb_band = bb_upper - bb_lower (à 4 décimales)', () => {
    const closes = makePrices(30);
    const bb = calcBollinger(closes);
    bb.filter(v => v.bb_mid !== null).forEach(v => {
      const expected = +(v.bb_upper - v.bb_lower).toFixed(4);
      expect(v.bb_band).toBeCloseTo(expected, 3);
    });
  });

  it('bb_mid est la moyenne des 20 derniers closes', () => {
    const closes = makePrices(25);
    const bb = calcBollinger(closes);
    const slice = closes.slice(5, 25); // 20 derniers
    const mean = slice.reduce((s, v) => s + v, 0) / 20;
    expect(bb[24].bb_mid).toBeCloseTo(mean, 2);
  });

  it('bb_upper et bb_lower sont symétriques autour de bb_mid', () => {
    const closes = makePrices(30);
    const bb = calcBollinger(closes);
    bb.filter(v => v.bb_mid !== null).forEach(v => {
      const distUp  = +(v.bb_upper - v.bb_mid).toFixed(4);
      const distDown = +(v.bb_mid - v.bb_lower).toFixed(4);
      expect(distUp).toBeCloseTo(distDown, 3);
    });
  });

  it('retourne tout null si moins de 20 points', () => {
    const closes = makePrices(19);
    const bb = calcBollinger(closes);
    expect(bb.every(v => v.bb_mid === null)).toBe(true);
  });
});
