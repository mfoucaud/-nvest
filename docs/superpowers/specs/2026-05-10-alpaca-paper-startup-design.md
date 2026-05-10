# Design : Alpaca Paper Trading + Démarrage automatique

**Date :** 2026-05-10  
**Statut :** Validé

---

## Objectif

1. Au démarrage du PC (Windows), lancer automatiquement la détection d'ordres et ouvrir le dashboard.
2. Les ordres générés par le scan sont soumis à Alpaca Paper Trading (et non insérés en DB locale).
3. Le dashboard affiche les données Alpaca (positions, ordres clôturés, equity, courbe capital).

---

## Section 1 — Démarrage automatique Windows

### Mécanisme

- Un raccourci dans `shell:startup` pointe vers `start.bat` existant.
- `start.bat` lance : backend FastAPI (port 8000) + frontend React (port 5173) + ouvre le navigateur.
- Un script one-shot `setup_startup.bat` crée ce raccourci via PowerShell.

### Scan au démarrage

- Dans `backend/main.py`, le lifespan FastAPI démarre un thread en arrière-plan.
- Ce thread attend 10 secondes (temps que le serveur soit prêt), puis appelle `run_daily_scan(triggered_by="startup")`.
- Si un scan a déjà été effectué aujourd'hui (`ScanRun` en DB), le scan au démarrage est ignoré (idempotent).

---

## Section 2 — Alpaca Paper Service

### Fichier : `backend/services/alpaca_service.py`

SDK : `alpaca-py` (`pip install alpaca-py`).

Variables d'environnement (depuis `.env`) :
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`
- `ALPACA_BASE_URL=https://paper-api.alpaca.markets`

### Fonctions exposées

| Fonction | Description |
|---|---|
| `get_account()` | Retourne equity, buying_power, currency |
| `submit_bracket_order(ticker, qty, side, tp, sl)` | Soumet un ordre bracket avec TP/SL |
| `get_positions()` | Liste des positions ouvertes (format unifié dashboard) |
| `get_closed_orders(limit=50)` | Ordres clôturés/remplis (format unifié dashboard) |
| `get_portfolio_history()` | Série temporelle equity (pour CapitalChart) |

### Format unifié

Les fonctions retournent des dicts compatibles avec le format actuel du frontend (mêmes clés que les endpoints existants) pour éviter tout changement côté React.

---

## Section 3 — Refactoring backend

### `backend/services/scheduler.py`

- Suppression de `_refresh_open_orders()` — Alpaca gère l'état des ordres.
- Suppression de `_insert_order_from_candidate()` — remplacé par `alpaca_service.submit_bracket_order()`.
- L'insertion de `Decision` en DB est conservée (contexte Claude enrichi).
- `_next_order_id()` supprimé (Alpaca génère ses propres IDs).
- Le résumé du `ScanRun` intègre les IDs Alpaca des ordres soumis.

### `backend/routers/orders.py`

- Tous les endpoints remplacés pour lire depuis `alpaca_service`.
- Endpoint principal `GET /api/orders/` retourne :
  ```json
  {
    "metriques": { "capital_actuel": ..., "pnl_total": ..., ... },
    "ouverts": [...],
    "cloturer": [...],
    "historique_capital": [...]
  }
  ```
- Même contrat qu'aujourd'hui → frontend inchangé.

### `backend/models.py`

- Suppression des classes `Order` et `CapitalHistory`.
- Conservation de `Decision` et `ScanRun`.

### `backend/main.py`

- Ajout dans le lifespan : thread de démarrage qui attend 10s puis appelle `run_daily_scan()`.
- Vérification d'idempotence : si un `ScanRun` existe pour aujourd'hui avec `status="termine"`, le scan est ignoré.

### Fichiers inchangés

- `frontend/` — aucun changement (contrat API préservé)
- `routers/scan.py` — inchangé
- `routers/prices.py` — inchangé
- `services/scanner.py` — inchangé
- `services/claude_service.py` — inchangé

---

## Section 4 — Setup one-shot

### `setup_startup.bat`

Script à lancer une seule fois, crée le raccourci dans `shell:startup` :

```powershell
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\nvest.lnk")
$Shortcut.TargetPath = "<chemin_absolu>\start.bat"
$Shortcut.WorkingDirectory = "<chemin_absolu>"
$Shortcut.Save()
```

---

## Migration

- Alembic : migration pour supprimer les tables `orders` et `capital_history`.
- Les données existantes en DB ne sont pas migrées vers Alpaca (compte paper vierge à $10 000).
- `requirements.txt` : ajout de `alpaca-py`.

---

## Périmètre hors-scope

- Authentification Alpaca OAuth (clés statiques suffisent)
- Alpaca Broker API (on utilise Trading API Paper seulement)
- Gestion des fractional shares
- Notifications (Slack, email) sur ordre exécuté
