# Design — Intégration détection d'ordres dans le backend !nvest

**Date :** 2026-03-30
**Statut :** Approuvé
**Auteur :** Brainstorming session

---

## Contexte

Actuellement, la détection d'opportunités de trading repose sur l'exécution manuelle du prompt `prompt_trading_fictif.md` dans Claude. L'objectif est d'intégrer cette logique directement dans le backend FastAPI pour que l'utilisateur n'ait qu'à se connecter à l'application — le scan tourne automatiquement.

Changements majeurs :
- Persistance : JSON files → **PostgreSQL** (SQLAlchemy + Alembic)
- Détection d'ordres : prompt manuel → **scan automatique** (APScheduler + Claude API)
- Analyse contextuelle : WebSearch manuel → **Claude sonnet-4-6 avec tool `web_search`**

---

## Architecture

### Approche retenue : APScheduler intégré (sync)

APScheduler tourne dans le même process FastAPI via les `lifespan` events. Le scan est synchrone (yfinance → indicateurs → Claude API → PostgreSQL). Un endpoint `/api/scan/run` permet de forcer un scan à la demande.

**Justification :** usage solo, 1-2 scans/jour, scan ~2 min max. La simplicité l'emporte sur une architecture async ou un worker séparé (Celery).

### Structure des fichiers

```
backend/
├── main.py                      # FastAPI app + lifespan (APScheduler)
├── database.py                  # Engine SQLAlchemy, SessionLocal, Base
├── models.py                    # ORM : Order, Decision, CapitalHistory
├── requirements.txt
├── .env
├── routers/
│   ├── orders.py                # CRUD ordres (refactorisé → PostgreSQL)
│   ├── prices.py                # Historique yfinance (inchangé)
│   └── scan.py                  # POST /api/scan/run, GET /api/scan/status
├── services/
│   ├── price_service.py         # Inchangé
│   ├── scanner.py               # Indicateurs techniques yfinance + scoring
│   ├── claude_service.py        # Appel Claude API (web_search + analyse JSON)
│   └── scheduler.py             # APScheduler setup + job quotidien 9h Paris
├── scripts/
│   └── migrate_json_to_pg.py    # Migration one-shot JSON → PostgreSQL
└── migrations/
    └── alembic/                 # Gestion du schéma PostgreSQL
```

`data_loader.py` est supprimé — remplacé par la couche SQLAlchemy.

### Flux de données

```
APScheduler (9h) ou POST /api/scan/run
    → 1. Refresh des positions ouvertes (yfinance prix actuels)
         → Clôtures automatiques si TP/SL/expiration atteints
         → Mise à jour capital_history si clôtures déclenchées
    → 2. Scan nouveaux signaux
         → scanner.py : yfinance OHLCV 30j → RSI, MACD, Bollinger, EMA, Volume, ATR
         → Pour chaque candidat (score technique ≥ 30) :
             → claude_service.py : Claude sonnet-4-6 + web_search
                 → actualité, sentiment, bonus/malus, score final
         → Ordres retenus (score final ≥ 45) → INSERT en base (orders + decisions)
    → 3. INSERT scan_runs (résumé du scan : durée, nb ordres, erreurs)

Frontend → GET /api/orders/ → même interface, données depuis PostgreSQL
```

---

## Modèle de données PostgreSQL

### Table `orders`

Fusion de `portfolio["ordres"]` et `portfolio["ordres_cloturer"]`, discriminés par `statut`.

| Colonne | Type | Notes |
|---------|------|-------|
| id | SERIAL PK | |
| id_ordre | VARCHAR(20) UNIQUE | ORD-001, ORD-002… |
| actif | VARCHAR(20) | Ticker yfinance |
| classe | VARCHAR(20) | Action, Crypto, Forex, ETF |
| direction | VARCHAR(10) | ACHAT, VENTE |
| statut | VARCHAR(30) | OUVERT, CLOTURE_GAGNANT, CLOTURE_PERDANT, EXPIRE |
| prix_entree | FLOAT | |
| stop_loss | FLOAT | |
| take_profit | FLOAT | |
| prix_actuel | FLOAT | Mis à jour par /refresh |
| prix_sortie | FLOAT | Null si ouvert |
| ratio_rr | FLOAT | Calculé à la création |
| taille | FLOAT | Défaut 1000.0 € |
| quantite_fictive | FLOAT | taille / prix_entree |
| confiance | INT | Score /100 |
| raison | TEXT | Signal technique déclencheur |
| pnl_latent | FLOAT | Recalculé à chaque refresh |
| date_ouverture | TIMESTAMP | |
| date_expiration | DATE | J+5 ouvrés |
| date_cloture | DATE | Null si ouvert |
| created_at | TIMESTAMP | DEFAULT now() |

### Table `decisions`

Journal des décisions d'investissement, relation 1:1 avec `orders`.

| Colonne | Type | Notes |
|---------|------|-------|
| id | SERIAL PK | |
| id_ordre | VARCHAR(20) UNIQUE FK→orders | |
| signaux_techniques | TEXT | |
| contexte_actualite | TEXT | Résultat web_search Claude |
| sentiment_communaute | TEXT | HAUSSIER/NEUTRE/BAISSIER |
| risques_identifies | TEXT | |
| conclusion | TEXT | |
| score_confiance | INT | Score final /100 |
| detail_score | JSONB | 12 composantes du score |
| date_cloture | DATE | Null si ouvert |
| statut_final | VARCHAR(30) | Rempli à la clôture |
| pnl_euros | VARCHAR(20) | Ex: "+45.20" |
| commentaire_retour | TEXT | Analyse post-trade |
| created_at | TIMESTAMP | |

### Table `scan_runs`

Historique des exécutions du scan (automatiques + manuelles).

| Colonne | Type | Notes |
|---------|------|-------|
| id | SERIAL PK | |
| triggered_by | VARCHAR(20) | "scheduler" ou "manual" |
| started_at | TIMESTAMP | |
| finished_at | TIMESTAMP | Null si en cours |
| status | VARCHAR(20) | en_cours, termine, erreur |
| nb_candidats | INT | Actifs analysés techniquement |
| nb_ordres_generes | INT | Ordres effectivement insérés |
| nb_clotures | INT | Positions clôturées lors du refresh |
| erreur | TEXT | Message d'erreur si status=erreur |

### Table `capital_history`

Courbe d'évolution du capital fictif.

| Colonne | Type | Notes |
|---------|------|-------|
| id | SERIAL PK | |
| date | DATE | |
| capital | FLOAT | |
| note | TEXT | Ex: "Clôture ORD-012 PnL +45€" |
| created_at | TIMESTAMP | |

**Règles :**
- Les métriques (win_rate, profit_factor…) sont calculées à la volée, non stockées
- `capital_depart` (10 000 €) est une variable d'environnement `CAPITAL_DEPART`
- `detail_score` en JSONB pour garder la flexibilité des 12 composantes

---

## Intégration Claude API

### `claude_service.py`

Appel pour chaque candidat (score technique ≥ 30) :

```python
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=[{"type": "web_search", "name": "web_search"}],
    messages=[{
        "role": "user",
        "content": f"""
        Actif: {ticker} — Score technique brut: {score_technique}/100
        Indicateurs: RSI={rsi:.1f}, MACD={macd_signal}, prix={prix}€

        1. Recherche l'actualité récente sur {ticker}
        2. Recherche le sentiment investisseurs (Reddit, Twitter, analystes)
        3. Retourne UNIQUEMENT un JSON valide :
        {{
          "contexte_actualite": "...",
          "sentiment_communaute": "HAUSSIER|NEUTRE|BAISSIER|MITIGÉ",
          "risques_identifies": "...",
          "conclusion": "...",
          "bonus_malus": {{
            "bonus_actualite_positive": 0,
            "bonus_sentiment_haussier": 0,
            "bonus_aucune_actualite_negative": 0,
            "malus_evenement_macro": 0,
            "malus_actualite_negative": 0,
            "malus_resultats_proches": 0
          }},
          "score_final": {score_technique}
        }}
        """
    }]
)
```

- Timeout : 60s par appel
- Max 2 candidats → max ~2 min de scan
- Coût estimé : ~0.01–0.05$/scan
- En cas d'erreur Claude : score technique retenu sans ajustement (pas de blocage du scan)

### `scheduler.py`

```python
scheduler = BackgroundScheduler(timezone="Europe/Paris")
scheduler.add_job(
    run_daily_scan,
    trigger="cron",
    hour=9, minute=0,
    id="daily_scan",
    replace_existing=True,
    max_instances=1
)
```

Monté dans le `lifespan` FastAPI :
```python
@asynccontextmanager
async def lifespan(app):
    scheduler.start()
    yield
    scheduler.shutdown()
```

### Endpoints scan

| Méthode | URL | Description |
|---------|-----|-------------|
| POST | /api/scan/run | Lance un scan immédiatement, retourne `{"status": "started"}` |
| GET | /api/scan/status | État du dernier scan : en_cours / termine / erreur + résumé |
| GET | /api/scan/history | Historique des scans (date, nb_ordres_generés, durée) |

Le scan tourne dans un thread séparé (pas de blocage HTTP). Le client poll `/api/scan/status`.

---

## Tests

### Stratégie

PostgreSQL réelle (base `nvest_test` isolée) — pas de mock DB. Seul `claude_service` est mocké.

```
tests/
├── conftest.py              # DB test, client FastAPI, fixtures seed
├── test_models.py           # Contraintes ORM, FK, unicité id_ordre
├── test_orders.py           # CRUD : création, clôture, refresh prix
├── test_scan.py             # Indicateurs techniques sur OHLCV fixes
├── test_claude_service.py   # Claude mocké : parsing JSON, gestion erreurs
└── test_migration.py        # Migration JSON → PG : intégrité des données
```

- Chaque test démarre avec une transaction, rollback à la fin
- `test_scan.py` utilise des données OHLCV statiques (pas de yfinance réel)
- `test_claude_service.py` mock `anthropic.Anthropic` pour tester le parsing et la gestion d'erreurs sans appels réels

### Migration des données

Script one-shot `backend/scripts/migrate_json_to_pg.py` :
1. Lire `portfolio_fictif.json` → INSERT dans `orders` + `capital_history`
2. Lire `journal_decisions.json` → INSERT dans `decisions`
3. Vérifier les FK (chaque décision doit avoir un ordre)
4. Rapport : N ordres, N décisions, N entrées capital

Les JSON sont conservés comme backup, non supprimés.

---

## Alembic — gestion du schéma

```bash
alembic init backend/migrations
alembic revision --autogenerate -m "initial schema"
alembic upgrade head   # lancé automatiquement au démarrage (render.yaml)
```

`render.yaml` mis à jour pour exécuter `alembic upgrade head` en preDeployCommand.

---

## Variables d'environnement

| Variable | Valeur par défaut | Description |
|----------|-------------------|-------------|
| `DATABASE_URL` | postgresql://localhost/nvest | Connexion PostgreSQL |
| `ANTHROPIC_API_KEY` | — | Clé API Claude (obligatoire) |
| `FRONTEND_URL` | http://localhost:5173 | CORS |
| `SCAN_HOUR` | 9 | Heure du scan automatique (Paris) |
| `SCAN_MIN_CONFIDENCE` | 45 | Seuil minimum score final |
| `SCAN_MAX_SUGGESTIONS` | 2 | Nombre max d'ordres par scan |
| `CAPITAL_DEPART` | 10000 | Capital fictif de départ (€) |

---

## Ce qui ne change pas

- `routers/prices.py` — historique OHLCV inchangé
- Interface API `/api/orders/` — même contrat, même format de réponse
- Frontend React — aucune modification requise pour les fonctionnalités existantes
- Logique de calcul des métriques — recalculée à la volée depuis la DB
