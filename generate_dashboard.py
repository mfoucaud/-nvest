import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('portfolio_fictif.json', encoding='utf-8') as f:
    p = json.load(f)
with open('journal_decisions.json', encoding='utf-8') as f:
    j = json.load(f)

m = p['metriques']
ouverts   = p['ordres']
clotures  = p['ordres_cloturer']
histo_cap = p['historique_capital']

cap_actuel = m['capital_actuel']
cap_latent = cap_actuel + m['pnl_latent_eur']
pnl_pct    = round((cap_latent - 10000)/10000*100, 2)

# Lookup journal
journal_map = {d['id_ordre']: d for d in j['decisions']}

def pnl_class(v):
    if v is None: return ''
    return 'pos' if v >= 0 else 'neg'

def fmt_pnl(v):
    if v is None: return '-'
    return f"{v:+.2f} EUR"

html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>!nvest Dashboard - {p['metriques']['derniere_mise_a_jour']}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  :root {{
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #c9d1d9; --muted: #8b949e;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
    --blue: #58a6ff; --purple: #bc8cff;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ font-size: 1.5rem; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: .85rem; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
  .card .label {{ font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }}
  .card .value {{ font-size: 1.5rem; font-weight: 700; margin-top: 4px; }}
  .card .value.pos {{ color: var(--green); }}
  .card .value.neg {{ color: var(--red); }}
  .card .value.neutral {{ color: var(--blue); }}
  .section {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
  .section h2 {{ font-size: 1rem; margin-bottom: 14px; color: var(--blue); }}
  table {{ width: 100%; border-collapse: collapse; font-size: .83rem; }}
  th {{ text-align: left; color: var(--muted); font-weight: 500; padding: 6px 10px; border-bottom: 1px solid var(--border); }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #21262d; }}
  tr:last-child td {{ border-bottom: none; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: .75rem; font-weight: 600; }}
  .badge.ouvert    {{ background: #1f6feb33; color: var(--blue); }}
  .badge.gagnant   {{ background: #3fb95033; color: var(--green); }}
  .badge.perdant   {{ background: #f8514933; color: var(--red); }}
  .badge.expire    {{ background: #d2992233; color: var(--yellow); }}
  .badge.degrade   {{ background: #bc8cff33; color: var(--purple); }}
  .pos {{ color: var(--green); }}
  .neg {{ color: var(--red); }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }}
  .chart-wrap {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
  .chart-wrap h2 {{ font-size: .9rem; color: var(--blue); margin-bottom: 12px; }}
  .conf-bar {{ display: flex; align-items: center; gap: 8px; margin: 4px 0; font-size: .8rem; }}
  .conf-bar .name {{ width: 90px; color: var(--muted); }}
  .conf-bar .bar-wrap {{ flex: 1; background: #21262d; border-radius: 4px; height: 8px; }}
  .conf-bar .bar {{ height: 8px; border-radius: 4px; }}
  .conf-bar .score {{ width: 36px; text-align: right; }}
  .alert {{ background: #d2992222; border: 1px solid var(--yellow); border-radius: 6px; padding: 8px 12px; margin: 8px 0; font-size: .8rem; color: var(--yellow); }}
  @media (max-width: 768px) {{ .charts {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<h1>!nvest — Trading Fictif Dashboard</h1>
<p class="subtitle">Rapport du {p['metriques']['derniere_mise_a_jour']} &bull; Capital fictif &bull; Swing 2-5 jours</p>

<!-- KPIs -->
<div class="grid">
  <div class="card">
    <div class="label">Capital actuel</div>
    <div class="value neutral">{cap_actuel:,.2f} EUR</div>
  </div>
  <div class="card">
    <div class="label">Capital + latent</div>
    <div class="value {'pos' if cap_latent >= 10000 else 'neg'}">{cap_latent:,.2f} EUR</div>
  </div>
  <div class="card">
    <div class="label">PnL total</div>
    <div class="value {'pos' if pnl_pct >= 0 else 'neg'}">{pnl_pct:+.2f}%</div>
  </div>
  <div class="card">
    <div class="label">PnL realise</div>
    <div class="value {'pos' if m['pnl_total_eur'] >= 0 else 'neg'}">{m['pnl_total_eur']:+.2f} EUR</div>
  </div>
  <div class="card">
    <div class="label">Win Rate</div>
    <div class="value neutral">{m['win_rate'] or 0:.1f}%</div>
  </div>
  <div class="card">
    <div class="label">Trades ouverts</div>
    <div class="value neutral">{m['nb_trades_ouverts']}</div>
  </div>
  <div class="card">
    <div class="label">Gagnants / Perdants</div>
    <div class="value neutral"><span class="pos">{m['nb_trades_gagnants']}</span> / <span class="neg">{m['nb_trades_perdants']}</span></div>
  </div>
  <div class="card">
    <div class="label">Expires</div>
    <div class="value neutral">{m['nb_trades_expires']}</div>
  </div>
</div>

<!-- Positions ouvertes -->
<div class="section">
  <h2>Positions Ouvertes ({len(ouverts)})</h2>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Actif</th><th>Direction</th><th>Entree</th>
        <th>Stop Loss</th><th>Take Profit</th><th>Prix actuel</th>
        <th>PnL latent</th><th>Confiance</th><th>Expiration</th><th>Statut</th>
      </tr>
    </thead>
    <tbody>
"""

for o in ouverts:
    pnl_v = o.get('pnl_latent', 0)
    pnl_cls = 'pos' if pnl_v >= 0 else 'neg'
    conf = o['confiance']
    conf_cls = 'gagnant' if conf >= 55 else 'degrade'
    badge_label = 'Ideal' if conf >= 55 else 'Degrade'
    alerte = o.get('alerte', '')
    devise = 'EUR' if o['actif'].endswith('.PA') else 'USD'
    row = f"""
      <tr>
        <td>{o['id_ordre']}</td>
        <td><strong>{o['actif']}</strong></td>
        <td>{o['direction']}</td>
        <td>{o['prix_entree']} {devise}</td>
        <td class="neg">{o['stop_loss']} {devise}</td>
        <td class="pos">{o['take_profit']} {devise}</td>
        <td>{o.get('prix_actuel', '-')} {devise}</td>
        <td class="{pnl_cls}">{pnl_v:+.2f} EUR</td>
        <td><span class="badge {conf_cls}">{conf}/100 {badge_label}</span></td>
        <td>{o.get('date_expiration', '-')}</td>
        <td><span class="badge ouvert">OUVERT</span></td>
      </tr>"""
    if alerte:
        row += f'<tr><td colspan="11"><div class="alert">{alerte}</div></td></tr>'
    html += row

html += """
    </tbody>
  </table>
</div>

<!-- Historique -->
<div class="section">
  <h2>Historique des Ordres Clotures</h2>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Actif</th><th>Cloture</th><th>Entree</th>
        <th>Exit</th><th>PnL realise</th><th>Confiance</th><th>Statut</th>
      </tr>
    </thead>
    <tbody>
"""

for o in sorted(clotures, key=lambda x: x.get('date_cloture',''), reverse=True):
    pnl_v = o.get('pnl_latent', 0)
    pnl_cls = 'pos' if pnl_v >= 0 else 'neg'
    statut = o['statut']
    badge_cls = 'gagnant' if 'GAGNANT' in statut else ('expire' if 'EXPIRE' in statut else 'perdant')
    badge_label = 'GAGNANT' if 'GAGNANT' in statut else ('EXPIRE' if 'EXPIRE' in statut else 'PERDANT')
    devise = 'EUR' if o['actif'].endswith('.PA') else 'USD'
    html += f"""
      <tr>
        <td>{o['id_ordre']}</td>
        <td><strong>{o['actif']}</strong></td>
        <td>{o.get('date_cloture','-')}</td>
        <td>{o['prix_entree']} {devise}</td>
        <td>{o.get('prix_actuel', '-')} {devise}</td>
        <td class="{pnl_cls}">{pnl_v:+.2f} EUR</td>
        <td>{o['confiance']}/100</td>
        <td><span class="badge {badge_cls}">{badge_label}</span></td>
      </tr>"""

html += """
    </tbody>
  </table>
</div>

<!-- Charts -->
<div class="charts">
  <div class="chart-wrap">
    <h2>Evolution du Capital Fictif</h2>
    <canvas id="capChart" height="180"></canvas>
  </div>
  <div class="chart-wrap">
    <h2>Confiance des Ordres Actifs</h2>
"""

all_orders = ouverts + clotures
for o in sorted(all_orders, key=lambda x: x['confiance'], reverse=True):
    c = o['confiance']
    color = '#3fb950' if c >= 55 else ('#d29922' if c >= 45 else '#f85149')
    html += f"""
    <div class="conf-bar">
      <span class="name">{o['id_ordre']}<br><small>{o['actif']}</small></span>
      <div class="bar-wrap"><div class="bar" style="width:{c}%;background:{color}"></div></div>
      <span class="score">{c}</span>
    </div>"""

html += """
  </div>
</div>

<!-- Capital chart script -->
<script>
const capCtx = document.getElementById('capChart').getContext('2d');
"""

dates  = [h['date'] for h in histo_cap]
caps   = [h['capital'] for h in histo_cap]
html += f"const capLabels = {json.dumps(dates)};\n"
html += f"const capData   = {json.dumps(caps)};\n"
html += """
new Chart(capCtx, {
  type: 'line',
  data: {
    labels: capLabels,
    datasets: [{
      label: 'Capital (EUR)',
      data: capData,
      borderColor: '#58a6ff',
      backgroundColor: 'rgba(88,166,255,0.08)',
      tension: 0.3,
      pointBackgroundColor: capData.map(v => v >= 10000 ? '#3fb950' : '#f85149'),
      pointRadius: 5,
      fill: true
    }]
  },
  options: {
    plugins: { legend: { display: false } },
    scales: {
      x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
      y: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } }
    }
  }
});
</script>

<div class="section" style="font-size:.8rem;color:var(--muted);">
  Derniere mise a jour : """ + p['metriques']['derniere_mise_a_jour'] + """ &bull;
  Capital depart : 10 000 EUR &bull; Taille trade : 1 000 EUR &bull;
  <em>Tous les ordres sont purement fictifs et a but educatif.</em>
</div>

</body>
</html>
"""

with open('dashboard_trading.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("Dashboard genere : dashboard_trading.html")
