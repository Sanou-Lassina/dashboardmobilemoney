"""Page 2 — Ventes et tendances : trajectoire, objectifs, effets volume/mix/panier, saisonnalité, prévision."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import charts, kpis, ui
from src import config as C

ctx = ui.get_ctx()
ok = ctx.dff_ok
ui.bandeau(ctx)


@st.fragment
def bloc_tendance():
    """Fragment : changer la granularité ne recalcule pas toute la page."""
    ui.titre_section("📈 Évolution du chiffre d'affaires")
    gran = st.radio("Granularité", ["Jour", "Semaine", "Mois", "Trimestre"], index=2, horizontal=True, key="gran")
    s = kpis.serie(ok, gran)
    c1, c2 = st.columns(2)
    with c1:
        ui.plot(charts.serie_gtv(s, gran, f"GTV et transactions par {gran.lower()}"))
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=s["Période"], y=s["Revenu_net"], name="Revenu net (FCFA)", marker_color=C.VERT))
        fig.add_trace(go.Scatter(x=s["Période"], y=s["Actifs"], name="Clients actifs", yaxis="y2", mode="lines+markers",
                                 line=dict(color=C.BLEU, width=2)))
        fig.update_layout(yaxis2=dict(title="Clients actifs", overlaying="y", side="right", showgrid=False))
        fig.update_xaxes(type="category" if gran != "Jour" else "date")
        ui.plot(charts.layout(fig, f"Revenu net et clients actifs par {gran.lower()}", 380, unifie=True))
    st.caption("Les périodes situées aux bornes de la sélection peuvent être partielles.")


bloc_tendance()

# ─────────── Réalisé vs objectif ───────────
ui.titre_section("🎯 Réalisé vs objectif")
if ctx.objectifs_pertinents:
    perf = kpis.performance_objectifs(ok, ctx.obj, ctx.d1, ctx.d2, ctx.agences_scope)
    if perf.empty:
        st.info("Aucun mois complet dans la période sélectionnée : choisissez au moins un mois calendaire entier.")
    else:
        m = perf.groupby("Période").agg(CA=("CA", "sum"), Objectif=("Objectif_Montant (FCFA)", "sum")).reset_index()
        m["Taux"] = m["CA"] / m["Objectif"] * 100
        ui.plot(charts.reel_vs_objectif(m, "Réalisé vs objectif mensuel (mois complets, agences sélectionnées)"))
else:
    ui.avertissement_objectifs(ctx)

# ─────────── Cascade volume / mix / panier ───────────
ui.titre_section("🧮 Qu'est-ce qui explique l'évolution du GTV ?")
if ctx.has_prev:
    w = kpis.decomposition_pvm(ctx.prev_ok, ok)
    if w is not None:
        ui.plot(charts.waterfall(w, "Cascade : volume, mix produits et panier"))
        st.caption("Effet volume : plus ou moins de transactions. Effet mix : bascule vers des produits à panier plus ou moins élevé. "
                   "Effet panier : variation du montant moyen à produit constant. La somme des trois effets égale exactement la variation du GTV.")
else:
    st.info("Activez une comparaison (période précédente ou N-1) dans la barre latérale pour voir la cascade.")

# ─────────── Saisonnalité ───────────
ui.titre_section("🗓️ Rythmes d'activité")
s1, s2 = st.columns(2)
with s1:
    if ctx.meta["a_heures"]:
        h = ok.pivot_table(index="Jour_sem", columns="Heure", values="ID_Transaction", aggfunc="count", fill_value=0)
        h = h.reindex(index=range(7), columns=range(24), fill_value=0)
        h.index = C.JOURS_FR
        ui.plot(charts.matrice(h, "Transactions par jour et heure (pics de charge)", 360, suffixe="tx"))
    else:
        st.info("Les dates du classeur ne contiennent pas l'heure : profil horaire indisponible.")
with s2:
    j = ok.groupby(["Date_jour"])["Montant (FCFA)"].sum().reset_index()
    j["Jour du mois"] = j["Date_jour"].dt.day
    moy = j.groupby("Jour du mois")["Montant (FCFA)"].mean().reset_index()
    fig = go.Figure(go.Bar(x=moy["Jour du mois"], y=moy["Montant (FCFA)"], marker_color=C.ORANGE))
    ui.plot(charts.layout(fig, "GTV journalier moyen selon le jour du mois (effet fin de mois / salaires)", 360, legende_bas=False))

sm = kpis.serie(ok, "Mois")
if len(sm) >= 12:
    sm["Mois_num"] = sm["Période"].str[5:7].astype(int)
    idx = sm.groupby("Mois_num")["GTV"].mean()
    idx = (idx / idx.mean() * 100).reset_index()
    idx["Mois"] = idx["Mois_num"].map(lambda m: C.MOIS_NOMS[m - 1][:4])
    fig = go.Figure(go.Bar(x=idx["Mois"], y=idx["GTV"], marker_color=[C.VERT if v >= 100 else C.JAUNE for v in idx["GTV"]],
                           text=[f"{v:.0f}" for v in idx["GTV"]], textposition="outside"))
    fig.add_hline(y=100, line_dash="dot", line_color=C.BLEU)
    ui.plot(charts.layout(fig, "Indice saisonnier (100 = mois moyen)", 340, legende_bas=False))

# ─────────── Prévision ───────────
ui.titre_section("🔮 Prévision du GTV mensuel (indicative)")
hist = ctx.dimf[ctx.dimf["Réussi"] & (ctx.dimf["Date"] < ctx.d2 + pd.Timedelta(days=1))]
ser = hist.groupby("Mois_label")["Montant (FCFA)"].sum()
if ctx.d2.normalize() < (ctx.d2 + pd.offsets.MonthEnd(0)).normalize() and len(ser):
    ser = ser.iloc[:-1]                                  # on retire le mois en cours, incomplet
horizon = st.slider("Horizon (mois)", 3, 12, 6, key="horizon")
prev_df, methode = kpis.prevoir(ser, horizon)
if prev_df is None:
    st.info("Historique insuffisant (moins de 6 mois complets) pour produire une prévision.")
else:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ser.index, y=ser.values, name="Historique", mode="lines+markers", line=dict(color=C.BLEU, width=2.5)))
    fig.add_trace(go.Scatter(x=prev_df["Période"], y=prev_df["Haut"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=prev_df["Période"], y=prev_df["Bas"], mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(255,107,44,0.18)", name="Intervalle à 80 %", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=prev_df["Période"], y=prev_df["Prévision"], name="Prévision", mode="lines+markers",
                             line=dict(color=C.ORANGE, width=2.5, dash="dash")))
    fig.update_xaxes(type="category")
    ui.plot(charts.layout(fig, "GTV mensuel : historique et prévision", 400, unifie=True))
    st.caption(f"Méthode : {methode}. Prévision statistique indicative : elle ne tient pas compte des campagnes, "
               "changements de tarifs ou événements exceptionnels.")
    ui.bouton_export("Exporter la prévision", {"Prévision": prev_df}, "prevision_gtv.xlsx", "exp_prev")
ui.pied_de_page()
