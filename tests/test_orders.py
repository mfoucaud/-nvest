"""Tests des endpoints orders avec alpaca_service mocké."""
import pytest
from unittest.mock import patch, MagicMock


MOCK_POSITIONS = [
    {
        "id_ordre": "asset-uuid-aapl",
        "actif": "AAPL",
        "classe": "Action",
        "direction": "ACHAT",
        "statut": "OUVERT",
        "prix_entree": 150.0,
        "prix_actuel": 155.0,
        "pnl_latent": 33.35,
        "quantite_fictive": 6.67,
        "taille": 1000.5,
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
    }
]

MOCK_ACCOUNT = {"equity": 10500.0, "buying_power": 9500.0, "currency": "USD"}


def test_list_orders_empty(client):
    with patch("backend.routers.orders.alpaca_service") as mock_alpaca:
        mock_alpaca.get_positions.return_value = []
        mock_alpaca.get_closed_orders.return_value = []
        mock_alpaca.get_account.return_value = MOCK_ACCOUNT
        mock_alpaca.get_portfolio_history.return_value = []

        response = client.get("/api/orders/")
        assert response.status_code == 200
        data = response.json()
        assert data["ouverts"] == []
        assert data["cloturer"] == []
        assert data["metriques"]["capital_actuel"] == 10500.0


def test_list_orders_with_position(client):
    with patch("backend.routers.orders.alpaca_service") as mock_alpaca:
        mock_alpaca.get_positions.return_value = MOCK_POSITIONS.copy()
        mock_alpaca.get_closed_orders.return_value = []
        mock_alpaca.get_account.return_value = MOCK_ACCOUNT
        mock_alpaca.get_portfolio_history.return_value = []

        response = client.get("/api/orders/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["ouverts"]) == 1
        assert data["ouverts"][0]["actif"] == "AAPL"
        assert data["metriques"]["nb_trades_ouverts"] == 1


def test_refresh_orders(client):
    with patch("backend.routers.orders.alpaca_service") as mock_alpaca:
        mock_alpaca.get_positions.return_value = []
        mock_alpaca.get_closed_orders.return_value = []
        mock_alpaca.get_account.return_value = MOCK_ACCOUNT
        mock_alpaca.get_portfolio_history.return_value = []

        response = client.post("/api/orders/refresh")
        assert response.status_code == 200


def test_get_order_not_found(client):
    with patch("backend.routers.orders.alpaca_service") as mock_alpaca:
        mock_alpaca.get_positions.return_value = []
        mock_alpaca.get_closed_orders.return_value = []

        response = client.get("/api/orders/unknown-id")
        assert response.status_code == 404


def test_get_order_enriched_with_decision(client, sample_decision):
    with patch("backend.routers.orders.alpaca_service") as mock_alpaca:
        pos = MOCK_POSITIONS[0].copy()
        pos["actif"] = "NVDA"
        mock_alpaca.get_positions.return_value = [pos]
        mock_alpaca.get_closed_orders.return_value = []
        mock_alpaca.get_account.return_value = MOCK_ACCOUNT
        mock_alpaca.get_portfolio_history.return_value = []

        response = client.get("/api/orders/alpaca-test-order-001")
        assert response.status_code == 200
        data = response.json()
        assert data["actif"] == "NVDA"
        assert data["stop_loss"] == 185.0
        assert data["take_profit"] == 230.0
