"""Page 6 — Qualité de service et risques : échecs, incidents, fraude et conformité."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import charts, kpis, ui
from src import config as C

ctx = ui.get_ctx()
dff, ok = ctx.dff, ctx.dff_ok
ui.bandeau(ctx)
t_qs, t_risque = st.tabs(["🛠️ Qualité de service", "🕵️ Fraude & conformité"])

# ═════════ Qualité de service ═════════
with t_qs:
    syn = kpis.synthese(dff)
    ko, att = dff[dff["Est_Echec"]], dff[dff["Est_Attente"]]
    inc = kpis.jours_incident(dff)
    k = st.columns(5)
    ui.metrique(k[0], "✅ Taux de succès", ui.fmt_pct(syn["taux_succes"]))
    ui.metrique(k[1], "❌ Transactions échouées", ui.fr(syn["nb_echec"]), aide="Statut « Échoué ».")
    ui.metrique(k[2], "⏳ En attente", ui.fr(syn["nb_attente"]), aide="Statut « En Attente » : à rapprocher (peut aboutir ou échouer).")
    ui.metrique(k[3], "💸 Valeur échouée", ui.fmt_fcfa(ko["Montant (FCFA)"].sum()), aide="Montants des transactions échouées (opportunité manquée, hors « en attente »).")
    ui.metrique(k[4], "🚨 Jours d'incident probable", ui.fr(inc["Date"].nunique() if len(inc) else 0))

    ui.titre_section("🧩 Pourquoi les transactions échouent-elles ?")
    if len(ko):
        mo = ko.groupby(["Motif_Echec", "Canal"]).size().reset_index(name="Échecs")
        ordre = mo.groupby("Motif_Echec")["Échecs"].sum().sort_values(ascending=False).index.tolist()
        fig = px.bar(mo, x="Motif_Echec", y="Échecs", color="Canal", color_discrete_sequence=C.PALETTE, category_orders={"Motif_Echec": ordre})
        ui.plot(charts.layout(fig, "Motifs d'échec par canal", 380))
    else:
        st.success("Aucun échec sur ce périmètre.")

    @st.fragment
    def analyse_axe():
        axe = st.radio("Analyser les échecs par", ["Agence", "Produit", "Canal", "Commercial", "Heure"], horizontal=True, key="axe_echec")
        g = kpis.taux_succes_par(dff, axe)
        perdu = dff[dff["Est_Echec"]].groupby(axe)["Montant (FCFA)"].sum().rename("Valeur_échouée").reset_index()
        g = g.merge(perdu, on=axe, how="left").fillna({"Valeur_échouée": 0})
        c1, c2 = st.columns(2)
        with c1:
            if axe == "Heure":
                fig = px.line(g.sort_values(axe), x=axe, y="Taux_echec_%", markers=True, color_discrete_sequence=[C.ROUGE])
            else:
                fig = px.bar(g.sort_values("Taux_echec_%", ascending=False), x=axe, y="Taux_echec_%", color="Taux_echec_%",
                             color_continuous_scale=[[0, C.VERT], [0.5, C.JAUNE], [1, C.ROUGE]])
                fig.update_coloraxes(showscale=False)
            fig.update_yaxes(ticksuffix=" %")
            ui.plot(charts.layout(fig, f"Taux d'échec par {axe.lower()}", 360, legende_bas=False))
        with c2:
            if axe == "Heure":
                fig = px.bar(g, x="Heure", y="Valeur_échouée", color_discrete_sequence=[C.ROUGE])
            else:
                fig = px.bar(g.sort_values("Valeur_échouée"), x="Valeur_échouée", y=axe, orientation="h", color_discrete_sequence=[C.ROUGE])
            ui.plot(charts.layout(fig, f"Valeur des transactions échouées par {axe.lower()}", 360, legende_bas=False))
    analyse_axe()

    ft = dff.groupby("Mois_label").agg(Total=("ID_Transaction", "count"), Echecs=("Est_Echec", "sum")).reset_index()
    ft["Taux"] = ft["Echecs"] / ft["Total"] * 100
    fig = go.Figure()
    fig.add_trace(go.Bar(x=ft["Mois_label"], y=ft["Total"], name="Transactions", marker_color="#D9DEE7"))
    fig.add_trace(go.Scatter(x=ft["Mois_label"], y=ft["Taux"], name="Taux d'échec (%)", yaxis="y2", mode="lines+markers", line=dict(color=C.ROUGE, width=2.5)))
    fig.update_layout(yaxis2=dict(title="Taux d'échec (%)", overlaying="y", side="right", showgrid=False))
    fig.update_xaxes(type="category")
    ui.plot(charts.layout(fig, "Volume et taux d'échec par mois", 360, unifie=True))

    ui.titre_section("🚨 Jours d'incident probable")
    if len(inc):
        st.caption("Détection statistique (test binomial) : un périmètre dont le taux d'échec dépasse nettement son niveau habituel. "
                   "Signaux à confirmer avec les équipes techniques ; quelques faux positifs sont possibles.")
        ui.tableau(inc)
    else:
        st.success("Aucun pic d'échecs anormal détecté sur la période.")

    with st.expander("📋 Détail des transactions non abouties"):
        statuts = st.multiselect("Statuts", [C.STATUT_KO, C.STATUT_ATT, C.STATUT_INCONNU], default=[C.STATUT_KO], key="statuts_detail")
        det = dff[dff["Statut"].isin(statuts)][["Date", "ID_Transaction", "Agence", "Commercial", "Produit", "Canal", "Montant (FCFA)", "Statut", "Motif_Echec"]]
        det = det.sort_values("Date", ascending=False)
        ui.tableau(det.head(500), column_config={"Date": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                                                 "Montant (FCFA)": st.column_config.NumberColumn(format="%d")})
        st.caption(f"{len(det):,} lignes (500 affichées).".replace(",", "\u202f"))
        ui.bouton_export("Exporter le détail", {"Détail": det}, "transactions_non_abouties.xlsx", "exp_ko")

# ═════════ Fraude & conformité ═════════
with t_risque:
    st.warning("Ces alertes sont des **signaux à instruire** par la conformité, pas des conclusions de fraude. "
               "Les seuils sont paramétrables dans `src/config.py`.", icon="⚠️")
    al = kpis.detecter_alertes(dff)
    sy = al["synthese"]
    k = st.columns(5)
    ui.metrique(k[0], "👤 Clients en alerte", ui.fr(len(sy)))
    ui.metrique(k[1], "🔴 Score ≥ 70", ui.fr(int((sy["Score_risque"] >= 70).sum()) if len(sy) else 0))
    ui.metrique(k[2], "✂️ Fractionnement", ui.fr(len(al["structuring"])), aide=f"≥ 3 transactions entre {C.SEUIL_STRUCTURING:.0%} et 100 % du plafond ({C.PLAFOND_TX:,} FCFA) en 7 jours.".replace(",", " "))
    ui.metrique(k[3], "⚡ Rafales", ui.fr(len(al["velocite"])), aide=f"≥ {C.SEUIL_VELOCITE} transactions dans la même heure.")
    ui.metrique(k[4], "🌙 Gros montants nocturnes", ui.fr(len(al["nuit"])), aide=f"Transactions ≥ {C.SEUIL_NUIT_MONTANT:,} FCFA entre 00h et 05h.".replace(",", " "))

    if sy.empty:
        st.success("Aucune alerte sur ce périmètre.")
    else:
        ui.titre_section("📋 Clients à instruire (classés par score de risque)")
        ui.tableau(sy, column_config={"Score_risque": st.column_config.ProgressColumn("Score de risque", format="%d", min_value=0, max_value=100),
                                      "GTV_période": st.column_config.NumberColumn("GTV période (FCFA)", format="%d")})
        types = pd.DataFrame({"Type d'alerte": ["Fractionnement sous plafond", "Rafale de transactions", "Gros montant nocturne", "Montant atypique"],
                              "Clients": [len(al["structuring"]), len(al["velocite"]), len(al["nuit"]), len(al["atypiques"])]})
        fig = px.bar(types, x="Type d'alerte", y="Clients", color_discrete_sequence=[C.ORANGE], text="Clients")
        ui.plot(charts.layout(fig, "Clients concernés par type d'alerte", 320, legende_bas=False))

        @st.fragment
        def fiche_client():
            cid = st.selectbox("Examiner un client", sy["ID_Client"].tolist(), key="cli_alerte")
            t = dff[dff["ID_Client"] == cid].sort_values("Date", ascending=False)[["Date", "Produit", "Canal", "Agence", "Montant (FCFA)", "Statut"]]
            st.caption(f"{len(t)} transactions sur la période.")
            ui.tableau(t.head(200), column_config={"Date": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                                                   "Montant (FCFA)": st.column_config.NumberColumn(format="%d")})
        fiche_client()
        ui.bouton_export("Exporter les alertes", {"Synthèse": sy, "Fractionnement": al["structuring"], "Rafales": al["velocite"],
                                                  "Nocturnes": al["nuit"], "Atypiques": al["atypiques"]}, "alertes_risque.xlsx", "exp_risque")
ui.pied_de_page()
