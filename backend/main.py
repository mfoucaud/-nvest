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
