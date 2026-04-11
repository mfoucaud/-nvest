"""
routers/orders.py — Endpoints CRUD pour les ordres fictifs (!nvest).
Persistance via PostgreSQL (SQLAlchemy) — remplace data_loader.py.

Endpoints:
    GET    /api/orders/              → Liste tous les ordres + métriques
    POST   /api/orders/              → Crée un nouvel ordre
    GET    /api/orders/{id}          → Détail ordre + décision
    PATCH  /api/orders/{id}/price    → Met à jour le prix actuel
    PATCH  /api/orders/{id}/close    → Clôture un ordre
    POST   /api/orders/refresh       → Rafraîchit tous les prix + clôtures auto
"""
from datetime import datetime, date, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Order, Decision, CapitalHistory

router = APIRouter(prefix="/orders", tags=["orders"])


# ---------------------------------------------------------------------------
# Modèles Pydantic
# ---------------------------------------------------------------------------

class DetailScore(BaseModel):
    rsi_survente: int = 0
    macd_croisement: int = 0
    bollinger_rebond: int = 0
    ema_tendance: int = 0
    volume_confirmation: int = 0
    support_horizontal: int = 0
    bonus_actualite_positive: int = 0
    bonus_sentiment_haussier: int = 0
    bonus_aucune_actualite_negative: int = 0
    malus_evenement_macro: int = 0
    malus_actualite_negative: int = 0
    malus_resultats_proches: int = 0


class DecisionIn(BaseModel):
    signaux_techniques: str = ""
    contexte_actualite: str = ""
    sentiment_communaute: str = ""
    risques_identifies: str = ""
    conclusion: str = ""
    detail_score: DetailScore = Field(default_factory=DetailScore)


class OrderIn(BaseModel):
    actif: str
    classe: Literal["Action", "Crypto", "Forex", "ETF"]
    direction: Literal["ACHAT", "VENTE"]
    prix_entree: float
    stop_loss: float
    take_profit: float
    taille: float = 1000.0
    confiance: int = Field(..., ge=0, le=100)
    raison: str = ""
    decision: Optional[DecisionIn] = None


class PriceUpdate(BaseModel):
    prix_actuel: float


class CloseOrder(BaseModel):
    statut: Literal["CLOTURE_GAGNANT", "CLOTURE_PERDANT", "EXPIRE"]
    prix_sortie: Optional[float] = None
    commentaire: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _business_days_later(start: date, days: int = 5) -> date:
    d = start
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def _next_order_id(db: Session) -> str:
    last = db.query(Order).order_by(Order.id.desc()).first()
    if last is None:
        return "ORD-001"
    try:
        n = int(last.id_ordre.split("-")[1])
        return f"ORD-{n + 1:03d}"
    except (IndexError, ValueError):
        return "ORD-001"


def _order_to_dict(order: Order) -> dict:
    return {
        "id_ordre": order.id_ordre,
        "date_ouverture": order.date_ouverture.strftime("%Y-%m-%d %H:%M") if order.date_ouverture else None,
        "actif": order.actif,
        "classe": order.classe,
        "direction": order.direction,
        "statut": order.statut,
        "prix_entree": order.prix_entree,
        "stop_loss": order.stop_loss,
        "take_profit": order.take_profit,
        "ratio_rr": order.ratio_rr,
        "taille": order.taille,
        "quantite_fictive": order.quantite_fictive,
        "confiance": order.confiance,
        "raison": order.raison,
        "pnl_latent": order.pnl_latent,
        "prix_actuel": order.prix_actuel,
        "prix_sortie": order.prix_sortie,
        "date_expiration": order.date_expiration.isoformat() if order.date_expiration else None,
        "date_cloture": order.date_cloture.isoformat() if order.date_cloture else None,
        "atr_utilise": order.atr_utilise,
        "alerte": order.alerte,
    }


def _decision_to_dict(decision: Decision) -> dict | None:
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


def _calc_metrics(db: Session) -> dict:
    import os
    capital_depart = float(os.getenv("CAPITAL_DEPART", "10000"))

    ouverts  = db.query(Order).filter(Order.statut == "OUVERT").all()
    clotures = db.query(Order).filter(Order.statut != "OUVERT").all()

    gagnants = [o for o in clotures if o.statut == "CLOTURE_GAGNANT"]
    perdants = [o for o in clotures if o.statut == "CLOTURE_PERDANT"]
    expires  = [o for o in clotures if o.statut == "EXPIRE"]
    nb_clos  = len(clotures)

    pnl_realise    = sum(o.pnl_latent or 0 for o in clotures)
    pnl_latent     = sum(o.pnl_latent or 0 for o in ouverts)
    capital_actuel = capital_depart + pnl_realise
    gains  = sum(o.pnl_latent or 0 for o in gagnants)
    pertes = abs(sum(o.pnl_latent or 0 for o in perdants))

    return {
        "win_rate":            round(len(gagnants) / nb_clos * 100, 1) if nb_clos else None,
        "pnl_total_eur":       round(pnl_realise, 2),
        "pnl_latent_eur":      round(pnl_latent, 2),
        "pnl_total_pct":       round(pnl_realise / capital_depart * 100, 2),
        "profit_factor":       round(gains / pertes, 2) if pertes > 0 else None,
        "nb_trades_total":     nb_clos + len(ouverts),
        "nb_trades_ouverts":   len(ouverts),
        "max_positions":       int(os.getenv("SCAN_MAX_POSITIONS", "20")),
        "nb_trades_gagnants":  len(gagnants),
        "nb_trades_perdants":  len(perdants),
        "nb_trades_expires":   len(expires),
        "meilleur_trade":      max((o.pnl_latent for o in clotures if o.pnl_latent), default=None),
        "pire_trade":          min((o.pnl_latent for o in clotures if o.pnl_latent), default=None),
        "capital_actuel":      round(capital_actuel, 2),
        "derniere_mise_a_jour": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/orders/
# ---------------------------------------------------------------------------

@router.get("/", summary="Liste tous les ordres + métriques")
def list_orders(db: Session = Depends(get_db)) -> dict:
    ouverts  = db.query(Order).filter(Order.statut == "OUVERT").all()
    cloturer = db.query(Order).filter(Order.statut != "OUVERT").all()
    capital  = db.query(CapitalHistory).order_by(CapitalHistory.date).all()

    return {
        "ouverts":            [_order_to_dict(o) for o in ouverts],
        "cloturer":           [_order_to_dict(o) for o in cloturer],
        "metriques":          _calc_metrics(db),
        "historique_capital": [
            {"date": h.date.isoformat(), "capital": h.capital, "note": h.note}
            for h in capital
        ],
    }


# ---------------------------------------------------------------------------
# POST /api/orders/
# ---------------------------------------------------------------------------

@router.post("/", status_code=201, summary="Crée un nouvel ordre fictif")
def create_order(body: OrderIn, db: Session = Depends(get_db)) -> dict:
    id_ordre = _next_order_id(db)
    now      = datetime.now()
    today    = date.today()
    expiry   = _business_days_later(today)

    prix = body.prix_entree
    sl   = body.stop_loss
    tp   = body.take_profit
    qty  = round(body.taille / prix, 4) if prix else 0
    rr   = round((tp - prix) / (prix - sl), 2) if (prix - sl) != 0 else None

    order = Order(
        id_ordre=id_ordre,
        date_ouverture=now,
        actif=body.actif,
        classe=body.classe,
        direction=body.direction,
        statut="OUVERT",
        prix_entree=prix,
        stop_loss=sl,
        take_profit=tp,
        ratio_rr=rr,
        taille=body.taille,
        quantite_fictive=qty,
        confiance=body.confiance,
        raison=body.raison,
        date_expiration=expiry,
        prix_actuel=prix,
        pnl_latent=0.0,
    )
    db.add(order)
    db.flush()

    if body.decision:
        d = body.decision
        decision = Decision(
            id_ordre=id_ordre,
            signaux_techniques=d.signaux_techniques,
            contexte_actualite=d.contexte_actualite,
            sentiment_communaute=d.sentiment_communaute,
            risques_identifies=d.risques_identifies,
            conclusion=d.conclusion,
            score_confiance=body.confiance,
            detail_score=d.detail_score.model_dump(),
        )
        db.add(decision)
        db.flush()

    return {"id_ordre": id_ordre, "ordre": _order_to_dict(order)}


# ---------------------------------------------------------------------------
# POST /api/orders/refresh  — doit être avant GET /{id_ordre} (route statique > dynamique)
# ---------------------------------------------------------------------------

@router.post("/refresh", summary="Rafraîchit tous les prix + clôtures automatiques")
def refresh_prices(db: Session = Depends(get_db)) -> dict:
    try:
        import yfinance as yf
    except ImportError:
        raise HTTPException(500, detail="yfinance non installé.")

    import os
    capital_depart = float(os.getenv("CAPITAL_DEPART", "10000"))
    today_str = date.today()
    updated = []
    closed  = []
    errors  = []

    ouverts = db.query(Order).filter(Order.statut == "OUVERT").all()

    for order in ouverts:
        try:
            hist = yf.Ticker(order.actif).history(period="2d", interval="1d")
            if hist.empty:
                raise ValueError("Pas de données")
            prix = round(float(hist["Close"].iloc[-1]), 4)
        except Exception as e:
            errors.append({"actif": order.actif, "erreur": str(e)})
            continue

        sl     = order.stop_loss
        tp     = order.take_profit
        expiry = order.date_expiration
        qty    = order.quantite_fictive or 0

        if prix <= sl:
            statut, exit_price = "CLOTURE_PERDANT", sl
        elif prix >= tp:
            statut, exit_price = "CLOTURE_GAGNANT", tp
        elif expiry and expiry <= today_str:
            statut, exit_price = "EXPIRE", prix
        else:
            statut, exit_price = "OUVERT", None

        pnl = round((prix - order.prix_entree) * qty, 2)

        if statut != "OUVERT":
            exit_pnl = round((exit_price - order.prix_entree) * qty, 2)
            order.statut       = statut
            order.prix_actuel  = exit_price
            order.prix_sortie  = exit_price
            order.pnl_latent   = exit_pnl
            order.date_cloture = today_str

            decision = db.query(Decision).filter(Decision.id_ordre == order.id_ordre).first()
            if decision and not decision.statut_final:
                decision.date_cloture       = today_str
                decision.statut_final       = statut
                decision.pnl_euros          = f"{exit_pnl:+.2f}"
                decision.commentaire_retour = f"Clôture automatique (prix={prix})."

            closed.append({"id_ordre": order.id_ordre, "actif": order.actif, "statut": statut, "pnl": exit_pnl})
        else:
            order.prix_actuel = prix
            order.pnl_latent  = pnl
            updated.append({"id_ordre": order.id_ordre, "actif": order.actif, "prix": prix, "pnl_latent": pnl})

    if closed:
        pnl_realise = sum(
            o.pnl_latent or 0
            for o in db.query(Order).filter(Order.statut != "OUVERT").all()
        )
        db.add(CapitalHistory(
            date=today_str,
            capital=round(capital_depart + pnl_realise, 2),
            note=f"Refresh auto: {len(closed)} cloture(s).",
        ))

    db.flush()

    return {
        "date":       today_str.isoformat(),
        "mis_a_jour": updated,
        "clotures":   closed,
        "erreurs":    errors,
        "metriques":  _calc_metrics(db),
    }


# ---------------------------------------------------------------------------
# GET /api/orders/{id_ordre}
# ---------------------------------------------------------------------------

@router.get("/{id_ordre}", summary="Détail d'un ordre fusionné avec sa décision")
def get_order(id_ordre: str, db: Session = Depends(get_db)) -> dict:
    order = db.query(Order).filter(Order.id_ordre == id_ordre).first()
    if order is None:
        raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")
    decision = db.query(Decision).filter(Decision.id_ordre == id_ordre).first()
    merged = _order_to_dict(order)
    merged["decision"] = _decision_to_dict(decision)
    return merged


# ---------------------------------------------------------------------------
# PATCH /api/orders/{id_ordre}/price
# ---------------------------------------------------------------------------

@router.patch("/{id_ordre}/price", summary="Met à jour le prix actuel d'un ordre ouvert")
def update_price(id_ordre: str, body: PriceUpdate, db: Session = Depends(get_db)) -> dict:
    order = db.query(Order).filter(Order.id_ordre == id_ordre).first()
    if order is None:
        raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")
    if order.statut != "OUVERT":
        raise HTTPException(409, detail=f"Ordre '{id_ordre}' déjà clôturé.")

    order.prix_actuel = body.prix_actuel
    order.pnl_latent  = round((body.prix_actuel - order.prix_entree) * (order.quantite_fictive or 0), 2)
    db.flush()
    return {"id_ordre": id_ordre, "prix_actuel": body.prix_actuel, "pnl_latent": order.pnl_latent}


# ---------------------------------------------------------------------------
# PATCH /api/orders/{id_ordre}/close
# ---------------------------------------------------------------------------

@router.patch("/{id_ordre}/close", summary="Clôture manuellement un ordre")
def close_order(id_ordre: str, body: CloseOrder, db: Session = Depends(get_db)) -> dict:
    order = db.query(Order).filter(Order.id_ordre == id_ordre).first()
    if order is None:
        raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")
    if order.statut != "OUVERT":
        raise HTTPException(409, detail=f"Ordre '{id_ordre}' déjà clôturé.")

    if body.prix_sortie is not None:
        exit_price = body.prix_sortie
    elif body.statut == "CLOTURE_PERDANT":
        exit_price = order.stop_loss
    elif body.statut == "CLOTURE_GAGNANT":
        exit_price = order.take_profit
    else:
        exit_price = order.prix_actuel or order.prix_entree

    pnl = round((exit_price - order.prix_entree) * (order.quantite_fictive or 0), 2)
    today_str = date.today()

    order.statut       = body.statut
    order.prix_actuel  = exit_price
    order.prix_sortie  = exit_price
    order.pnl_latent   = pnl
    order.date_cloture = today_str

    # Historique capital
    import os
    capital_depart = float(os.getenv("CAPITAL_DEPART", "10000"))
    pnl_realise = sum(
        o.pnl_latent or 0
        for o in db.query(Order).filter(Order.statut != "OUVERT").all()
    )
    capital_actuel = capital_depart + pnl_realise + pnl
    db.add(CapitalHistory(
        date=today_str,
        capital=round(capital_actuel, 2),
        note=f"Cloture {id_ordre} ({body.statut}) PnL {pnl:+.2f}EUR",
    ))

    # Mise à jour décision
    decision = db.query(Decision).filter(Decision.id_ordre == id_ordre).first()
    if decision:
        decision.date_cloture       = today_str
        decision.statut_final       = body.statut
        decision.pnl_euros          = f"{pnl:+.2f}"
        decision.commentaire_retour = body.commentaire or "Cloture manuelle via API."

    db.flush()
    return {"id_ordre": id_ordre, "statut": body.statut, "pnl": pnl, "exit_price": exit_price}
