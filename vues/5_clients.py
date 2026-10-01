"""Page 5 — Clients : activité, rétention (cohortes), activation, segmentation RFM."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import charts, kpis, ui
from src import config as C

ctx = ui.get_ctx()
ok = ctx.dff_ok
ui.bandeau(ctx)
act = kpis.activite_clients(ctx.hist_ok, ctx.cl_f, ctx.d2)

ui.titre_section("👥 Santé de la base clients")
k = st.columns(6)
ui.metrique(k[0], "📋 Clients inscrits", ui.fr(act["inscrits"]))
ui.metrique(k[1], "✅ Actifs 30 j", ui.fr(act["actifs30"]))
ui.metrique(k[2], "✅ Actifs 90 j", ui.fr(act["actifs90"]))
ui.metrique(k[3], "📲 Taux d'activité 30 j", ui.fmt_pct(act["taux_activite30"]))
ui.metrique(k[4], "🔻 Churn 30 j", ui.fmt_pct(act["churn30"]), aide="Actifs de la fenêtre précédente devenus inactifs.")
ui.metrique(k[5], "😴 Dormants (> 90 j)", ui.fr(act["dormants"]), aide="Inscrits depuis plus de 90 jours sans transaction réussie sur 90 jours.")
st.caption(f"Cycle de vie calculé sur l'historique des clients du périmètre (agence, ville, segment) jusqu'au {ctx.d2:%d/%m/%Y}. "
           f"Part des clients avec KYC niveau 2 ou plus : {ui.fmt_pct(act['part_kyc2'], 0)}.")

# ─────────── MAU et inscriptions ───────────
mau = kpis.mau_mensuel(ctx.hist_ok)
mau = mau[mau["Mois_label"] >= ctx.d1.strftime("%Y-%m")]
ins = ctx.cl_f.dropna(subset=["Date_Inscription"]).assign(M=lambda d: d["Date_Inscription"].dt.strftime("%Y-%m"))
ins = ins[(ins["Date_Inscription"] >= ctx.d1) & (ins["Date_Inscription"] <= ctx.d2)].groupby("M").size().reset_index(name="Inscriptions")
fig = go.Figure()
fig.add_trace(go.Bar(x=ins["M"], y=ins["Inscriptions"], name="Nouvelles inscriptions", marker_color="rgba(0,51,102,0.3)"))
fig.add_trace(go.Scatter(x=mau["Mois_label"], y=mau["Actifs"], name="Clients actifs du mois (MAU)", mode="lines+markers",
                         line=dict(color=C.ORANGE, width=2.5), yaxis="y2"))
fig.update_layout(yaxis2=dict(title="MAU", overlaying="y", side="right", showgrid=False))
fig.update_xaxes(type="category")
ui.plot(charts.layout(fig, "Inscriptions et clients actifs par mois", 380, unifie=True))

# ─────────── Démographie ───────────
ui.titre_section("🧑‍🤝‍🧑 Qui sont les clients actifs ?")
cla = ctx.cl_f[ctx.cl_f["ID_Client"].isin(act["ids_actifs30"])]
d1c, d2c, d3c = st.columns(3)
with d1c:
    fig = px.histogram(cla[cla["Age"].notna()], x="Age", color="Sexe", nbins=20, barmode="overlay", opacity=0.75,
                       color_discrete_map={"M": C.BLEU, "F": C.ORANGE, "NR": "#B0B7C3"})
    ui.plot(charts.layout(fig, "Âge et sexe (actifs 30 j)", 340))
with d2c:
    sg = ok.groupby("Segment").agg(GTV=("Montant (FCFA)", "sum"), Clients=("ID_Client", "nunique")).reset_index()
    fig = px.bar(sg, x="Segment", y="GTV", color="Segment", color_discrete_sequence=C.PALETTE, text=sg["Clients"].map(lambda v: f"{v} clients"))
    fig.update_layout(showlegend=False)
    ui.plot(charts.layout(fig, "GTV et clients par segment", 340, legende_bas=False))
with d3c:
    fm = cla["Sexe"].value_counts().reindex(["F", "M", "NR"]).dropna().reset_index()
    fm.columns = ["Sexe", "Clients"]
    fig = px.pie(fm, values="Clients", names="Sexe", hole=0.5, color="Sexe", color_discrete_map={"M": C.BLEU, "F": C.ORANGE, "NR": "#B0B7C3"})
    ui.plot(charts.layout(fig, "Répartition par sexe", 340, legende_bas=False))

# ─────────── Activation et cohortes ───────────
ui.titre_section("🚀 Activation et rétention")
e1, e2 = st.columns([2, 3])
with e1:
    ent = kpis.entonnoir_activation(ctx.hist_ok, ctx.cl_f, ctx.d1, ctx.d2)
    if ent is None:
        st.info("Aucun client inscrit depuis plus de 30 jours dans la période : entonnoir indisponible.")
    else:
        ui.plot(charts.entonnoir(ent, "Entonnoir d'activation des nouveaux clients"))
        st.caption("Uniquement les clients inscrits dans la période depuis au moins 30 jours (pour laisser le temps d'agir).")
with e2:
    coh = kpis.cohortes(ctx.hist_ok, ctx.cl_f, ctx.d2)
    if coh is None:
        st.info("Pas assez de cohortes d'inscription pour la période.")
    else:
        ui.plot(charts.matrice(coh, "Rétention par cohorte d'inscription (% actifs au mois M+k)", 380, fmt=".0f", suffixe="%",
                               echelle=[[0, "white"], [0.5, C.JAUNE], [1, C.VERT]]))

# ─────────── RFM ───────────
ui.titre_section("💎 Segmentation RFM (Récence – Fréquence – Montant)")
r = kpis.rfm(ok, ctx.cl_f if len(ctx.cl_f) else ctx.cl, ctx.d2)
if r is None:
    st.info("Moins de 10 clients actifs : segmentation RFM non significative.")
else:
    seg = r.groupby("Segment_RFM").agg(Clients=("ID_Client", "count"), GTV=("Montant", "sum"),
                                       Récence_moy=("Récence", "mean"), Fréquence_moy=("Fréquence", "mean")).reset_index()
    seg["Part du GTV (%)"] = seg["GTV"] / seg["GTV"].sum() * 100
    ordre = ["Champions", "Fidèles", "Nouveaux / prometteurs", "Occasionnels", "À risque (à relancer)", "Dormants / perdus"]
    seg["o"] = seg["Segment_RFM"].map({s: i for i, s in enumerate(ordre)})
    seg = seg.sort_values("o").drop(columns="o")
    q1, q2 = st.columns(2)
    with q1:
        fig = px.bar(seg, x="Segment_RFM", y="Clients", color="Segment_RFM", color_discrete_sequence=C.PALETTE, text="Clients")
        fig.update_layout(showlegend=False)
        ui.plot(charts.layout(fig, "Clients par segment RFM", 360, legende_bas=False))
    with q2:
        fig = px.bar(seg, x="Segment_RFM", y="Part du GTV (%)", color="Segment_RFM", color_discrete_sequence=C.PALETTE)
        fig.update_layout(showlegend=False)
        ui.plot(charts.layout(fig, "Part du GTV par segment RFM", 360, legende_bas=False))
    conseils = {"Champions": "Fidéliser : avantages, parrainage.", "Fidèles": "Faire monter en gamme : produits additionnels.",
                "Nouveaux / prometteurs": "Accompagner : bonus de 2e/3e transaction.", "Occasionnels": "Stimuler : rappels, offres ciblées.",
                "À risque (à relancer)": "Relancer en priorité : forte valeur passée, activité en baisse.", "Dormants / perdus": "Réactiver à faible coût (SMS) ou abandonner."}
    seg["Action recommandée"] = seg["Segment_RFM"].map(conseils)
    ui.tableau(seg, column_config={"GTV": st.column_config.NumberColumn("GTV (FCFA)", format="%d"),
                                   "Récence_moy": st.column_config.NumberColumn("Récence moy. (j)", format="%.0f"),
                                   "Fréquence_moy": st.column_config.NumberColumn("Fréquence moy.", format="%.1f"),
                                   "Part du GTV (%)": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=100)})

    @st.fragment
    def liste_segment():
        choix = st.selectbox("Liste d'action marketing pour le segment", ordre, key="seg_rfm")
        lst = r[r["Segment_RFM"] == choix].sort_values("Montant", ascending=False)[
            ["ID_Client", "Identité (masquée)", "Segment", "Agence", "Récence", "Fréquence", "Montant", "R", "F", "M"]]
        st.caption(f"{len(lst)} clients — identités masquées par défaut (données personnelles).")
        ui.tableau(lst.head(200), column_config={"Montant": st.column_config.NumberColumn("Montant (FCFA)", format="%d")})
        ui.bouton_export("Exporter cette liste", {choix[:30]: lst}, "liste_rfm.xlsx", "exp_rfm")
    liste_segment()
ui.pied_de_page()
