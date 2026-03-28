"""
routers/orders.py — Endpoints pour la gestion des ordres du portefeuille fictif.

Prefix: /orders (monté sous /api dans main.py → URLs finales: /api/orders/...)

Endpoints:
    GET /api/orders/
        Retourne tous les ordres classés (ouverts / clôturés) + métriques globales.

    GET /api/orders/{id_ordre}
        Retourne un ordre fusionné avec sa décision du journal.
        404 si l'id_ordre est inconnu.
"""

from fastapi import APIRouter, HTTPException

from backend.services.data_loader import (
    load_portfolio,
    get_merged_order,
)

router = APIRouter(prefix="/orders", tags=["orders"])


# ---------------------------------------------------------------------------
# GET /api/orders/
# ---------------------------------------------------------------------------

@router.get("/", summary="Liste tous les ordres + métriques")
def list_orders() -> dict:
    """
    Retourne le portefeuille structuré :
    - `ouverts`   : liste des ordres avec statut OUVERT
    - `cloturer`  : liste des ordres clôturés (quel que soit le statut final)
    - `metriques` : indicateurs globaux de performance (win rate, PnL, etc.)
    """
    portfolio = load_portfolio()

    ouverts: list = portfolio.get("ordres", []) or []
    cloturer: list = portfolio.get("ordres_cloturer", []) or []
    metriques: dict = portfolio.get("metriques", {}) or {}
    historique_capital: list = portfolio.get("historique_capital", []) or []

    return {
        "ouverts": ouverts,
        "cloturer": cloturer,
        "metriques": metriques,
        "historique_capital": historique_capital,
    }


# ---------------------------------------------------------------------------
# GET /api/orders/{id_ordre}
# ---------------------------------------------------------------------------

@router.get("/{id_ordre}", summary="Détail d'un ordre fusionné avec sa décision")
def get_order(id_ordre: str) -> dict:
    """
    Retourne un ordre enrichi avec les données du journal de décisions.

    La réponse contient tous les champs de l'ordre auxquels s'ajoute
    une clé `decision` contenant l'analyse complète (signaux techniques,
    contexte actualité, sentiment, risques, conclusion, score, etc.).

    `decision` est `null` si aucune entrée du journal ne correspond
    à cet ordre (ne devrait pas arriver en production normale).

    Retourne **404** si l'`id_ordre` est inconnu dans le portefeuille.
    """
    merged = get_merged_order(id_ordre)

    if merged is None:
        raise HTTPException(
            status_code=404,
            detail=f"Ordre '{id_ordre}' introuvable dans le portefeuille.",
        )

    return merged
