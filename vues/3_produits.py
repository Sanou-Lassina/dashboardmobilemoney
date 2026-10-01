"""Page 3 — Produits et canaux : mix, rentabilité, digitalisation."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import charts, kpis, ui
from src import config as C

ctx = ui.get_ctx()
ok, dff = ctx.dff_ok, ctx.dff
ui.bandeau(ctx)

# ─────────── Produits ───────────
ui.titre_section("📦 Performance par produit")
ps = kpis.stats_produit(ok)
c1, c2 = st.columns(2)
with c1:
    fig = px.pie(ps, values="GTV", names="Produit", hole=0.45, color_discrete_sequence=C.PALETTE)
    fig.update_traces(textposition="outside", textinfo="label+percent")
    ui.plot(charts.layout(fig, "Répartition du GTV par produit", 400, legende_bas=False))
with c2:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=ps["Produit"], y=ps["Revenu_net"], name="Revenu net (FCFA)", marker_color=C.VERT))
    fig.add_trace(go.Scatter(x=ps["Produit"], y=ps["Take_rate_%"], name="Take rate (%)", yaxis="y2", mode="lines+markers",
                             line=dict(color=C.BLEU, width=2)))
    fig.update_layout(yaxis2=dict(title="Take rate (%)", overlaying="y", side="right", showgrid=False))
    ui.plot(charts.layout(fig, "Rentabilité : revenu net et take rate par produit", 400))
st.caption("Le dépôt (cash-in) génère du volume mais peu de revenu : la commission versée à l'agent peut rendre son revenu net négatif.")

aff = ps.rename(columns={"GTV": "GTV (FCFA)", "Tx": "Transactions", "Revenu": "Revenu brut (FCFA)", "Revenu_net": "Revenu net (FCFA)",
                         "Panier_moyen": "Panier moyen", "Panier_median": "Panier médian"})
ui.tableau(aff, column_config={
    "GTV (FCFA)": st.column_config.NumberColumn(format="%d"), "Revenu brut (FCFA)": st.column_config.NumberColumn(format="%d"),
    "Revenu net (FCFA)": st.column_config.NumberColumn(format="%d"), "Panier moyen": st.column_config.NumberColumn(format="%d"),
    "Panier médian": st.column_config.NumberColumn(format="%d"),
    "Part_GTV_%": st.column_config.ProgressColumn("Part du GTV (%)", format="%.1f", min_value=0, max_value=100),
    "Take_rate_%": st.column_config.NumberColumn("Take rate (%)", format="%.2f")})

b1, b2 = st.columns(2)
with b1:
    ech = ok.sample(min(len(ok), 8000), random_state=0)
    fig = px.box(ech, x="Produit", y="Montant (FCFA)", color="Produit", log_y=True, color_discrete_sequence=C.PALETTE, points=False)
    fig.update_layout(showlegend=False)
    ui.plot(charts.layout(fig, "Distribution des montants (échelle log, échantillon)", 400, legende_bas=False))
with b2:
    mix = ok.groupby(["Mois_label", "Produit"])["Montant (FCFA)"].sum().reset_index().sort_values("Mois_label")
    fig = px.area(mix, x="Mois_label", y="Montant (FCFA)", color="Produit", groupnorm="percent", color_discrete_sequence=C.PALETTE)
    fig.update_yaxes(ticksuffix=" %")
    ui.plot(charts.layout(fig, "Évolution du mix produits (part du GTV)", 400, unifie=True))

# ─────────── Canaux ───────────
ui.titre_section("📡 Canaux et digitalisation")
cs = ok.groupby("Canal").agg(GTV=("Montant (FCFA)", "sum"), Tx=("ID_Transaction", "count")).reset_index()
cs = cs.merge(kpis.taux_succes_par(dff, "Canal")[["Canal", "Taux_succes_%"]], on="Canal")
d1c, d2c = st.columns(2)
with d1c:
    fig = px.bar(cs, x="Canal", y="GTV", color="Canal", color_discrete_sequence=C.PALETTE, text=cs["Taux_succes_%"].map(lambda v: f"{v:.1f} % succès"))
    fig.update_layout(showlegend=False)
    ui.plot(charts.layout(fig, "GTV par canal (et taux de succès)", 380, legende_bas=False))
with d2c:
    dm = ok.assign(Digital=ok["Canal"] != C.CANAL_AGENT).groupby("Mois_label")["Digital"].mean().mul(100).reset_index()
    fig = px.line(dm, x="Mois_label", y="Digital", markers=True, color_discrete_sequence=[C.ORANGE])
    fig.update_yaxes(ticksuffix=" %", title="Part digitale")
    ui.plot(charts.layout(fig, "Part des transactions digitales (hors agent)", 380, unifie=True))

cross = ok.pivot_table(index="Produit", columns="Canal", values="Montant (FCFA)", aggfunc="sum", fill_value=0) / 1e6
ui.plot(charts.matrice(cross, "GTV Produit × Canal (millions FCFA)", 360, fmt=".1f", suffixe="M FCFA"))
ui.bouton_export("Exporter produits et canaux", {"Produits": ps, "Canaux": cs, "Produit x Canal (M FCFA)": cross.reset_index()},
                 "produits_canaux.xlsx", "exp_prod")
ui.pied_de_page()
