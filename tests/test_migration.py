"""test_migration.py — Vérifie que la migration JSON → PG préserve toutes les données."""
import json
from pathlib import Path
from backend.models import Order, Decision, CapitalHistory
from backend.scripts.migrate_json_to_pg import migrate

PROJECT_ROOT = Path(__file__).parent.parent


def test_migration_orders_count(db):
    portfolio = json.loads((PROJECT_ROOT / "portfolio_fictif.json").read_text(encoding="utf-8"))
    all_orders_json = (portfolio.get("ordres") or []) + (portfolio.get("ordres_cloturer") or [])

    result = migrate(db)

    orders_in_db = db.query(Order).count()
    assert orders_in_db == len(all_orders_json)
    assert result["nb_orders"] == len(all_orders_json)
    assert result["errors"] == []


def test_migration_decisions_count(db):
    journal = json.loads((PROJECT_ROOT / "journal_decisions.json").read_text(encoding="utf-8"))
    nb_decisions_json = len(journal.get("decisions") or [])

    migrate(db)

    decisions_in_db = db.query(Decision).count()
    assert decisions_in_db == nb_decisions_json


def test_migration_order_fields(db):
    """Vérifie qu'un ordre migré a tous ses champs correctement."""
    migrate(db)

    order = db.query(Order).filter(Order.id_ordre == "ORD-001").first()
    assert order is not None
    assert order.actif == "NVDA"
    assert order.direction == "ACHAT"
    assert order.prix_entree == 182.0


def test_migration_decision_with_cloture(db):
    """Vérifie qu'une décision clôturée a son champ statut_final rempli."""
    migrate(db)

    decision = db.query(Decision).filter(Decision.id_ordre == "ORD-001").first()
    assert decision is not None
    assert decision.statut_final == "CLOTURE_PERDANT"
    assert decision.pnl_euros == "-70.00"


def test_migration_idempotent(db):
    """Appeler migrate() deux fois ne doit pas dupliquer les données."""
    migrate(db)
    migrate(db)

    portfolio = json.loads((PROJECT_ROOT / "portfolio_fictif.json").read_text(encoding="utf-8"))
    all_orders_json = (portfolio.get("ordres") or []) + (portfolio.get("ordres_cloturer") or [])
    assert db.query(Order).count() == len(all_orders_json)
