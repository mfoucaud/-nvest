"""
conftest.py — Fixtures partagées pour tous les tests.

DB de test : nvest_test (PostgreSQL)
Chaque test est isolé par rollback de transaction.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/nvest_test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("ALPACA_API_KEY", "test-key")
os.environ.setdefault("ALPACA_SECRET_KEY", "test-secret")

from backend.database import Base, get_db  # noqa: E402
from backend.main import app              # noqa: E402


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db(test_engine) -> Session:
    connection = test_engine.connect()
    transaction = connection.begin()
    TestSession = sessionmaker(bind=connection)
    session = TestSession()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db) -> TestClient:
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_decision(db):
    """Insère une Decision en DB de test et retourne son dict."""
    from backend.models import Decision
    from datetime import datetime, date

    decision = Decision(
        id_ordre="alpaca-test-order-001",
        actif="NVDA",
        classe="Action",
        direction="ACHAT",
        prix_entree=200.0,
        stop_loss=185.0,
        take_profit=230.0,
        taille=1000.0,
        quantite=5.0,
        raison="Test order",
        date_ouverture=datetime(2026, 3, 30, 9, 30),
        date_expiration=date(2026, 4, 4),
        score_confiance=75,
    )
    db.add(decision)
    db.flush()
    return {
        "id_ordre": decision.id_ordre,
        "actif": decision.actif,
        "prix_entree": decision.prix_entree,
    }
