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

app.include_router(orders_router, prefix="/api")
app.include_router(prices.router, prefix="/api")
app.include_router(scan_router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health_check() -> dict:
    return {"status": "ok", "version": "2.0.0"}
