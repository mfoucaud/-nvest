"""test_alpaca_service.py — Tests pour alpaca_service (TradingClient mocké)."""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("ALPACA_API_KEY", "test-key")
os.environ.setdefault("ALPACA_SECRET_KEY", "test-secret")

import backend.services.alpaca_service as alpaca_service
from alpaca.trading.enums import OrderSide


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
        assert result[0]["classe"] == "Action"
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
        assert result[0]["date"] == "2025-01-01"
        assert result[0]["note"] is None


def test_submit_bracket_order():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-abc123"
        MockClient.return_value.submit_order.return_value = mock_order

        order_id = alpaca_service.submit_bracket_order("AAPL", qty=6.67, side="ACHAT", tp=165.0, sl=140.0)

        assert order_id == "alpaca-order-abc123"
        MockClient.return_value.submit_order.assert_called_once()


def test_submit_bracket_order_sell():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-sell-001"
        MockClient.return_value.submit_order.return_value = mock_order

        alpaca_service.submit_bracket_order("TSLA", qty=2.0, side="VENTE", tp=100.0, sl=200.0)

        call_args = MockClient.return_value.submit_order.call_args
        submitted = call_args.kwargs.get("order_data") or call_args.args[0]
        assert submitted.side == OrderSide.SELL


def test_get_closed_orders_empty():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        MockClient.return_value.get_orders.return_value = []

        result = alpaca_service.get_closed_orders()
        assert result == []


def test_get_closed_orders_bracket_gagnant():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        # Simuler un ordre bracket avec la jambe TP remplie
        tp_leg = MagicMock()
        tp_leg.status = "OrderStatus.FILLED"
        tp_leg.type = "OrderType.LIMIT"
        tp_leg.filled_avg_price = "165.0"

        sl_leg = MagicMock()
        sl_leg.status = "OrderStatus.CANCELED"
        sl_leg.type = "OrderType.STOP"
        sl_leg.filled_avg_price = None

        order = MagicMock()
        order.id = "order-uuid-001"
        order.symbol = "AAPL"
        order.order_class = "OrderClass.BRACKET"
        order.status = "OrderStatus.FILLED"
        order.side = "OrderSide.BUY"
        order.qty = "6.67"
        order.filled_avg_price = "150.0"
        order.filled_at = None
        order.created_at = None
        order.legs = [tp_leg, sl_leg]

        MockClient.return_value.get_orders.return_value = [order]

        result = alpaca_service.get_closed_orders()

        assert len(result) == 1
        assert result[0]["statut"] == "CLOTURE_GAGNANT"
        assert result[0]["prix_sortie"] == 165.0
