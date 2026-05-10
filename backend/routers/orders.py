"""
routers/orders.py — Endpoints ordres lus depuis Alpaca Paper Trading.

Endpoints :
    GET  /api/orders/              → Positions + ordres clôturés + métriques (Alpaca + DB)
    POST /api/orders/refresh       → Identique à GET (fresh fetch Alpaca)
    GET  /api/orders/{id_ordre}    → Détail ordre + décision Claude
"""
import os
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Decision
from backend.services import alpaca_service

router = APIRouter(prefix="/orders", tags=["orders"])

CAPITAL_DEPART = float(os.getenv("CAPITAL_DEPART", "10000"))
SCAN_MAX_POSITIONS = int(os.getenv("SCAN_MAX_POSITIONS", "20"))


def _enrich_positions_from_db(positions: list[dict], db: Session) -> list[dict]:
    """Enrichit les positions ouvertes avec les données Decision (SL, TP, raison, etc.)."""
    for pos in positions:
        decision = (
            db.query(Decision)
            .filter(Decision.actif == pos["actif"], Decision.statut_final == None)  # noqa: E711
            .order_by(Decision.id.desc())
            .first()
        )
        if decision:
            pos["id_ordre"] = decision.id_ordre
            pos["stop_loss"] = decision.stop_loss
            pos["take_profit"] = decision.take_profit
            pos["confiance"] = decision.score_confiance
            pos["raison"] = decision.raison
            pos["taille"] = decision.taille
            pos["date_ouverture"] = decision.date_ouverture.isoformat() if decision.date_ouverture else None
            pos["date_expiration"] = decision.date_expiration.isoformat() if decision.date_expiration else None
            entry = pos["prix_entree"]
            sl = decision.stop_loss
            tp = decision.take_profit
            if sl and tp and (entry - sl) != 0:
                pos["ratio_rr"] = round((tp - entry) / (entry - sl), 2)
    return positions


def _enrich_closed_from_db(closed: list[dict], db: Session) -> list[dict]:
    """Enrichit les ordres clôturés avec les données Decision."""
    for order in closed:
        decision = (
            db.query(Decision)
            .filter(Decision.id_ordre == order["id_ordre"])
            .first()
        )
        if decision:
            order["stop_loss"] = decision.stop_loss
            order["take_profit"] = decision.take_profit
            order["confiance"] = decision.score_confiance
            order["raison"] = decision.raison
            order["taille"] = decision.taille
            order["quantite_fictive"] = decision.quantite
            order["date_ouverture"] = decision.date_ouverture.isoformat() if decision.date_ouverture else None
            order["date_expiration"] = decision.date_expiration.isoformat() if decision.date_expiration else None
            entry = decision.prix_entree
            qty = decision.quantite
            sortie = order.get("prix_sortie")
            if entry and qty and sortie:
                order["pnl_latent"] = round((sortie - entry) * qty, 2)
    return closed


def _compute_metrics(positions: list[dict], closed: list[dict], equity: float) -> dict:
    gagnants = [o for o in closed if o["statut"] == "CLOTURE_GAGNANT"]
    perdants = [o for o in closed if o["statut"] == "CLOTURE_PERDANT"]
    expires  = [o for o in closed if o["statut"] == "EXPIRE"]
    nb_clos  = len(closed)

    pnl_realise = sum(o["pnl_latent"] or 0 for o in closed if o["pnl_latent"] is not None)
    pnl_latent  = sum(p.get("pnl_latent") or 0 for p in positions)
    gains  = sum(o["pnl_latent"] or 0 for o in gagnants if o["pnl_latent"])
    pertes = abs(sum(o["pnl_latent"] or 0 for o in perdants if o["pnl_latent"]))

    return {
        "win_rate":            round(len(gagnants) / nb_clos * 100, 1) if nb_clos else None,
        "pnl_total_eur":       round(pnl_realise, 2),
        "pnl_latent_eur":      round(pnl_latent, 2),
        "pnl_total_pct":       round(pnl_realise / CAPITAL_DEPART * 100, 2),
        "profit_factor":       round(gains / pertes, 2) if pertes > 0 else None,
        "nb_trades_total":     nb_clos + len(positions),
        "nb_trades_ouverts":   len(positions),
        "max_positions":       SCAN_MAX_POSITIONS,
        "nb_trades_gagnants":  len(gagnants),
        "nb_trades_perdants":  len(perdants),
        "nb_trades_expires":   len(expires),
        "meilleur_trade":      max((o["pnl_latent"] for o in closed if o["pnl_latent"]), default=None),
        "pire_trade":          min((o["pnl_latent"] for o in closed if o["pnl_latent"]), default=None),
        "capital_actuel":      round(equity, 2),
        "derniere_mise_a_jour": date.today().isoformat(),
    }


def _decision_to_dict(decision: Decision | None) -> dict | None:
    if decision is None:
        return None
    cloture = None
    if decision.statut_final:
        cloture = {
            "date_cloture": decision.date_cloture.isoformat() if decision.date_cloture else None,
            "statut_final": decision.statut_final,
            "pnl_euros": decision.pnl_euros,
            "commentaire_retour": decision.commentaire_retour,
        }
    return {
        "id_ordre": decision.id_ordre,
        "signaux_techniques": decision.signaux_techniques,
        "contexte_actualite": decision.contexte_actualite,
        "sentiment_communaute": decision.sentiment_communaute,
        "risques_identifies": decision.risques_identifies,
        "conclusion": decision.conclusion,
        "score_confiance": decision.score_confiance,
        "detail_score": decision.detail_score,
        "cloture": cloture,
    }


def _build_full_response(db: Session) -> dict:
    positions = _enrich_positions_from_db(alpaca_service.get_positions(), db)
    closed    = _enrich_closed_from_db(alpaca_service.get_closed_orders(), db)
    account   = alpaca_service.get_account()
    history   = alpaca_service.get_portfolio_history()

    return {
        "ouverts":            positions,
        "cloturer":           closed,
        "metriques":          _compute_metrics(positions, closed, account["equity"]),
        "historique_capital": history,
    }


@router.get("/", summary="Positions + ordres clôturés depuis Alpaca")
def list_orders(db: Session = Depends(get_db)) -> dict:
    return _build_full_response(db)


@router.post("/refresh", summary="Rafraîchit depuis Alpaca (même réponse que GET /)")
def refresh_orders(db: Session = Depends(get_db)) -> dict:
    return _build_full_response(db)


@router.get("/{id_ordre}", summary="Détail d'un ordre + décision Claude")
def get_order(id_ordre: str, db: Session = Depends(get_db)) -> dict:
    decision = db.query(Decision).filter(Decision.id_ordre == id_ordre).first()

    # Chercher dans les positions ouvertes
    try:
        positions = _enrich_positions_from_db(alpaca_service.get_positions(), db)
        for pos in positions:
            if pos.get("id_ordre") == id_ordre or pos.get("actif") == id_ordre:
                pos["decision"] = _decision_to_dict(decision)
                return pos
    except Exception as e:
        print(f"[orders] get_positions failed for {id_ordre}: {e}")

    # Chercher dans les ordres clôturés
    try:
        closed = _enrich_closed_from_db(alpaca_service.get_closed_orders(limit=100), db)
        for order in closed:
            if order["id_ordre"] == id_ordre:
                order["decision"] = _decision_to_dict(decision)
                return order
    except Exception as e:
        print(f"[orders] get_closed_orders failed for {id_ordre}: {e}")

    if decision:
        return {
            "id_ordre": decision.id_ordre,
            "actif": decision.actif,
            "classe": decision.classe,
            "direction": decision.direction,
            "statut": "INCONNU",
            "prix_entree": decision.prix_entree,
            "stop_loss": decision.stop_loss,
            "take_profit": decision.take_profit,
            "confiance": decision.score_confiance,
            "raison": decision.raison,
            "decision": _decision_to_dict(decision),
        }

    raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")
