"""
conftest.py — Fixtures partagées pour tous les tests.

Base de données de test : nvest_test (PostgreSQL)
Chaque test est isolé par rollback de transaction.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Pointer vers la DB de test AVANT tout import backend
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/nvest_test"

from backend.database import Base, get_db  # noqa: E402
from backend.main import app              # noqa: E402

TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/nvest_test"


@pytest.fixture(scope="session")
def test_engine():
    """Crée les tables dans nvest_test une fois pour toute la session."""
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db(test_engine) -> Session:
    """Session DB isolée : chaque test commence une transaction et rollback à la fin."""
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
    """Client FastAPI utilisant la session de test (avec rollback)."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_order(db) -> dict:
    """Insère un ordre ouvert dans la DB de test et retourne son dict."""
    from backend.models import Order
    from datetime import datetime, date, timedelta

    order = Order(
        id_ordre="ORD-TEST-001",
        actif="NVDA",
        classe="Action",
        direction="ACHAT",
        statut="OUVERT",
        prix_entree=200.0,
        stop_loss=185.0,
        take_profit=230.0,
        ratio_rr=2.0,
        taille=1000.0,
        quantite_fictive=5.0,
        confiance=75,
        raison="Test order",
        pnl_latent=0.0,
        date_ouverture=datetime(2026, 3, 30, 9, 30),
        date_expiration=date(2026, 4, 4),
    )
    db.add(order)
    db.flush()
    return {
        "id_ordre": order.id_ordre,
        "actif": order.actif,
        "statut": order.statut,
        "prix_entree": order.prix_entree,
        "stop_loss": order.stop_loss,
        "take_profit": order.take_profit,
    }
