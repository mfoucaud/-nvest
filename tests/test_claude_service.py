"""test_claude_service.py — Tests avec Claude mocké (pas d'appels réels)."""
import json
import pytest
from unittest.mock import MagicMock, patch
from backend.services.scanner import Candidate
from backend.services.claude_service import enrich_candidate, _parse_claude_response


VALID_JSON_RESPONSE = json.dumps({
    "contexte_actualite": "Résultats positifs, upgrade analyste.",
    "sentiment_communaute": "HAUSSIER",
    "risques_identifies": "Résultats dans 5 jours.",
    "conclusion": "Bon signal avec catalyseur positif.",
    "bonus_malus": {
        "bonus_actualite_positive": 10,
        "bonus_sentiment_haussier": 5,
        "bonus_aucune_actualite_negative": 0,
        "malus_evenement_macro": 0,
        "malus_actualite_negative": 0,
        "malus_resultats_proches": -20,
    },
    "score_final": 55,
})


def make_candidate(score: int = 45) -> Candidate:
    return Candidate(
        ticker="AAPL", classe="Action", prix=200.0,
        rsi=32.0, macd_signal="haussier", atr=5.0,
        score_technique=score,
        detail_score={"rsi_survente": 20, "macd_croisement": 20},
    )


# --- _parse_claude_response ---

def test_parse_valid_json():
    result = _parse_claude_response(VALID_JSON_RESPONSE, fallback_score=45)
    assert result["sentiment_communaute"] == "HAUSSIER"
    assert result["score_final"] == 55


def test_parse_json_in_markdown():
    text = f"Voici l'analyse:\n```json\n{VALID_JSON_RESPONSE}\n```"
    result = _parse_claude_response(text, fallback_score=45)
    assert result["score_final"] == 55


def test_parse_invalid_json_returns_fallback():
    result = _parse_claude_response("texte invalide non-JSON", fallback_score=40)
    assert result["score_final"] == 40
    assert result["sentiment_communaute"] == "NEUTRE"


# --- enrich_candidate ---

def test_enrich_candidate_success():
    candidate = make_candidate(score=45)

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text=VALID_JSON_RESPONSE)]

    with patch("backend.services.claude_service.client") as mock_client:
        mock_client.messages.create.return_value = mock_response
        result = enrich_candidate(candidate)

    assert result["score_final"] == 55
    assert result["sentiment_communaute"] == "HAUSSIER"
    mock_client.messages.create.assert_called_once()


def test_enrich_candidate_api_error_returns_fallback():
    candidate = make_candidate(score=50)

    with patch("backend.services.claude_service.client") as mock_client:
        mock_client.messages.create.side_effect = Exception("API timeout")
        result = enrich_candidate(candidate)

    assert result["score_final"] == 50  # fallback = score technique
    assert "indisponible" in result["contexte_actualite"].lower()


def test_enrich_candidate_uses_correct_model():
    candidate = make_candidate()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text=VALID_JSON_RESPONSE)]

    with patch("backend.services.claude_service.client") as mock_client:
        mock_client.messages.create.return_value = mock_response
        enrich_candidate(candidate)

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-6"
