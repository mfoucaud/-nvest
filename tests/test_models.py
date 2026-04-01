"""test_models.py — Contraintes ORM : unicité, FK, valeurs par défaut."""
import pytest
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date
from backend.models import Order, Decision, CapitalHistory, ScanRun


def make_order(id_ordre="ORD-001", actif="AAPL"):
    return Order(
        id_ordre=id_ordre,
        actif=actif,
        classe="Action",
        direction="ACHAT",
        statut="OUVERT",
        prix_entree=200.0,
        stop_loss=185.0,
        take_profit=230.0,
        taille=1000.0,
        quantite_fictive=5.0,
        date_ouverture=datetime(2026, 3, 30, 9, 30),
        date_expiration=date(2026, 4, 4),
    )


def test_order_insert(db):
    order = make_order()
    db.add(order)
    db.flush()
    assert order.id is not None
    assert order.statut == "OUVERT"
    assert order.pnl_latent == 0.0


def test_order_id_ordre_unique(db):
    db.add(make_order("ORD-DUP"))
    db.flush()
    db.add(make_order("ORD-DUP"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_order_nullable_prix_entree(db):
    """prix_entree est NOT NULL — doit échouer si absent."""
    order = Order(
        id_ordre="ORD-NULL",
        actif="NVDA",
        classe="Action",
        direction="ACHAT",
        statut="OUVERT",
        stop_loss=100.0,
        take_profit=120.0,
        date_ouverture=datetime(2026, 3, 30, 9, 30),
    )
    db.add(order)
    with pytest.raises(IntegrityError):
        db.flush()


def test_decision_fk_order(db):
    """Une décision sans ordre correspondant doit violer la FK."""
    decision = Decision(
        id_ordre="ORD-INEXISTANT",
        score_confiance=75,
    )
    db.add(decision)
    with pytest.raises(IntegrityError):
        db.flush()


def test_decision_linked_to_order(db):
    order = make_order("ORD-LINKED")
    db.add(order)
    db.flush()

    decision = Decision(
        id_ordre="ORD-LINKED",
        score_confiance=80,
        detail_score={"rsi_survente": 20},
        signaux_techniques="RSI en survente",
        conclusion="Signal fort",
    )
    db.add(decision)
    db.flush()
    assert decision.id is not None


def test_capital_history_insert(db):
    entry = CapitalHistory(date=date(2026, 3, 30), capital=10250.0, note="Test")
    db.add(entry)
    db.flush()
    assert entry.id is not None


def test_scan_run_defaults(db):
    from datetime import datetime
    run = ScanRun(started_at=datetime.now())
    db.add(run)
    db.flush()
    assert run.status == "en_cours"
    assert run.triggered_by == "manual"
    assert run.nb_ordres_generes == 0
