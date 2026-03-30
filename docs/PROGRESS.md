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
- [ ] Plan d'implémentation (writing-plans)

### Phase 2 — Base de données
- [ ] `backend/database.py` — Engine SQLAlchemy, SessionLocal, Base
- [ ] `backend/models.py` — ORM : Order, Decision, CapitalHistory, ScanRun
- [ ] Alembic init + première migration (`initial schema`)
- [ ] `backend/scripts/migrate_json_to_pg.py` — migration one-shot JSON → PG

### Phase 3 — Services
- [ ] `backend/services/scanner.py` — indicateurs techniques (RSI, MACD, Bollinger, EMA, Volume, ATR)
- [ ] `backend/services/claude_service.py` — appel Claude sonnet-4-6 + web_search + parsing JSON
- [ ] `backend/services/scheduler.py` — APScheduler setup + job quotidien

### Phase 4 — Routers
- [ ] `backend/routers/orders.py` — refactorisé pour PostgreSQL (remplace data_loader.py)
- [ ] `backend/routers/scan.py` — POST /api/scan/run, GET /api/scan/status, GET /api/scan/history

### Phase 5 — Tests
- [ ] `tests/conftest.py` — DB nvest_test, client FastAPI, fixtures
- [ ] `tests/test_models.py` — contraintes ORM, FK, unicité
- [ ] `tests/test_orders.py` — CRUD ordres
- [ ] `tests/test_scan.py` — indicateurs techniques sur OHLCV statiques
- [ ] `tests/test_claude_service.py` — Claude mocké, parsing, gestion erreurs
- [ ] `tests/test_migration.py` — intégrité migration JSON → PG

### Phase 6 — Finalisation
- [ ] `backend/requirements.txt` — ajout dépendances (sqlalchemy, alembic, apscheduler, anthropic, psycopg2)
- [ ] `render.yaml` — preDeployCommand `alembic upgrade head`
- [ ] `backend/main.py` — lifespan APScheduler
- [ ] Code review final (`superpowers:requesting-code-review`)
- [ ] Suppression `backend/services/data_loader.py`

---

## Décisions architecturales

| Sujet | Décision | Raison |
|-------|----------|--------|
| DB | PostgreSQL | Déploiement Render envisagé |
| Scheduler | APScheduler intégré (sync) | Usage solo, simplicité |
| Claude | sonnet-4-6 + web_search | Analyse actualité/sentiment |
| Tests DB | PostgreSQL réelle (nvest_test) | Pas de mock DB |
| Scan on-demand | Thread séparé + poll status | Pas de blocage HTTP |
