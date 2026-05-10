"""
alpaca_service.py — Client Alpaca Paper Trading centralisé.
"""
import os
from datetime import datetime, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetPortfolioHistoryRequest,
    GetOrdersRequest,
    MarketOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)
from alpaca.trading.enums import (
    OrderSide,
    TimeInForce,
    OrderClass,
    QueryOrderStatus,
)


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


def _determine_bracket_status(order) -> str | None:
    """Détermine CLOTURE_GAGNANT/PERDANT/EXPIRE depuis les jambes d'un ordre bracket."""
    if not order.legs:
        return None
    for leg in order.legs:
        status_str = str(leg.status).lower()
        if "filled" in status_str:
            type_str = str(leg.type).lower()
            if "limit" in type_str:
                return "CLOTURE_GAGNANT"
            if "stop" in type_str:
                return "CLOTURE_PERDANT"
    if "canceled" in str(order.status).lower():
        return "EXPIRE"
    return None


def _get_filled_leg_price(order) -> float | None:
    """Retourne le prix de la jambe remplie d'un ordre bracket."""
    if not order.legs:
        return None
    for leg in order.legs:
        if "filled" in str(leg.status).lower() and leg.filled_avg_price:
            return float(leg.filled_avg_price)
    return None


def get_closed_orders(limit: int = 50) -> list[dict]:
    """
    Retourne les ordres clôturés au format dashboard.
    Pour les ordres bracket, détermine CLOTURE_GAGNANT/PERDANT depuis la jambe remplie.
    """
    client = _get_client()
    request = GetOrdersRequest(
        status=QueryOrderStatus.CLOSED,
        limit=limit,
        nested=True,
    )
    orders = client.get_orders(filter=request)

    result = []
    for order in orders:
        order_class_str = str(order.order_class).lower()
        status_str = str(order.status).lower()

        if "bracket" in order_class_str:
            statut = _determine_bracket_status(order)
            if statut is None:
                continue
            filled_price = _get_filled_leg_price(order)
        elif "filled" in status_str:
            statut = "CLOTURE_GAGNANT"
            filled_price = float(order.filled_avg_price) if order.filled_avg_price else None
        elif "canceled" in status_str:
            statut = "EXPIRE"
            filled_price = float(order.filled_avg_price) if order.filled_avg_price else None
        else:
            continue

        entry_price = float(order.filled_avg_price) if order.filled_avg_price else None
        result.append({
            "id_ordre": str(order.id),
            "actif": order.symbol,
            "classe": "Action",
            "direction": "ACHAT" if "buy" in str(order.side).lower() else "VENTE",
            "statut": statut,
            "prix_entree": entry_price,
            "prix_sortie": filled_price,
            "prix_actuel": filled_price,
            "pnl_latent": None,
            "quantite_fictive": float(order.qty) if order.qty else None,
            "taille": None,
            "stop_loss": None,
            "take_profit": None,
            "ratio_rr": None,
            "confiance": None,
            "raison": None,
            "atr_utilise": None,
            "alerte": None,
            "date_ouverture": order.created_at.isoformat() if order.created_at else None,
            "date_expiration": None,
            "date_cloture": order.filled_at.isoformat()[:10] if order.filled_at else None,
        })
    return result


def submit_bracket_order(
    ticker: str,
    qty: float,
    side: str,
    tp: float,
    sl: float,
) -> str:
    """
    Soumet un ordre bracket Paper Trading.
    side : "ACHAT" ou "VENTE"
    Retourne l'ID Alpaca de l'ordre parent (UUID str).
    """
    client = _get_client()
    order_side = OrderSide.BUY if side == "ACHAT" else OrderSide.SELL
    request = MarketOrderRequest(
        symbol=ticker,
        qty=round(qty, 4),
        side=order_side,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=round(tp, 4)),
        stop_loss=StopLossRequest(stop_price=round(sl, 4)),
    )
    order = client.submit_order(order_data=request)
    return str(order.id)
