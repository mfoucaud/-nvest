import json
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TODAY = "2026-03-28"

CURRENT_PRICES = {
    "NVDA":    167.52,
    "TSLA":    361.83,
    "ETH-USD": 2023.80,
    "AAPL":    248.80,
    "MSFT":    356.77,
}

with open('portfolio_fictif.json', encoding='utf-8') as f:
    portfolio = json.load(f)
with open('journal_decisions.json', encoding='utf-8') as f:
    journal = json.load(f)

ordres_ouverts  = portfolio['ordres']
ordres_clotures = portfolio['ordres_cloturer']

# ── Cloture des positions ──────────────────────────────────────────────────────
nouveaux_fermes = []
encore_ouverts  = []
pnl_realise_session = 0.0

for ordre in ordres_ouverts:
    actif  = ordre['actif']
    prix   = CURRENT_PRICES.get(actif)
    entree = ordre['prix_entree']
    sl     = ordre['stop_loss']
    tp     = ordre['take_profit']
    qty    = ordre['quantite_fictive']
    expiry = ordre.get('date_expiration', '')

    statut = "OUVERT"
    exit_price = None
    commentaire = ""

    if prix is None:
        encore_ouverts.append(ordre)
        continue

    if prix <= sl:
        statut = "CLOTURE_PERDANT"
        exit_price = sl
        commentaire = "Stop Loss atteint."
    elif prix >= tp:
        statut = "CLOTURE_GAGNANT"
        exit_price = tp
        commentaire = "Take Profit atteint."
    elif expiry <= TODAY:
        statut = "EXPIRE"
        exit_price = prix
        commentaire = "Position expiree (5 jours ouvres sans declenchement TP/SL)."

    if statut != "OUVERT":
        pnl = round((exit_price - entree) * qty, 2)
        pnl_realise_session += pnl
        ordre_ferme = dict(ordre)
        ordre_ferme['statut']      = statut
        ordre_ferme['prix_actuel'] = exit_price
        ordre_ferme['pnl_latent']  = pnl
        ordre_ferme['date_cloture'] = TODAY
        nouveaux_fermes.append(ordre_ferme)
        print(f"[CLOTURE] {ordre['id_ordre']} {actif:8s} {statut:20s}  exit={exit_price}  PnL={pnl:+.2f}EUR")
        for dec in journal['decisions']:
            if dec['id_ordre'] == ordre['id_ordre']:
                dec['cloture'] = {
                    "date_cloture": TODAY,
                    "statut_final": statut,
                    "pnl_euros": f"{pnl:+.2f}",
                    "commentaire_retour": commentaire
                }
    else:
        pnl_latent = round((prix - entree) * qty, 2)
        ordre['prix_actuel'] = prix
        ordre['pnl_latent']  = pnl_latent
        encore_ouverts.append(ordre)
        print(f"[OUVERT]  {ordre['id_ordre']} {actif:8s} prix={prix}  PnL latent={pnl_latent:+.2f}EUR")

# ── Nouveaux ordres ────────────────────────────────────────────────────────────
ord_006 = {
    "id_ordre": "ORD-006",
    "date_ouverture": f"{TODAY} 09:30",
    "actif": "AIR.PA",
    "classe": "Action",
    "direction": "ACHAT",
    "prix_entree": 160.42,
    "stop_loss": 151.99,
    "take_profit": 174.47,
    "ratio_rr": 1.67,
    "taille": 1000,
    "quantite_fictive": 6.2336,
    "atr_utilise": 5.62,
    "confiance": 70,
    "statut": "OUVERT",
    "raison": "RSI(14) survente (32.4), rebond Bollinger inf, support 157.88. Consensus 15/21 BUY, cible 219.55 EUR (+37%). Correction -11.6%/4 semaines = point d'entree attractif.",
    "date_expiration": "2026-04-04",
    "prix_actuel": 160.42,
    "pnl_latent": 0.0
}

ord_007 = {
    "id_ordre": "ORD-007",
    "date_ouverture": f"{TODAY} 09:30",
    "actif": "META",
    "classe": "Action",
    "direction": "ACHAT",
    "prix_entree": 525.72,
    "stop_loss": 497.31,
    "take_profit": 573.07,
    "ratio_rr": 1.67,
    "taille": 1000,
    "quantite_fictive": 1.9022,
    "atr_utilise": 18.94,
    "confiance": 45,
    "statut": "OUVERT",
    "raison": "RSI(14)=18.0 survente extreme, volume x1.7, Bollinger inf, support 520. Signal pivot bottom 24/03. Seuil degrade: verdict jury deja price dans -19.5% sur 30j.",
    "date_expiration": "2026-04-04",
    "prix_actuel": 525.72,
    "pnl_latent": 0.0
}

encore_ouverts.extend([ord_006, ord_007])
print(f"\n[NOUVEAU] ORD-006 AIR.PA  @160.42EUR  score=70  SL=151.99  TP=174.47")
print(f"[NOUVEAU] ORD-007 META    @525.72USD  score=45  SL=497.31  TP=573.07  (seuil degrade)")

# ── Metriques ─────────────────────────────────────────────────────────────────
todos_clotures = ordres_clotures + nouveaux_fermes
capital_actuel = portfolio['metriques']['capital_actuel'] + pnl_realise_session
pnl_latent_total = sum(o.get('pnl_latent', 0) for o in encore_ouverts)

gagnants = [o for o in todos_clotures if o['statut'] == 'CLOTURE_GAGNANT']
perdants = [o for o in todos_clotures if o['statut'] == 'CLOTURE_PERDANT']
expires  = [o for o in todos_clotures if o['statut'] == 'EXPIRE']
nb_total = len(todos_clotures)
win_rate = round(len(gagnants)/nb_total*100, 1) if nb_total else None

gains_tot  = sum(o['pnl_latent'] for o in gagnants)
pertes_tot = abs(sum(o['pnl_latent'] for o in perdants))
pf = round(gains_tot/pertes_tot, 2) if pertes_tot > 0 else None
pnl_total_realise = sum(o['pnl_latent'] for o in todos_clotures)

portfolio['ordres']          = encore_ouverts
portfolio['ordres_cloturer'] = todos_clotures
portfolio['metriques'] = {
    "win_rate": win_rate,
    "pnl_total_eur": round(pnl_total_realise, 2),
    "pnl_latent_eur": round(pnl_latent_total, 2),
    "pnl_total_pct": round(pnl_total_realise/10000*100, 2),
    "profit_factor": pf,
    "nb_trades_total": nb_total + len(encore_ouverts),
    "nb_trades_ouverts": len(encore_ouverts),
    "nb_trades_gagnants": len(gagnants),
    "nb_trades_perdants": len(perdants),
    "nb_trades_expires": len(expires),
    "meilleur_trade": max((o['pnl_latent'] for o in todos_clotures), default=None),
    "pire_trade": min((o['pnl_latent'] for o in todos_clotures), default=None),
    "capital_actuel": round(capital_actuel, 2),
    "derniere_mise_a_jour": TODAY
}
portfolio['historique_capital'].append({
    "date": TODAY,
    "capital": round(capital_actuel, 2),
    "note": f"J7 - 3 clotures (NVDA SL {pnl_realise_session:+.2f}EUR session). 2 nouveaux: AIR.PA (70), META (45 seuil degrade). Ouvertes: ETH, AAPL, AIR.PA, META."
})

# ── Journal - nouveaux ordres ─────────────────────────────────────────────────
journal['decisions'].append({
    "id_ordre": "ORD-006",
    "date": f"{TODAY} 09:30",
    "actif": "AIR.PA",
    "direction": "ACHAT",
    "prix_entree": 160.42,
    "stop_loss": 151.99,
    "take_profit": 174.47,
    "taille": 1000,
    "score_confiance": 70,
    "detail_score": {
        "rsi_survente": 20, "macd_croisement": 0, "bollinger_rebond": 15,
        "ema_tendance": 0, "volume_confirmation": 0, "support_horizontal": 15,
        "bonus_actualite_positive": 10, "bonus_sentiment_haussier": 5,
        "bonus_aucune_actualite_negative": 5, "malus_evenement_macro": 0,
        "malus_actualite_negative": 0, "malus_resultats_proches": 0
    },
    "signaux_techniques": "RSI(14) a 32.4 en zone survente. Prix (160.42 EUR) rebondit sur bande Bollinger inf et support 157.88. Correction -11.6% sur 4 semaines a ramene le titre aux plus bas aout 2025. MACD negatif mais momentum vente ralentit. ATR 5.62 EUR.",
    "contexte_actualite": "Consensus analyste exceptionnel: 15 BUY/0 SELL/6 HOLD sur 21 analystes. Cible moyenne 219.55 EUR (+37% upside), haut 259 EUR. Resultats Q1 le 28 avril (31 jours, hors risque immediat). Fort carnet de commandes A320neo. Tensions Moyen-Orient impactent marginalement les livraisons court terme.",
    "sentiment_communaute": "HAUSSIER — Analystes communautaires positifs. eToro/TradingView cible analyste 214 EUR. Aucune panique communautaire detectable. Correction percue comme opportunite d'achat.",
    "risques_identifies": "1) Tensions geopolitiques Moyen-Orient (livraisons). 2) MACD negatif. 3) EMA20 < EMA50. 4) EUR/USD appreciation pesant sur revenus USD. 5) Resultats Q1 le 28 avril.",
    "conclusion": "Airbus RSI survente + support Bollinger + consensus analyste tres haussier (cible +37%) + aucune mauvaise nouvelle specifique = profil risque/rendement excellent. Score 70/100, seuil ideal. SL 151.99 EUR, risque max ~52 EUR.",
    "cloture": None
})

journal['decisions'].append({
    "id_ordre": "ORD-007",
    "date": f"{TODAY} 09:30",
    "actif": "META",
    "direction": "ACHAT",
    "prix_entree": 525.72,
    "stop_loss": 497.31,
    "take_profit": 573.07,
    "taille": 1000,
    "score_confiance": 45,
    "detail_score": {
        "rsi_survente": 20, "macd_croisement": 0, "bollinger_rebond": 15,
        "ema_tendance": 0, "volume_confirmation": 15, "support_horizontal": 15,
        "bonus_actualite_positive": 0, "bonus_sentiment_haussier": 0,
        "bonus_aucune_actualite_negative": 0, "malus_evenement_macro": 0,
        "malus_actualite_negative": -15, "malus_resultats_proches": 0,
        "ajustement_sentiment": -5
    },
    "signaux_techniques": "RSI(14) a 18.0 (survente extreme et historiquement rare). Volume x1.7 confirme acceleration de vente pouvant preceder retournement. Prix rebondit sur Bollinger inf et support 520. Signal pivot bottom technique detecte le 24/03. MACD negatif mais histogramme se contracte.",
    "contexte_actualite": "Double verdict negatif: jury californien (4.2M USD dommages) + Nouveau-Mexique (375M USD) pour harm to young users. Chute 7-8% post-verdict. CEPENDANT: 379M USD total < 1% benefice annuel META (~50B USD). Evercore ISI reitere Outperform. Consensus analyste long terme reste majoritairement bullish (AI advertising).",
    "sentiment_communaute": "TRES BAISSIER/CONTRARIAN — 95% bearish selon Altindex. Extreme polarisation = signal contrarian historique fort. Reddit WSB identifie ce niveau comme potentiel retournement. Selling exhaustion observable. Malus applique -5 (vs -10 standard) car RSI=18 integre deja la panique.",
    "risques_identifies": "1) Vague de proces potentiels (risque systemique juridique). 2) MACD negatif, momentum vente non epuise. 3) Marche risk-off (Moyen-Orient, Fed hawkish). 4) Brent a 110 USD impact consommation publicitaire. 5) Sentiment peut rester tres negatif plusieurs semaines.",
    "conclusion": "ORDRE A SEUIL DEGRADE (45/100). Survente extreme RSI=18 + mauvaises nouvelles deja pricees dans -19.5% sur 30j justifie trade contrarian. Dommages negligeables vs rentabilite META. Pivot bottom 24/03 + Evercore Outperform supportent la these. Risque max ~54 EUR (SL 497.31). Regle 1-2 ordres/jour avec seuil degrade appliquee.",
    "cloture": None
})

# ── Sauvegarde ────────────────────────────────────────────────────────────────
with open('portfolio_fictif.json', 'w', encoding='utf-8') as f:
    json.dump(portfolio, f, ensure_ascii=False, indent=2)
with open('journal_decisions.json', 'w', encoding='utf-8') as f:
    json.dump(journal, f, ensure_ascii=False, indent=2)

print(f"\n=== METRIQUES ===")
m = portfolio['metriques']
print(f"Capital actuel (realise) : {m['capital_actuel']}EUR")
print(f"PnL realise total        : {m['pnl_total_eur']:+.2f}EUR ({m['pnl_total_pct']:+.2f}%)")
print(f"PnL latent               : {m['pnl_latent_eur']:+.2f}EUR")
print(f"Win Rate                 : {m['win_rate']}%")
print(f"Profit Factor            : {m['profit_factor']}")
print(f"Trades : {m['nb_trades_ouverts']} ouverts | {m['nb_trades_gagnants']} gagnants | {m['nb_trades_perdants']} perdants | {m['nb_trades_expires']} expires")
print(f"PnL session              : {pnl_realise_session:+.2f}EUR")
