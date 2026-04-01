"""test_orders.py — Tests CRUD des endpoints /api/orders/."""
from datetime import date


def test_list_orders_empty(client):
    resp = client.get("/api/orders/")
    assert resp.status_code == 200
    data = resp.json()
    assert "ouverts" in data
    assert "cloturer" in data
    assert "metriques" in data
    assert "historique_capital" in data
    assert data["ouverts"] == []


def test_list_orders_with_data(client, sample_order):
    resp = client.get("/api/orders/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["ouverts"]) == 1
    assert data["ouverts"][0]["id_ordre"] == "ORD-TEST-001"


def test_create_order(client):
    payload = {
        "actif": "AAPL",
        "classe": "Action",
        "direction": "ACHAT",
        "prix_entree": 200.0,
        "stop_loss": 185.0,
        "take_profit": 230.0,
        "taille": 1000.0,
        "confiance": 70,
        "raison": "RSI survente",
    }
    resp = client.post("/api/orders/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id_ordre"].startswith("ORD-")
    assert data["ordre"]["statut"] == "OUVERT"


def test_create_order_with_decision(client):
    payload = {
        "actif": "NVDA",
        "classe": "Action",
        "direction": "ACHAT",
        "prix_entree": 180.0,
        "stop_loss": 165.0,
        "take_profit": 205.0,
        "confiance": 80,
        "raison": "Signal fort",
        "decision": {
            "signaux_techniques": "RSI 32, MACD haussier",
            "contexte_actualite": "Résultats positifs",
            "sentiment_communaute": "HAUSSIER",
            "risques_identifies": "Aucun majeur",
            "conclusion": "Bon R/R",
            "detail_score": {
                "rsi_survente": 20, "macd_croisement": 20,
                "bollinger_rebond": 0, "ema_tendance": 15,
                "volume_confirmation": 15, "support_horizontal": 0,
                "bonus_actualite_positive": 10, "bonus_sentiment_haussier": 5,
                "bonus_aucune_actualite_negative": 5,
                "malus_evenement_macro": 0, "malus_actualite_negative": 0,
                "malus_resultats_proches": 0,
            }
        }
    }
    resp = client.post("/api/orders/", json=payload)
    assert resp.status_code == 201


def test_get_order_detail(client, sample_order):
    resp = client.get(f"/api/orders/{sample_order['id_ordre']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id_ordre"] == "ORD-TEST-001"
    assert "decision" in data


def test_get_order_not_found(client):
    resp = client.get("/api/orders/ORD-INEXISTANT")
    assert resp.status_code == 404


def test_update_price(client, sample_order):
    resp = client.patch(
        f"/api/orders/{sample_order['id_ordre']}/price",
        json={"prix_actuel": 210.0}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["prix_actuel"] == 210.0
    assert data["pnl_latent"] == round((210.0 - 200.0) * 5.0, 2)


def test_close_order(client, sample_order):
    resp = client.patch(
        f"/api/orders/{sample_order['id_ordre']}/close",
        json={"statut": "CLOTURE_GAGNANT", "commentaire": "TP atteint"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["statut"] == "CLOTURE_GAGNANT"

    # L'ordre ne doit plus être dans les ouverts
    orders = client.get("/api/orders/").json()
    ids_ouverts = [o["id_ordre"] for o in orders["ouverts"]]
    assert "ORD-TEST-001" not in ids_ouverts


def test_close_already_closed_order(client, sample_order):
    client.patch(
        f"/api/orders/{sample_order['id_ordre']}/close",
        json={"statut": "CLOTURE_GAGNANT"}
    )
    resp = client.patch(
        f"/api/orders/{sample_order['id_ordre']}/close",
        json={"statut": "CLOTURE_PERDANT"}
    )
    assert resp.status_code == 409
