"""test_alpaca_service.py — Tests pour alpaca_service (TradingClient mocké)."""
import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("ALPACA_API_KEY", "test-key")
os.environ.setdefault("ALPACA_SECRET_KEY", "test-secret")


def test_get_account_returns_equity():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_account = MagicMock()
        mock_account.equity = "10500.00"
        mock_account.buying_power = "9500.00"
        mock_account.currency = "USD"
        MockClient.return_value.get_account.return_value = mock_account

        from backend.services.alpaca_service import get_account
        result = get_account()

        assert result["equity"] == 10500.0
        assert result["buying_power"] == 9500.0
        assert result["currency"] == "USD"
