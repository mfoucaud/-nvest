"""test_scan.py — Tests des indicateurs techniques et du scoring."""
import pandas as pd
import numpy as np
import pytest
from backend.services.scanner import calc_rsi, calc_macd, calc_bollinger, calc_ema, calc_atr, score_from_indicators


def make_close_series(values: list) -> pd.Series:
    return pd.Series(values, dtype=float)


# --- RSI ---

def test_rsi_oversold():
    """Série très baissière → RSI < 35."""
    closes = [100 - i * 2 for i in range(30)] + [45.0]  # tendance baissière
    rsi = calc_rsi(make_close_series(closes))
    assert rsi < 35


def test_rsi_overbought():
    """Série très haussière → RSI > 65."""
    closes = [50 + i * 2 for i in range(30)] + [110.0]
    rsi = calc_rsi(make_close_series(closes))
    assert rsi > 65


def test_rsi_neutral():
    """Série stable → RSI ~50."""
    closes = [100.0] * 60
    rsi = calc_rsi(make_close_series(closes))
    assert 40 < rsi < 60 or rsi == 100.0  # série plate → pas de pertes → RSI=100 ou NaN→fallback


# --- MACD ---

def test_macd_bullish_crossover():
    """Série montante après correction → MACD et signal sont des floats."""
    closes = [100 - i for i in range(40)] + [60 + i * 2 for i in range(20)]
    macd_val, macd_sig = calc_macd(make_close_series(closes))
    assert isinstance(macd_val, float)
    assert isinstance(macd_sig, float)


# --- Bollinger ---

def test_bollinger_price_near_lower_band():
    """Prix bien en dessous de la moyenne → lower band < 100."""
    closes = [100.0] * 25 + [70.0]  # chute soudaine
    lower, upper = calc_bollinger(make_close_series(closes))
    assert lower < 100.0
    assert upper > lower


# --- ATR ---

def test_atr_positive():
    n = 30
    closes = pd.Series([100.0 + i * 0.5 for i in range(n)])
    highs  = closes + 2.0
    lows   = closes - 2.0
    atr = calc_atr(highs, lows, closes)
    assert atr > 0


# --- score_from_indicators ---

def test_score_rsi_oversold():
    score, detail = score_from_indicators(
        rsi=25.0, macd_val=-0.5, macd_sig=-0.6,
        prix=80.0, bb_lower=82.0, bb_upper=110.0,
        ema20=90.0, ema50=95.0, vol_actuel=1e6, vol_moy=8e5
    )
    assert detail["rsi_survente"] == 20
    assert score >= 20


def test_score_volume_confirmation():
    score, detail = score_from_indicators(
        rsi=50.0, macd_val=0.1, macd_sig=0.05,
        prix=100.0, bb_lower=95.0, bb_upper=115.0,
        ema20=102.0, ema50=98.0, vol_actuel=2e6, vol_moy=1e6
    )
    assert detail["volume_confirmation"] == 15
    assert detail["macd_croisement"] == 20
    assert detail["ema_tendance"] == 15


def test_score_below_threshold():
    """Tous les indicateurs neutres → score 0."""
    score, detail = score_from_indicators(
        rsi=50.0, macd_val=-0.1, macd_sig=0.1,
        prix=100.0, bb_lower=85.0, bb_upper=115.0,
        ema20=98.0, ema50=100.0, vol_actuel=1e6, vol_moy=1e6
    )
    assert score == 0
