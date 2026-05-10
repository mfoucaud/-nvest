"""
alpaca_service.py — Client Alpaca Paper Trading centralisé.
"""
import os
from datetime import datetime, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetPortfolioHistoryRequest


def _get_client() -> TradingClient:
    # New instance per call — keeps mocking straightforward and avoids stale auth.
    return TradingClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
        paper=True,
    )


def get_account() -> dict:
    """Retourne equity et buying_power depuis le compte Alpaca Paper."""
    client = _get_client()
    account = client.get_account()
    return {
        "equity": float(account.equity),
        "buying_power": float(account.buying_power),
        "currency": account.currency,
    }


def get_positions() -> list[dict]:
    """Retourne les positions ouvertes au format dashboard."""
    client = _get_client()
    positions = client.get_all_positions()
    result = []
    for p in positions:
        entry = float(p.avg_entry_price)
        current = float(p.current_price)
        qty = float(p.qty)
        pnl = float(p.unrealized_pl)

        # Normalisation robuste pour us_equity → Action
        asset_str = str(p.asset_class).lower()
        if "equity" in asset_str:
            classe = "Action"
        elif "crypto" in asset_str:
            classe = "Crypto"
        elif "forex" in asset_str:
            classe = "Forex"
        else:
            classe = "Action"

        direction = "ACHAT" if "long" in str(p.side).lower() else "VENTE"
        result.append({
            "id_ordre": str(p.asset_id),
            "actif": p.symbol,
            "classe": classe,
            "direction": direction,
            "statut": "OUVERT",
            "prix_entree": entry,
            "prix_actuel": current,
            "pnl_latent": round(pnl, 2),
            "quantite_fictive": qty,
            "taille": round(entry * qty, 2),
            "stop_loss": None,
            "take_profit": None,
            "ratio_rr": None,
            "confiance": None,
            "raison": None,
            "atr_utilise": None,
            "alerte": None,
            "prix_sortie": None,
            "date_ouverture": None,
            "date_expiration": None,
            "date_cloture": None,
        })
    return result


def get_portfolio_history() -> list[dict]:
    """Retourne l'historique journalier de l'equity (pour CapitalChart)."""
    client = _get_client()
    request = GetPortfolioHistoryRequest(period="1Y", timeframe="1D")
    history = client.get_portfolio_history(history_filter=request)
    result = []
    for ts, equity in zip(history.timestamp, history.equity):
        if equity is None:
            continue
        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        result.append({"date": date_str, "capital": round(float(equity), 2), "note": None})
    return result
