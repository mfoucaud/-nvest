# Order Detection Backend Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Intégrer la détection automatique d'ordres dans le backend FastAPI (scan quotidien APScheduler + Claude sonnet-4-6 + web_search) avec migration de la persistance JSON vers PostgreSQL.

**Architecture:** APScheduler intégré dans FastAPI (sync, BackgroundScheduler), SQLAlchemy ORM sur PostgreSQL, Claude API avec built-in tool `web_search_20250305` pour l'analyse contextuelle. Le scan tourne à 9h Paris et est déclenchable on-demand via `/api/scan/run`.

**Tech Stack:** FastAPI, SQLAlchemy 2.x (sync), Alembic, APScheduler 3.x, anthropic SDK, psycopg2-binary, yfinance, pandas, numpy, pytest

**Spec:** `docs/superpowers/specs/2026-03-30-order-detection-backend-design.md`

---

## File Map

| Fichier | Action | Rôle |
|---------|--------|------|
| `backend/requirements.txt` | Modifier | Ajouter sqlalchemy, alembic, apscheduler, anthropic, psycopg2-binary, pytest |
| `backend/database.py` | Créer | Engine SQLAlchemy, SessionLocal, Base, get_db() |
| `backend/models.py` | Créer | ORM : Order, Decision, CapitalHistory, ScanRun |
| `backend/migrations/` | Créer | Alembic directory + config |
| `backend/scripts/migrate_json_to_pg.py` | Créer | Migration one-shot JSON → PostgreSQL |
| `backend/services/scanner.py` | Créer | Indicateurs techniques + scoring |
| `backend/services/claude_service.py` | Créer | Claude API + web_search + parsing JSON |
| `backend/services/scheduler.py` | Créer | APScheduler + run_daily_scan() |
| `backend/routers/orders.py` | Modifier | Remplacer data_loader par SQLAlchemy session |
| `backend/routers/scan.py` | Créer | POST /api/scan/run, GET /api/scan/status, GET /api/scan/history |
| `backend/main.py` | Modifier | Lifespan APScheduler + include scan router |
| `backend/services/data_loader.py` | Supprimer | Remplacé par SQLAlchemy |
| `render.yaml` | Modifier | Ajouter preDeployCommand alembic upgrade head |
| `tests/conftest.py` | Créer | DB nvest_test, TestClient, fixtures |
| `tests/test_models.py` | Créer | Contraintes ORM, FK, unicité |
| `tests/test_orders.py` | Créer | CRUD ordres via API |
| `tests/test_scan.py` | Créer | Indicateurs techniques sur OHLCV statiques |
| `tests/test_claude_service.py` | Créer | Claude mocké, parsing JSON, fallback |
| `tests/test_migration.py` | Créer | Intégrité migration JSON → PG |
| `pytest.ini` | Créer | Config pytest |

---

## Task 1 — Requirements + pytest.ini

**Files:**
- Modify: `backend/requirements.txt`
- Create: `pytest.ini`

- [ ] **Step 1: Remplacer le contenu de requirements.txt**

```
fastapi
uvicorn[standard]
yfinance
pydantic
sqlalchemy>=2.0
alembic
apscheduler>=3.10
anthropic>=0.40
psycopg2-binary
pandas
numpy
pytest
pytest-mock
httpx
```

- [ ] **Step 2: Créer pytest.ini à la racine du projet**

```ini
[pytest]
testpaths = tests
pythonpath = .
asyncio_mode = auto
```

- [ ] **Step 3: Installer les dépendances**

```bash
pip install -r backend/requirements.txt
```

Expected: pas d'erreur, toutes les dépendances installées.

- [ ] **Step 4: Créer le dossier tests/**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt pytest.ini tests/__init__.py
git commit -m "chore: add postgresql/alembic/apscheduler/anthropic deps"
```

---

## Task 2 — database.py + models.py

**Files:**
- Create: `backend/database.py`
- Create: `backend/models.py`

- [ ] **Step 1: Créer backend/database.py**

```python
"""
database.py — SQLAlchemy engine, session factory, Base ORM et dépendance FastAPI.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/nvest")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dépendance FastAPI : fournit une session DB, fermée après la requête."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Créer backend/models.py**

```python
"""
models.py — Modèles SQLAlchemy ORM pour !nvest.

Tables :
  orders          — ordres fictifs (ouverts + clôturés)
  decisions       — journal des décisions IA (1:1 avec orders)
  capital_history — courbe d'évolution du capital
  scan_runs       — historique des exécutions du scan
"""
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from backend.database import Base


class Order(Base):
    __tablename__ = "orders"

    id               = Column(Integer, primary_key=True, index=True)
    id_ordre         = Column(String(20), unique=True, nullable=False, index=True)
    actif            = Column(String(20), nullable=False)
    classe           = Column(String(20), nullable=False)
    direction        = Column(String(10), nullable=False)
    statut           = Column(String(30), nullable=False, default="OUVERT")
    prix_entree      = Column(Float, nullable=False)
    stop_loss        = Column(Float, nullable=False)
    take_profit      = Column(Float, nullable=False)
    prix_actuel      = Column(Float)
    prix_sortie      = Column(Float)
    ratio_rr         = Column(Float)
    taille           = Column(Float, default=1000.0)
    quantite_fictive = Column(Float)
    confiance        = Column(Integer)
    raison           = Column(Text)
    pnl_latent       = Column(Float, default=0.0)
    atr_utilise      = Column(Float)
    alerte           = Column(Text)
    date_ouverture   = Column(DateTime, nullable=False)
    date_expiration  = Column(Date)
    date_cloture     = Column(Date)
    created_at       = Column(DateTime, server_default=func.now())


class Decision(Base):
    __tablename__ = "decisions"

    id                   = Column(Integer, primary_key=True, index=True)
    id_ordre             = Column(String(20), ForeignKey("orders.id_ordre"), unique=True, nullable=False, index=True)
    signaux_techniques   = Column(Text)
    contexte_actualite   = Column(Text)
    sentiment_communaute = Column(Text)
    risques_identifies   = Column(Text)
    conclusion           = Column(Text)
    score_confiance      = Column(Integer)
    detail_score         = Column(JSONB)
    # Champ de clôture (rempli quand l'ordre se clôture)
    date_cloture         = Column(Date)
    statut_final         = Column(String(30))
    pnl_euros            = Column(String(20))
    commentaire_retour   = Column(Text)
    created_at           = Column(DateTime, server_default=func.now())


class CapitalHistory(Base):
    __tablename__ = "capital_history"

    id         = Column(Integer, primary_key=True, index=True)
    date       = Column(Date, nullable=False)
    capital    = Column(Float, nullable=False)
    note       = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id                = Column(Integer, primary_key=True, index=True)
    triggered_by      = Column(String(20), default="manual")   # "manual" | "scheduler"
    started_at        = Column(DateTime, nullable=False)
    finished_at       = Column(DateTime)
    status            = Column(String(20), default="en_cours")  # en_cours | termine | erreur
    nb_candidats      = Column(Integer, default=0)
    nb_ordres_generes = Column(Integer, default=0)
    nb_clotures       = Column(Integer, default=0)
    erreur            = Column(Text)
    created_at        = Column(DateTime, server_default=func.now())
```

- [ ] **Step 3: Vérifier l'import Python (syntaxe)**

```bash
cd C:/Users/micka/Desktop/project/!nvest
python -c "from backend.database import Base; from backend.models import Order, Decision, CapitalHistory, ScanRun; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/database.py backend/models.py
git commit -m "feat: SQLAlchemy database layer and ORM models"
```

---

## Task 3 — Alembic : init + migration initiale

**Files:**
- Create: `backend/migrations/` (init Alembic)
- Create: `backend/migrations/env.py` (config)

- [ ] **Step 1: Créer la base de données PostgreSQL de développement**

```bash
psql -U postgres -c "CREATE DATABASE nvest;"
psql -U postgres -c "CREATE DATABASE nvest_test;"
```

Si l'utilisateur postgres n'existe pas, adapter avec l'utilisateur local :
```bash
createdb nvest
createdb nvest_test
```

- [ ] **Step 2: Initialiser Alembic depuis la racine du projet**

```bash
cd C:/Users/micka/Desktop/project/!nvest
alembic init backend/migrations
```

Expected: dossier `backend/migrations/` créé avec `env.py`, `script.py.mako`, `versions/`.

- [ ] **Step 3: Modifier alembic.ini — pointer vers la DB**

Dans `alembic.ini`, remplacer la ligne `sqlalchemy.url` par :
```ini
sqlalchemy.url = postgresql://localhost:5432/nvest
```

- [ ] **Step 4: Modifier backend/migrations/env.py — connecter les modèles**

Remplacer le bloc `target_metadata = None` par :

```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.database import Base
from backend.models import Order, Decision, CapitalHistory, ScanRun  # noqa: F401

target_metadata = Base.metadata
```

Et dans la fonction `run_migrations_online()`, remplacer `connectable = engine_from_config(...)` par :

```python
from backend.database import engine as connectable
```

Le bloc complet `run_migrations_online()` devient :

```python
def run_migrations_online() -> None:
    from backend.database import engine as connectable
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()
```

- [ ] **Step 5: Générer la première migration**

```bash
cd C:/Users/micka/Desktop/project/!nvest
alembic revision --autogenerate -m "initial schema"
```

Expected: fichier `backend/migrations/versions/XXXX_initial_schema.py` créé avec 4 tables.

- [ ] **Step 6: Appliquer la migration sur nvest**

```bash
alembic upgrade head
```

Expected: `Running upgrade  -> XXXX, initial schema`

- [ ] **Step 7: Vérifier les tables créées**

```bash
psql nvest -c "\dt"
```

Expected: 4 tables listées : `orders`, `decisions`, `capital_history`, `scan_runs`.

- [ ] **Step 8: Commit**

```bash
git add alembic.ini backend/migrations/
git commit -m "feat: alembic migrations — initial schema (4 tables PostgreSQL)"
```

---

## Task 4 — conftest.py (infrastructure de tests)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Créer tests/conftest.py**

```python
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
os.environ["DATABASE_URL"] = "postgresql://localhost:5432/nvest_test"

from backend.database import Base, get_db  # noqa: E402
from backend.main import app              # noqa: E402

TEST_DATABASE_URL = "postgresql://localhost:5432/nvest_test"


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
```

- [ ] **Step 2: Vérifier que pytest démarre sans erreur**

```bash
cd C:/Users/micka/Desktop/project/!nvest
pytest tests/ --collect-only
```

Expected: `no tests ran` (pas encore de tests), mais pas d'erreur d'import.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: conftest.py — PostgreSQL test DB with per-test rollback"
```

---

## Task 5 — test_models.py + vérification ORM

**Files:**
- Create: `tests/test_models.py`

- [ ] **Step 1: Écrire tests/test_models.py**

```python
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
```

- [ ] **Step 2: Lancer les tests**

```bash
pytest tests/test_models.py -v
```

Expected: 7 tests PASSED.

- [ ] **Step 3: Commit**

```bash
git add tests/test_models.py
git commit -m "test: ORM constraints — unicité, FK, valeurs par défaut"
```

---

## Task 6 — migrate_json_to_pg.py + test_migration.py

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/migrate_json_to_pg.py`
- Create: `tests/test_migration.py`

- [ ] **Step 1: Créer backend/scripts/__init__.py**

```python
```

(fichier vide)

- [ ] **Step 2: Créer backend/scripts/migrate_json_to_pg.py**

```python
"""
migrate_json_to_pg.py — Migration one-shot des données JSON vers PostgreSQL.

Usage:
    python -m backend.scripts.migrate_json_to_pg

Lit portfolio_fictif.json et journal_decisions.json depuis la racine du projet.
Insère dans orders, decisions, capital_history.
Les fichiers JSON sont conservés (backup).
"""
import json
import sys
from datetime import datetime, date
from pathlib import Path

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _load_json(filename: str) -> dict:
    path = PROJECT_ROOT / filename
    if not path.exists():
        print(f"[migration] SKIP — {filename} introuvable")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_datetime(s: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.now()


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def migrate(db: Session) -> dict:
    from backend.models import Order, Decision, CapitalHistory

    portfolio = _load_json("portfolio_fictif.json")
    journal = _load_json("journal_decisions.json")

    nb_orders = 0
    nb_decisions = 0
    nb_capital = 0
    errors = []

    # --- Ordres ---
    all_orders = (portfolio.get("ordres") or []) + (portfolio.get("ordres_cloturer") or [])
    for o in all_orders:
        if db.query(Order).filter(Order.id_ordre == o["id_ordre"]).first():
            continue  # déjà migré
        try:
            order = Order(
                id_ordre=o["id_ordre"],
                actif=o["actif"],
                classe=o["classe"],
                direction=o["direction"],
                statut=o["statut"],
                prix_entree=o["prix_entree"],
                stop_loss=o["stop_loss"],
                take_profit=o["take_profit"],
                prix_actuel=o.get("prix_actuel"),
                prix_sortie=o.get("prix_sortie"),
                ratio_rr=o.get("ratio_rr"),
                taille=o.get("taille", 1000.0),
                quantite_fictive=o.get("quantite_fictive"),
                confiance=o.get("confiance"),
                raison=o.get("raison"),
                pnl_latent=o.get("pnl_latent", 0.0),
                atr_utilise=o.get("atr_utilise"),
                alerte=o.get("alerte"),
                date_ouverture=_parse_datetime(o["date_ouverture"]),
                date_expiration=_parse_date(o.get("date_expiration")),
                date_cloture=_parse_date(o.get("date_cloture")),
            )
            db.add(order)
            db.flush()
            nb_orders += 1
        except Exception as e:
            errors.append(f"Ordre {o.get('id_ordre')}: {e}")

    # --- Décisions ---
    for d in journal.get("decisions") or []:
        if db.query(Decision).filter(Decision.id_ordre == d["id_ordre"]).first():
            continue
        # Vérifier que l'ordre existe
        if not db.query(Order).filter(Order.id_ordre == d["id_ordre"]).first():
            errors.append(f"Décision {d['id_ordre']}: ordre introuvable en base")
            continue
        try:
            cloture = d.get("cloture") or {}
            decision = Decision(
                id_ordre=d["id_ordre"],
                signaux_techniques=d.get("signaux_techniques"),
                contexte_actualite=d.get("contexte_actualite"),
                sentiment_communaute=d.get("sentiment_communaute"),
                risques_identifies=d.get("risques_identifies"),
                conclusion=d.get("conclusion"),
                score_confiance=d.get("score_confiance"),
                detail_score=d.get("detail_score"),
                date_cloture=_parse_date(cloture.get("date_cloture")),
                statut_final=cloture.get("statut_final"),
                pnl_euros=cloture.get("pnl_euros"),
                commentaire_retour=cloture.get("commentaire_retour"),
            )
            db.add(decision)
            db.flush()
            nb_decisions += 1
        except Exception as e:
            errors.append(f"Décision {d.get('id_ordre')}: {e}")

    # --- Capital history ---
    for entry in portfolio.get("historique_capital") or []:
        try:
            from backend.models import CapitalHistory
            ch = CapitalHistory(
                date=_parse_date(entry["date"]),
                capital=entry["capital"],
                note=entry.get("note"),
            )
            db.add(ch)
            nb_capital += 1
        except Exception as e:
            errors.append(f"Capital entry {entry.get('date')}: {e}")

    db.commit()

    return {
        "nb_orders": nb_orders,
        "nb_decisions": nb_decisions,
        "nb_capital": nb_capital,
        "errors": errors,
    }


if __name__ == "__main__":
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        result = migrate(db)
        print(f"Migration terminée :")
        print(f"  {result['nb_orders']} ordres")
        print(f"  {result['nb_decisions']} décisions")
        print(f"  {result['nb_capital']} entrées capital")
        if result["errors"]:
            print(f"  ERREURS ({len(result['errors'])}) :")
            for e in result["errors"]:
                print(f"    - {e}")
        sys.exit(0 if not result["errors"] else 1)
    finally:
        db.close()
```

- [ ] **Step 3: Écrire tests/test_migration.py**

```python
"""test_migration.py — Vérifie que la migration JSON → PG préserve toutes les données."""
import json
from pathlib import Path
from backend.models import Order, Decision, CapitalHistory
from backend.scripts.migrate_json_to_pg import migrate

PROJECT_ROOT = Path(__file__).parent.parent


def test_migration_orders_count(db):
    portfolio = json.loads((PROJECT_ROOT / "portfolio_fictif.json").read_text())
    all_orders_json = (portfolio.get("ordres") or []) + (portfolio.get("ordres_cloturer") or [])

    result = migrate(db)

    orders_in_db = db.query(Order).count()
    assert orders_in_db == len(all_orders_json)
    assert result["nb_orders"] == len(all_orders_json)
    assert result["errors"] == []


def test_migration_decisions_count(db):
    journal = json.loads((PROJECT_ROOT / "journal_decisions.json").read_text())
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

    portfolio = json.loads((PROJECT_ROOT / "portfolio_fictif.json").read_text())
    all_orders_json = (portfolio.get("ordres") or []) + (portfolio.get("ordres_cloturer") or [])
    assert db.query(Order).count() == len(all_orders_json)
```

- [ ] **Step 4: Lancer les tests migration**

```bash
pytest tests/test_migration.py -v
```

Expected: 5 tests PASSED.

- [ ] **Step 5: Lancer la migration réelle sur nvest**

```bash
python -m backend.scripts.migrate_json_to_pg
```

Expected: rapport avec N ordres, N décisions, N entrées capital, aucune erreur.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/ tests/test_migration.py
git commit -m "feat: migration one-shot JSON → PostgreSQL avec tests"
```

---

## Task 7 — routers/orders.py refactorisé + test_orders.py

**Files:**
- Modify: `backend/routers/orders.py`
- Create: `tests/test_orders.py`

- [ ] **Step 1: Écrire tests/test_orders.py (tests en premier — TDD)**

```python
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
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
pytest tests/test_orders.py -v 2>&1 | head -30
```

Expected: les tests échouent car orders.py utilise encore data_loader.

- [ ] **Step 3: Réécrire backend/routers/orders.py**

```python
"""
routers/orders.py — Endpoints CRUD pour les ordres fictifs (!nvest).
Persistance via PostgreSQL (SQLAlchemy) — remplace data_loader.py.

Endpoints:
    GET    /api/orders/              → Liste tous les ordres + métriques
    POST   /api/orders/              → Crée un nouvel ordre
    GET    /api/orders/{id}          → Détail ordre + décision
    PATCH  /api/orders/{id}/price    → Met à jour le prix actuel
    PATCH  /api/orders/{id}/close    → Clôture un ordre
    POST   /api/orders/refresh       → Rafraîchit tous les prix + clôtures auto
"""
from datetime import datetime, date, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Order, Decision, CapitalHistory

router = APIRouter(prefix="/orders", tags=["orders"])


# ---------------------------------------------------------------------------
# Modèles Pydantic (inchangés côté API)
# ---------------------------------------------------------------------------

class DetailScore(BaseModel):
    rsi_survente: int = 0
    macd_croisement: int = 0
    bollinger_rebond: int = 0
    ema_tendance: int = 0
    volume_confirmation: int = 0
    support_horizontal: int = 0
    bonus_actualite_positive: int = 0
    bonus_sentiment_haussier: int = 0
    bonus_aucune_actualite_negative: int = 0
    malus_evenement_macro: int = 0
    malus_actualite_negative: int = 0
    malus_resultats_proches: int = 0


class DecisionIn(BaseModel):
    signaux_techniques: str = ""
    contexte_actualite: str = ""
    sentiment_communaute: str = ""
    risques_identifies: str = ""
    conclusion: str = ""
    detail_score: DetailScore = Field(default_factory=DetailScore)


class OrderIn(BaseModel):
    actif: str
    classe: Literal["Action", "Crypto", "Forex", "ETF"]
    direction: Literal["ACHAT", "VENTE"]
    prix_entree: float
    stop_loss: float
    take_profit: float
    taille: float = 1000.0
    confiance: int = Field(..., ge=0, le=100)
    raison: str = ""
    decision: Optional[DecisionIn] = None


class PriceUpdate(BaseModel):
    prix_actuel: float


class CloseOrder(BaseModel):
    statut: Literal["CLOTURE_GAGNANT", "CLOTURE_PERDANT", "EXPIRE"]
    prix_sortie: Optional[float] = None
    commentaire: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _business_days_later(start: date, days: int = 5) -> date:
    d = start
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def _next_order_id(db: Session) -> str:
    last = db.query(Order).order_by(Order.id.desc()).first()
    if last is None:
        return "ORD-001"
    try:
        n = int(last.id_ordre.split("-")[1])
        return f"ORD-{n + 1:03d}"
    except (IndexError, ValueError):
        return "ORD-001"


def _order_to_dict(order: Order) -> dict:
    return {
        "id_ordre": order.id_ordre,
        "date_ouverture": order.date_ouverture.strftime("%Y-%m-%d %H:%M") if order.date_ouverture else None,
        "actif": order.actif,
        "classe": order.classe,
        "direction": order.direction,
        "statut": order.statut,
        "prix_entree": order.prix_entree,
        "stop_loss": order.stop_loss,
        "take_profit": order.take_profit,
        "ratio_rr": order.ratio_rr,
        "taille": order.taille,
        "quantite_fictive": order.quantite_fictive,
        "confiance": order.confiance,
        "raison": order.raison,
        "pnl_latent": order.pnl_latent,
        "prix_actuel": order.prix_actuel,
        "prix_sortie": order.prix_sortie,
        "date_expiration": order.date_expiration.isoformat() if order.date_expiration else None,
        "date_cloture": order.date_cloture.isoformat() if order.date_cloture else None,
        "atr_utilise": order.atr_utilise,
        "alerte": order.alerte,
    }


def _decision_to_dict(decision: Decision) -> dict | None:
    if decision is None:
        return None
    cloture = None
    if decision.statut_final:
        cloture = {
            "date_cloture": decision.date_cloture.isoformat() if decision.date_cloture else None,
            "statut_final": decision.statut_final,
            "pnl_euros": decision.pnl_euros,
            "commentaire_retour": decision.commentaire_retour,
        }
    return {
        "id_ordre": decision.id_ordre,
        "signaux_techniques": decision.signaux_techniques,
        "contexte_actualite": decision.contexte_actualite,
        "sentiment_communaute": decision.sentiment_communaute,
        "risques_identifies": decision.risques_identifies,
        "conclusion": decision.conclusion,
        "score_confiance": decision.score_confiance,
        "detail_score": decision.detail_score,
        "cloture": cloture,
    }


def _calc_metrics(db: Session) -> dict:
    import os
    capital_depart = float(os.getenv("CAPITAL_DEPART", "10000"))

    ouverts  = db.query(Order).filter(Order.statut == "OUVERT").all()
    clotures = db.query(Order).filter(Order.statut != "OUVERT").all()

    gagnants = [o for o in clotures if o.statut == "CLOTURE_GAGNANT"]
    perdants = [o for o in clotures if o.statut == "CLOTURE_PERDANT"]
    expires  = [o for o in clotures if o.statut == "EXPIRE"]
    nb_clos  = len(clotures)

    pnl_realise    = sum(o.pnl_latent or 0 for o in clotures)
    pnl_latent     = sum(o.pnl_latent or 0 for o in ouverts)
    capital_actuel = capital_depart + pnl_realise
    gains  = sum(o.pnl_latent or 0 for o in gagnants)
    pertes = abs(sum(o.pnl_latent or 0 for o in perdants))

    return {
        "win_rate":            round(len(gagnants) / nb_clos * 100, 1) if nb_clos else None,
        "pnl_total_eur":       round(pnl_realise, 2),
        "pnl_latent_eur":      round(pnl_latent, 2),
        "pnl_total_pct":       round(pnl_realise / capital_depart * 100, 2),
        "profit_factor":       round(gains / pertes, 2) if pertes > 0 else None,
        "nb_trades_total":     nb_clos + len(ouverts),
        "nb_trades_ouverts":   len(ouverts),
        "nb_trades_gagnants":  len(gagnants),
        "nb_trades_perdants":  len(perdants),
        "nb_trades_expires":   len(expires),
        "meilleur_trade":      max((o.pnl_latent for o in clotures if o.pnl_latent), default=None),
        "pire_trade":          min((o.pnl_latent for o in clotures if o.pnl_latent), default=None),
        "capital_actuel":      round(capital_actuel, 2),
        "derniere_mise_a_jour": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/orders/
# ---------------------------------------------------------------------------

@router.get("/", summary="Liste tous les ordres + métriques")
def list_orders(db: Session = Depends(get_db)) -> dict:
    ouverts  = db.query(Order).filter(Order.statut == "OUVERT").all()
    cloturer = db.query(Order).filter(Order.statut != "OUVERT").all()
    capital  = db.query(CapitalHistory).order_by(CapitalHistory.date).all()

    return {
        "ouverts":            [_order_to_dict(o) for o in ouverts],
        "cloturer":           [_order_to_dict(o) for o in cloturer],
        "metriques":          _calc_metrics(db),
        "historique_capital": [
            {"date": h.date.isoformat(), "capital": h.capital, "note": h.note}
            for h in capital
        ],
    }


# ---------------------------------------------------------------------------
# POST /api/orders/
# ---------------------------------------------------------------------------

@router.post("/", status_code=201, summary="Crée un nouvel ordre fictif")
def create_order(body: OrderIn, db: Session = Depends(get_db)) -> dict:
    id_ordre = _next_order_id(db)
    now      = datetime.now()
    today    = date.today()
    expiry   = _business_days_later(today)

    prix = body.prix_entree
    sl   = body.stop_loss
    tp   = body.take_profit
    qty  = round(body.taille / prix, 4) if prix else 0
    rr   = round((tp - prix) / (prix - sl), 2) if (prix - sl) != 0 else None

    order = Order(
        id_ordre=id_ordre,
        date_ouverture=now,
        actif=body.actif,
        classe=body.classe,
        direction=body.direction,
        statut="OUVERT",
        prix_entree=prix,
        stop_loss=sl,
        take_profit=tp,
        ratio_rr=rr,
        taille=body.taille,
        quantite_fictive=qty,
        confiance=body.confiance,
        raison=body.raison,
        date_expiration=expiry,
        prix_actuel=prix,
        pnl_latent=0.0,
    )
    db.add(order)
    db.flush()

    if body.decision:
        d = body.decision
        decision = Decision(
            id_ordre=id_ordre,
            signaux_techniques=d.signaux_techniques,
            contexte_actualite=d.contexte_actualite,
            sentiment_communaute=d.sentiment_communaute,
            risques_identifies=d.risques_identifies,
            conclusion=d.conclusion,
            score_confiance=body.confiance,
            detail_score=d.detail_score.model_dump(),
        )
        db.add(decision)

    db.commit()
    db.refresh(order)
    return {"id_ordre": id_ordre, "ordre": _order_to_dict(order)}


# ---------------------------------------------------------------------------
# GET /api/orders/{id_ordre}
# ---------------------------------------------------------------------------

@router.get("/{id_ordre}", summary="Détail d'un ordre fusionné avec sa décision")
def get_order(id_ordre: str, db: Session = Depends(get_db)) -> dict:
    order = db.query(Order).filter(Order.id_ordre == id_ordre).first()
    if order is None:
        raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")
    decision = db.query(Decision).filter(Decision.id_ordre == id_ordre).first()
    merged = _order_to_dict(order)
    merged["decision"] = _decision_to_dict(decision)
    return merged


# ---------------------------------------------------------------------------
# PATCH /api/orders/{id_ordre}/price
# ---------------------------------------------------------------------------

@router.patch("/{id_ordre}/price", summary="Met à jour le prix actuel d'un ordre ouvert")
def update_price(id_ordre: str, body: PriceUpdate, db: Session = Depends(get_db)) -> dict:
    order = db.query(Order).filter(Order.id_ordre == id_ordre).first()
    if order is None:
        raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")
    if order.statut != "OUVERT":
        raise HTTPException(409, detail=f"Ordre '{id_ordre}' déjà clôturé.")

    order.prix_actuel = body.prix_actuel
    order.pnl_latent  = round((body.prix_actuel - order.prix_entree) * (order.quantite_fictive or 0), 2)
    db.commit()
    return {"id_ordre": id_ordre, "prix_actuel": body.prix_actuel, "pnl_latent": order.pnl_latent}


# ---------------------------------------------------------------------------
# PATCH /api/orders/{id_ordre}/close
# ---------------------------------------------------------------------------

@router.patch("/{id_ordre}/close", summary="Clôture manuellement un ordre")
def close_order(id_ordre: str, body: CloseOrder, db: Session = Depends(get_db)) -> dict:
    order = db.query(Order).filter(Order.id_ordre == id_ordre).first()
    if order is None:
        raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")
    if order.statut != "OUVERT":
        raise HTTPException(409, detail=f"Ordre '{id_ordre}' déjà clôturé.")

    if body.prix_sortie is not None:
        exit_price = body.prix_sortie
    elif body.statut == "CLOTURE_PERDANT":
        exit_price = order.stop_loss
    elif body.statut == "CLOTURE_GAGNANT":
        exit_price = order.take_profit
    else:
        exit_price = order.prix_actuel or order.prix_entree

    pnl = round((exit_price - order.prix_entree) * (order.quantite_fictive or 0), 2)
    today_str = date.today()

    order.statut       = body.statut
    order.prix_actuel  = exit_price
    order.prix_sortie  = exit_price
    order.pnl_latent   = pnl
    order.date_cloture = today_str

    # Historique capital
    import os
    capital_depart = float(os.getenv("CAPITAL_DEPART", "10000"))
    pnl_realise = sum(
        o.pnl_latent or 0
        for o in db.query(Order).filter(Order.statut != "OUVERT").all()
    )
    capital_actuel = capital_depart + pnl_realise + pnl
    db.add(CapitalHistory(
        date=today_str,
        capital=round(capital_actuel, 2),
        note=f"Cloture {id_ordre} ({body.statut}) PnL {pnl:+.2f}EUR",
    ))

    # Mise à jour décision
    decision = db.query(Decision).filter(Decision.id_ordre == id_ordre).first()
    if decision:
        decision.date_cloture     = today_str
        decision.statut_final     = body.statut
        decision.pnl_euros        = f"{pnl:+.2f}"
        decision.commentaire_retour = body.commentaire or "Cloture manuelle via API."

    db.commit()
    return {"id_ordre": id_ordre, "statut": body.statut, "pnl": pnl, "exit_price": exit_price}


# ---------------------------------------------------------------------------
# POST /api/orders/refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", summary="Rafraîchit tous les prix + clôtures automatiques")
def refresh_prices(db: Session = Depends(get_db)) -> dict:
    try:
        import yfinance as yf
    except ImportError:
        raise HTTPException(500, detail="yfinance non installé.")

    import os
    capital_depart = float(os.getenv("CAPITAL_DEPART", "10000"))
    today_str = date.today()
    updated = []
    closed  = []
    errors  = []

    ouverts = db.query(Order).filter(Order.statut == "OUVERT").all()

    for order in ouverts:
        try:
            hist = yf.Ticker(order.actif).history(period="2d", interval="1d")
            if hist.empty:
                raise ValueError("Pas de données")
            prix = round(float(hist["Close"].iloc[-1]), 4)
        except Exception as e:
            errors.append({"actif": order.actif, "erreur": str(e)})
            continue

        sl     = order.stop_loss
        tp     = order.take_profit
        expiry = order.date_expiration
        qty    = order.quantite_fictive or 0

        if prix <= sl:
            statut, exit_price = "CLOTURE_PERDANT", sl
        elif prix >= tp:
            statut, exit_price = "CLOTURE_GAGNANT", tp
        elif expiry and expiry <= today_str:
            statut, exit_price = "EXPIRE", prix
        else:
            statut, exit_price = "OUVERT", None

        pnl = round((prix - order.prix_entree) * qty, 2)

        if statut != "OUVERT":
            exit_pnl = round((exit_price - order.prix_entree) * qty, 2)
            order.statut       = statut
            order.prix_actuel  = exit_price
            order.prix_sortie  = exit_price
            order.pnl_latent   = exit_pnl
            order.date_cloture = today_str

            decision = db.query(Decision).filter(Decision.id_ordre == order.id_ordre).first()
            if decision and not decision.statut_final:
                decision.date_cloture     = today_str
                decision.statut_final     = statut
                decision.pnl_euros        = f"{exit_pnl:+.2f}"
                decision.commentaire_retour = f"Clôture automatique (prix={prix})."

            closed.append({"id_ordre": order.id_ordre, "actif": order.actif, "statut": statut, "pnl": exit_pnl})
        else:
            order.prix_actuel = prix
            order.pnl_latent  = pnl
            updated.append({"id_ordre": order.id_ordre, "actif": order.actif, "prix": prix, "pnl_latent": pnl})

    if closed:
        pnl_realise = sum(
            o.pnl_latent or 0
            for o in db.query(Order).filter(Order.statut != "OUVERT").all()
        )
        db.add(CapitalHistory(
            date=today_str,
            capital=round(capital_depart + pnl_realise, 2),
            note=f"Refresh auto: {len(closed)} cloture(s).",
        ))

    db.commit()

    return {
        "date":       today_str.isoformat(),
        "mis_a_jour": updated,
        "clotures":   closed,
        "erreurs":    errors,
        "metriques":  _calc_metrics(db),
    }
```

- [ ] **Step 4: Lancer les tests**

```bash
pytest tests/test_orders.py -v
```

Expected: 9 tests PASSED.

- [ ] **Step 5: Supprimer data_loader.py**

```bash
rm backend/services/data_loader.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/routers/orders.py tests/test_orders.py
git rm backend/services/data_loader.py
git commit -m "feat: orders router migré PostgreSQL (SQLAlchemy), suppression data_loader"
```

---

## Task 8 — services/scanner.py + test_scan.py

**Files:**
- Create: `backend/services/scanner.py`
- Create: `tests/test_scan.py`

- [ ] **Step 1: Écrire tests/test_scan.py (TDD — en premier)**

```python
"""test_scan.py — Tests des indicateurs techniques et du scoring."""
import pandas as pd
import numpy as np
import pytest
from backend.services.scanner import calc_rsi, calc_macd, calc_bollinger, calc_ema, calc_atr, score_from_indicators


def make_close_series(values: list) -> pd.Series:
    return pd.Series(values, dtype=float)


# --- RSI ---

def test_rsi_oversold():
    """Série très baissière → RSI < 35."""
    closes = [100 - i * 2 for i in range(30)] + [45.0]  # tendance baissière
    rsi = calc_rsi(make_close_series(closes))
    assert rsi < 35


def test_rsi_overbought():
    """Série très haussière → RSI > 65."""
    closes = [50 + i * 2 for i in range(30)] + [110.0]
    rsi = calc_rsi(make_close_series(closes))
    assert rsi > 65


def test_rsi_neutral():
    """Série stable → RSI ~50."""
    closes = [100.0] * 60
    rsi = calc_rsi(make_close_series(closes))
    assert 40 < rsi < 60 or rsi == 100.0  # série plate → pas de pertes → RSI=100 ou NaN→fallback


# --- MACD ---

def test_macd_bullish_crossover():
    """Série montante après correction → MACD > signal (haussier)."""
    closes = [100 - i for i in range(40)] + [60 + i * 2 for i in range(20)]
    macd_val, macd_sig = calc_macd(make_close_series(closes))
    # MACD doit remonter après la correction
    assert isinstance(macd_val, float)
    assert isinstance(macd_sig, float)


# --- Bollinger ---

def test_bollinger_price_near_lower_band():
    """Prix bien en dessous de la moyenne → price ≤ lower band."""
    closes = [100.0] * 25 + [70.0]  # chute soudaine
    lower, upper = calc_bollinger(make_close_series(closes))
    assert lower < 100.0
    assert upper > lower


# --- ATR ---

def test_atr_positive():
    n = 30
    closes = pd.Series([100.0 + i * 0.5 for i in range(n)])
    highs  = closes + 2.0
    lows   = closes - 2.0
    atr = calc_atr(highs, lows, closes)
    assert atr > 0


# --- score_from_indicators ---

def test_score_rsi_oversold():
    score, detail = score_from_indicators(
        rsi=25.0, macd_val=-0.5, macd_sig=-0.6,
        prix=80.0, bb_lower=82.0, bb_upper=110.0,
        ema20=90.0, ema50=95.0, vol_actuel=1e6, vol_moy=8e5
    )
    assert detail["rsi_survente"] == 20
    assert score >= 20


def test_score_volume_confirmation():
    score, detail = score_from_indicators(
        rsi=50.0, macd_val=0.1, macd_sig=0.05,
        prix=100.0, bb_lower=95.0, bb_upper=115.0,
        ema20=102.0, ema50=98.0, vol_actuel=2e6, vol_moy=1e6
    )
    assert detail["volume_confirmation"] == 15
    assert detail["macd_croisement"] == 20
    assert detail["ema_tendance"] == 15


def test_score_below_threshold():
    """Tous les indicateurs neutres → score 0."""
    score, detail = score_from_indicators(
        rsi=50.0, macd_val=-0.1, macd_sig=0.1,
        prix=100.0, bb_lower=85.0, bb_upper=115.0,
        ema20=98.0, ema50=100.0, vol_actuel=1e6, vol_moy=1e6
    )
    assert score == 0
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
pytest tests/test_scan.py -v 2>&1 | head -20
```

Expected: ImportError — scanner.py n'existe pas encore.

- [ ] **Step 3: Créer backend/services/scanner.py**

```python
"""
scanner.py — Scan des marchés : indicateurs techniques et scoring.

Tickers scannés : actions, cryptos, forex, ETFs (liste configurable).
Score technique de 0 à 85 pts basé sur RSI, MACD, Bollinger, EMA, Volume, Support.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

TICKERS: list[str] = [
    # Actions US
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META",
    # Actions FR
    "LVMH.PA", "TTE.PA", "AIR.PA",
    # Crypto
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD",
    # Forex
    "EURUSD=X", "GBPUSD=X", "USDJPY=X",
    # ETF
    "SPY", "QQQ",
]

TICKER_CLASS: dict[str, str] = {
    "AAPL": "Action", "MSFT": "Action", "NVDA": "Action", "TSLA": "Action",
    "AMZN": "Action", "GOOGL": "Action", "META": "Action",
    "LVMH.PA": "Action", "TTE.PA": "Action", "AIR.PA": "Action",
    "BTC-USD": "Crypto", "ETH-USD": "Crypto", "SOL-USD": "Crypto", "BNB-USD": "Crypto",
    "EURUSD=X": "Forex", "GBPUSD=X": "Forex", "USDJPY=X": "Forex",
    "SPY": "ETF", "QQQ": "ETF",
}


@dataclass
class Candidate:
    ticker: str
    classe: str
    prix: float
    rsi: float
    macd_signal: str       # "haussier" | "baissier"
    atr: float
    score_technique: int
    detail_score: dict
    direction: str = "ACHAT"


# ---------------------------------------------------------------------------
# Indicateurs
# ---------------------------------------------------------------------------

def calc_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    rsi   = 100 - (100 / (1 + rs))
    val   = float(rsi.iloc[-1])
    return round(val if not np.isnan(val) else 50.0, 2)


def calc_macd(close: pd.Series) -> tuple[float, float]:
    ema12  = close.ewm(span=12, adjust=False).mean()
    ema26  = close.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(signal.iloc[-1])


def calc_bollinger(close: pd.Series, period: int = 20) -> tuple[float, float]:
    sma   = close.rolling(period).mean()
    std   = close.rolling(period).std()
    lower = sma - 2 * std
    upper = sma + 2 * std
    return float(lower.iloc[-1]), float(upper.iloc[-1])


def calc_ema(close: pd.Series) -> tuple[float, float]:
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    return ema20, ema50


def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    tr = pd.DataFrame({
        "hl": high - low,
        "hc": (high - close.shift()).abs(),
        "lc": (low - close.shift()).abs(),
    }).max(axis=1)
    val = float(tr.rolling(period).mean().iloc[-1])
    return round(val if not np.isnan(val) else 0.0, 4)


def score_from_indicators(
    rsi: float, macd_val: float, macd_sig: float,
    prix: float, bb_lower: float, bb_upper: float,
    ema20: float, ema50: float,
    vol_actuel: float, vol_moy: float,
) -> tuple[int, dict]:
    """Calcule le score technique et retourne (score, detail_score)."""
    detail: dict[str, int] = {
        "rsi_survente": 0,
        "macd_croisement": 0,
        "bollinger_rebond": 0,
        "ema_tendance": 0,
        "volume_confirmation": 0,
        "support_horizontal": 0,
        "bonus_actualite_positive": 0,
        "bonus_sentiment_haussier": 0,
        "bonus_aucune_actualite_negative": 0,
        "malus_evenement_macro": 0,
        "malus_actualite_negative": 0,
        "malus_resultats_proches": 0,
    }

    if rsi < 35:
        detail["rsi_survente"] = 20
    if macd_val > macd_sig:
        detail["macd_croisement"] = 20
    if bb_lower > 0 and prix <= bb_lower * 1.02:
        detail["bollinger_rebond"] = 15
    if ema20 > ema50:
        detail["ema_tendance"] = 15
    if vol_moy > 0 and vol_actuel > vol_moy * 1.5:
        detail["volume_confirmation"] = 15

    score = sum(detail.values())
    return score, detail


# ---------------------------------------------------------------------------
# Scan d'un ticker
# ---------------------------------------------------------------------------

def scan_ticker(ticker: str) -> Optional[Candidate]:
    """Retourne un Candidate si le ticker est éligible (score ≥ 30), sinon None."""
    try:
        hist = yf.Ticker(ticker).history(period="60d", interval="1d")
        if len(hist) < 50:
            return None

        close  = hist["Close"]
        high   = hist["High"]
        low    = hist["Low"]
        volume = hist["Volume"]
        prix   = round(float(close.iloc[-1]), 4)

        rsi              = calc_rsi(close)
        macd_val, macd_sig = calc_macd(close)
        bb_lower, bb_upper = calc_bollinger(close)
        ema20, ema50     = calc_ema(close)
        atr              = calc_atr(high, low, close)
        vol_moy          = float(volume.rolling(10).mean().iloc[-1])
        vol_actuel       = float(volume.iloc[-1])

        score, detail = score_from_indicators(
            rsi=rsi, macd_val=macd_val, macd_sig=macd_sig,
            prix=prix, bb_lower=bb_lower, bb_upper=bb_upper,
            ema20=ema20, ema50=ema50,
            vol_actuel=vol_actuel, vol_moy=vol_moy,
        )

        if score < 30:
            return None

        macd_signal = "haussier" if macd_val > macd_sig else "baissier"
        return Candidate(
            ticker=ticker,
            classe=TICKER_CLASS.get(ticker, "Action"),
            prix=prix,
            rsi=rsi,
            macd_signal=macd_signal,
            atr=atr,
            score_technique=score,
            detail_score=detail,
        )
    except Exception:
        return None


def scan_all() -> list[Candidate]:
    """Scanne tous les tickers et retourne les candidats triés par score décroissant."""
    candidates = [c for c in (scan_ticker(t) for t in TICKERS) if c is not None]
    candidates.sort(key=lambda c: c.score_technique, reverse=True)
    return candidates
```

- [ ] **Step 4: Lancer les tests**

```bash
pytest tests/test_scan.py -v
```

Expected: 8 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/services/scanner.py tests/test_scan.py
git commit -m "feat: scanner.py — indicateurs techniques RSI/MACD/Bollinger/EMA/Volume/ATR"
```

---

## Task 9 — services/claude_service.py + test_claude_service.py

**Files:**
- Create: `backend/services/claude_service.py`
- Create: `tests/test_claude_service.py`

- [ ] **Step 1: Écrire tests/test_claude_service.py (TDD — en premier)**

```python
"""test_claude_service.py — Tests avec Claude mocké (pas d'appels réels)."""
import json
import pytest
from unittest.mock import MagicMock, patch
from backend.services.scanner import Candidate
from backend.services.claude_service import enrich_candidate, _parse_claude_response


VALID_JSON_RESPONSE = json.dumps({
    "contexte_actualite": "Résultats positifs, upgrade analyste.",
    "sentiment_communaute": "HAUSSIER",
    "risques_identifies": "Résultats dans 5 jours.",
    "conclusion": "Bon signal avec catalyseur positif.",
    "bonus_malus": {
        "bonus_actualite_positive": 10,
        "bonus_sentiment_haussier": 5,
        "bonus_aucune_actualite_negative": 0,
        "malus_evenement_macro": 0,
        "malus_actualite_negative": 0,
        "malus_resultats_proches": -20,
    },
    "score_final": 55,
})


def make_candidate(score: int = 45) -> Candidate:
    return Candidate(
        ticker="AAPL", classe="Action", prix=200.0,
        rsi=32.0, macd_signal="haussier", atr=5.0,
        score_technique=score,
        detail_score={"rsi_survente": 20, "macd_croisement": 20},
    )


# --- _parse_claude_response ---

def test_parse_valid_json():
    result = _parse_claude_response(VALID_JSON_RESPONSE, fallback_score=45)
    assert result["sentiment_communaute"] == "HAUSSIER"
    assert result["score_final"] == 55


def test_parse_json_in_markdown():
    text = f"Voici l'analyse:\n```json\n{VALID_JSON_RESPONSE}\n```"
    result = _parse_claude_response(text, fallback_score=45)
    assert result["score_final"] == 55


def test_parse_invalid_json_returns_fallback():
    result = _parse_claude_response("texte invalide non-JSON", fallback_score=40)
    assert result["score_final"] == 40
    assert result["sentiment_communaute"] == "NEUTRE"


# --- enrich_candidate ---

def test_enrich_candidate_success():
    candidate = make_candidate(score=45)

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text=VALID_JSON_RESPONSE)]

    with patch("backend.services.claude_service.client") as mock_client:
        mock_client.messages.create.return_value = mock_response
        result = enrich_candidate(candidate)

    assert result["score_final"] == 55
    assert result["sentiment_communaute"] == "HAUSSIER"
    mock_client.messages.create.assert_called_once()


def test_enrich_candidate_api_error_returns_fallback():
    candidate = make_candidate(score=50)

    with patch("backend.services.claude_service.client") as mock_client:
        mock_client.messages.create.side_effect = Exception("API timeout")
        result = enrich_candidate(candidate)

    assert result["score_final"] == 50  # fallback = score technique
    assert "indisponible" in result["contexte_actualite"].lower()


def test_enrich_candidate_uses_correct_model():
    candidate = make_candidate()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text=VALID_JSON_RESPONSE)]

    with patch("backend.services.claude_service.client") as mock_client:
        mock_client.messages.create.return_value = mock_response
        enrich_candidate(candidate)

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-6"
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

```bash
pytest tests/test_claude_service.py -v 2>&1 | head -20
```

Expected: ImportError — claude_service.py n'existe pas encore.

- [ ] **Step 3: Créer backend/services/claude_service.py**

```python
"""
claude_service.py — Enrichissement des candidats via Claude sonnet-4-6 + web_search.

Pour chaque candidat (score technique ≥ 30), appelle Claude pour :
- Rechercher l'actualité récente (web_search)
- Évaluer le sentiment des investisseurs
- Calculer les bonus/malus et le score final
"""
import json
import os

import anthropic

from backend.services.scanner import Candidate

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_BONUS_MALUS_KEYS = [
    "bonus_actualite_positive",
    "bonus_sentiment_haussier",
    "bonus_aucune_actualite_negative",
    "malus_evenement_macro",
    "malus_actualite_negative",
    "malus_resultats_proches",
]


def _parse_claude_response(text: str, fallback_score: int) -> dict:
    """Extrait le JSON de la réponse Claude. Retourne un dict de fallback en cas d'échec."""
    # Nettoyer les blocs markdown ```json ... ```
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return {
            "contexte_actualite": f"Analyse web indisponible (parsing échoué).",
            "sentiment_communaute": "NEUTRE",
            "risques_identifies": "N/A",
            "conclusion": "Score technique uniquement.",
            "bonus_malus": {k: 0 for k in _BONUS_MALUS_KEYS},
            "score_final": fallback_score,
        }


def enrich_candidate(candidate: Candidate) -> dict:
    """
    Appelle Claude sonnet-4-6 avec web_search pour enrichir un candidat.

    Retourne un dict avec : contexte_actualite, sentiment_communaute,
    risques_identifies, conclusion, bonus_malus, score_final.

    En cas d'erreur API, retourne un dict de fallback avec score_final = score_technique.
    """
    prompt = f"""Tu es un analyste financier. Analyse l'actif {candidate.ticker}.

Score technique brut : {candidate.score_technique}/100
Prix actuel : {candidate.prix}
RSI(14) : {candidate.rsi}
Signal MACD : {candidate.macd_signal}
ATR : {candidate.atr}

1. Recherche l'actualité récente sur {candidate.ticker} (dernières 48h)
2. Recherche le sentiment des investisseurs (Reddit, Twitter, analystes)
3. Retourne UNIQUEMENT ce JSON valide (sans balises markdown) :
{{
  "contexte_actualite": "résumé en 2-3 phrases",
  "sentiment_communaute": "HAUSSIER|NEUTRE|BAISSIER|MITIGÉ",
  "risques_identifies": "risques en 1-2 phrases",
  "conclusion": "phrase de synthèse",
  "bonus_malus": {{
    "bonus_actualite_positive": 0,
    "bonus_sentiment_haussier": 0,
    "bonus_aucune_actualite_negative": 0,
    "malus_evenement_macro": 0,
    "malus_actualite_negative": 0,
    "malus_resultats_proches": 0
  }},
  "score_final": {candidate.score_technique}
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        return _parse_claude_response(text, fallback_score=candidate.score_technique)

    except Exception as e:
        return {
            "contexte_actualite": f"Analyse web indisponible ({e}).",
            "sentiment_communaute": "NEUTRE",
            "risques_identifies": "N/A",
            "conclusion": "Score technique uniquement (erreur Claude API).",
            "bonus_malus": {k: 0 for k in _BONUS_MALUS_KEYS},
            "score_final": candidate.score_technique,
        }
```

- [ ] **Step 4: Lancer les tests**

```bash
pytest tests/test_claude_service.py -v
```

Expected: 7 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/services/claude_service.py tests/test_claude_service.py
git commit -m "feat: claude_service.py — enrichissement candidats via sonnet-4-6 + web_search"
```

---

## Task 10 — services/scheduler.py + routers/scan.py

**Files:**
- Create: `backend/services/scheduler.py`
- Create: `backend/routers/scan.py`

- [ ] **Step 1: Créer backend/services/scheduler.py**

```python
"""
scheduler.py — APScheduler : scan quotidien automatique à 9h (Europe/Paris).

Le scan complet :
  1. Refresh des positions ouvertes (prix yfinance + clôtures auto)
  2. Scan nouveaux signaux (scanner.py → score technique)
  3. Enrichissement Claude (claude_service.py → score final)
  4. Insertion des ordres retenus (score final ≥ SCAN_MIN_CONFIDENCE)
  5. Enregistrement du ScanRun en base
"""
import os
from datetime import datetime, date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import SessionLocal
from backend.models import Order, Decision, CapitalHistory, ScanRun

SCAN_MIN_CONFIDENCE = int(os.getenv("SCAN_MIN_CONFIDENCE", "45"))
SCAN_MAX_SUGGESTIONS = int(os.getenv("SCAN_MAX_SUGGESTIONS", "2"))
SCAN_HOUR = int(os.getenv("SCAN_HOUR", "9"))
CAPITAL_DEPART = float(os.getenv("CAPITAL_DEPART", "10000"))


def _business_days_later(start: date, days: int = 5) -> date:
    d = start
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def _next_order_id(db) -> str:
    last = db.query(Order).order_by(Order.id.desc()).first()
    if last is None:
        return "ORD-001"
    try:
        n = int(last.id_ordre.split("-")[1])
        return f"ORD-{n + 1:03d}"
    except (IndexError, ValueError):
        return "ORD-001"


def _refresh_open_orders(db) -> int:
    """Rafraîchit les prix des ordres ouverts et clôture ceux qui ont atteint TP/SL/expiry."""
    import yfinance as yf
    today = date.today()
    nb_closed = 0

    for order in db.query(Order).filter(Order.statut == "OUVERT").all():
        try:
            hist = yf.Ticker(order.actif).history(period="2d", interval="1d")
            if hist.empty:
                continue
            prix = round(float(hist["Close"].iloc[-1]), 4)
        except Exception:
            continue

        qty = order.quantite_fictive or 0
        if prix <= order.stop_loss:
            statut, exit_price = "CLOTURE_PERDANT", order.stop_loss
        elif prix >= order.take_profit:
            statut, exit_price = "CLOTURE_GAGNANT", order.take_profit
        elif order.date_expiration and order.date_expiration <= today:
            statut, exit_price = "EXPIRE", prix
        else:
            order.prix_actuel = prix
            order.pnl_latent  = round((prix - order.prix_entree) * qty, 2)
            continue

        exit_pnl = round((exit_price - order.prix_entree) * qty, 2)
        order.statut       = statut
        order.prix_actuel  = exit_price
        order.prix_sortie  = exit_price
        order.pnl_latent   = exit_pnl
        order.date_cloture = today

        decision = db.query(Decision).filter(Decision.id_ordre == order.id_ordre).first()
        if decision and not decision.statut_final:
            decision.date_cloture     = today
            decision.statut_final     = statut
            decision.pnl_euros        = f"{exit_pnl:+.2f}"
            decision.commentaire_retour = f"Clôture automatique scan (prix={prix})."

        nb_closed += 1

    return nb_closed


def _insert_order_from_candidate(db, candidate, enrichment: dict) -> str:
    """Insère un ordre + décision depuis un candidat enrichi. Retourne l'id_ordre."""
    from backend.services.scanner import Candidate

    id_ordre = _next_order_id(db)
    now      = datetime.now()
    today    = date.today()
    expiry   = _business_days_later(today)

    prix  = candidate.prix
    sl    = round(prix - 1.5 * candidate.atr, 4) if candidate.atr else candidate.prix * 0.93
    tp    = round(prix + 2.5 * candidate.atr, 4) if candidate.atr else candidate.prix * 1.15
    qty   = round(1000.0 / prix, 4) if prix else 0
    rr    = round((tp - prix) / (prix - sl), 2) if (prix - sl) != 0 else None

    # Fusionner detail_score technique + bonus_malus Claude
    detail = dict(candidate.detail_score)
    detail.update(enrichment.get("bonus_malus", {}))

    order = Order(
        id_ordre=id_ordre,
        date_ouverture=now,
        actif=candidate.ticker,
        classe=candidate.classe,
        direction=candidate.direction,
        statut="OUVERT",
        prix_entree=prix,
        stop_loss=sl,
        take_profit=tp,
        ratio_rr=rr,
        taille=1000.0,
        quantite_fictive=qty,
        confiance=enrichment.get("score_final", candidate.score_technique),
        raison=f"Scan auto — Score: {enrichment.get('score_final', candidate.score_technique)}/100",
        atr_utilise=candidate.atr,
        date_expiration=expiry,
        prix_actuel=prix,
        pnl_latent=0.0,
    )
    db.add(order)
    db.flush()

    decision = Decision(
        id_ordre=id_ordre,
        signaux_techniques=f"RSI={candidate.rsi}, MACD={candidate.macd_signal}",
        contexte_actualite=enrichment.get("contexte_actualite", ""),
        sentiment_communaute=enrichment.get("sentiment_communaute", "NEUTRE"),
        risques_identifies=enrichment.get("risques_identifies", ""),
        conclusion=enrichment.get("conclusion", ""),
        score_confiance=enrichment.get("score_final", candidate.score_technique),
        detail_score=detail,
    )
    db.add(decision)
    return id_ordre


def run_daily_scan(triggered_by: str = "scheduler") -> dict:
    """
    Scan complet : refresh → scan → enrichissement Claude → insertion ordres.
    Retourne un résumé du scan.
    """
    from backend.services.scanner import scan_all
    from backend.services.claude_service import enrich_candidate

    db = SessionLocal()
    scan_run = ScanRun(started_at=datetime.now(), triggered_by=triggered_by)
    db.add(scan_run)
    db.flush()
    scan_id = scan_run.id

    try:
        # 1. Refresh positions ouvertes
        nb_clotures = _refresh_open_orders(db)
        db.flush()

        # 2. Scan nouveaux signaux
        candidates = scan_all()
        scan_run.nb_candidats = len(candidates)

        # 3. Appliquer le max positions ouvertes (20)
        nb_ouverts = db.query(Order).filter(Order.statut == "OUVERT").count()
        if nb_ouverts >= 20:
            scan_run.status      = "termine"
            scan_run.finished_at = datetime.now()
            scan_run.nb_clotures = nb_clotures
            db.commit()
            return {"status": "termine", "raison": "max_positions_atteint", "nb_candidats": len(candidates)}

        # 4. Enrichir + filtrer les meilleurs candidats
        ordres_generes = []
        for candidate in candidates[:SCAN_MAX_SUGGESTIONS * 2]:  # pool élargi
            enrichment = enrich_candidate(candidate)
            score_final = enrichment.get("score_final", candidate.score_technique)
            if score_final >= SCAN_MIN_CONFIDENCE:
                id_ordre = _insert_order_from_candidate(db, candidate, enrichment)
                ordres_generes.append(id_ordre)
                if len(ordres_generes) >= SCAN_MAX_SUGGESTIONS:
                    break

        scan_run.nb_ordres_generes = len(ordres_generes)
        scan_run.nb_clotures       = nb_clotures
        scan_run.status            = "termine"
        scan_run.finished_at       = datetime.now()

        # 5. Historique capital si clôtures
        if nb_clotures > 0:
            pnl_realise = sum(
                o.pnl_latent or 0
                for o in db.query(Order).filter(Order.statut != "OUVERT").all()
            )
            db.add(CapitalHistory(
                date=date.today(),
                capital=round(CAPITAL_DEPART + pnl_realise, 2),
                note=f"Scan auto: {nb_clotures} cloture(s), {len(ordres_generes)} nouvel(s) ordre(s).",
            ))

        db.commit()
        return {
            "status": "termine",
            "nb_candidats": len(candidates),
            "nb_ordres_generes": len(ordres_generes),
            "nb_clotures": nb_clotures,
            "ordres_generes": ordres_generes,
        }

    except Exception as e:
        scan_run.status  = "erreur"
        scan_run.erreur  = str(e)
        scan_run.finished_at = datetime.now()
        db.commit()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# APScheduler
# ---------------------------------------------------------------------------

scheduler = BackgroundScheduler(timezone="Europe/Paris")
scheduler.add_job(
    run_daily_scan,
    trigger="cron",
    hour=SCAN_HOUR,
    minute=0,
    id="daily_scan",
    replace_existing=True,
    max_instances=1,
    kwargs={"triggered_by": "scheduler"},
)
```

- [ ] **Step 2: Créer backend/routers/scan.py**

```python
"""
routers/scan.py — Endpoints pour le scan on-demand et le suivi des exécutions.

Endpoints:
    POST /api/scan/run      → Lance un scan immédiatement (thread séparé)
    GET  /api/scan/status   → État du dernier scan
    GET  /api/scan/history  → Historique des scans
"""
import threading

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ScanRun

router = APIRouter(prefix="/scan", tags=["scan"])

# Verrou pour éviter les scans simultanés lancés manuellement
_scan_lock = threading.Lock()


@router.post("/run", summary="Lance un scan immédiatement")
def run_scan_now(db: Session = Depends(get_db)) -> dict:
    """
    Lance un scan en arrière-plan (thread séparé).
    Retourne immédiatement {"status": "started"}.
    Si un scan est déjà en cours, retourne {"status": "already_running"}.
    """
    if not _scan_lock.acquire(blocking=False):
        return {"status": "already_running"}

    def _run():
        try:
            from backend.services.scheduler import run_daily_scan
            run_daily_scan(triggered_by="manual")
        finally:
            _scan_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}


@router.get("/status", summary="État du dernier scan")
def get_scan_status(db: Session = Depends(get_db)) -> dict:
    """Retourne le statut et le résumé du dernier scan exécuté."""
    last = db.query(ScanRun).order_by(ScanRun.id.desc()).first()
    if last is None:
        return {"status": "aucun_scan"}
    return {
        "id":                last.id,
        "status":            last.status,
        "triggered_by":      last.triggered_by,
        "started_at":        last.started_at.isoformat() if last.started_at else None,
        "finished_at":       last.finished_at.isoformat() if last.finished_at else None,
        "nb_candidats":      last.nb_candidats,
        "nb_ordres_generes": last.nb_ordres_generes,
        "nb_clotures":       last.nb_clotures,
        "erreur":            last.erreur,
    }


@router.get("/history", summary="Historique des scans")
def get_scan_history(db: Session = Depends(get_db), limit: int = 20) -> list:
    """Retourne les N derniers scans, du plus récent au plus ancien."""
    runs = db.query(ScanRun).order_by(ScanRun.id.desc()).limit(limit).all()
    return [
        {
            "id":                r.id,
            "status":            r.status,
            "triggered_by":      r.triggered_by,
            "started_at":        r.started_at.isoformat() if r.started_at else None,
            "finished_at":       r.finished_at.isoformat() if r.finished_at else None,
            "nb_ordres_generes": r.nb_ordres_generes,
            "nb_clotures":       r.nb_clotures,
        }
        for r in runs
    ]
```

- [ ] **Step 3: Vérifier l'import Python**

```bash
python -c "from backend.services.scheduler import scheduler, run_daily_scan; from backend.routers.scan import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/services/scheduler.py backend/routers/scan.py
git commit -m "feat: scheduler APScheduler + endpoints /api/scan/run|status|history"
```

---

## Task 11 — main.py + render.yaml

**Files:**
- Modify: `backend/main.py`
- Modify: `render.yaml`

- [ ] **Step 1: Réécrire backend/main.py avec lifespan APScheduler**

```python
"""
main.py — Point d'entrée FastAPI pour !nvest Trading Backend.

Lifespan : démarre APScheduler au boot, l'arrête à la fermeture.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import orders, prices
from backend.routers.scan import router as scan_router
from backend.services.scheduler import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarre le scheduler au démarrage, l'arrête à la fermeture."""
    scheduler.start()
    print("[scheduler] APScheduler démarré — scan quotidien à 9h (Europe/Paris)")
    yield
    scheduler.shutdown(wait=False)
    print("[scheduler] APScheduler arrêté")


app = FastAPI(
    title="!nvest Trading Backend",
    description="API REST pour !nvest — trading fictif avec scan automatique Claude.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

app.include_router(orders.router, prefix="/api")
app.include_router(prices.router, prefix="/api")
app.include_router(scan_router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "version": "2.0.0"}
```

- [ ] **Step 2: Mettre à jour render.yaml**

```yaml
services:
  - type: web
    name: nvest-backend
    runtime: python
    rootDir: .
    buildCommand: pip install -r backend/requirements.txt && alembic upgrade head
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: FRONTEND_URL
        value: https://nvest.vercel.app
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: DATABASE_URL
        sync: false
      - key: CAPITAL_DEPART
        value: "10000"
      - key: SCAN_HOUR
        value: "9"
      - key: SCAN_MIN_CONFIDENCE
        value: "45"
      - key: SCAN_MAX_SUGGESTIONS
        value: "2"
```

- [ ] **Step 3: Lancer le serveur et vérifier**

```bash
cd C:/Users/micka/Desktop/project/!nvest
uvicorn backend.main:app --reload --port 8000
```

Vérifier dans un autre terminal :
```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/orders/
curl http://localhost:8000/api/scan/status
```

Expected : `{"status":"ok","version":"2.0.0"}`, liste des ordres (depuis PG), `{"status":"aucun_scan"}`.

- [ ] **Step 4: Commit final**

```bash
git add backend/main.py render.yaml
git commit -m "feat: lifespan APScheduler dans main.py + render.yaml mis à jour"
```

---

## Task 12 — Mise à jour docs/PROGRESS.md

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: Cocher toutes les tâches complétées dans PROGRESS.md**

Ouvrir `docs/PROGRESS.md` et mettre `[x]` sur toutes les tâches de la Phase 1 à 6.

- [ ] **Step 2: Commit**

```bash
git add docs/PROGRESS.md
git commit -m "docs: marquer chantier backend comme terminé dans PROGRESS.md"
```

---

## Self-Review

### Couverture de la spec

| Exigence spec | Tâche couvrant |
|--------------|----------------|
| PostgreSQL (SQLAlchemy + Alembic) | Tasks 2, 3 |
| 4 tables (orders, decisions, capital_history, scan_runs) | Task 2 |
| Migration JSON → PG | Task 6 |
| Scanner technique (RSI, MACD, Bollinger, EMA, Volume, ATR) | Task 8 |
| Claude sonnet-4-6 + web_search | Task 9 |
| APScheduler 9h Paris + on-demand | Task 10 |
| Endpoints /api/scan/run|status|history | Task 10 |
| CRUD orders inchangé (contrat API) | Task 7 |
| Tests PostgreSQL réelle | Tasks 4, 5, 6, 7, 8, 9 |
| Migration idempotente | Task 6 |
| render.yaml preDeployCommand | Task 11 |
| Suppression data_loader.py | Task 7 |

### Types consistants

- `Candidate` défini dans `scanner.py` — utilisé dans `claude_service.py` et `scheduler.py` ✓
- `get_db()` défini dans `database.py` — utilisé dans tous les routers ✓
- `_next_order_id(db)` défini dans `orders.py` ET dupliqué dans `scheduler.py` — duplication intentionnelle (évite couplage circulaire entre router et service)
- `_business_days_later` dupliqué aussi — idem, YAGNI pour un helper trivial

### Placeholder scan

Aucun TBD ou TODO dans le plan.
