"""
scheduler.py — APScheduler : scan quotidien automatique à 9h (Europe/Paris).

Le scan complet :
  1. Refresh des positions ouvertes (prix yfinance + clôtures auto)
  2. Scan nouveaux signaux (scanner.py → score technique)
  3. Enrichissement Claude (claude_service.py → score final)
  4. Insertion des ordres retenus (score final ≥ SCAN_MIN_CONFIDENCE)
  5. Enregistrement du ScanRun en base
"""
import os
from datetime import datetime, date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import SessionLocal
from backend.models import Order, Decision, CapitalHistory, ScanRun

SCAN_MIN_CONFIDENCE = int(os.getenv("SCAN_MIN_CONFIDENCE", "45"))
SCAN_MAX_SUGGESTIONS = int(os.getenv("SCAN_MAX_SUGGESTIONS", "2"))
SCAN_HOUR = int(os.getenv("SCAN_HOUR", "9"))
CAPITAL_DEPART = float(os.getenv("CAPITAL_DEPART", "10000"))


def _business_days_later(start: date, days: int = 5) -> date:
    d = start
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def _next_order_id(db) -> str:
    last = db.query(Order).order_by(Order.id.desc()).first()
    if last is None:
        return "ORD-001"
    try:
        n = int(last.id_ordre.split("-")[1])
        return f"ORD-{n + 1:03d}"
    except (IndexError, ValueError):
        return "ORD-001"


def _refresh_open_orders(db) -> int:
    """Rafraîchit les prix des ordres ouverts et clôture ceux qui ont atteint TP/SL/expiry."""
    import yfinance as yf
    today = date.today()
    nb_closed = 0

    for order in db.query(Order).filter(Order.statut == "OUVERT").all():
        try:
            hist = yf.Ticker(order.actif).history(period="2d", interval="1d")
            if hist.empty:
                continue
            prix = round(float(hist["Close"].iloc[-1]), 4)
        except Exception:
            continue

        qty = order.quantite_fictive or 0
        if prix <= order.stop_loss:
            statut, exit_price = "CLOTURE_PERDANT", order.stop_loss
        elif prix >= order.take_profit:
            statut, exit_price = "CLOTURE_GAGNANT", order.take_profit
        elif order.date_expiration and order.date_expiration <= today:
            statut, exit_price = "EXPIRE", prix
        else:
            order.prix_actuel = prix
            order.pnl_latent  = round((prix - order.prix_entree) * qty, 2)
            continue

        exit_pnl = round((exit_price - order.prix_entree) * qty, 2)
        order.statut       = statut
        order.prix_actuel  = exit_price
        order.prix_sortie  = exit_price
        order.pnl_latent   = exit_pnl
        order.date_cloture = today

        decision = db.query(Decision).filter(Decision.id_ordre == order.id_ordre).first()
        if decision and not decision.statut_final:
            decision.date_cloture     = today
            decision.statut_final     = statut
            decision.pnl_euros        = f"{exit_pnl:+.2f}"
            decision.commentaire_retour = f"Clôture automatique scan (prix={prix})."

        nb_closed += 1

    return nb_closed


def _insert_order_from_candidate(db, candidate, enrichment: dict) -> str:
    """Insère un ordre + décision depuis un candidat enrichi. Retourne l'id_ordre."""
    id_ordre = _next_order_id(db)
    now      = datetime.now()
    today    = date.today()
    expiry   = _business_days_later(today)

    prix  = candidate.prix
    sl    = round(prix - 1.5 * candidate.atr, 4) if candidate.atr else candidate.prix * 0.93
    tp    = round(prix + 2.5 * candidate.atr, 4) if candidate.atr else candidate.prix * 1.15
    qty   = round(1000.0 / prix, 4) if prix else 0
    rr    = round((tp - prix) / (prix - sl), 2) if (prix - sl) != 0 else None

    # Fusionner detail_score technique + bonus_malus Claude
    detail = dict(candidate.detail_score)
    detail.update(enrichment.get("bonus_malus", {}))

    order = Order(
        id_ordre=id_ordre,
        date_ouverture=now,
        actif=candidate.ticker,
        classe=candidate.classe,
        direction=candidate.direction,
        statut="OUVERT",
        prix_entree=prix,
        stop_loss=sl,
        take_profit=tp,
        ratio_rr=rr,
        taille=1000.0,
        quantite_fictive=qty,
        confiance=enrichment.get("score_final", candidate.score_technique),
        raison=f"Scan auto — Score: {enrichment.get('score_final', candidate.score_technique)}/100",
        atr_utilise=candidate.atr,
        date_expiration=expiry,
        prix_actuel=prix,
        pnl_latent=0.0,
    )
    db.add(order)
    db.flush()

    decision = Decision(
        id_ordre=id_ordre,
        signaux_techniques=f"RSI={candidate.rsi}, MACD={candidate.macd_signal}",
        contexte_actualite=enrichment.get("contexte_actualite", ""),
        sentiment_communaute=enrichment.get("sentiment_communaute", "NEUTRE"),
        risques_identifies=enrichment.get("risques_identifies", ""),
        conclusion=enrichment.get("conclusion", ""),
        score_confiance=enrichment.get("score_final", candidate.score_technique),
        detail_score=detail,
    )
    db.add(decision)
    return id_ordre


def run_daily_scan(triggered_by: str = "scheduler") -> dict:
    """
    Scan complet : refresh → scan → enrichissement Claude → insertion ordres.
    Retourne un résumé du scan.
    """
    from backend.services.scanner import scan_all
    from backend.services.claude_service import enrich_candidate

    db = SessionLocal()
    scan_run = ScanRun(started_at=datetime.now(), triggered_by=triggered_by)
    db.add(scan_run)
    db.flush()
    scan_id = scan_run.id

    try:
        # 1. Refresh positions ouvertes
        nb_clotures = _refresh_open_orders(db)
        db.flush()

        # 2. Scan nouveaux signaux
        candidates = scan_all()
        scan_run.nb_candidats = len(candidates)

        # 3. Appliquer le max positions ouvertes (20)
        nb_ouverts = db.query(Order).filter(Order.statut == "OUVERT").count()
        if nb_ouverts >= 20:
            scan_run.status      = "termine"
            scan_run.finished_at = datetime.now()
            scan_run.nb_clotures = nb_clotures
            db.commit()
            return {"status": "termine", "raison": "max_positions_atteint", "nb_candidats": len(candidates)}

        # 4. Enrichir + filtrer les meilleurs candidats
        ordres_generes = []
        for candidate in candidates[:SCAN_MAX_SUGGESTIONS * 2]:  # pool élargi
            enrichment = enrich_candidate(candidate)
            score_final = enrichment.get("score_final", candidate.score_technique)
            if score_final >= SCAN_MIN_CONFIDENCE:
                id_ordre = _insert_order_from_candidate(db, candidate, enrichment)
                ordres_generes.append(id_ordre)
                if len(ordres_generes) >= SCAN_MAX_SUGGESTIONS:
                    break

        scan_run.nb_ordres_generes = len(ordres_generes)
        scan_run.nb_clotures       = nb_clotures
        scan_run.status            = "termine"
        scan_run.finished_at       = datetime.now()

        # 5. Historique capital si clôtures
        if nb_clotures > 0:
            pnl_realise = sum(
                o.pnl_latent or 0
                for o in db.query(Order).filter(Order.statut != "OUVERT").all()
            )
            db.add(CapitalHistory(
                date=date.today(),
                capital=round(CAPITAL_DEPART + pnl_realise, 2),
                note=f"Scan auto: {nb_clotures} cloture(s), {len(ordres_generes)} nouvel(s) ordre(s).",
            ))

        db.commit()
        return {
            "status": "termine",
            "nb_candidats": len(candidates),
            "nb_ordres_generes": len(ordres_generes),
            "nb_clotures": nb_clotures,
            "ordres_generes": ordres_generes,
        }

    except Exception as e:
        scan_run.status  = "erreur"
        scan_run.erreur  = str(e)
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
    minute=0,
    id="daily_scan",
    replace_existing=True,
    max_instances=1,
    kwargs={"triggered_by": "scheduler"},
)
