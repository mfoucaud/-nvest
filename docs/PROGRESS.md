# !nvest — Avancement du chantier backend

**Chantier :** Intégration détection d'ordres + migration PostgreSQL
**Spec :** `docs/superpowers/specs/2026-03-30-order-detection-backend-design.md`
**Démarré :** 2026-03-30

---

## Objectif

Intégrer la logique de détection d'ordres directement dans le backend FastAPI :
- Migration persistance JSON → **PostgreSQL** (SQLAlchemy + Alembic)
- Scan automatique quotidien via **APScheduler** (9h Paris)
- Analyse contextuelle via **Claude sonnet-4-6 + web_search**
- Endpoint `/api/scan/run` pour scan on-demand

---

## Tâches

### Phase 1 — Design
- [x] Brainstorming + questions de cadrage
- [x] Design validé (architecture, DB, Claude API, tests)
- [x] Spec doc écrit et committé (`be587bd`)
- [x] Plan d'implémentation (writing-plans)

### Phase 2 — Base de données
- [x] `backend/database.py` — Engine SQLAlchemy, SessionLocal, Base
- [x] `backend/models.py` — ORM : Order, Decision, CapitalHistory, ScanRun
- [x] Alembic init + première migration (`initial schema`)
- [x] `backend/scripts/migrate_json_to_pg.py` — migration one-shot JSON → PG

### Phase 3 — Services
- [x] `backend/services/scanner.py` — indicateurs techniques (RSI, MACD, Bollinger, EMA, Volume, ATR)
- [x] `backend/services/claude_service.py` — appel Claude sonnet-4-6 + web_search + parsing JSON
- [x] `backend/services/scheduler.py` — APScheduler setup + job quotidien

### Phase 4 — Routers
- [x] `backend/routers/orders.py` — refactorisé pour PostgreSQL (remplace data_loader.py)
- [x] `backend/routers/scan.py` — POST /api/scan/run, GET /api/scan/status, GET /api/scan/history

### Phase 5 — Tests
- [x] `tests/conftest.py` — DB nvest_test, client FastAPI, fixtures
- [x] `tests/test_models.py` — contraintes ORM, FK, unicité
- [x] `tests/test_orders.py` — CRUD ordres
- [x] `tests/test_scan.py` — indicateurs techniques sur OHLCV statiques
- [x] `tests/test_claude_service.py` — Claude mocké, parsing, gestion erreurs
- [x] `tests/test_migration.py` — intégrité migration JSON → PG

### Phase 6 — Finalisation
- [x] `backend/requirements.txt` — ajout dépendances (sqlalchemy, alembic, apscheduler, anthropic, psycopg2)
- [x] `render.yaml` — preDeployCommand `alembic upgrade head`
- [x] `backend/main.py` — lifespan APScheduler
- [x] Code review final (`superpowers:requesting-code-review`)
- [x] Suppression `backend/services/data_loader.py`

---

## Décisions architecturales

| Sujet | Décision | Raison |
|-------|----------|--------|
| DB | PostgreSQL | Déploiement Render envisagé |
| Scheduler | APScheduler intégré (sync) | Usage solo, simplicité |
| Claude | sonnet-4-6 + web_search | Analyse actualité/sentiment |
| Tests DB | PostgreSQL réelle (nvest_test) | Pas de mock DB |
| Scan on-demand | Thread séparé + poll status | Pas de blocage HTTP |
