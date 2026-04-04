"""
migrate_json_to_pg.py — Migration one-shot des données JSON vers PostgreSQL.

Usage:
    python -m backend.scripts.migrate_json_to_pg

Lit portfolio_fictif.json et journal_decisions.json depuis la racine du projet.
Insère dans orders, decisions, capital_history.
Les fichiers JSON sont conservés (backup).
"""
import json
import sys
from datetime import datetime, date
from pathlib import Path

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _load_json(filename: str) -> dict:
    path = PROJECT_ROOT / filename
    if not path.exists():
        print(f"[migration] SKIP — {filename} introuvable")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_datetime(s: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.now()


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def migrate(db: Session, commit: bool = False) -> dict:
    from backend.models import Order, Decision, CapitalHistory

    portfolio = _load_json("portfolio_fictif.json")
    journal = _load_json("journal_decisions.json")

    nb_orders = 0
    nb_decisions = 0
    nb_capital = 0
    errors = []

    nb_updates = 0

    # --- Ordres ---
    all_orders = (portfolio.get("ordres") or []) + (portfolio.get("ordres_cloturer") or [])
    for o in all_orders:
        existing = db.query(Order).filter(Order.id_ordre == o["id_ordre"]).first()
        if existing:
            # Mettre à jour si le JSON a fermé un ordre encore OUVERT en base
            if existing.statut == "OUVERT" and o["statut"] != "OUVERT":
                existing.statut        = o["statut"]
                existing.prix_actuel   = o.get("prix_actuel", existing.prix_actuel)
                existing.prix_sortie   = o.get("prix_sortie", existing.prix_sortie)
                existing.pnl_latent    = o.get("pnl_latent", existing.pnl_latent)
                existing.date_cloture  = _parse_date(o.get("date_cloture"))
                db.flush()
                nb_updates += 1
            continue
        try:
            order = Order(
                id_ordre=o["id_ordre"],
                actif=o["actif"],
                classe=o["classe"],
                direction=o["direction"],
                statut=o["statut"],
                prix_entree=o["prix_entree"],
                stop_loss=o["stop_loss"],
                take_profit=o["take_profit"],
                prix_actuel=o.get("prix_actuel"),
                prix_sortie=o.get("prix_sortie"),
                ratio_rr=o.get("ratio_rr"),
                taille=o.get("taille", 1000.0),
                quantite_fictive=o.get("quantite_fictive"),
                confiance=o.get("confiance"),
                raison=o.get("raison"),
                pnl_latent=o.get("pnl_latent", 0.0),
                atr_utilise=o.get("atr_utilise"),
                alerte=o.get("alerte"),
                date_ouverture=_parse_datetime(o["date_ouverture"]),
                date_expiration=_parse_date(o.get("date_expiration")),
                date_cloture=_parse_date(o.get("date_cloture")),
            )
            db.add(order)
            db.flush()
            nb_orders += 1
        except Exception as e:
            errors.append(f"Ordre {o.get('id_ordre')}: {e}")

    # --- Décisions ---
    for d in journal.get("decisions") or []:
        if db.query(Decision).filter(Decision.id_ordre == d["id_ordre"]).first():
            continue
        # Vérifier que l'ordre existe
        if not db.query(Order).filter(Order.id_ordre == d["id_ordre"]).first():
            errors.append(f"Décision {d['id_ordre']}: ordre introuvable en base")
            continue
        try:
            cloture = d.get("cloture") or {}
            decision = Decision(
                id_ordre=d["id_ordre"],
                signaux_techniques=d.get("signaux_techniques"),
                contexte_actualite=d.get("contexte_actualite"),
                sentiment_communaute=d.get("sentiment_communaute"),
                risques_identifies=d.get("risques_identifies"),
                conclusion=d.get("conclusion"),
                score_confiance=d.get("score_confiance"),
                detail_score=d.get("detail_score"),
                date_cloture=_parse_date(cloture.get("date_cloture")),
                statut_final=cloture.get("statut_final"),
                pnl_euros=cloture.get("pnl_euros"),
                commentaire_retour=cloture.get("commentaire_retour"),
            )
            db.add(decision)
            db.flush()
            nb_decisions += 1
        except Exception as e:
            errors.append(f"Décision {d.get('id_ordre')}: {e}")

    # --- Capital history ---
    for entry in portfolio.get("historique_capital") or []:
        entry_date = _parse_date(entry["date"])
        if entry_date and db.query(CapitalHistory).filter(CapitalHistory.date == entry_date).first():
            continue  # déjà migré
        try:
            ch = CapitalHistory(
                date=entry_date,
                capital=entry["capital"],
                note=entry.get("note"),
            )
            db.add(ch)
            nb_capital += 1
        except Exception as e:
            errors.append(f"Capital entry {entry.get('date')}: {e}")

    if commit:
        db.commit()

    return {
        "nb_orders": nb_orders,
        "nb_updates": nb_updates,
        "nb_decisions": nb_decisions,
        "nb_capital": nb_capital,
        "errors": errors,
    }


if __name__ == "__main__":
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        result = migrate(db, commit=True)
        print(f"Migration terminée :")
        print(f"  {result['nb_orders']} ordres insérés")
        print(f"  {result['nb_updates']} ordres mis à jour (statut)")
        print(f"  {result['nb_decisions']} décisions")
        print(f"  {result['nb_capital']} entrées capital")
        if result["errors"]:
            print(f"  ERREURS ({len(result['errors'])}) :")
            for e in result["errors"]:
                print(f"    - {e}")
        sys.exit(0 if not result["errors"] else 1)
    finally:
        db.close()
