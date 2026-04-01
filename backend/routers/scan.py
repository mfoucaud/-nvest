"""
routers/scan.py — Endpoints pour le scan on-demand et le suivi des exécutions.

Endpoints:
    POST /api/scan/run      → Lance un scan immédiatement (thread séparé)
    GET  /api/scan/status   → État du dernier scan
    GET  /api/scan/history  → Historique des scans
"""
import threading

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ScanRun

router = APIRouter(prefix="/scan", tags=["scan"])

# Verrou pour éviter les scans simultanés lancés manuellement
_scan_lock = threading.Lock()


@router.post("/run", summary="Lance un scan immédiatement")
def run_scan_now(db: Session = Depends(get_db)) -> dict:
    """
    Lance un scan en arrière-plan (thread séparé).
    Retourne immédiatement {"status": "started"}.
    Si un scan est déjà en cours, retourne {"status": "already_running"}.
    """
    if not _scan_lock.acquire(blocking=False):
        return {"status": "already_running"}

    def _run():
        try:
            from backend.services.scheduler import run_daily_scan
            run_daily_scan(triggered_by="manual")
        finally:
            _scan_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started"}


@router.get("/status", summary="État du dernier scan")
def get_scan_status(db: Session = Depends(get_db)) -> dict:
    """Retourne le statut et le résumé du dernier scan exécuté."""
    last = db.query(ScanRun).order_by(ScanRun.id.desc()).first()
    if last is None:
        return {"status": "aucun_scan"}
    return {
        "id":                last.id,
        "status":            last.status,
        "triggered_by":      last.triggered_by,
        "started_at":        last.started_at.isoformat() if last.started_at else None,
        "finished_at":       last.finished_at.isoformat() if last.finished_at else None,
        "nb_candidats":      last.nb_candidats,
        "nb_ordres_generes": last.nb_ordres_generes,
        "nb_clotures":       last.nb_clotures,
        "erreur":            last.erreur,
    }


@router.get("/history", summary="Historique des scans")
def get_scan_history(db: Session = Depends(get_db), limit: int = 20) -> list:
    """Retourne les N derniers scans, du plus récent au plus ancien."""
    runs = db.query(ScanRun).order_by(ScanRun.id.desc()).limit(limit).all()
    return [
        {
            "id":                r.id,
            "status":            r.status,
            "triggered_by":      r.triggered_by,
            "started_at":        r.started_at.isoformat() if r.started_at else None,
            "finished_at":       r.finished_at.isoformat() if r.finished_at else None,
            "nb_ordres_generes": r.nb_ordres_generes,
            "nb_clotures":       r.nb_clotures,
        }
        for r in runs
    ]
