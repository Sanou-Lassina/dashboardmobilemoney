"""Page 4 — Réseau : agences, agents (points de service), commerciaux, liquidité et carte."""
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
hist_dim = ctx.dimf[ctx.dimf["Réussi"] & (ctx.dimf["Date"] < ctx.d2 + pd.Timedelta(days=1))]

perf = pa = None
if ctx.objectifs_pertinents:
    perf = kpis.performance_objectifs(ok, ctx.obj, ctx.d1, ctx.d2, ctx.agences_scope)
    pa = kpis.par_agence(perf)

t_ag, t_agents, t_com, t_liq = st.tabs(["🏢 Agences", "🏪 Agents (points de service)", "👔 Commerciaux", "💧 Liquidité & carte"])

# ═════════ Agences ═════════
with t_ag:
    ui.avertissement_objectifs(ctx)
    g = ok.groupby("Agence").agg(GTV=("Montant (FCFA)", "sum"), Tx=("ID_Transaction", "count"),
                                 Revenu_net=("Commission_Nette (FCFA)", "sum"), Clients=("ID_Client", "nunique")).reset_index()
    if pa is not None and len(pa):
        c1, c2 = st.columns(2)
        with c1:
            ui.plot(charts.barres_atteinte(pa, "Taux_Montant_%", "🎯 Atteinte objectif montant"))
        with c2:
            ui.plot(charts.barres_atteinte(pa, "Taux_Tx_%", "🎯 Atteinte objectif transactions"))

        @st.fragment
        def detail_agence():
            ag = st.selectbox("Détail mensuel d'une agence", pa["Agence"].tolist(), key="sel_ag")
            m = perf[perf["Agence"] == ag].sort_values("Période")
            m = m.assign(Objectif=m["Objectif_Montant (FCFA)"], Taux=np.where(m["Objectif_Montant (FCFA)"] > 0, m["CA"] / m["Objectif_Montant (FCFA)"] * 100, np.nan))
            ui.plot(charts.reel_vs_objectif(m, f"{ag} — réalisé vs objectif par mois"))
        detail_agence()
    p = kpis.pareto(g, "GTV", "Agence")
    ui.plot(charts.pareto(p, "Agence", "GTV", "Pareto : contribution des agences au GTV"))
    ui.tableau(g.sort_values("GTV", ascending=False), column_config={
        "GTV": st.column_config.NumberColumn("GTV (FCFA)", format="%d"), "Revenu_net": st.column_config.NumberColumn("Revenu net (FCFA)", format="%d")})

# ═════════ Agents ═════════
with t_agents:
    st_ag = kpis.stats_agents(ok, ctx.ag, ctx.d2, ctx.agences_scope, hist_ok=hist_dim)
    if st_ag.empty:
        st.info("Aucun agent pour ce périmètre.")
    else:
        n, actifs = len(st_ag), int(st_ag["Actif_30j"].sum())
        k = st.columns(4)
        ui.metrique(k[0], "🏪 Agents activés", ui.fr(n))
        ui.metrique(k[1], "✅ Actifs sur 30 j", ui.fr(actifs), aide="≥ 1 transaction réussie sur les 30 derniers jours.")
        ui.metrique(k[2], "😴 Inactifs sur 30 j", ui.fr(n - actifs))
        ui.metrique(k[3], "📍 Taux d'activité", ui.fmt_pct(actifs / n * 100, 0))
        pg = kpis.pareto(st_ag[st_ag["GTV"] > 0], "GTV", "ID_Agent")
        if len(pg):
            n80 = int((pg["Cumul_%"] < 80).sum() + 1)
            st.info(f"📌 **{n80} agents sur {len(pg)} ({n80 / len(pg) * 100:.0f} %)** génèrent 80 % du GTV du réseau.")
            ui.plot(charts.pareto(pg, "ID_Agent", "GTV", "Pareto des agents (GTV)"))
        cols = ["ID_Agent", "Nom_Point", "Agence", "Commercial", "GTV", "Tx", "Clients", "Revenu_net", "Derniere_activite", "Actif_30j"]
        cc = {"GTV": st.column_config.NumberColumn("GTV (FCFA)", format="%d"), "Revenu_net": st.column_config.NumberColumn("Revenu net (FCFA)", format="%d"),
              "Derniere_activite": st.column_config.DatetimeColumn("Dernière activité", format="DD/MM/YYYY"),
              "Actif_30j": st.column_config.CheckboxColumn("Actif 30 j")}
        a1, a2 = st.columns(2)
        with a1:
            st.markdown("**🏆 Top 15 agents**")
            ui.tableau(st_ag.head(15)[cols], column_config=cc)
        with a2:
            st.markdown("**⚠️ Agents inactifs à relancer**")
            ina = st_ag[~st_ag["Actif_30j"]].sort_values("Derniere_activite")[cols]
            ui.tableau(ina.head(15), column_config=cc)
        ui.bouton_export("Exporter les agents", {"Agents": st_ag[cols], "Inactifs": ina}, "agents.xlsx", "exp_agents")

# ═════════ Commerciaux ═════════
with t_com:
    cs = ok.groupby("Commercial").agg(GTV=("Montant (FCFA)", "sum"), Tx=("ID_Transaction", "count"),
                                      Revenu_net=("Commission_Nette (FCFA)", "sum"), Clients=("ID_Client", "nunique"),
                                      Agents=("ID_Agent", "nunique")).reset_index()
    cs = cs.merge(kpis.taux_succes_par(dff, "Commercial")[["Commercial", "Taux_succes_%"]], on="Commercial", how="left")
    cs = cs.sort_values("GTV", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(cs.head(10).sort_values("GTV"), x="GTV", y="Commercial", orientation="h", color="GTV",
                     color_continuous_scale=[C.VERT, C.ORANGE])
        fig.update_coloraxes(showscale=False)
        ui.plot(charts.layout(fig, "🏆 Top 10 commerciaux par GTV", 420, legende_bas=False))
    with c2:
        fig = px.scatter(cs, x="Tx", y="GTV", size="Clients", color="Taux_succes_%",
                         hover_name="Commercial", color_continuous_scale=[C.ROUGE, C.JAUNE, C.VERT])
        ui.plot(charts.layout(fig, "Transactions vs GTV (taille = clients, couleur = taux de succès)", 420, legende_bas=False))
    ui.tableau(cs, column_config={"GTV": st.column_config.NumberColumn("GTV (FCFA)", format="%d"),
                                  "Revenu_net": st.column_config.NumberColumn("Revenu net (FCFA)", format="%d"),
                                  "Taux_succes_%": st.column_config.NumberColumn("Taux de succès (%)", format="%.1f")})
    ui.bouton_export("Exporter les commerciaux", {"Commerciaux": cs}, "commerciaux.xlsx", "exp_com")

# ═════════ Liquidité & carte ═════════
with t_liq:
    st.markdown("**Équilibre cash-in / cash-out (liquidité des agents)**")
    rc = kpis.ratio_cash(ok, "Agence")
    coul = {"Équilibré": C.VERT, "Tension e-float (trop de dépôts)": C.ORANGE, "Tension cash (trop de retraits)": C.ROUGE}
    fig = go.Figure(go.Bar(x=rc["Agence"], y=rc["Ratio"], marker_color=[coul[l] for l in rc["Lecture"]],
                           text=[f"{v:.2f}" for v in rc["Ratio"]], textposition="outside"))
    fig.add_hline(y=1, line_dash="dash", line_color=C.BLEU, annotation_text="Équilibre")
    fig.add_hrect(y0=0.7, y1=1.3, fillcolor=C.VERT, opacity=0.08, line_width=0)
    ui.plot(charts.layout(fig, "Ratio cash-in ÷ cash-out par agence", 380, legende_bas=False))
    st.caption("Ratio > 1,3 : les clients déposent plus qu'ils ne retirent, l'e-float des agents se vide (réapprovisionnement e-float). "
               "Ratio < 0,7 : les agents manquent de cash. Seuils indicatifs, à calibrer avec la trésorerie.")
    ui.tableau(rc, column_config={"Cash-in": st.column_config.NumberColumn(format="%d"), "Cash-out": st.column_config.NumberColumn(format="%d"),
                                  "Position nette": st.column_config.NumberColumn(format="%d"), "Ratio": st.column_config.NumberColumn(format="%.2f")})
    geo = ctx.meta["geo"]
    if geo is None or geo.empty:
        st.info("Coordonnées des agents absentes (feuille Agents) : carte indisponible.")
    else:
        mg = geo.merge(g, on="Agence", how="inner")
        if pa is not None and len(pa):
            mg = mg.merge(pa[["Agence", "Taux_Montant_%"]], on="Agence", how="left").dropna(subset=["Taux_Montant_%"])
            col_c, echelle, lib = "Taux_Montant_%", [[0, C.ROUGE], [0.5, C.JAUNE], [1, C.VERT]], "atteinte de l'objectif"
        else:
            col_c, echelle, lib = "GTV", [[0, "#CFE3F5"], [1, C.BLEU]], "GTV"
        if len(mg):
            ui.plot(charts.carte(mg, "GTV", col_c, f"Carte du réseau (taille = GTV, couleur = {lib})", echelle=echelle))
ui.pied_de_page()
