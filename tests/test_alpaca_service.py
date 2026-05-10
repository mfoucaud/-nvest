"""test_alpaca_service.py — Tests pour alpaca_service (TradingClient mocké)."""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("ALPACA_API_KEY", "test-key")
os.environ.setdefault("ALPACA_SECRET_KEY", "test-secret")

import backend.services.alpaca_service as alpaca_service


def test_get_account_returns_equity():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_account = MagicMock()
        mock_account.equity = "10500.00"
        mock_account.buying_power = "9500.00"
        mock_account.currency = "USD"
        MockClient.return_value.get_account.return_value = mock_account

        result = alpaca_service.get_account()

        assert result["equity"] == 10500.0
        assert result["buying_power"] == 9500.0
        assert result["currency"] == "USD"


def test_get_positions_empty():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        MockClient.return_value.get_all_positions.return_value = []
        result = alpaca_service.get_positions()
        assert result == []


def test_get_positions_returns_formatted_list():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        pos = MagicMock()
        pos.asset_id = "asset-uuid-001"
        pos.symbol = "AAPL"
        pos.qty = "6.67"
        pos.avg_entry_price = "150.0"
        pos.current_price = "155.0"
        pos.unrealized_pl = "33.35"
        pos.asset_class = "AssetClass.US_EQUITY"
        pos.side = "PositionSide.LONG"
        MockClient.return_value.get_all_positions.return_value = [pos]

        result = alpaca_service.get_positions()

        assert len(result) == 1
        assert result[0]["actif"] == "AAPL"
        assert result[0]["statut"] == "OUVERT"
        assert result[0]["direction"] == "ACHAT"
        assert result[0]["prix_entree"] == 150.0
        assert result[0]["prix_actuel"] == 155.0
        assert result[0]["pnl_latent"] == 33.35


def test_get_portfolio_history_empty():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_history = MagicMock()
        mock_history.timestamp = []
        mock_history.equity = []
        MockClient.return_value.get_portfolio_history.return_value = mock_history

        result = alpaca_service.get_portfolio_history()
        assert result == []


def test_get_portfolio_history_returns_formatted_list():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_history = MagicMock()
        mock_history.timestamp = [1735689600]  # 2025-01-01 00:00:00 UTC
        mock_history.equity = [10500.0]
        MockClient.return_value.get_portfolio_history.return_value = mock_history

        result = alpaca_service.get_portfolio_history()

        assert len(result) == 1
        assert result[0]["capital"] == 10500.0
        assert "date" in result[0]
