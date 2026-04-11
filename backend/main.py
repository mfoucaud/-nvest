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


def _startup_refresh() -> None:
    """Au boot, clôture les ordres expirés/TP/SL sans attendre le scheduler."""
    from datetime import date
    from backend.database import SessionLocal
    from backend.models import Order
    try:
        db = SessionLocal()
        today = date.today()
        expired = db.query(Order).filter(
            Order.statut == "OUVERT",
            Order.date_expiration < today,
        ).count()
        db.close()
        if expired > 0:
            print(f"[startup] {expired} ordre(s) expiré(s) détecté(s) — refresh automatique")
            from backend.routers.orders import refresh_prices
            db2 = SessionLocal()
            try:
                refresh_prices(db=db2)
                db2.commit()
            finally:
                db2.close()
        else:
            print("[startup] Aucun ordre expiré — pas de refresh nécessaire")
    except Exception as e:
        print(f"[startup] Refresh échoué (non bloquant) : {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Démarre le scheduler au démarrage, l'arrête à la fermeture."""
    _startup_refresh()
    scheduler.start()
    print("[scheduler] APScheduler démarré — scan quotidien à 14h30 (Europe/Paris)")
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

app.include_router(orders.router, prefix="/api")
app.include_router(prices.router, prefix="/api")
app.include_router(scan_router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/debug/db", tags=["debug"])
def debug_db() -> dict:
    import os
    raw = os.getenv("DATABASE_URL", "NOT_SET")
    masked = raw[:30] + "..." if len(raw) > 30 else raw
    try:
        from backend.database import engine
        with engine.connect() as conn:
            from sqlalchemy import text
            result = conn.execute(text("SELECT 1")).fetchone()
            return {"db_url_prefix": masked, "connection": "ok", "result": str(result)}
    except Exception as e:
        return {"db_url_prefix": masked, "connection": "error", "error": str(e)}
