"""
main.py — Point d'entrée de l'application FastAPI pour !nvest Trading Backend.

Lancement:
    uvicorn backend.main:app --reload --port 8000

    Depuis le dossier projet (parent de backend/) :
    cd C:/Users/micka/Desktop/project/!nvest
    uvicorn backend.main:app --reload --port 8000

Endpoints disponibles:
    GET    /api/health                  → Santé du serveur
    GET    /api/orders/                 → Liste des ordres + métriques
    POST   /api/orders/                 → Crée un nouvel ordre fictif
    GET    /api/orders/{id}             → Détail d'un ordre avec décision
    PATCH  /api/orders/{id}/price       → Met à jour le prix actuel
    PATCH  /api/orders/{id}/close       → Clôture manuellement un ordre
    POST   /api/orders/refresh          → Rafraîchit tous les prix + clôtures auto
    GET    /api/prices/{ticker}         → Historique OHLCV (query: ?days=10)

Documentation interactive:
    http://localhost:8000/docs     (Swagger UI)
    http://localhost:8000/redoc    (ReDoc)
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import orders, prices

# ---------------------------------------------------------------------------
# Initialisation de l'application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="!nvest Trading Backend",
    description=(
        "API REST pour l'application de trading fictif !nvest. "
        "Expose les ordres du portefeuille, les décisions du journal "
        "et les historiques de prix en temps réel via yfinance."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — autoriser le frontend Vite (port 5173)
# ---------------------------------------------------------------------------

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_url, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Inclusion des routers sous le prefix /api
# ---------------------------------------------------------------------------

app.include_router(orders.router, prefix="/api")
app.include_router(prices.router, prefix="/api")

# ---------------------------------------------------------------------------
# Routes de base
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["health"], summary="Vérification de l'état du serveur")
def health_check() -> dict:
    """
    Endpoint de santé — permet de vérifier que le serveur FastAPI est opérationnel.
    Utilisé par le frontend pour confirmer la disponibilité de l'API.
    """
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Événements de démarrage / arrêt
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup() -> None:
    print("=" * 60)
    print("  !nvest Trading Backend — Démarrage")
    print("=" * 60)
    print("  Serveur FastAPI opérationnel")
    print("  Documentation : http://localhost:8000/docs")
    print("  Health check  : http://localhost:8000/api/health")
    print("  Ordres        : http://localhost:8000/api/orders/")
    print("  Prix (ex.)    : http://localhost:8000/api/prices/NVDA?days=10")
    print("  CORS autorisé : http://localhost:5173")
    print("=" * 60)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    print("=" * 60)
    print("  !nvest Trading Backend — Arrêt du serveur")
    print("=" * 60)
