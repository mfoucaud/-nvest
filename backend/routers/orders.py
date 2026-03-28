"""
routers/orders.py — Endpoints pour la gestion des ordres du portefeuille fictif.

Prefix: /orders (monté sous /api dans main.py → URLs finales: /api/orders/...)

Endpoints:
    GET    /api/orders/              → Liste tous les ordres + métriques
    POST   /api/orders/              → Crée un nouvel ordre fictif
    GET    /api/orders/{id}          → Détail d'un ordre fusionné avec sa décision
    PATCH  /api/orders/{id}/price    → Met à jour le prix actuel d'un ordre ouvert
    PATCH  /api/orders/{id}/close    → Clôture manuellement un ordre
    POST   /api/orders/refresh       → Rafraîchit tous les prix + clôtures automatiques
"""

from datetime import datetime, date, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.data_loader import (
    load_portfolio,
    load_journal,
    save_portfolio,
    save_journal,
    get_merged_order,
    next_order_id,
)

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
    prix_sortie: Optional[float] = None   # si None → utilise le SL/TP/prix actuel selon statut
    commentaire: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _business_days_later(start: date, days: int = 5) -> str:
    """Retourne la date d'expiration en jours ouvrés."""
    d = start
    added = 0
    while added < days:
        d += timedelta(days=1)
        if d.weekday() < 5:  # lundi-vendredi
            added += 1
    return d.isoformat()


def _recalc_metrics(portfolio: dict) -> None:
    """Recalcule les métriques à partir des ordres en place."""
    ouverts  = portfolio.get("ordres", []) or []
    clotures = portfolio.get("ordres_cloturer", []) or []

    gagnants = [o for o in clotures if o["statut"] == "CLOTURE_GAGNANT"]
    perdants = [o for o in clotures if o["statut"] == "CLOTURE_PERDANT"]
    expires  = [o for o in clotures if o["statut"] == "EXPIRE"]
    nb_clos  = len(clotures)

    pnl_realise    = sum(o.get("pnl_latent", 0) for o in clotures)
    pnl_latent     = sum(o.get("pnl_latent", 0) for o in ouverts)
    capital_actuel = portfolio["capital_depart"] + pnl_realise

    gains  = sum(o.get("pnl_latent", 0) for o in gagnants)
    pertes = abs(sum(o.get("pnl_latent", 0) for o in perdants))

    portfolio["metriques"] = {
        "win_rate":            round(len(gagnants) / nb_clos * 100, 1) if nb_clos else None,
        "pnl_total_eur":       round(pnl_realise, 2),
        "pnl_latent_eur":      round(pnl_latent, 2),
        "pnl_total_pct":       round(pnl_realise / portfolio["capital_depart"] * 100, 2),
        "profit_factor":       round(gains / pertes, 2) if pertes > 0 else None,
        "nb_trades_total":     nb_clos + len(ouverts),
        "nb_trades_ouverts":   len(ouverts),
        "nb_trades_gagnants":  len(gagnants),
        "nb_trades_perdants":  len(perdants),
        "nb_trades_expires":   len(expires),
        "meilleur_trade":      max((o["pnl_latent"] for o in clotures), default=None),
        "pire_trade":          min((o["pnl_latent"] for o in clotures), default=None),
        "capital_actuel":      round(capital_actuel, 2),
        "derniere_mise_a_jour": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /api/orders/
# ---------------------------------------------------------------------------

@router.get("/", summary="Liste tous les ordres + métriques")
def list_orders() -> dict:
    portfolio = load_portfolio()
    return {
        "ouverts":            portfolio.get("ordres", []) or [],
        "cloturer":           portfolio.get("ordres_cloturer", []) or [],
        "metriques":          portfolio.get("metriques", {}) or {},
        "historique_capital": portfolio.get("historique_capital", []) or [],
    }


# ---------------------------------------------------------------------------
# POST /api/orders/
# ---------------------------------------------------------------------------

@router.post("/", status_code=201, summary="Crée un nouvel ordre fictif")
def create_order(body: OrderIn) -> dict:
    """
    Crée un ordre dans portfolio_fictif.json et, si une `decision` est fournie,
    l'enregistre dans journal_decisions.json.

    Le ratio RR et la quantité fictive sont calculés automatiquement.
    L'ID et la date d'expiration (J+5 ouvrés) sont générés côté serveur.
    """
    portfolio = load_portfolio()
    journal   = load_journal()

    id_ordre  = next_order_id()
    now       = datetime.now().strftime("%Y-%m-%d %H:%M")
    today     = date.today()
    expiry    = _business_days_later(today)

    prix  = body.prix_entree
    sl    = body.stop_loss
    tp    = body.take_profit
    qty   = round(body.taille / prix, 4) if prix else 0
    rr    = round((tp - prix) / (prix - sl), 2) if (prix - sl) != 0 else None

    ordre = {
        "id_ordre":         id_ordre,
        "date_ouverture":   now,
        "actif":            body.actif,
        "classe":           body.classe,
        "direction":        body.direction,
        "prix_entree":      prix,
        "stop_loss":        sl,
        "take_profit":      tp,
        "ratio_rr":         rr,
        "taille":           body.taille,
        "quantite_fictive": qty,
        "confiance":        body.confiance,
        "statut":           "OUVERT",
        "raison":           body.raison,
        "date_expiration":  expiry,
        "prix_actuel":      prix,
        "pnl_latent":       0.0,
    }

    portfolio.setdefault("ordres", []).append(ordre)
    _recalc_metrics(portfolio)
    save_portfolio(portfolio)

    # Journal de décision
    if body.decision:
        d = body.decision
        journal.setdefault("decisions", []).append({
            "id_ordre":              id_ordre,
            "date":                  now,
            "actif":                 body.actif,
            "direction":             body.direction,
            "prix_entree":           prix,
            "stop_loss":             sl,
            "take_profit":           tp,
            "taille":                body.taille,
            "score_confiance":       body.confiance,
            "detail_score":          d.detail_score.model_dump(),
            "signaux_techniques":    d.signaux_techniques,
            "contexte_actualite":    d.contexte_actualite,
            "sentiment_communaute":  d.sentiment_communaute,
            "risques_identifies":    d.risques_identifies,
            "conclusion":            d.conclusion,
            "cloture":               None,
        })
        save_journal(journal)

    return {"id_ordre": id_ordre, "ordre": ordre}


# ---------------------------------------------------------------------------
# GET /api/orders/{id_ordre}
# ---------------------------------------------------------------------------

@router.get("/{id_ordre}", summary="Détail d'un ordre fusionné avec sa décision")
def get_order(id_ordre: str) -> dict:
    merged = get_merged_order(id_ordre)
    if merged is None:
        raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")
    return merged


# ---------------------------------------------------------------------------
# PATCH /api/orders/{id_ordre}/price
# ---------------------------------------------------------------------------

@router.patch("/{id_ordre}/price", summary="Met à jour le prix actuel d'un ordre ouvert")
def update_price(id_ordre: str, body: PriceUpdate) -> dict:
    """
    Met à jour `prix_actuel` et recalcule `pnl_latent`.
    Ne modifie pas le statut — utilisez `/close` pour clôturer.
    Retourne 404 si l'ordre est inconnu, 409 s'il est déjà clôturé.
    """
    portfolio = load_portfolio()
    ouverts   = portfolio.get("ordres", []) or []

    for ordre in ouverts:
        if ordre["id_ordre"] == id_ordre:
            ordre["prix_actuel"] = body.prix_actuel
            ordre["pnl_latent"]  = round(
                (body.prix_actuel - ordre["prix_entree"]) * ordre["quantite_fictive"], 2
            )
            _recalc_metrics(portfolio)
            save_portfolio(portfolio)
            return {"id_ordre": id_ordre, "prix_actuel": body.prix_actuel, "pnl_latent": ordre["pnl_latent"]}

    # Vérifier si clôturé
    for o in portfolio.get("ordres_cloturer", []) or []:
        if o["id_ordre"] == id_ordre:
            raise HTTPException(409, detail=f"Ordre '{id_ordre}' déjà clôturé.")

    raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")


# ---------------------------------------------------------------------------
# PATCH /api/orders/{id_ordre}/close
# ---------------------------------------------------------------------------

@router.patch("/{id_ordre}/close", summary="Clôture manuellement un ordre")
def close_order(id_ordre: str, body: CloseOrder) -> dict:
    """
    Déplace l'ordre des `ordres` vers `ordres_cloturer`, calcule le PnL réalisé
    et met à jour le champ `cloture` dans le journal de décisions.

    - `prix_sortie` optionnel : si absent, utilise le SL pour CLOTURE_PERDANT,
      le TP pour CLOTURE_GAGNANT, le `prix_actuel` pour EXPIRE.
    """
    portfolio = load_portfolio()
    journal   = load_journal()
    ouverts   = portfolio.get("ordres", []) or []

    idx = next((i for i, o in enumerate(ouverts) if o["id_ordre"] == id_ordre), None)
    if idx is None:
        for o in portfolio.get("ordres_cloturer", []) or []:
            if o["id_ordre"] == id_ordre:
                raise HTTPException(409, detail=f"Ordre '{id_ordre}' déjà clôturé.")
        raise HTTPException(404, detail=f"Ordre '{id_ordre}' introuvable.")

    ordre = ouverts.pop(idx)

    # Déterminer le prix de sortie
    if body.prix_sortie is not None:
        exit_price = body.prix_sortie
    elif body.statut == "CLOTURE_PERDANT":
        exit_price = ordre["stop_loss"]
    elif body.statut == "CLOTURE_GAGNANT":
        exit_price = ordre["take_profit"]
    else:
        exit_price = ordre.get("prix_actuel", ordre["prix_entree"])

    pnl = round((exit_price - ordre["prix_entree"]) * ordre["quantite_fictive"], 2)

    ordre.update({
        "statut":       body.statut,
        "prix_actuel":  exit_price,
        "pnl_latent":   pnl,
        "date_cloture": date.today().isoformat(),
    })

    portfolio.setdefault("ordres_cloturer", []).append(ordre)
    _recalc_metrics(portfolio)

    # Historique capital
    capital = portfolio["metriques"]["capital_actuel"]
    portfolio.setdefault("historique_capital", []).append({
        "date":    date.today().isoformat(),
        "capital": capital,
        "note":    f"Cloture {id_ordre} ({body.statut}) PnL {pnl:+.2f}EUR",
    })

    save_portfolio(portfolio)

    # Mise à jour journal
    for dec in journal.get("decisions", []) or []:
        if dec["id_ordre"] == id_ordre:
            dec["cloture"] = {
                "date_cloture":      date.today().isoformat(),
                "statut_final":      body.statut,
                "pnl_euros":         f"{pnl:+.2f}",
                "commentaire_retour": body.commentaire or f"Cloture manuelle via API.",
            }
            save_journal(journal)
            break

    return {"id_ordre": id_ordre, "statut": body.statut, "pnl": pnl, "exit_price": exit_price}


# ---------------------------------------------------------------------------
# POST /api/orders/refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", summary="Rafraîchit tous les prix + clôtures automatiques")
def refresh_prices() -> dict:
    """
    Pour chaque ordre ouvert :
      1. Récupère le prix actuel via yfinance.
      2. Recalcule le PnL latent.
      3. Clôture automatiquement si TP/SL atteint ou expiration dépassée.

    Retourne un résumé des prix mis à jour et des clôtures déclenchées.
    """
    try:
        import yfinance as yf
    except ImportError:
        raise HTTPException(500, detail="yfinance non installé (pip install yfinance).")

    portfolio = load_portfolio()
    journal   = load_journal()
    ouverts   = portfolio.get("ordres", []) or []
    today_str = date.today().isoformat()

    updated   = []
    closed    = []
    errors    = []

    encore_ouverts = []

    for ordre in ouverts:
        actif = ordre["actif"]
        try:
            hist = yf.Ticker(actif).history(period="2d", interval="1d")
            if hist.empty:
                raise ValueError("Pas de données retournées")
            prix = round(float(hist["Close"].iloc[-1]), 4)
        except Exception as e:
            errors.append({"actif": actif, "erreur": str(e)})
            encore_ouverts.append(ordre)
            continue

        entree = ordre["prix_entree"]
        sl     = ordre["stop_loss"]
        tp     = ordre["take_profit"]
        qty    = ordre["quantite_fictive"]
        expiry = ordre.get("date_expiration", "")

        # Déterminer statut
        if prix <= sl:
            statut = "CLOTURE_PERDANT"
            exit_price = sl
        elif prix >= tp:
            statut = "CLOTURE_GAGNANT"
            exit_price = tp
        elif expiry and expiry <= today_str:
            statut = "EXPIRE"
            exit_price = prix
        else:
            statut = "OUVERT"
            exit_price = None

        pnl = round((prix - entree) * qty, 2)

        if statut != "OUVERT":
            exit_pnl = round((exit_price - entree) * qty, 2)
            ordre.update({
                "statut":       statut,
                "prix_actuel":  exit_price,
                "pnl_latent":   exit_pnl,
                "date_cloture": today_str,
            })
            portfolio.setdefault("ordres_cloturer", []).append(ordre)
            closed.append({"id_ordre": ordre["id_ordre"], "actif": actif, "statut": statut, "pnl": exit_pnl})

            # Journal
            for dec in journal.get("decisions", []) or []:
                if dec["id_ordre"] == ordre["id_ordre"] and dec.get("cloture") is None:
                    dec["cloture"] = {
                        "date_cloture":       today_str,
                        "statut_final":       statut,
                        "pnl_euros":          f"{exit_pnl:+.2f}",
                        "commentaire_retour": f"Cloture automatique via /refresh (prix={prix}).",
                    }
        else:
            ordre["prix_actuel"] = prix
            ordre["pnl_latent"]  = pnl
            encore_ouverts.append(ordre)
            updated.append({"id_ordre": ordre["id_ordre"], "actif": actif, "prix": prix, "pnl_latent": pnl})

    portfolio["ordres"] = encore_ouverts
    _recalc_metrics(portfolio)

    # Historique capital si au moins une clôture
    if closed:
        portfolio.setdefault("historique_capital", []).append({
            "date":    today_str,
            "capital": portfolio["metriques"]["capital_actuel"],
            "note":    f"Refresh auto: {len(closed)} cloture(s), {len(encore_ouverts)} ouvert(s).",
        })

    save_portfolio(portfolio)
    save_journal(journal)

    return {
        "date":         today_str,
        "mis_a_jour":   updated,
        "clotures":     closed,
        "erreurs":      errors,
        "metriques":    portfolio["metriques"],
    }
