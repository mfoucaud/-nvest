"""
scanner.py — Scan des marchés : indicateurs techniques et scoring.

Tickers scannés : actions, cryptos, forex, ETFs (liste configurable).
Score technique de 0 à 85 pts basé sur RSI, MACD, Bollinger, EMA, Volume, Support.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

TICKERS: list[str] = [
    # Actions US
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META",
    # Actions FR
    "LVMH.PA", "TTE.PA", "AIR.PA",
    # Crypto
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD",
    # Forex
    "EURUSD=X", "GBPUSD=X", "USDJPY=X",
    # ETF
    "SPY", "QQQ",
]

TICKER_CLASS: dict[str, str] = {
    "AAPL": "Action", "MSFT": "Action", "NVDA": "Action", "TSLA": "Action",
    "AMZN": "Action", "GOOGL": "Action", "META": "Action",
    "LVMH.PA": "Action", "TTE.PA": "Action", "AIR.PA": "Action",
    "BTC-USD": "Crypto", "ETH-USD": "Crypto", "SOL-USD": "Crypto", "BNB-USD": "Crypto",
    "EURUSD=X": "Forex", "GBPUSD=X": "Forex", "USDJPY=X": "Forex",
    "SPY": "ETF", "QQQ": "ETF",
}


@dataclass
class Candidate:
    ticker: str
    classe: str
    prix: float
    rsi: float
    macd_signal: str       # "haussier" | "baissier"
    atr: float
    score_technique: int
    detail_score: dict
    direction: str = "ACHAT"


# ---------------------------------------------------------------------------
# Indicateurs
# ---------------------------------------------------------------------------

def calc_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    last_gain = float(gain.iloc[-1])
    last_loss = float(loss.iloc[-1])
    if np.isnan(last_gain) or np.isnan(last_loss):
        return 50.0
    if last_loss == 0:
        return 100.0 if last_gain > 0 else 50.0
    rs  = last_gain / last_loss
    val = 100 - (100 / (1 + rs))
    return round(val, 2)


def calc_macd(close: pd.Series) -> tuple[float, float]:
    ema12  = close.ewm(span=12, adjust=False).mean()
    ema26  = close.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(signal.iloc[-1])


def calc_bollinger(close: pd.Series, period: int = 20) -> tuple[float, float]:
    sma   = close.rolling(period).mean()
    std   = close.rolling(period).std()
    lower = sma - 2 * std
    upper = sma + 2 * std
    return float(lower.iloc[-1]), float(upper.iloc[-1])


def calc_ema(close: pd.Series) -> tuple[float, float]:
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    return ema20, ema50


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    tr = pd.DataFrame({
        "hl": high - low,
        "hc": (high - close.shift()).abs(),
        "lc": (low - close.shift()).abs(),
    }).max(axis=1)
    val = float(tr.rolling(period).mean().iloc[-1])
    return round(val if not np.isnan(val) else 0.0, 4)


def score_from_indicators(
    rsi: float, macd_val: float, macd_sig: float,
    prix: float, bb_lower: float, bb_upper: float,
    ema20: float, ema50: float,
    vol_actuel: float, vol_moy: float,
) -> tuple[int, dict]:
    """Calcule le score technique et retourne (score, detail_score)."""
    detail: dict[str, int] = {
        "rsi_survente": 0,
        "macd_croisement": 0,
        "bollinger_rebond": 0,
        "ema_tendance": 0,
        "volume_confirmation": 0,
        "support_horizontal": 0,
        "bonus_actualite_positive": 0,
        "bonus_sentiment_haussier": 0,
        "bonus_aucune_actualite_negative": 0,
        "malus_evenement_macro": 0,
        "malus_actualite_negative": 0,
        "malus_resultats_proches": 0,
    }

    if rsi < 35:
        detail["rsi_survente"] = 20
    if macd_val > macd_sig:
        detail["macd_croisement"] = 20
    if bb_lower > 0 and prix <= bb_lower * 1.02:
        detail["bollinger_rebond"] = 15
    if ema20 > ema50:
        detail["ema_tendance"] = 15
    if vol_moy > 0 and vol_actuel > vol_moy * 1.5:
        detail["volume_confirmation"] = 15

    score = sum(detail.values())
    return score, detail


# ---------------------------------------------------------------------------
# Scan d'un ticker
# ---------------------------------------------------------------------------

def scan_ticker(ticker: str) -> Optional[Candidate]:
    """Retourne un Candidate si le ticker est éligible (score ≥ 30), sinon None."""
    try:
        hist = yf.Ticker(ticker).history(period="60d", interval="1d")
        if len(hist) < 50:
            return None

        close  = hist["Close"]
        high   = hist["High"]
        low    = hist["Low"]
        volume = hist["Volume"]
        prix   = round(float(close.iloc[-1]), 4)

        rsi              = calc_rsi(close)
        macd_val, macd_sig = calc_macd(close)
        bb_lower, bb_upper = calc_bollinger(close)
        ema20, ema50     = calc_ema(close)
        atr              = calc_atr(high, low, close)
        vol_moy          = float(volume.rolling(10).mean().iloc[-1])
        vol_actuel       = float(volume.iloc[-1])

        score, detail = score_from_indicators(
            rsi=rsi, macd_val=macd_val, macd_sig=macd_sig,
            prix=prix, bb_lower=bb_lower, bb_upper=bb_upper,
            ema20=ema20, ema50=ema50,
            vol_actuel=vol_actuel, vol_moy=vol_moy,
        )

        if score < 30:
            return None

        macd_signal = "haussier" if macd_val > macd_sig else "baissier"
        return Candidate(
            ticker=ticker,
            classe=TICKER_CLASS.get(ticker, "Action"),
            prix=prix,
            rsi=rsi,
            macd_signal=macd_signal,
            atr=atr,
            score_technique=score,
            detail_score=detail,
        )
    except Exception as e:
        logger.warning(f"scan_ticker {ticker} failed: {e}")
        return None


def scan_all() -> list[Candidate]:
    """Scanne tous les tickers et retourne les candidats triés par score décroissant."""
    candidates = [c for c in (scan_ticker(t) for t in TICKERS) if c is not None]
    candidates.sort(key=lambda c: c.score_technique, reverse=True)
    return candidates
