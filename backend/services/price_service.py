"""
price_service.py — Récupération des historiques de prix via yfinance.

Cache en mémoire avec TTL de 15 minutes pour éviter les appels répétés
à l'API Yahoo Finance pendant une même session.

Tickers supportés : actions (ex: NVDA, TSLA, AAPL, MSFT)
                    et cryptos compatibles yfinance (ex: ETH-USD, BTC-USD).
"""

import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# Cache en mémoire
# ---------------------------------------------------------------------------

# Structure: { ticker_days_key: {"expires_at": float, "data": list[dict]} }
_cache: dict = {}

CACHE_TTL_SECONDS = 15 * 60  # 15 minutes


def _cache_key(ticker: str, days: int) -> str:
    return f"{ticker.upper()}:{days}"


def _get_from_cache(ticker: str, days: int) -> Optional[list]:
    """Retourne les données du cache si elles sont encore valides, sinon None."""
    key = _cache_key(ticker, days)
    entry = _cache.get(key)
    if entry is None:
        return None
    if time.monotonic() > entry["expires_at"]:
        # Entrée expirée : on la supprime
        del _cache[key]
        return None
    return entry["data"]


def _set_cache(ticker: str, days: int, data: list) -> None:
    """Stocke les données dans le cache avec expiration TTL."""
    key = _cache_key(ticker, days)
    _cache[key] = {
        "expires_at": time.monotonic() + CACHE_TTL_SECONDS,
        "data": data,
    }


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------

def get_price_history(ticker: str, days: int = 10) -> list[dict]:
    """
    Retourne l'historique de prix pour un ticker sur les `days` derniers jours.

    Paramètres:
        ticker: Symbole boursier (ex: "NVDA", "ETH-USD").
                Les cryptos doivent utiliser le format Yahoo Finance (ex: "ETH-USD").
        days:   Nombre de jours d'historique (1 à 90).

    Retourne:
        Liste de dicts ordonnés du plus ancien au plus récent :
        [{"date": "YYYY-MM-DD", "open": float, "high": float,
          "low": float, "close": float, "volume": int}, ...]

    Lève:
        RuntimeError: Si yfinance ne renvoie aucune donnée ou échoue.
        ValueError:   Si le ticker est vide ou les paramètres invalides.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Le ticker ne peut pas être vide.")

    if days < 1 or days > 365:
        raise ValueError(f"Le paramètre 'days' doit être compris entre 1 et 365 (reçu: {days}).")

    # Vérification du cache avant tout appel réseau
    cached = _get_from_cache(ticker, days)
    if cached is not None:
        print(f"[price_service] Cache HIT pour {ticker} ({days}j)")
        return cached

    print(f"[price_service] Appel yfinance pour {ticker} ({days}j)...")

    # yfinance attend une période ou un intervalle de dates
    # On utilise period via start/end pour un contrôle précis
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days + 5)  # marge pour les jours fériés/week-ends

    try:
        tkr = yf.Ticker(ticker)
        df = tkr.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,   # prix ajustés aux splits/dividendes
            actions=False,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Échec de la requête yfinance pour '{ticker}' : {exc}"
        ) from exc

    if df is None or df.empty:
        raise RuntimeError(
            f"yfinance n'a retourné aucune donnée pour le ticker '{ticker}'. "
            "Vérifiez que le symbole est correct (ex: 'ETH-USD' pour Ethereum)."
        )

    # Filtrer sur les `days` derniers jours effectifs (après exclusion des W-E et fériés)
    df = df.tail(days)

    # Conversion en liste de dicts
    result: list[dict] = []
    for date_index, row in df.iterrows():
        # L'index est un Timestamp (pandas), on extrait la date
        date_str = date_index.strftime("%Y-%m-%d")
        result.append({
            "date": date_str,
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
        })

    if not result:
        raise RuntimeError(
            f"Historique vide après traitement pour '{ticker}'. "
            "Le marché était peut-être fermé sur la période demandée."
        )

    _set_cache(ticker, days, result)
    print(f"[price_service] {len(result)} bougies récupérées pour {ticker} → mises en cache (TTL 15min)")

    return result
