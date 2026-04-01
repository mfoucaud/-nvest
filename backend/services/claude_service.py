"""
claude_service.py — Enrichissement des candidats via Claude sonnet-4-6 + web_search.

Pour chaque candidat (score technique ≥ 30), appelle Claude pour :
- Rechercher l'actualité récente (web_search)
- Évaluer le sentiment des investisseurs
- Calculer les bonus/malus et le score final
"""
import json
import os

import anthropic

from backend.services.scanner import Candidate

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_BONUS_MALUS_KEYS = [
    "bonus_actualite_positive",
    "bonus_sentiment_haussier",
    "bonus_aucune_actualite_negative",
    "malus_evenement_macro",
    "malus_actualite_negative",
    "malus_resultats_proches",
]


def _parse_claude_response(text: str, fallback_score: int) -> dict:
    """Extrait le JSON de la réponse Claude. Retourne un dict de fallback en cas d'échec."""
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return {
            "contexte_actualite": "Analyse web indisponible (parsing échoué).",
            "sentiment_communaute": "NEUTRE",
            "risques_identifies": "N/A",
            "conclusion": "Score technique uniquement.",
            "bonus_malus": {k: 0 for k in _BONUS_MALUS_KEYS},
            "score_final": fallback_score,
        }


def enrich_candidate(candidate: Candidate) -> dict:
    """
    Appelle Claude sonnet-4-6 avec web_search pour enrichir un candidat.

    Retourne un dict avec : contexte_actualite, sentiment_communaute,
    risques_identifies, conclusion, bonus_malus, score_final.

    En cas d'erreur API, retourne un dict de fallback avec score_final = score_technique.
    """
    prompt = f"""Tu es un analyste financier. Analyse l'actif {candidate.ticker}.

Score technique brut : {candidate.score_technique}/100
Prix actuel : {candidate.prix}
RSI(14) : {candidate.rsi}
Signal MACD : {candidate.macd_signal}
ATR : {candidate.atr}

1. Recherche l'actualité récente sur {candidate.ticker} (dernières 48h)
2. Recherche le sentiment des investisseurs (Reddit, Twitter, analystes)
3. Retourne UNIQUEMENT ce JSON valide (sans balises markdown) :
{{
  "contexte_actualite": "résumé en 2-3 phrases",
  "sentiment_communaute": "HAUSSIER|NEUTRE|BAISSIER|MITIGÉ",
  "risques_identifies": "risques en 1-2 phrases",
  "conclusion": "phrase de synthèse",
  "bonus_malus": {{
    "bonus_actualite_positive": 0,
    "bonus_sentiment_haussier": 0,
    "bonus_aucune_actualite_negative": 0,
    "malus_evenement_macro": 0,
    "malus_actualite_negative": 0,
    "malus_resultats_proches": 0
  }},
  "score_final": {candidate.score_technique}
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        return _parse_claude_response(text, fallback_score=candidate.score_technique)

    except Exception as e:
        return {
            "contexte_actualite": f"Analyse web indisponible ({e}).",
            "sentiment_communaute": "NEUTRE",
            "risques_identifies": "N/A",
            "conclusion": "Score technique uniquement (erreur Claude API).",
            "bonus_malus": {k: 0 for k in _BONUS_MALUS_KEYS},
            "score_final": candidate.score_technique,
        }
