"""Page 1 — Résumé exécutif : l'essentiel pour décider en 2 minutes."""
import numpy as np
import pandas as pd
import streamlit as st

from src import charts, insights, kpis, rapport, ui
from src import config as C

ctx = ui.get_ctx()
ok, dff = ctx.dff_ok, ctx.dff

# ─────────── Calculs ───────────
syn = kpis.synthese(dff)
syn_prev = kpis.synthese(ctx.prev) if ctx.has_prev else None
dl = lambda k: kpis.variation(syn[k], syn_prev[k]) if syn_prev else None  # noqa: E731

act = kpis.activite_clients(ctx.hist_ok, ctx.cl_f, ctx.d2)
act_prev = None
if ctx.has_prev:
    act_prev = kpis.activite_clients(ctx.hist_ok[ctx.hist_ok["Date"] < ctx.p2 + pd.Timedelta(days=1)], ctx.cl_f, ctx.p2)

arpu = kpis.arpu_mensuel(ok)
arpu_prev = kpis.arpu_mensuel(ctx.prev_ok) if ctx.has_prev else None

perf = pa = None
taux_m = taux_t = np.nan
proj = None
if ctx.objectifs_pertinents:
    perf = kpis.performance_objectifs(ok, ctx.obj, ctx.d1, ctx.d2, ctx.agences_scope)
    taux_m, taux_t = kpis.taux_atteinte(perf)
    pa = kpis.par_agence(perf)
    proj = kpis.projection_fin_de_mois(ok, ctx.obj, ctx.d2, ctx.agences_scope)
taux_m_prev = None
if ctx.has_prev and ctx.objectifs_pertinents:
    pp = kpis.performance_objectifs(ctx.prev_ok, ctx.obj, ctx.p1, ctx.p2, ctx.agences_scope)
    taux_m_prev = kpis.taux_atteinte(pp)[0]

hist_dim = ctx.dimf[ctx.dimf["Réussi"] & (ctx.dimf["Date"] < ctx.d2 + pd.Timedelta(days=1))]
agents = kpis.stats_agents(ok, ctx.ag, ctx.d2, ctx.agences_scope, hist_ok=hist_dim)
part_agents_actifs = agents["Actif_30j"].mean() * 100 if len(agents) else np.nan
rc = kpis.ratio_cash(ok, "Agence")
incidents = kpis.jours_incident(dff)
alertes = kpis.detecter_alertes(dff)["synthese"]
motifs = dff[dff["Est_Echec"]]["Motif_Echec"].value_counts(normalize=True)
motif_top = (motifs.index[0], motifs.iloc[0] * 100) if len(motifs) else None

# ─────────── KPI ───────────
ui.bandeau(ctx)
ui.titre_section("📌 Indicateurs clés")
c = st.columns(6)
ui.metrique(c[0], "💰 GTV (valeur traitée)", ui.fmt_fcfa(syn["gtv"]), dl("gtv"),
            aide="Valeur brute des transactions réussies.")
ui.metrique(c[1], "📈 Revenu net", ui.fmt_fcfa(syn["revenu_net"]), dl("revenu_net"),
            aide="Commissions perçues − commissions reversées aux agents.")
ui.metrique(c[2], "🏷️ Take rate", ui.fmt_pct(syn["take_rate"], 2), dl("take_rate"),
            aide="Revenu brut ÷ GTV.")
ui.metrique(c[3], "👥 Clients actifs 30 j", ui.fr(act["actifs30"]),
            kpis.variation(act["actifs30"], act_prev["actifs30"]) if act_prev else None,
            aide="Clients distincts avec ≥ 1 transaction réussie sur les 30 derniers jours de la période.")
ui.metrique(c[4], "💵 ARPU mensuel", ui.fmt_fcfa(arpu, compact=False), kpis.variation(arpu, arpu_prev) if ctx.has_prev else None,
            aide="Revenu brut mensuel par client actif du mois (moyenne sur la période).")
ui.metrique(c[5], "✅ Taux de succès", ui.fmt_pct(syn["taux_succes"]), dl("taux_succes"),
            aide="Transactions réussies ÷ transactions initiées.")

c = st.columns(6)
ui.metrique(c[0], "🎯 Atteinte objectif montant", ui.fmt_pct(taux_m) if ctx.objectifs_pertinents else "n/d",
            kpis.variation(taux_m, taux_m_prev) if taux_m_prev else None,
            aide="Réalisé ÷ objectif sur les mois complets de la période (agrégé agence × mois).")
ui.metrique(c[1], "🎯 Atteinte objectif transactions", ui.fmt_pct(taux_t) if ctx.objectifs_pertinents else "n/d")
ui.metrique(c[2], "🏪 Agents actifs 30 j", ui.fmt_pct(part_agents_actifs, 0),
            aide="Agents ayant traité ≥ 1 transaction réussie sur 30 jours ÷ agents activés.")
ui.metrique(c[3], "📲 Taux d'activité 30 j", ui.fmt_pct(act["taux_activite30"]),
            kpis.variation(act["taux_activite30"], act_prev["taux_activite30"]) if act_prev else None,
            aide="Clients actifs 30 j ÷ clients inscrits.")
ui.metrique(c[4], "🛒 Panier médian", ui.fmt_fcfa(syn["panier_median"], compact=False), dl("panier_median"),
            aide="Médiane : plus fiable que la moyenne car les montants sont très asymétriques.")
ui.metrique(c[5], "🔻 Churn 30 j", ui.fmt_pct(act["churn30"]),
            kpis.variation(act["churn30"], act_prev["churn30"]) if act_prev else None, bon_si_hausse=False,
            aide="Part des actifs de la fenêtre précédente qui ne le sont plus.")
ui.avertissement_objectifs(ctx)

# ─────────── Messages clés ───────────
ui.titre_section("🧭 Ce qu'il faut retenir")
messages = insights.generer({
    "syn": syn, "syn_prev": syn_prev, "par_agence": pa, "objectifs_pertinents": ctx.objectifs_pertinents,
    "proj": proj, "ratio_cash": rc, "agents": agents, "incidents": incidents, "alertes": alertes,
    "activite": act, "motif_top": motif_top, "dq_global": ctx.dq["score_global"]})
icones = {"critique": "🔴", "attention": "🟠", "positif": "🟢", "info": "🔵"}
for niv, txt in messages:
    {"critique": st.error, "attention": st.warning, "positif": st.success, "info": st.info}[niv](txt, icon=icones[niv])
if not messages:
    st.info("Aucun signal particulier sur ce périmètre.")

# ─────────── Graphiques ───────────
ui.titre_section("📊 Tendance et performance")
g1, g2 = st.columns(2)
with g1:
    ui.plot(charts.serie_gtv(kpis.serie(ok, "Mois"), "Mois", "GTV et transactions par mois"))
with g2:
    if pa is not None and len(pa):
        ui.plot(charts.barres_atteinte(pa, "Taux_Montant_%", "Atteinte de l'objectif de montant par agence"))
    else:
        p = kpis.pareto(ok.groupby("Agence")["Montant (FCFA)"].sum().reset_index(name="GTV"), "GTV", "Agence")
        ui.plot(charts.pareto(p, "Agence", "GTV", "Concentration du GTV par agence (Pareto)"))

# ─────────── Tableau par agence ───────────
ui.titre_section("🏢 Tableau de bord par agence")
tab = (dff.groupby("Agence").agg(Transactions=("ID_Transaction", "count"), Succès=("Réussi", "sum")).reset_index()
          .merge(ok.groupby("Agence").agg(GTV=("Montant (FCFA)", "sum"), Revenu_net=("Commission_Nette (FCFA)", "sum"),
                                          Clients=("ID_Client", "nunique")).reset_index(), on="Agence", how="left"))
tab["Taux de succès (%)"] = tab["Succès"] / tab["Transactions"] * 100
if pa is not None and len(pa):
    tab = tab.merge(pa[["Agence", "Taux_Montant_%", "Taux_Tx_%"]], on="Agence", how="left")
else:
    tab["Taux_Montant_%"] = np.nan
    tab["Taux_Tx_%"] = np.nan
tab = tab.merge(rc[["Agence", "Ratio"]], on="Agence", how="left").sort_values("GTV", ascending=False)
tab = tab.rename(columns={"Taux_Montant_%": "Atteinte montant (%)", "Taux_Tx_%": "Atteinte transactions (%)",
                          "Ratio": "Ratio cash-in/out", "Revenu_net": "Revenu net (FCFA)", "GTV": "GTV (FCFA)"})
cols = ["Agence", "GTV (FCFA)", "Revenu net (FCFA)", "Transactions", "Clients", "Taux de succès (%)",
        "Atteinte montant (%)", "Atteinte transactions (%)", "Ratio cash-in/out"]
ui.tableau(tab[cols], column_config={
    "GTV (FCFA)": st.column_config.NumberColumn(format="%d"),
    "Revenu net (FCFA)": st.column_config.NumberColumn(format="%d"),
    "Taux de succès (%)": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=100),
    "Atteinte montant (%)": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=120),
    "Atteinte transactions (%)": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=120),
    "Ratio cash-in/out": st.column_config.NumberColumn(format="%.2f", help="1 = équilibré ; > 1,3 : e-float des agents sous tension ; < 0,7 : cash sous tension"),
})

# ─────────── Exports ───────────
ui.titre_section("📤 Exports pour le comité de direction")
kpi_rows = [("GTV", ui.fmt_fcfa(syn["gtv"]), ui.fmt_pct(dl("gtv")) if dl("gtv") is not None else "–"),
            ("Revenu net", ui.fmt_fcfa(syn["revenu_net"]), ui.fmt_pct(dl("revenu_net")) if dl("revenu_net") is not None else "–"),
            ("Take rate", ui.fmt_pct(syn["take_rate"], 2), "–"),
            ("Clients actifs 30 j", ui.fr(act["actifs30"]), "–"),
            ("Taux de succès", ui.fmt_pct(syn["taux_succes"]), "–"),
            ("Atteinte objectif montant", ui.fmt_pct(taux_m) if ctx.objectifs_pertinents else "n/d", "–")]
e1, e2 = st.columns(2)
with e1:
    ui.bouton_export("Pack Excel (KPI, agences, messages)", {
        "KPI": pd.DataFrame(kpi_rows, columns=["Indicateur", "Valeur", "Évolution"]),
        "Agences": tab[cols], "Messages": pd.DataFrame(messages, columns=["Niveau", "Message"])},
        "resume_mobile_money.xlsx", "exp_resume_xlsx")
with e2:
    st.download_button("⬇️ Note de synthèse (HTML → PDF via Ctrl+P)",
                       rapport.note_synthese_html(ctx.libelle_periode, kpi_rows, messages, tab[cols].round(1)),
                       "note_synthese.html", mime="text/html", key="exp_resume_html")
ui.pied_de_page()
