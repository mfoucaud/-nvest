"""
models.py — Modèles SQLAlchemy ORM pour !nvest.

Tables :
  orders          — ordres fictifs (ouverts + clôturés)
  decisions       — journal des décisions IA (1:1 avec orders)
  capital_history — courbe d'évolution du capital
  scan_runs       — historique des exécutions du scan
"""
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from backend.database import Base


class Order(Base):
    __tablename__ = "orders"

    id               = Column(Integer, primary_key=True, index=True)
    id_ordre         = Column(String(20), unique=True, nullable=False, index=True)
    actif            = Column(String(20), nullable=False)
    classe           = Column(String(20), nullable=False)
    direction        = Column(String(10), nullable=False)
    statut           = Column(String(30), nullable=False, default="OUVERT")
    prix_entree      = Column(Float, nullable=False)
    stop_loss        = Column(Float, nullable=False)
    take_profit      = Column(Float, nullable=False)
    prix_actuel      = Column(Float)
    prix_sortie      = Column(Float)
    ratio_rr         = Column(Float)
    taille           = Column(Float, default=1000.0)
    quantite_fictive = Column(Float)
    confiance        = Column(Integer)
    raison           = Column(Text)
    pnl_latent       = Column(Float, default=0.0)
    atr_utilise      = Column(Float)
    alerte           = Column(Text)
    date_ouverture   = Column(DateTime, nullable=False)
    date_expiration  = Column(Date)
    date_cloture     = Column(Date)
    created_at       = Column(DateTime, server_default=func.now())


class Decision(Base):
    __tablename__ = "decisions"

    id                   = Column(Integer, primary_key=True, index=True)
    id_ordre             = Column(String(20), ForeignKey("orders.id_ordre"), unique=True, nullable=False, index=True)
    signaux_techniques   = Column(Text)
    contexte_actualite   = Column(Text)
    sentiment_communaute = Column(Text)
    risques_identifies   = Column(Text)
    conclusion           = Column(Text)
    score_confiance      = Column(Integer)
    detail_score         = Column(JSONB)
    # Champ de clôture (rempli quand l'ordre se clôture)
    date_cloture         = Column(Date)
    statut_final         = Column(String(30))
    pnl_euros            = Column(String(20))
    commentaire_retour   = Column(Text)
    created_at           = Column(DateTime, server_default=func.now())


class CapitalHistory(Base):
    __tablename__ = "capital_history"

    id         = Column(Integer, primary_key=True, index=True)
    date       = Column(Date, nullable=False)
    capital    = Column(Float, nullable=False)
    note       = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id                = Column(Integer, primary_key=True, index=True)
    triggered_by      = Column(String(20), default="manual")   # "manual" | "scheduler"
    started_at        = Column(DateTime, nullable=False)
    finished_at       = Column(DateTime)
    status            = Column(String(20), default="en_cours")  # en_cours | termine | erreur
    nb_candidats      = Column(Integer, default=0)
    nb_ordres_generes = Column(Integer, default=0)
    nb_clotures       = Column(Integer, default=0)
    erreur            = Column(Text)
    created_at        = Column(DateTime, server_default=func.now())
