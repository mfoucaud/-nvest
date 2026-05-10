# Alpaca Paper Trading + Démarrage automatique — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer la DB locale pour les ordres par Alpaca Paper Trading, et lancer le scan automatiquement au démarrage du PC via un raccourci Windows Startup.

**Architecture:** `alpaca_service.py` centralise tous les appels Alpaca. `routers/orders.py` lit depuis Alpaca + enrichit via la table `decisions` (conservée). `scheduler.py` soumet les ordres à Alpaca. `main.py` lance un scan au démarrage (thread, 10s de délai, idempotent). Les tables `orders` et `capital_history` sont supprimées ; `decisions` reçoit les colonnes métadonnées de l'ordre.

**Tech Stack:** `alpaca-py`, FastAPI, SQLAlchemy/PostgreSQL (pour `decisions` + `scan_runs`), Alembic, React (inchangé)

---

## Carte des fichiers

| Action | Fichier | Responsabilité |
|---|---|---|
| CRÉER | `backend/services/alpaca_service.py` | Client Alpaca Paper centralisé |
| CRÉER | `backend/migrations/versions/XXXX_alpaca_migration.py` | Supprime orders/capital_history, étend decisions |
| CRÉER | `setup_startup.bat` | Raccourci Windows Startup (one-shot) |
| CRÉER | `tests/test_alpaca_service.py` | Tests alpaca_service (mockés) |
| MODIFIER | `backend/models.py` | Supprime Order/CapitalHistory, étend Decision |
| MODIFIER | `backend/routers/orders.py` | Réécrit sur alpaca_service |
| MODIFIER | `backend/services/scheduler.py` | Soumet à Alpaca au lieu d'insérer en DB |
| MODIFIER | `backend/main.py` | Simplifie lifespan + ajoute scan au démarrage |
| MODIFIER | `backend/requirements.txt` | Ajoute alpaca-py |
| MODIFIER | `tests/conftest.py` | Supprime fixture sample_order (Order supprimé) |
| MODIFIER | `tests/test_models.py` | Adapte aux nouveaux modèles |
| SUPPRIMER | `tests/test_migration.py` | Script migrate_json_to_pg plus pertinent |
| RÉÉCRIRE | `tests/test_orders.py` | Mock alpaca_service |

---

## Task 1 : Dépendance alpaca-py

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1 : Ajouter alpaca-py à requirements.txt**

Ajouter la ligne suivante après `anthropic>=0.40` :

```
alpaca-py>=0.28
```

- [ ] **Step 2 : Installer**

```bash
pip install alpaca-py
```

Expected : `Successfully installed alpaca-py-...` (ou déjà installé).

- [ ] **Step 3 : Vérifier l'import**

```bash
python -c "from alpaca.trading.client import TradingClient; print('OK')"
```

Expected : `OK`

- [ ] **Step 4 : Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add alpaca-py dependency"
```

---

## Task 2 : alpaca_service.py — squelette + get_account()

**Files:**
- Create: `backend/services/alpaca_service.py`
- Create: `tests/test_alpaca_service.py`

- [ ] **Step 1 : Écrire le test get_account()**

Créer `tests/test_alpaca_service.py` :

```python
import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("ALPACA_API_KEY", "test-key")
os.environ.setdefault("ALPACA_SECRET_KEY", "test-secret")


def test_get_account_returns_equity():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_account = MagicMock()
        mock_account.equity = "10500.00"
        mock_account.buying_power = "9500.00"
        mock_account.currency = "USD"
        MockClient.return_value.get_account.return_value = mock_account

        from backend.services.alpaca_service import get_account
        result = get_account()

        assert result["equity"] == 10500.0
        assert result["buying_power"] == 9500.0
        assert result["currency"] == "USD"
```

- [ ] **Step 2 : Lancer le test — vérifier qu'il échoue**

```bash
pytest tests/test_alpaca_service.py::test_get_account_returns_equity -v
```

Expected : FAIL avec `ModuleNotFoundError` ou `ImportError`

- [ ] **Step 3 : Créer backend/services/alpaca_service.py**

```python
"""
alpaca_service.py — Client Alpaca Paper Trading centralisé.
"""
import os
from datetime import datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOrdersRequest,
    GetPortfolioHistoryRequest,
    MarketOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
)
from alpaca.trading.enums import (
    OrderSide,
    TimeInForce,
    OrderClass,
    QueryOrderStatus,
)

_ASSET_CLASS_MAP = {
    "us_equity": "Action",
    "crypto": "Crypto",
    "forex": "Forex",
}


def _get_client() -> TradingClient:
    return TradingClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
        paper=True,
    )


def get_account() -> dict:
    """Retourne equity et buying_power depuis le compte Alpaca Paper."""
    client = _get_client()
    account = client.get_account()
    return {
        "equity": float(account.equity),
        "buying_power": float(account.buying_power),
        "currency": account.currency,
    }
```

- [ ] **Step 4 : Relancer le test**

```bash
pytest tests/test_alpaca_service.py::test_get_account_returns_equity -v
```

Expected : PASS

- [ ] **Step 5 : Commit**

```bash
git add backend/services/alpaca_service.py tests/test_alpaca_service.py
git commit -m "feat: alpaca_service skeleton + get_account()"
```

---

## Task 3 : alpaca_service — get_positions() et get_portfolio_history()

**Files:**
- Modify: `backend/services/alpaca_service.py`
- Modify: `tests/test_alpaca_service.py`

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `tests/test_alpaca_service.py` :

```python
def test_get_positions_empty():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        MockClient.return_value.get_all_positions.return_value = []
        from backend.services.alpaca_service import get_positions
        assert get_positions() == []


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

        from backend.services.alpaca_service import get_positions
        result = get_positions()

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

        from backend.services.alpaca_service import get_portfolio_history
        assert get_portfolio_history() == []


def test_get_portfolio_history_returns_formatted_list():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_history = MagicMock()
        mock_history.timestamp = [1735689600]  # 2025-01-01 00:00:00 UTC
        mock_history.equity = [10500.0]
        MockClient.return_value.get_portfolio_history.return_value = mock_history

        from backend.services.alpaca_service import get_portfolio_history
        result = get_portfolio_history()

        assert len(result) == 1
        assert result[0]["capital"] == 10500.0
        assert "date" in result[0]
```

- [ ] **Step 2 : Lancer les tests — vérifier qu'ils échouent**

```bash
pytest tests/test_alpaca_service.py -v -k "positions or portfolio"
```

Expected : FAIL (fonctions non définies)

- [ ] **Step 3 : Implémenter get_positions() et get_portfolio_history()**

Ajouter dans `backend/services/alpaca_service.py` après `get_account()` :

```python
def get_positions() -> list[dict]:
    """Retourne les positions ouvertes au format dashboard."""
    client = _get_client()
    positions = client.get_all_positions()
    result = []
    for p in positions:
        entry = float(p.avg_entry_price)
        current = float(p.current_price)
        qty = float(p.qty)
        pnl = float(p.unrealized_pl)
        classe = _ASSET_CLASS_MAP.get(
            str(p.asset_class).lower().split(".")[-1].replace("_", " ").strip(),
            "Action",
        )
        # Normalisation plus robuste pour us_equity -> Action
        asset_str = str(p.asset_class).lower()
        if "equity" in asset_str:
            classe = "Action"
        elif "crypto" in asset_str:
            classe = "Crypto"
        direction = "ACHAT" if "long" in str(p.side).lower() else "VENTE"
        result.append({
            "id_ordre": str(p.asset_id),
            "actif": p.symbol,
            "classe": classe,
            "direction": direction,
            "statut": "OUVERT",
            "prix_entree": entry,
            "prix_actuel": current,
            "pnl_latent": round(pnl, 2),
            "quantite_fictive": qty,
            "taille": round(entry * qty, 2),
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
        })
    return result


def get_portfolio_history() -> list[dict]:
    """Retourne l'historique journalier de l'equity (pour CapitalChart)."""
    client = _get_client()
    request = GetPortfolioHistoryRequest(period="1Y", timeframe="1D")
    history = client.get_portfolio_history(history_filter=request)
    result = []
    for ts, equity in zip(history.timestamp, history.equity):
        if equity is None:
            continue
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        result.append({"date": date_str, "capital": round(float(equity), 2), "note": None})
    return result
```

- [ ] **Step 4 : Relancer les tests**

```bash
pytest tests/test_alpaca_service.py -v
```

Expected : tous PASS

- [ ] **Step 5 : Commit**

```bash
git add backend/services/alpaca_service.py tests/test_alpaca_service.py
git commit -m "feat: alpaca_service — get_positions() + get_portfolio_history()"
```

---

## Task 4 : alpaca_service — get_closed_orders() et submit_bracket_order()

**Files:**
- Modify: `backend/services/alpaca_service.py`
- Modify: `tests/test_alpaca_service.py`

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `tests/test_alpaca_service.py` :

```python
def test_submit_bracket_order():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-abc123"
        MockClient.return_value.submit_order.return_value = mock_order

        from backend.services.alpaca_service import submit_bracket_order
        order_id = submit_bracket_order("AAPL", qty=6.67, side="ACHAT", tp=165.0, sl=140.0)

        assert order_id == "alpaca-order-abc123"
        MockClient.return_value.submit_order.assert_called_once()


def test_submit_bracket_order_sell():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        mock_order = MagicMock()
        mock_order.id = "alpaca-order-sell-001"
        MockClient.return_value.submit_order.return_value = mock_order

        from backend.services.alpaca_service import submit_bracket_order
        from alpaca.trading.enums import OrderSide

        submit_bracket_order("TSLA", qty=2.0, side="VENTE", tp=100.0, sl=200.0)

        call_args = MockClient.return_value.submit_order.call_args
        submitted = call_args.kwargs.get("order_data") or call_args.args[0]
        assert submitted.side == OrderSide.SELL


def test_get_closed_orders_empty():
    with patch("backend.services.alpaca_service.TradingClient") as MockClient:
        MockClient.return_value.get_orders.return_value = []

        from backend.services.alpaca_service import get_closed_orders
        assert get_closed_orders() == []


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

        from backend.services.alpaca_service import get_closed_orders
        result = get_closed_orders()

        assert len(result) == 1
        assert result[0]["statut"] == "CLOTURE_GAGNANT"
        assert result[0]["prix_sortie"] == 165.0
```

- [ ] **Step 2 : Lancer les tests — vérifier qu'ils échouent**

```bash
pytest tests/test_alpaca_service.py -v -k "submit or closed"
```

Expected : FAIL

- [ ] **Step 3 : Implémenter get_closed_orders() et submit_bracket_order()**

Ajouter dans `backend/services/alpaca_service.py` :

```python
def _determine_bracket_status(order) -> str | None:
    """Détermine CLOTURE_GAGNANT/PERDANT/EXPIRE depuis les jambes d'un ordre bracket."""
    if not order.legs:
        return None
    for leg in order.legs:
        status_str = str(leg.status).lower()
        if "filled" in status_str:
            type_str = str(leg.type).lower()
            if "limit" in type_str:
                return "CLOTURE_GAGNANT"
            if "stop" in type_str:
                return "CLOTURE_PERDANT"
    if "canceled" in str(order.status).lower():
        return "EXPIRE"
    return None


def _get_filled_leg_price(order) -> float | None:
    """Retourne le prix de la jambe remplie d'un ordre bracket."""
    if not order.legs:
        return None
    for leg in order.legs:
        if "filled" in str(leg.status).lower() and leg.filled_avg_price:
            return float(leg.filled_avg_price)
    return None


def get_closed_orders(limit: int = 50) -> list[dict]:
    """
    Retourne les ordres clôturés au format dashboard.
    Pour les ordres bracket, détermine CLOTURE_GAGNANT/PERDANT depuis la jambe remplie.
    """
    client = _get_client()
    request = GetOrdersRequest(
        status=QueryOrderStatus.CLOSED,
        limit=limit,
        nested=True,
    )
    orders = client.get_orders(filter=request)

    result = []
    for order in orders:
        order_class_str = str(order.order_class).lower()
        status_str = str(order.status).lower()

        if "bracket" in order_class_str:
            statut = _determine_bracket_status(order)
            if statut is None:
                continue
            filled_price = _get_filled_leg_price(order)
        elif "filled" in status_str:
            statut = "CLOTURE_GAGNANT"
            filled_price = float(order.filled_avg_price) if order.filled_avg_price else None
        elif "canceled" in status_str:
            statut = "EXPIRE"
            filled_price = float(order.filled_avg_price) if order.filled_avg_price else None
        else:
            continue

        entry_price = float(order.filled_avg_price) if order.filled_avg_price else None
        result.append({
            "id_ordre": str(order.id),
            "actif": order.symbol,
            "classe": "Action",
            "direction": "ACHAT" if "buy" in str(order.side).lower() else "VENTE",
            "statut": statut,
            "prix_entree": entry_price,
            "prix_sortie": filled_price,
            "prix_actuel": filled_price,
            "pnl_latent": None,
            "quantite_fictive": float(order.qty) if order.qty else None,
            "taille": None,
            "stop_loss": None,
            "take_profit": None,
            "ratio_rr": None,
            "confiance": None,
            "raison": None,
            "atr_utilise": None,
            "alerte": None,
            "date_ouverture": order.created_at.isoformat() if order.created_at else None,
            "date_expiration": None,
            "date_cloture": order.filled_at.isoformat()[:10] if order.filled_at else None,
        })
    return result


def submit_bracket_order(
    ticker: str,
    qty: float,
    side: str,
    tp: float,
    sl: float,
) -> str:
    """
    Soumet un ordre bracket Paper Trading.
    side : "ACHAT" ou "VENTE"
    Retourne l'ID Alpaca de l'ordre parent (UUID str).
    """
    client = _get_client()
    order_side = OrderSide.BUY if side == "ACHAT" else OrderSide.SELL
    request = MarketOrderRequest(
        symbol=ticker,
        qty=round(qty, 4),
        side=order_side,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit=TakeProfitRequest(limit_price=round(tp, 4)),
        stop_loss=StopLossRequest(stop_price=round(sl, 4)),
    )
    order = client.submit_order(order_data=request)
    return str(order.id)
```

- [ ] **Step 4 : Relancer tous les tests alpaca_service**

```bash
pytest tests/test_alpaca_service.py -v
```

Expected : tous PASS

- [ ] **Step 5 : Commit**

```bash
git add backend/services/alpaca_service.py tests/test_alpaca_service.py
git commit -m "feat: alpaca_service — get_closed_orders() + submit_bracket_order()"
```

---

## Task 5 : Mise à jour models.py + migration Alembic

**Files:**
- Modify: `backend/models.py`
- Create: `backend/migrations/versions/<hash>_alpaca_migration.py`

- [ ] **Step 1 : Réécrire backend/models.py**

Remplacer **tout le contenu** de `backend/models.py` par :

```python
"""
models.py — Modèles SQLAlchemy ORM pour !nvest.

Tables conservées :
  decisions   — journal des décisions IA + métadonnées ordre (id_ordre = Alpaca order UUID)
  scan_runs   — historique des exécutions du scan

Tables supprimées (gérées par Alpaca) :
  orders, capital_history
"""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from backend.database import Base


class Decision(Base):
    __tablename__ = "decisions"

    id                   = Column(Integer, primary_key=True, index=True)
    # Identifiant Alpaca (UUID de l'ordre parent bracket)
    id_ordre             = Column(String(100), nullable=False, index=True)
    # Métadonnées de l'ordre (plus de FK vers orders)
    actif                = Column(String(20))
    classe               = Column(String(20))
    direction            = Column(String(10))
    prix_entree          = Column(Float)
    stop_loss            = Column(Float)
    take_profit          = Column(Float)
    taille               = Column(Float)
    quantite             = Column(Float)
    raison               = Column(Text)
    date_ouverture       = Column(DateTime)
    date_expiration      = Column(Date)
    # Analyse Claude
    signaux_techniques   = Column(Text)
    contexte_actualite   = Column(Text)
    sentiment_communaute = Column(Text)
    risques_identifies   = Column(Text)
    conclusion           = Column(Text)
    score_confiance      = Column(Integer)
    detail_score         = Column(JSONB)
    # Clôture (rempli manuellement si nécessaire)
    date_cloture         = Column(Date)
    statut_final         = Column(String(30))
    pnl_euros            = Column(String(20))
    commentaire_retour   = Column(Text)
    created_at           = Column(DateTime, server_default=func.now())


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id                = Column(Integer, primary_key=True, index=True)
    triggered_by      = Column(String(20), default="manual")
    started_at        = Column(DateTime, nullable=False)
    finished_at       = Column(DateTime)
    status            = Column(String(20), default="en_cours")
    nb_candidats      = Column(Integer, default=0)
    nb_ordres_generes = Column(Integer, default=0)
    nb_clotures       = Column(Integer, default=0)
    erreur            = Column(Text)
    created_at        = Column(DateTime, server_default=func.now())
```

- [ ] **Step 2 : Générer la migration Alembic**

```bash
cd C:/Users/micka/Desktop/project/!nvest
alembic revision --autogenerate -m "alpaca_migration_drop_orders_capital_history"
```

Expected : création d'un fichier dans `backend/migrations/versions/`.

- [ ] **Step 3 : Vérifier et corriger la migration générée**

Ouvrir le fichier généré. Si `upgrade()` ne contient pas les bonnes opérations, le remplacer manuellement par :

```python
import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    # 1. Ajouter les nouvelles colonnes à decisions
    op.add_column('decisions', sa.Column('actif', sa.String(20), nullable=True))
    op.add_column('decisions', sa.Column('classe', sa.String(20), nullable=True))
    op.add_column('decisions', sa.Column('direction', sa.String(10), nullable=True))
    op.add_column('decisions', sa.Column('prix_entree', sa.Float(), nullable=True))
    op.add_column('decisions', sa.Column('stop_loss', sa.Float(), nullable=True))
    op.add_column('decisions', sa.Column('take_profit', sa.Float(), nullable=True))
    op.add_column('decisions', sa.Column('taille', sa.Float(), nullable=True))
    op.add_column('decisions', sa.Column('quantite', sa.Float(), nullable=True))
    op.add_column('decisions', sa.Column('raison', sa.Text(), nullable=True))
    op.add_column('decisions', sa.Column('date_ouverture', sa.DateTime(), nullable=True))
    op.add_column('decisions', sa.Column('date_expiration', sa.Date(), nullable=True))

    # 2. Supprimer FK et élargir id_ordre (String 20 → 100)
    try:
        op.drop_constraint('decisions_id_ordre_fkey', 'decisions', type_='foreignkey')
    except Exception:
        pass  # contrainte peut avoir un nom différent selon l'environnement
    op.alter_column('decisions', 'id_ordre',
                    existing_type=sa.String(20), type_=sa.String(100))

    # 3. Supprimer les tables remplacées par Alpaca
    op.drop_table('orders')
    op.drop_table('capital_history')


def downgrade() -> None:
    op.create_table('capital_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('capital', sa.Float(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('id_ordre', sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.alter_column('decisions', 'id_ordre',
                    existing_type=sa.String(100), type_=sa.String(20))
    for col in ['actif', 'classe', 'direction', 'prix_entree', 'stop_loss',
                'take_profit', 'taille', 'quantite', 'raison', 'date_ouverture', 'date_expiration']:
        op.drop_column('decisions', col)
```

- [ ] **Step 4 : Appliquer la migration**

```bash
alembic upgrade head
```

Expected : `Running upgrade ... -> <hash>, alpaca_migration_drop_orders_capital_history`

- [ ] **Step 5 : Commit**

```bash
git add backend/models.py backend/migrations/versions/
git commit -m "feat: models — supprime Order/CapitalHistory, étend Decision pour Alpaca"
```

---

## Task 6 : Réécriture de routers/orders.py

**Files:**
- Modify: `backend/routers/orders.py`

Le router garde les 3 endpoints utilisés par le frontend : `GET /api/orders/`, `POST /api/orders/refresh`, `GET /api/orders/{id_ordre}`. Les endpoints de création/clôture manuelle sont supprimés (Alpaca les gère).

- [ ] **Step 1 : Réécrire backend/routers/orders.py**

Remplacer **tout le contenu** par :

```python
"""
routers/orders.py — Endpoints ordres lus depuis Alpaca Paper Trading.

Endpoints :
    GET  /api/orders/              → Positions + ordres clôturés + métriques (Alpaca + DB)
    POST /api/orders/refresh       → Identique à GET (fresh fetch Alpaca)
    GET  /api/orders/{id_ordre}    → Détail ordre + décision Claude
"""
import os
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Decision
from backend.services import alpaca_service

router = APIRouter(prefix="/orders", tags=["orders"])

CAPITAL_DEPART = float(os.getenv("CAPITAL_DEPART", "10000"))


def _enrich_positions_from_db(positions: list[dict], db: Session) -> list[dict]:
    """Enrichit les positions ouvertes avec les données Decision (SL, TP, raison, etc.)."""
    for pos in positions:
        decision = (
            db.query(Decision)
            .filter(Decision.actif == pos["actif"], Decision.statut_final == None)  # noqa: E711
            .order_by(Decision.id.desc())
            .first()
        )
        if decision:
            pos["id_ordre"] = decision.id_ordre
            pos["stop_loss"] = decision.stop_loss
            pos["take_profit"] = decision.take_profit
            pos["confiance"] = decision.score_confiance
            pos["raison"] = decision.raison
            pos["taille"] = decision.taille
            pos["date_ouverture"] = decision.date_ouverture.isoformat() if decision.date_ouverture else None
            pos["date_expiration"] = decision.date_expiration.isoformat() if decision.date_expiration else None
            entry = pos["prix_entree"]
            sl = decision.stop_loss
            tp = decision.take_profit
            if sl and tp and (entry - sl) != 0:
                pos["ratio_rr"] = round((tp - entry) / (entry - sl), 2)
    return positions


def _enrich_closed_from_db(closed: list[dict], db: Session) -> list[dict]:
    """Enrichit les ordres clôturés avec les données Decision."""
    for order in closed:
        decision = (
            db.query(Decision)
            .filter(Decision.id_ordre == order["id_ordre"])
            .first()
        )
        if decision:
            order["stop_loss"] = decision.stop_loss
            order["take_profit"] = decision.take_profit
            order["confiance"] = decision.score_confiance
            order["raison"] = decision.raison
            order["taille"] = decision.taille
            order["quantite_fictive"] = decision.quantite
            order["date_ouverture"] = decision.date_ouverture.isoformat() if decision.date_ouverture else None
            order["date_expiration"] = decision.date_expiration.isoformat() if decision.date_expiration else None
            entry = decision.prix_entree
            qty = decision.quantite
            sortie = order.get("prix_sortie")
            if entry and qty and sortie:
                order["pnl_latent"] = round((sortie - entry) * qty, 2)
    return closed


def _compute_metrics(positions: list[dict], closed: list[dict], equity: float) -> dict:
    gagnants = [o for o in closed if o["statut"] == "CLOTURE_GAGNANT"]
    perdants = [o for o in closed if o["statut"] == "CLOTURE_PERDANT"]
    expires  = [o for o in closed if o["statut"] == "EXPIRE"]
    nb_clos  = len(closed)

    pnl_realise = sum(o["pnl_latent"] or 0 for o in closed if o["pnl_latent"] is not None)
    pnl_latent  = sum(p["pnl_latent"] for p in positions)
    gains  = sum(o["pnl_latent"] or 0 for o in gagnants if o["pnl_latent"])
    pertes = abs(sum(o["pnl_latent"] or 0 for o in perdants if o["pnl_latent"]))

    return {
        "win_rate":            round(len(gagnants) / nb_clos * 100, 1) if nb_clos else None,
        "pnl_total_eur":       round(pnl_realise, 2),
        "pnl_latent_eur":      round(pnl_latent, 2),
        "pnl_total_pct":       round(pnl_realise / CAPITAL_DEPART * 100, 2),
        "profit_factor":       round(gains / pertes, 2) if pertes > 0 else None,
        "nb_trades_total":     nb_clos + len(positions),
        "nb_trades_ouverts":   len(positions),
        "max_positions":       int(os.getenv("SCAN_MAX_POSITIONS", "20")),
        "nb_trades_gagnants":  len(gagnants),
        "nb_trades_perdants":  len(perdants),
        "nb_trades_expires":   len(expires),
        "meilleur_trade":      max((o["pnl_latent"] for o in closed if o["pnl_latent"]), default=None),
        "pire_trade":          min((o["pnl_latent"] for o in closed if o["pnl_latent"]), default=None),
        "capital_actuel":      round(equity, 2),
        "derniere_mise_a_jour": date.today().isoformat(),
    }


def _build_full_response(db: Session) -> dict:
    positions = _enrich_positions_from_db(alpaca_service.get_positions(), db)
    closed    = _enrich_closed_from_db(alpaca_service.get_closed_orders(), db)
    account   = alpaca_service.get_account()
    history   = alpaca_service.get_portfolio_history()

    return {
        "ouverts":            positions,
        "cloturer":           closed,
        "metriques":          _compute_metrics(positions, closed, account["equity"]),
        "historique_capital": history,
    }


@router.get("/", summary="Positions + ordres clôturés depuis Alpaca")
def list_orders(db: Session = Depends(get_db)) -> dict:
    return _build_full_response(db)


@router.post("/refresh", summary="Rafraîchit depuis Alpaca (même réponse que GET /)")
def refresh_orders(db: Session = Depends(get_db)) -> dict:
    return _build_full_response(db)


@router.get("/{id_ordre}", summary="Détail d'un ordre + décision Claude")
def get_order(id_ordre: str, db: Session = Depends(get_db)) -> dict:
    decision = db.query(Decision).filter(Decision.id_ordre == id_ordre).first()

    # Chercher dans les positions ouvertes
    try:
        positions = _enrich_positions_from_db(alpaca_service.get_positions(), db)
        for pos in positions:
            if pos.get("id_ordre") == id_ordre or pos.get("actif") == id_ordre:
                pos["decision"] = _decision_to_dict(decision)
                return pos
    except Exception:
        pass

    # Chercher dans les ordres clôturés
    try:
        closed = _enrich_closed_from_db(alpaca_service.get_closed_orders(limit=100), db)
        for order in closed:
            if order["id_ordre"] == id_ordre:
                order["decision"] = _decision_to_dict(decision)
                return order
    except Exception:
        pass

    if decision:
        return {
            "id_ordre": decision.id_ordre,
            "actif": decision.actif,
            "classe": decision.classe,
            "direction": decision.direction,
            "statut": "INCONNU",
            "prix_entree": decision.prix_entree,
            "stop_loss": decision.stop_loss,
            "take_profit": decision.take_profit,
            "confiance": decision.score_confiance,
            "raison": decision.raison,
            "decision": _decision_to_dict(decision),
        }

    from fastapi import HTTPException
    raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")


def _decision_to_dict(decision: Decision | None) -> dict | None:
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
```

- [ ] **Step 2 : Vérifier que le backend démarre sans erreur**

```bash
python -m uvicorn backend.main:app --port 8001 --reload
```

Expected : démarrage sans erreur de typage. Arrêter avec Ctrl+C.

- [ ] **Step 3 : Commit**

```bash
git add backend/routers/orders.py
git commit -m "feat: orders router — lecture depuis Alpaca Paper Trading"
```

---

## Task 7 : Mise à jour de scheduler.py

**Files:**
- Modify: `backend/services/scheduler.py`

- [ ] **Step 1 : Réécrire backend/services/scheduler.py**

Remplacer **tout le contenu** par :

```python
"""
scheduler.py — APScheduler : scan quotidien à 14h30 (Europe/Paris).

Le scan complet :
  1. Scan nouveaux signaux (scanner.py → score technique)
  2. Enrichissement Claude (claude_service.py → score final)
  3. Soumission ordre bracket à Alpaca Paper + insertion Decision en DB
  4. Enregistrement du ScanRun en base
"""
import os
from datetime import datetime, date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import SessionLocal
from backend.models import Decision, ScanRun

SCAN_MIN_CONFIDENCE = int(os.getenv("SCAN_MIN_CONFIDENCE", "45"))
SCAN_MAX_SUGGESTIONS = int(os.getenv("SCAN_MAX_SUGGESTIONS", "2"))
SCAN_HOUR   = int(os.getenv("SCAN_HOUR",   "14"))
SCAN_MINUTE = int(os.getenv("SCAN_MINUTE", "30"))


def _business_days_later(start: date, days: int = 5) -> date:
    d = start
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def _submit_order_to_alpaca(candidate, enrichment: dict, db) -> str | None:
    """Soumet un ordre bracket à Alpaca et insère la Decision en DB. Retourne l'Alpaca order ID."""
    from backend.services.alpaca_service import submit_bracket_order

    prix = candidate.prix
    sl   = round(prix - 1.5 * candidate.atr, 4) if candidate.atr else round(prix * 0.93, 4)
    tp   = round(prix + 2.5 * candidate.atr, 4) if candidate.atr else round(prix * 1.15, 4)
    qty  = round(1000.0 / prix, 4) if prix else 0
    rr   = round((tp - prix) / (prix - sl), 2) if (prix - sl) != 0 else None

    try:
        alpaca_order_id = submit_bracket_order(
            ticker=candidate.ticker,
            qty=qty,
            side=candidate.direction,
            tp=tp,
            sl=sl,
        )
    except Exception as e:
        print(f"[scheduler] Alpaca order failed for {candidate.ticker}: {e}")
        return None

    detail = dict(candidate.detail_score)
    detail.update(enrichment.get("bonus_malus", {}))

    today = date.today()
    decision = Decision(
        id_ordre=alpaca_order_id,
        actif=candidate.ticker,
        classe=candidate.classe,
        direction=candidate.direction,
        prix_entree=prix,
        stop_loss=sl,
        take_profit=tp,
        taille=1000.0,
        quantite=qty,
        raison=f"Scan auto — Score: {enrichment.get('score_final', candidate.score_technique)}/100",
        date_ouverture=datetime.now(),
        date_expiration=_business_days_later(today),
        signaux_techniques=f"RSI={candidate.rsi}, MACD={candidate.macd_signal}",
        contexte_actualite=enrichment.get("contexte_actualite", ""),
        sentiment_communaute=enrichment.get("sentiment_communaute", "NEUTRE"),
        risques_identifies=enrichment.get("risques_identifies", ""),
        conclusion=enrichment.get("conclusion", ""),
        score_confiance=enrichment.get("score_final", candidate.score_technique),
        detail_score=detail,
    )
    db.add(decision)
    return alpaca_order_id


def run_daily_scan(triggered_by: str = "scheduler") -> dict:
    """
    Scan complet : scan signaux → enrichissement Claude → soumission Alpaca → Decision en DB.
    Retourne un résumé.
    """
    from backend.services.scanner import scan_all
    from backend.services.claude_service import enrich_candidate

    db = SessionLocal()
    scan_run = ScanRun(started_at=datetime.now(), triggered_by=triggered_by)
    db.add(scan_run)
    db.flush()

    try:
        candidates = scan_all()
        scan_run.nb_candidats = len(candidates)

        ordres_generes = []
        for candidate in candidates[:SCAN_MAX_SUGGESTIONS * 2]:
            enrichment = enrich_candidate(candidate)
            score_final = enrichment.get("score_final", candidate.score_technique)
            if score_final >= SCAN_MIN_CONFIDENCE:
                alpaca_order_id = _submit_order_to_alpaca(candidate, enrichment, db)
                if alpaca_order_id:
                    ordres_generes.append(alpaca_order_id)
                    db.flush()
                if len(ordres_generes) >= SCAN_MAX_SUGGESTIONS:
                    break

        scan_run.nb_ordres_generes = len(ordres_generes)
        scan_run.nb_clotures       = 0
        scan_run.status            = "termine"
        scan_run.finished_at       = datetime.now()
        db.commit()

        return {
            "status": "termine",
            "nb_candidats": len(candidates),
            "nb_ordres_generes": len(ordres_generes),
            "nb_clotures": 0,
            "ordres_generes": ordres_generes,
        }

    except Exception as e:
        scan_run.status      = "erreur"
        scan_run.erreur      = str(e)
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
    minute=SCAN_MINUTE,
    id="daily_scan",
    replace_existing=True,
    max_instances=1,
    kwargs={"triggered_by": "scheduler"},
)
```

- [ ] **Step 2 : Vérifier l'import**

```bash
python -c "from backend.services.scheduler import run_daily_scan, scheduler; print('OK')"
```

Expected : `OK`

- [ ] **Step 3 : Commit**

```bash
git add backend/services/scheduler.py
git commit -m "feat: scheduler — soumet ordres à Alpaca Paper au lieu de la DB"
```

---

## Task 8 : Simplification de main.py + scan au démarrage

**Files:**
- Modify: `backend/main.py`

- [ ] **Step 1 : Réécrire backend/main.py**

Remplacer **tout le contenu** par :

```python
"""
main.py — Point d'entrée FastAPI pour !nvest Trading Backend.

Lifespan :
  1. Vérifie/crée les tables DB
  2. Démarre APScheduler (scan quotidien 14h30)
  3. Lance un scan en arrière-plan au démarrage (10s de délai, idempotent)
"""
import os
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import prices
from backend.routers.orders import router as orders_router
from backend.routers.scan import router as scan_router
from backend.services.scheduler import scheduler


def _run_startup_scan() -> None:
    """Lance un scan au démarrage si aucun scan n'a déjà été effectué aujourd'hui."""
    import time
    time.sleep(10)  # Laisser le serveur être prêt

    from backend.database import SessionLocal
    from backend.models import ScanRun
    try:
        db = SessionLocal()
        today_start = datetime.combine(date.today(), datetime.min.time())
        already_done = (
            db.query(ScanRun)
            .filter(ScanRun.started_at >= today_start, ScanRun.status == "termine")
            .first()
        )
        db.close()

        if already_done:
            print("[startup] Scan du jour déjà effectué — ignoré")
            return

        print("[startup] Lancement du scan automatique au démarrage")
        from backend.services.scheduler import run_daily_scan
        run_daily_scan(triggered_by="startup")
        print("[startup] Scan au démarrage terminé")
    except Exception as e:
        print(f"[startup] Scan au démarrage échoué (non bloquant) : {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.database import engine, Base
    import backend.models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)
        print("[startup] Tables DB vérifiées")
    except Exception as e:
        print(f"[startup] create_all échoué : {e}")

    scheduler.start()
    print("[scheduler] APScheduler démarré — scan quotidien à 14h30 (Europe/Paris)")

    threading.Thread(target=_run_startup_scan, daemon=True).start()

    yield
    scheduler.shutdown(wait=False)
    print("[scheduler] APScheduler arrêté")


app = FastAPI(
    title="!nvest Trading Backend",
    description="API REST pour !nvest — trading Paper Alpaca avec scan Claude.",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
_extra_origins = [o.strip() for o in os.getenv("FRONTEND_EXTRA_ORIGINS", "").split(",") if o.strip()]
_allowed_origins = list({_frontend_url, "http://localhost:5173"} | set(_extra_origins))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

app.include_router(orders_router, prefix="/api")
app.include_router(prices.router, prefix="/api")
app.include_router(scan_router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "version": "3.0.0"}
```

- [ ] **Step 2 : Démarrer le backend et vérifier**

```bash
python -m uvicorn backend.main:app --port 8001 --reload
```

Expected : démarrage propre, logs `[startup] Tables DB vérifiées`, `[scheduler] APScheduler démarré`. Arrêter avec Ctrl+C.

- [ ] **Step 3 : Commit**

```bash
git add backend/main.py
git commit -m "feat: main — lifespan simplifié + scan automatique au démarrage"
```

---

## Task 9 : Mise à jour des tests

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_models.py`
- Delete: `tests/test_migration.py`
- Rewrite: `tests/test_orders.py`

- [ ] **Step 1 : Mettre à jour conftest.py**

Remplacer **tout le contenu** de `tests/conftest.py` par :

```python
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
```

- [ ] **Step 2 : Mettre à jour tests/test_models.py**

Remplacer **tout le contenu** par :

```python
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
```

- [ ] **Step 3 : Supprimer tests/test_migration.py**

```bash
git rm tests/test_migration.py
```

- [ ] **Step 4 : Réécrire tests/test_orders.py**

Remplacer **tout le contenu** par :

```python
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
```

- [ ] **Step 5 : Lancer tous les tests**

```bash
pytest tests/ -v --ignore=tests/test_migration.py
```

Expected : tous PASS (les tests test_scan.py et test_claude_service.py devraient encore passer).

- [ ] **Step 6 : Commit**

```bash
git add tests/
git commit -m "test: adaptation tests post-migration Alpaca (supprime test_migration, adapte conftest + test_orders + test_models)"
```

---

## Task 10 : Script setup_startup.bat (raccourci Windows Startup)

**Files:**
- Create: `setup_startup.bat`

- [ ] **Step 1 : Créer setup_startup.bat à la racine du projet**

```bat
@echo off
echo ================================
echo   !nvest - Configuration Startup
echo ================================

set "PROJECT_DIR=%~dp0"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\nvest.lnk"

echo Création du raccourci dans : %STARTUP_DIR%

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $sc = $ws.CreateShortcut('%SHORTCUT_PATH%'); ^
   $sc.TargetPath = '%PROJECT_DIR%start.bat'; ^
   $sc.WorkingDirectory = '%PROJECT_DIR%'; ^
   $sc.WindowStyle = 7; ^
   $sc.Description = '!nvest Trading Dashboard'; ^
   $sc.Save()"

if exist "%SHORTCUT_PATH%" (
  echo.
  echo  Raccourci créé avec succes !
  echo  !nvest démarrera automatiquement à la prochaine connexion Windows.
  echo.
  echo  Pour supprimer : supprimer %SHORTCUT_PATH%
) else (
  echo.
  echo  ERREUR : Le raccourci n'a pas pu être créé.
  echo  Vérifiez les permissions PowerShell.
)

pause
```

- [ ] **Step 2 : Tester le script**

Double-cliquer sur `setup_startup.bat` ou lancer :

```bash
cmd /c setup_startup.bat
```

Expected : message "Raccourci créé avec succes !" et présence de `nvest.lnk` dans le dossier Startup.

- [ ] **Step 3 : Commit**

```bash
git add setup_startup.bat
git commit -m "feat: setup_startup.bat — raccourci Windows Startup pour démarrage automatique"
```

---

## Task 11 : Nettoyage — suppression des fichiers obsolètes

**Files:**
- Delete: `backend/scripts/migrate_json_to_pg.py`

- [ ] **Step 1 : Supprimer le script de migration JSON→PG**

```bash
git rm backend/scripts/migrate_json_to_pg.py
```

- [ ] **Step 2 : Vérifier que le backend démarre sans référence à ce fichier**

Vérifier `backend/main.py` — la référence à `migrate_json_to_pg` a été supprimée dans Task 8.

```bash
python -c "from backend.main import app; print('OK')"
```

Expected : `OK`

- [ ] **Step 3 : Lancer la suite de tests complète**

```bash
pytest tests/ -v
```

Expected : tous PASS (test_alpaca_service, test_models, test_orders, test_scan, test_claude_service).

- [ ] **Step 4 : Commit final**

```bash
git add -A
git commit -m "chore: supprime migrate_json_to_pg.py (plus nécessaire avec Alpaca)"
```

---

## Self-Review

**Couverture spec :**
- ✅ Démarrage Windows Startup → Task 10 (`setup_startup.bat`)
- ✅ Scan au démarrage (idempotent) → Task 8 (`_run_startup_scan` dans lifespan)
- ✅ Alpaca Paper comme source de vérité → Tasks 2-4 (`alpaca_service.py`)
- ✅ Capital depuis Alpaca `account.equity` → Task 6 (`_compute_metrics`)
- ✅ Dashboard inchangé → Task 6 (même contrat API)
- ✅ DB allégée (suppression orders/capital_history) → Task 5 (migration Alembic)
- ✅ Decision enrichie avec métadonnées ordre → Tasks 5+7
- ✅ ScanRun conservé → Tasks 5+7
- ✅ Tests adaptés → Task 9

**Cohérence types :**
- `Decision.id_ordre` = Alpaca order UUID (String 100) — cohérent Tasks 5, 6, 7
- `get_positions()` retourne `id_ordre = asset_id` puis enrichi via `decision.id_ordre` dans `orders.py` — Task 6
- `submit_bracket_order()` retourne `str(order.id)` — stocké dans `Decision.id_ordre` — Tasks 4, 7
