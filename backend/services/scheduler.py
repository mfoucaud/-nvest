"""
scheduler.py — APScheduler : scan quotidien à 14h30 (Europe/Paris).

Le scan complet :
  1. Scan nouveaux signaux (scanner.py → score technique)
  2. Enrichissement Claude (claude_service.py → score final)
  3. Soumission ordre bracket à Alpaca Paper + insertion Decision en DB
  4. Enregistrement du ScanRun en base
"""
import os
from datetime import datetime, date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import SessionLocal
from backend.models import Decision, ScanRun

SCAN_MIN_CONFIDENCE = int(os.getenv("SCAN_MIN_CONFIDENCE", "45"))
SCAN_MAX_SUGGESTIONS = int(os.getenv("SCAN_MAX_SUGGESTIONS", "2"))
SCAN_HOUR   = int(os.getenv("SCAN_HOUR",   "14"))
SCAN_MINUTE = int(os.getenv("SCAN_MINUTE", "30"))


def _business_days_later(start: date, days: int = 5) -> date:
    d = start
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def _submit_order_to_alpaca(candidate, enrichment: dict, db) -> str | None:
    """Soumet un ordre bracket à Alpaca et insère la Decision en DB. Retourne l'Alpaca order ID."""
    from backend.services.alpaca_service import submit_bracket_order

    prix = candidate.prix
    sl   = round(prix - 1.5 * candidate.atr, 4) if candidate.atr else round(prix * 0.93, 4)
    tp   = round(prix + 2.5 * candidate.atr, 4) if candidate.atr else round(prix * 1.15, 4)
    qty  = round(1000.0 / prix, 4) if prix else 0

    try:
        alpaca_order_id = submit_bracket_order(
            ticker=candidate.ticker,
            qty=qty,
            side=candidate.direction,
            tp=tp,
            sl=sl,
        )
    except Exception as e:
        print(f"[scheduler] Alpaca order failed for {candidate.ticker}: {e}")
        return None

    detail = dict(candidate.detail_score)
    detail.update(enrichment.get("bonus_malus", {}))

    today = date.today()
    decision = Decision(
        id_ordre=alpaca_order_id,
        actif=candidate.ticker,
        classe=candidate.classe,
        direction=candidate.direction,
        prix_entree=prix,
        stop_loss=sl,
        take_profit=tp,
        taille=1000.0,
        quantite=qty,
        raison=f"Scan auto — Score: {enrichment.get('score_final', candidate.score_technique)}/100",
        date_ouverture=datetime.now(),
        date_expiration=_business_days_later(today),
        signaux_techniques=f"RSI={candidate.rsi}, MACD={candidate.macd_signal}",
        contexte_actualite=enrichment.get("contexte_actualite", ""),
        sentiment_communaute=enrichment.get("sentiment_communaute", "NEUTRE"),
        risques_identifies=enrichment.get("risques_identifies", ""),
        conclusion=enrichment.get("conclusion", ""),
        score_confiance=enrichment.get("score_final", candidate.score_technique),
        detail_score=detail,
    )
    db.add(decision)
    return alpaca_order_id


def run_daily_scan(triggered_by: str = "scheduler") -> dict:
    """
    Scan complet : scan signaux → enrichissement Claude → soumission Alpaca → Decision en DB.
    Retourne un résumé.
    """
    from backend.services.scanner import scan_all
    from backend.services.claude_service import enrich_candidate

    db = SessionLocal()
    scan_run = ScanRun(started_at=datetime.now(), triggered_by=triggered_by)
    db.add(scan_run)
    db.flush()

    try:
        candidates = scan_all()
        scan_run.nb_candidats = len(candidates)

        ordres_generes = []
        for candidate in candidates[:SCAN_MAX_SUGGESTIONS * 2]:
            enrichment = enrich_candidate(candidate)
            score_final = enrichment.get("score_final", candidate.score_technique)
            if score_final >= SCAN_MIN_CONFIDENCE:
                alpaca_order_id = _submit_order_to_alpaca(candidate, enrichment, db)
                if alpaca_order_id:
                    ordres_generes.append(alpaca_order_id)
                    db.flush()
                if len(ordres_generes) >= SCAN_MAX_SUGGESTIONS:
                    break

        scan_run.nb_ordres_generes = len(ordres_generes)
        scan_run.nb_clotures       = 0
        scan_run.status            = "termine"
        scan_run.finished_at       = datetime.now()
        db.commit()

        return {
            "status": "termine",
            "nb_candidats": len(candidates),
            "nb_ordres_generes": len(ordres_generes),
            "nb_clotures": 0,
            "ordres_generes": ordres_generes,
        }

    except Exception as e:
        scan_run.status      = "erreur"
        scan_run.erreur      = str(e)
        scan_run.finished_at = datetime.now()
        db.commit()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# APScheduler
# ---------------------------------------------------------------------------

scheduler = BackgroundScheduler(timezone="Europe/Paris")
scheduler.add_job(
    run_daily_scan,
    trigger="cron",
    hour=SCAN_HOUR,
    minute=SCAN_MINUTE,
    id="daily_scan",
    replace_existing=True,
    max_instances=1,
    kwargs={"triggered_by": "scheduler"},
)
