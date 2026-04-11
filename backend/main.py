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


def _fix_capital_history() -> None:
    """Recalcule et upsert l'entrée capital_history d'aujourd'hui depuis les ordres clôturés."""
    import os
    from datetime import date
    from backend.database import SessionLocal
    from backend.models import Order, CapitalHistory
    try:
        capital_depart = float(os.getenv("CAPITAL_DEPART", "10000"))
        db = SessionLocal()
        try:
            today = date.today()
            pnl_realise = sum(
                o.pnl_latent or 0
                for o in db.query(Order).filter(Order.statut != "OUVERT").all()
            )
            capital_correct = round(capital_depart + pnl_realise, 2)
            # Supprimer l'entrée incorrecte d'aujourd'hui si elle existe
            db.query(CapitalHistory).filter(CapitalHistory.date == today).delete()
            db.add(CapitalHistory(
                date=today,
                capital=capital_correct,
                note="Capital recalculé au démarrage",
            ))
            db.commit()
            print(f"[startup] Capital history corrigé : {capital_correct} €")
        finally:
            db.close()
    except Exception as e:
        print(f"[startup] _fix_capital_history échoué : {e}")


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
    # Créer les tables si elles n'existent pas (fallback si alembic a échoué)
    from backend.database import engine, Base
    import backend.models  # noqa: F401 — ensure all models are registered
    try:
        Base.metadata.create_all(bind=engine)
        print("[startup] Tables DB vérifiées/créées via create_all")
    except Exception as e:
        print(f"[startup] create_all échoué : {e}")

    # Migrer les données JSON → PG si nécessaire
    try:
        from backend.database import SessionLocal
        from backend.models import Order
        db = SessionLocal()
        count = db.query(Order).count()
        db.close()
        if count == 0:
            print("[startup] Table orders vide — migration JSON→PG")
            from backend.scripts.migrate_json_to_pg import migrate
            db2 = SessionLocal()
            try:
                migrate(db2, commit=True)
                print("[startup] Migration JSON→PG terminée")
            finally:
                db2.close()
    except Exception as e:
        print(f"[startup] Migration JSON→PG échouée : {e}")

    _startup_refresh()
    _fix_capital_history()
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


