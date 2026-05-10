"""
alpaca_service.py — Client Alpaca Paper Trading centralisé.
"""
import os
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOrdersRequest,
    GetPortfolioHistoryRequest,
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

_ASSET_CLASS_MAP = {
    "us_equity": "Action",
    "crypto": "Crypto",
    "forex": "Forex",
}


def _get_client() -> TradingClient:
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
