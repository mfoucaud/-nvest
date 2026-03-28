"""
data_loader.py — Chargement et accès aux données JSON du portefeuille fictif.

Les fichiers JSON se trouvent dans le dossier PARENT du dossier backend/.
Arborescence attendue:
  project/
    portfolio_fictif.json
    journal_decisions.json
    backend/
      services/
        data_loader.py   ← ce fichier
"""

import json
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

def get_portfolio_path() -> Path:
    """Retourne le chemin absolu vers portfolio_fictif.json."""
    # __file__ = backend/services/data_loader.py
    # .parent        = backend/services/
    # .parent.parent = backend/
    # .parent.parent.parent = project/
    return Path(__file__).parent.parent.parent / "portfolio_fictif.json"


def get_journal_path() -> Path:
    """Retourne le chemin absolu vers journal_decisions.json."""
    return Path(__file__).parent.parent.parent / "journal_decisions.json"


# ---------------------------------------------------------------------------
# Loaders bruts
# ---------------------------------------------------------------------------

def load_portfolio() -> dict:
    """
    Lit et retourne le contenu complet de portfolio_fictif.json.
    Retourne une structure vide si le fichier est absent ou corrompu.
    """
    path = get_portfolio_path()
    if not path.exists():
        print(f"[data_loader] AVERTISSEMENT : fichier introuvable → {path}")
        return {"ordres": [], "ordres_cloturer": [], "metriques": {}, "historique_capital": []}

    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            print(f"[data_loader] AVERTISSEMENT : fichier vide → {path}")
            return {"ordres": [], "ordres_cloturer": [], "metriques": {}, "historique_capital": []}
        return json.loads(content)
    except json.JSONDecodeError as exc:
        print(f"[data_loader] ERREUR JSON dans {path} : {exc}")
        return {"ordres": [], "ordres_cloturer": [], "metriques": {}, "historique_capital": []}


def load_journal() -> dict:
    """
    Lit et retourne le contenu complet de journal_decisions.json.
    Retourne une structure vide si le fichier est absent ou corrompu.
    """
    path = get_journal_path()
    if not path.exists():
        print(f"[data_loader] AVERTISSEMENT : fichier introuvable → {path}")
        return {"decisions": []}

    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            print(f"[data_loader] AVERTISSEMENT : fichier vide → {path}")
            return {"decisions": []}
        return json.loads(content)
    except json.JSONDecodeError as exc:
        print(f"[data_loader] ERREUR JSON dans {path} : {exc}")
        return {"decisions": []}


# ---------------------------------------------------------------------------
# Accès aux ordres
# ---------------------------------------------------------------------------

def get_all_orders() -> list:
    """
    Retourne la liste combinée de tous les ordres :
    portfolio["ordres"] + portfolio["ordres_cloturer"].
    """
    portfolio = load_portfolio()
    ouverts = portfolio.get("ordres", []) or []
    clotures = portfolio.get("ordres_cloturer", []) or []
    return ouverts + clotures


def get_order_by_id(id_ordre: str) -> Optional[dict]:
    """
    Cherche un ordre par son id_ordre dans les ordres ouverts ET clôturés.
    Retourne None si introuvable.
    """
    for ordre in get_all_orders():
        if ordre.get("id_ordre") == id_ordre:
            return ordre
    return None


# ---------------------------------------------------------------------------
# Accès aux décisions
# ---------------------------------------------------------------------------

def get_decision_by_id(id_ordre: str) -> Optional[dict]:
    """
    Cherche une décision par son id_ordre dans journal_decisions.json.
    Retourne None si introuvable.
    """
    journal = load_journal()
    for decision in journal.get("decisions", []) or []:
        if decision.get("id_ordre") == id_ordre:
            return decision
    return None


# ---------------------------------------------------------------------------
# Fusion ordre + décision
# ---------------------------------------------------------------------------

def get_merged_order(id_ordre: str) -> Optional[dict]:
    """
    Fusionne les données d'un ordre avec sa décision du journal.

    - Retourne None si l'ordre est introuvable (id inexistant).
    - La décision est optionnelle : si absente, "decision" vaut None dans le résultat.
    - La décision ne remplace pas les champs de l'ordre (ordre a priorité).
    """
    ordre = get_order_by_id(id_ordre)
    if ordre is None:
        return None

    decision = get_decision_by_id(id_ordre)

    # Copie défensive pour ne pas muter les données sources
    merged = dict(ordre)
    merged["decision"] = decision  # None si non trouvé dans le journal

    return merged
