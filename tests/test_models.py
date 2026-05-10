"""Tests des modèles ORM Decision et ScanRun."""
from datetime import datetime, date
import pytest
from backend.models import Decision, ScanRun


def test_decision_creation(db):
    d = Decision(
        id_ordre="alpaca-uuid-001",
        actif="AAPL",
        classe="Action",
        direction="ACHAT",
        prix_entree=150.0,
        stop_loss=140.0,
        take_profit=170.0,
        taille=1000.0,
        quantite=6.67,
        score_confiance=75,
        date_ouverture=datetime(2026, 5, 10, 9, 30),
        date_expiration=date(2026, 5, 17),
    )
    db.add(d)
    db.flush()

    found = db.query(Decision).filter(Decision.id_ordre == "alpaca-uuid-001").first()
    assert found is not None
    assert found.actif == "AAPL"
    assert found.stop_loss == 140.0
    assert found.take_profit == 170.0


def test_decision_statut_final(db):
    d = Decision(
        id_ordre="alpaca-uuid-002",
        actif="TSLA",
        classe="Action",
        direction="ACHAT",
        prix_entree=200.0,
        stop_loss=185.0,
        take_profit=230.0,
        date_ouverture=datetime(2026, 5, 10, 9, 30),
    )
    db.add(d)
    db.flush()

    d.statut_final = "CLOTURE_GAGNANT"
    d.pnl_euros = "+150.00"
    d.date_cloture = date(2026, 5, 15)
    db.flush()

    found = db.query(Decision).filter(Decision.id_ordre == "alpaca-uuid-002").first()
    assert found.statut_final == "CLOTURE_GAGNANT"
    assert found.pnl_euros == "+150.00"


def test_scanrun_creation(db):
    s = ScanRun(
        started_at=datetime(2026, 5, 10, 14, 30),
        triggered_by="scheduler",
        nb_candidats=5,
        nb_ordres_generes=2,
        status="termine",
    )
    db.add(s)
    db.flush()

    found = db.query(ScanRun).filter(ScanRun.triggered_by == "scheduler").first()
    assert found is not None
    assert found.nb_candidats == 5
