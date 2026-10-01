"""Note de synthèse HTML autonome (s'imprime en PDF depuis le navigateur : Ctrl+P)."""
import html
from datetime import datetime

import pandas as pd

COULEURS = {"critique": "#E63946", "attention": "#FFB703", "positif": "#00B388", "info": "#003366"}


def note_synthese_html(periode: str, kpi_rows: list[tuple[str, str, str]], messages: list[tuple[str, str]],
                       tableau: pd.DataFrame | None) -> str:
    e = html.escape
    kpi = "".join(f"<tr><td>{e(l)}</td><td><b>{e(v)}</b></td><td>{e(d)}</td></tr>" for l, v, d in kpi_rows)
    msg = "".join(f"<li style='border-left:5px solid {COULEURS.get(n, '#003366')};padding:4px 10px;margin:6px 0;list-style:none'>{e(t)}</li>"
                  for n, t in messages)
    tab = tableau.to_html(index=False, border=0, classes="t", na_rep="–") if tableau is not None and len(tableau) else ""
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Note de synthèse Mobile Money</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;color:#1E2936;max-width:900px;margin:30px auto;padding:0 16px}}
h1{{color:#003366;border-bottom:4px solid #FF6B2C;padding-bottom:6px}} h2{{color:#003366;margin-top:26px}}
table{{border-collapse:collapse;width:100%}} td,th{{padding:6px 10px;border-bottom:1px solid #e5e8ee;text-align:left;font-size:.92rem}}
th{{background:#003366;color:#fff}} small{{color:#6b7280}}</style></head><body>
<h1>Note de synthèse – Mobile Money</h1><p><b>Période :</b> {e(periode)}<br><small>Généré le {datetime.now():%d/%m/%Y %H:%M} · données simulées</small></p>
<h2>Indicateurs clés</h2><table><tr><th>Indicateur</th><th>Valeur</th><th>Évolution</th></tr>{kpi}</table>
<h2>Messages clés</h2><ul style="padding:0">{msg}</ul>
<h2>Performance par agence</h2>{tab}</body></html>"""
