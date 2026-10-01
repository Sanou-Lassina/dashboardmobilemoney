"""Page 7 — Cadre de suivi des indicateurs (Suivi-Évaluation) et contrôle qualité des données (DQA)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import cadre, charts, dqa, kpis, ui
from src import config as C

ctx = ui.get_ctx()
donnees = ctx.donnees
dq = ctx.dq
ui.bandeau(ctx)
t_cadre, t_dqa = st.tabs(["🎯 Cadre de suivi des indicateurs", "🧪 Qualité des données (DQA)"])


def dernier_trimestre_complet(dmax: pd.Timestamp):
    dmax = dmax.normalize()
    fin = dmax if dmax == (dmax + pd.offsets.QuarterEnd(0)).normalize() else dmax.to_period("Q").start_time - pd.Timedelta(days=1)
    return fin.to_period("Q").start_time, fin


@st.cache_data(show_spinner="Calcul des indicateurs…")
def calcul(_donnees, cle: str, d1, d2):
    return kpis.calculer_indicateurs(_donnees["df"], _donnees["cl"], _donnees["obj"], _donnees["ag"], d1, d2,
                                     _donnees["dq"]["score_global"])


EMOJI = {"Atteint": "🟢 Atteint", "En bonne voie": "🟠 En bonne voie", "En retard": "🔴 En retard", "Non évalué": "⚪ Non évalué"}


def fmt_val(v, fmt, unite):
    if v is None or pd.isna(v):
        return "n/d"
    s = f"{v:{fmt}}".replace(",", "\u202f").replace(".", ",")
    return f"{s} {unite}" if unite not in ("%", "") else f"{s} %"


with t_cadre:
    base, cibles, origine = kpis.baselines_et_cibles(donnees)
    mode = st.radio("Valeur actuelle calculée sur", ["Dernier trimestre complet", "Période sélectionnée (périmètre national)"], horizontal=True, key="mode_cadre")
    d1, d2 = dernier_trimestre_complet(ctx.meta["date_max"]) if mode.startswith("Dernier") else (ctx.d1, ctx.d2)
    cle = f"{len(ctx.df)}-{ctx.meta['date_max']:%Y%m%d}"
    val = calcul(donnees, cle, d1, d2)
    tc = kpis.tableau_cadre(val, base, cibles, dq)
    st.caption(f"Période de mesure : {d1:%d/%m/%Y} → {d2:%d/%m/%Y} · Baselines et cibles : {origine}. "
               "Ce cadre porte sur l'ensemble du périmètre : les filtres Agence, Produit, Canal… ne s'appliquent pas.")

    k = st.columns(4)
    ui.metrique(k[0], "🟢 Atteints", ui.fr(int((tc["Statut"] == "Atteint").sum())))
    ui.metrique(k[1], "🟠 En bonne voie", ui.fr(int((tc["Statut"] == "En bonne voie").sum())))
    ui.metrique(k[2], "🔴 En retard", ui.fr(int((tc["Statut"] == "En retard").sum())))
    ui.metrique(k[3], "🧪 Score DQA moyen", ui.fmt_pct(tc["Score DQA (%)"].mean()))

    cats = st.multiselect("Catégorie", sorted(tc["Catégorie"].unique()), key="cat_cadre", placeholder="Toutes")
    vue = tc[tc["Catégorie"].isin(cats)] if cats else tc
    ligne = lambda col, row: fmt_val(row[col], row["fmt"], row["Unité"])  # noqa: E731
    aff = pd.DataFrame({
        "ID": vue["ID"], "Catégorie": vue["Catégorie"], "Indicateur": vue["Indicateur"],
        "Fréquence": vue["Fréquence"], "Source": vue["Source"],
        "Baseline": [ligne("Baseline", row) for _, row in vue.iterrows()],
        "Cible": [ligne("Cible", row) for _, row in vue.iterrows()],
        "Valeur actuelle": [ligne("Valeur actuelle", row) for _, row in vue.iterrows()],
        "Avancement (%)": vue["Avancement (%)"].astype(float).clip(lower=0, upper=100),
        "Statut": vue["Statut"].map(EMOJI), "Score DQA (%)": vue["Score DQA (%)"]})
    ui.tableau(aff, column_config={
        "Avancement (%)": st.column_config.ProgressColumn("Avancement vers la cible (%)", format="%.0f", min_value=0, max_value=100,
                                                          help="0 % = baseline, 100 % = cible atteinte."),
        "Score DQA (%)": st.column_config.ProgressColumn("Score DQA (%)", format="%.1f", min_value=0, max_value=100,
                                                         help="Fiabilité des données sources de l'indicateur.")})

    ui.titre_section("🔎 Fiche indicateur")
    choix = st.selectbox("Indicateur", tc["Indicateur"].tolist(), key="fiche_ind")
    r = tc[tc["Indicateur"] == choix].iloc[0]
    d = cadre.DEF_PAR_ID[r["ID"]]
    f1, f2 = st.columns([3, 2])
    with f1:
        st.markdown(f"**Définition :** {d['definition']}")
        st.markdown(f"**Formule :** `{d['formule']}`")
        st.markdown(f"**Source :** {d['source']} · **Fréquence :** {d['frequence']} · **Responsable :** {d['responsable']}")
        st.markdown(f"**Sens favorable :** {'hausse ↑' if d['sens'] == 'hausse' else 'baisse ↓'} · **Champs sources :** {d['champs'] or 'toutes les feuilles'}")
    with f2:
        c = st.columns(3)
        ui.metrique(c[0], "Baseline", fmt_val(r["Baseline"], r["fmt"], r["Unité"]))
        ui.metrique(c[1], "Actuel", fmt_val(r["Valeur actuelle"], r["fmt"], r["Unité"]))
        ui.metrique(c[2], "Cible", fmt_val(r["Cible"], r["fmt"], r["Unité"]))
        av = r["Avancement (%)"]
        st.progress(0.0 if av is None or pd.isna(av) else float(min(max(av, 0), 100)) / 100,
                    text=f"Avancement : {ui.fmt_pct(av, 0)} · Score DQA : {ui.fmt_pct(r['Score DQA (%)'])}")
    ui.bouton_export("Exporter le cadre de suivi (complet)", {"Cadre de suivi": tc.drop(columns="fmt")}, "cadre_de_suivi.xlsx", "exp_cadre")
    with st.expander("Méthode"):
        st.markdown(
            "- **Baseline** : valeur de référence avant la période de suivi (feuille *Indicateurs* du classeur, sinon 1er trimestre des données).\n"
            "- **Cible** : proposée par défaut, **à valider avec les parties prenantes**.\n"
            "- **Avancement** = (actuel − baseline) ÷ (cible − baseline), valable pour les indicateurs à la hausse comme à la baisse. "
            "🟢 ≥ 100 % · 🟠 60-99 % · 🔴 < 60 %.\n"
            "- **Score DQA de l'indicateur** = 70 % qualité des champs sources (complétude × validité) + 30 % contrôles transverses (unicité, intégrité, cohérence).")

with t_dqa:
    niv, coul = dqa.niveau_dqa(dq["score_global"])
    k = st.columns(4)
    ui.metrique(k[0], "🧪 Score global", ui.fmt_pct(dq["score_global"]), aide="50 % champs + 50 % contrôles transverses.")
    ui.metrique(k[1], "📋 Qualité des champs", ui.fmt_pct(dq["score_champs"]))
    ui.metrique(k[2], "🔗 Contrôles transverses", ui.fmt_pct(dq["score_transverse"]))
    k[3].markdown(f"<div style='padding:18px 6px;font-weight:800;color:{coul};font-size:1.3rem'>● {niv}</div>", unsafe_allow_html=True)
    st.caption("Les contrôles portent sur les données **brutes** (avant nettoyage) : ils mesurent la qualité de la source.")

    ch = dq["champs"]
    low = ch.sort_values("Score (%)").head(10)
    fig = go.Figure(go.Bar(x=low["Score (%)"], y=low["Table"] + " · " + low["Champ"], orientation="h",
                           marker_color=[dqa.niveau_dqa(v)[1] for v in low["Score (%)"]], text=[f"{v:.1f} %" for v in low["Score (%)"]], textposition="outside"))
    fig.update_xaxes(range=[max(0, float(low["Score (%)"].min()) - 10), 101])
    ui.plot(charts.layout(fig, "10 champs les moins fiables", 380, legende_bas=False))

    ui.titre_section("Qualité par champ")
    ui.tableau(ch, column_config={c: st.column_config.ProgressColumn(c, format="%.1f", min_value=0, max_value=100) for c in ["Complétude (%)", "Validité (%)", "Score (%)"]})
    ui.titre_section("Contrôles transverses")
    ui.tableau(dq["transverses"], column_config={"Résultat (%)": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=100)})
    ui.titre_section("Journal du nettoyage")
    if not donnees["journal"]:
        st.success("Aucune correction nécessaire.")
    for niveau, msg in donnees["journal"]:
        {"error": st.error, "warning": st.warning}.get(niveau, st.info)(msg)
    ui.bouton_export("Exporter le rapport DQA", {"Champs": ch, "Transverses": dq["transverses"],
                                                  "Journal": pd.DataFrame(donnees["journal"], columns=["Niveau", "Message"])}, "rapport_dqa.xlsx", "exp_dqa")
ui.pied_de_page()
