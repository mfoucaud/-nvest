"""
models.py — Modèles SQLAlchemy ORM pour !nvest.

Tables conservées :
  decisions   — journal des décisions IA + métadonnées ordre (id_ordre = Alpaca order UUID)
  scan_runs   — historique des exécutions du scan

Tables supprimées (gérées par Alpaca) :
  orders, capital_history
"""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from backend.database import Base


class Decision(Base):
    __tablename__ = "decisions"

    id                   = Column(Integer, primary_key=True, index=True)
    # Identifiant Alpaca (UUID de l'ordre parent bracket)
    id_ordre             = Column(String(100), nullable=False, index=True)
    # Métadonnées de l'ordre (plus de FK vers orders)
    actif                = Column(String(20))
    classe               = Column(String(20))
    direction            = Column(String(10))
    prix_entree          = Column(Float)
    stop_loss            = Column(Float)
    take_profit          = Column(Float)
    taille               = Column(Float)
    quantite             = Column(Float)
    raison               = Column(Text)
    date_ouverture       = Column(DateTime)
    date_expiration      = Column(Date)
    # Analyse Claude
    signaux_techniques   = Column(Text)
    contexte_actualite   = Column(Text)
    sentiment_communaute = Column(Text)
    risques_identifies   = Column(Text)
    conclusion           = Column(Text)
    score_confiance      = Column(Integer)
    detail_score         = Column(JSONB)
    # Clôture (rempli manuellement si nécessaire)
    date_cloture         = Column(Date)
    statut_final         = Column(String(30))
    pnl_euros            = Column(String(20))
    commentaire_retour   = Column(Text)
    created_at           = Column(DateTime, server_default=func.now())


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id                = Column(Integer, primary_key=True, index=True)
    triggered_by      = Column(String(20), default="manual")
    started_at        = Column(DateTime, nullable=False)
    finished_at       = Column(DateTime)
    status            = Column(String(20), default="en_cours")
    nb_candidats      = Column(Integer, default=0)
    nb_ordres_generes = Column(Integer, default=0)
    nb_clotures       = Column(Integer, default=0)
    erreur            = Column(Text)
    created_at        = Column(DateTime, server_default=func.now())
