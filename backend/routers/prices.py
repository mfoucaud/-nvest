"""
routers/prices.py — Endpoint pour la récupération des historiques de prix.

Prefix: /prices (monté sous /api dans main.py → URL finale: /api/prices/...)

Endpoints:
    GET /api/prices/{ticker}?days=10
        Retourne l'historique OHLCV des `days` derniers jours de trading.
        - `days` est optionnel (défaut: 10, max: 90).
        - 503 si yfinance est inaccessible ou retourne une erreur.
        - 422 si les paramètres sont invalides (FastAPI le gère automatiquement).
"""

from fastapi import APIRouter, HTTPException, Query

from backend.services.price_service import get_price_history

router = APIRouter(prefix="/prices", tags=["prices"])


# ---------------------------------------------------------------------------
# GET /api/prices/{ticker}
# ---------------------------------------------------------------------------

@router.get("/{ticker}", summary="Historique de prix OHLCV d'un actif")
def get_prices(
    ticker: str,
    days: int = Query(
        default=10,
        ge=1,
        le=365,
        description="Nombre de jours d'historique (1 à 365, défaut: 10).",
    ),
) -> dict:
    """
    Récupère l'historique de prix journalier (OHLCV) pour un ticker donné.

    **Tickers supportés** : actions US (ex: `NVDA`, `TSLA`, `AAPL`, `MSFT`)
    et cryptomonnaies au format Yahoo Finance (ex: `ETH-USD`, `BTC-USD`).

    **Réponse**:
    ```json
    {
        "ticker": "ETH-USD",
        "days_requested": 10,
        "count": 10,
        "data": [
            {"date": "2026-03-10", "open": 2010.5, "high": 2150.0,
             "low": 1995.3, "close": 2089.0, "volume": 123456789},
            ...
        ]
    }
    ```

    Retourne **503** si yfinance échoue (réseau indisponible, ticker invalide
    selon Yahoo Finance, ou données manquantes pour la période).
    """
    try:
        data = get_price_history(ticker=ticker, days=days)
    except ValueError as exc:
        # Paramètres invalides (ticker vide, days hors bornes)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Échec yfinance : service indisponible ou ticker inconnu
        raise HTTPException(
            status_code=503,
            detail=f"Impossible de récupérer les données de prix : {exc}",
        ) from exc
    except Exception as exc:
        # Filet de sécurité pour toute erreur inattendue
        raise HTTPException(
            status_code=503,
            detail=f"Erreur inattendue lors de la récupération des prix : {exc}",
        ) from exc

    return {
        "ticker": ticker.strip().upper(),
        "days_requested": days,
        "count": len(data),
        "data": data,
    }
