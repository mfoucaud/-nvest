"""
alpaca_service.py — Client Alpaca Paper Trading centralisé.
"""
import os

from alpaca.trading.client import TradingClient


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
