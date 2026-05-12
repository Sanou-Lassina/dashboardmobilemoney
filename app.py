"""
╔══════════════════════════════════════════════════════════════════════╗
║         MOBILE MONEY - TABLEAU DE BORD ANALYTIQUE DES VENTES          ║
║                       Burkina Faso  2024-2025                        ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
#  CONFIGURATION DE LA PAGE
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Mobile Money – Dashboard Analytique",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  PALETTE & STYLES SANK MONEY
# ─────────────────────────────────────────────
ORANGE   = "#FF6B2C"
VERT     = "#00B388"
BLEU     = "#003366"
GRIS     = "#F5F7FA"
GRIS_SIDEBAR = "#F0F2F6"  # Gris clair professionnel (comme Streamlit par défaut)
ROUGE    = "#E63946"
JAUNE    = "#FFB703"
VIOLET   = "#7B2D8B"

PALETTE  = [ORANGE, VERT, BLEU, JAUNE, ROUGE, VIOLET, "#06A77D", "#F4A261"]

st.markdown(f"""
<style>
    .main {{background-color: {GRIS};}}
    [data-testid="stSidebar"] {{background: {GRIS_SIDEBAR};}}
    [data-testid="stSidebar"] * {{color: #1E2936 !important;}}
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stDateInput label {{color: #4B5563 !important; font-weight:600;}}
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown p {{color: #1E2936 !important;}}
    [data-testid="stSidebar"] .st-emotion-cache-1wivap2 img {{filter: none;}}
    .metric-card {{
        background: white; border-radius: 14px; padding: 18px 20px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08); border-left: 5px solid {ORANGE};
        margin-bottom: 10px;
    }}
    .metric-value {{font-size: 1.7rem; font-weight: 800; color: {BLEU};}}
    .metric-label {{font-size: 0.78rem; color: #666; text-transform: uppercase; letter-spacing:.05em;}}
    .metric-delta-pos {{color: {VERT}; font-size:0.85rem; font-weight:700;}}
    .metric-delta-neg {{color: {ROUGE}; font-size:0.85rem; font-weight:700;}}
    .section-title {{
        font-size:1.25rem; font-weight:800; color:{BLEU};
        border-bottom: 3px solid {ORANGE}; padding-bottom:6px; margin: 18px 0 12px 0;
    }}
    .stTabs [data-baseweb="tab"] {{font-weight:600; font-size:0.95rem;}}
    .stTabs [aria-selected="true"] {{color:{ORANGE} !important; border-bottom-color:{ORANGE} !important;}}
    div[data-testid="stDataFrame"] {{border-radius:10px; overflow:hidden;}}
    .badge-vert  {{background:{VERT};  color:white; padding:3px 10px; border-radius:20px; font-size:.8rem;}}
    .badge-rouge {{background:{ROUGE}; color:white; padding:3px 10px; border-radius:20px; font-size:.8rem;}}
    .badge-jaune {{background:{JAUNE}; color:white; padding:3px 10px; border-radius:20px; font-size:.8rem;}}
    h1 {{color:{BLEU};}} h2,h3 {{color:{BLEU};}}
</style>
""", unsafe_allow_html=True)

MOIS_FR = {
    "Janvier":1,"Février":2,"Fevrier":2,"Mars":3,"Avril":4,"Mai":5,"Juin":6,
    "Juillet":7,"Août":8,"Aout":8,"Septembre":9,"Octobre":10,"Novembre":11,
    "Décembre":12,"Decembre":12,
}

# ─────────────────────────────────────────────
#  CHARGEMENT & NETTOYAGE
# ─────────────────────────────────────────────
@st.cache_data
def charger_donnees(fichier):
    xl = pd.ExcelFile(fichier)

    # — Transactions —
    tx = pd.read_excel(xl, sheet_name="Transactions")
    tx.columns = tx.columns.str.strip()
    tx["Date"] = pd.to_datetime(tx["Date"], errors="coerce")
    tx["Montant (FCFA)"]    = pd.to_numeric(tx["Montant (FCFA)"],    errors="coerce").fillna(0)
    tx["Commission (FCFA)"] = pd.to_numeric(tx["Commission (FCFA)"], errors="coerce").fillna(0)
    tx["Statut"]  = tx["Statut"].fillna("Inconnu")
    tx["Année"]   = tx["Date"].dt.year
    tx["Mois_num"]= tx["Date"].dt.month
    tx["Mois_nom"]= tx["Date"].dt.strftime("%B")
    tx["Trimestre"]= "T" + tx["Date"].dt.quarter.astype(str)
    tx["Semaine"] = tx["Date"].dt.isocalendar().week.astype(int)
    tx["Jour_sem"]= tx["Date"].dt.day_name()
    tx["Mois_label"] = tx["Date"].dt.to_period("M").astype(str)
    tx["Réussi"]  = tx["Statut"] == "Succès"

    # — Clients —
    cl = pd.read_excel(xl, sheet_name="Clients")
    cl.columns = cl.columns.str.strip()
    cl["Date_Inscription"] = pd.to_datetime(cl["Date_Inscription"], errors="coerce")
    cl["Age"] = pd.to_numeric(cl["Age"], errors="coerce")

    # — Objectifs —
    obj = pd.read_excel(xl, sheet_name="Objectifs")
    obj.columns = obj.columns.str.strip()
    obj["Mois_num"] = obj["Mois"].map(MOIS_FR)
    if "N° Mois" in obj.columns:
        obj["Mois_num"] = obj["Mois_num"].fillna(obj["N° Mois"])

    # — Fusion Transactions + Clients —
    df = tx.merge(cl[["ID_Client","Nom","Prénom","Sexe","Age","Segment","Date_Inscription"]],
                on="ID_Client", how="left")
    df["Ancienneté_jours"] = (df["Date"] - df["Date_Inscription"]).dt.days

    # — Fusion avec Objectifs —
    date_max = df["Date"].max()
    obj["Année"] = df["Année"].max()          # hypothèse : objectifs sur l'année courante
    df = df.merge(obj[["Agence","Mois_num","Objectif_Montant (FCFA)","Objectif_Transactions",
                        "Taux_Commission_Cible (%)","Région"]],
                on=["Agence","Mois_num"], how="left")

    # — KPI dérivés —
    df["Commission_Rate (%)"] = np.where(df["Montant (FCFA)"] > 0,
                                         df["Commission (FCFA)"] / df["Montant (FCFA)"] * 100, 0)
    return df, cl, obj, date_max

import base64
from pathlib import Path

# ─── Chemins relatifs ───
APP_DIR = Path(__file__).parent

# ─── Image logo ───
def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except FileNotFoundError:
        return None

img_base64 = get_image_base64(APP_DIR / "image.png")

# ─── Sidebar ───
with st.sidebar:
    if img_base64:
        st.markdown(
            f'<img src="data:image/png;base64,{img_base64}" width="300">',
            unsafe_allow_html=True
        )
    else:
        st.markdown("## 💸 SankMoney")

    st.markdown(
        "<h2 style='color:white;margin:0'>💸 Dashboard Analytique</h2>",
        unsafe_allow_html=True
    )
    st.divider()
    uploaded = st.file_uploader("📂 Charger un autre fichier Excel (optionnel)", type=["xlsx"])

# ─── Fichier à charger ───
# Priorité : fichier uploadé par l'utilisateur, sinon la base par défaut du dépôt
FICHIER = uploaded if uploaded else APP_DIR / "Base_MobileMoney.xlsx"

try:
    df, cl, obj, date_max = charger_donnees(FICHIER)
except Exception as e:
    st.error(f"❌ Erreur de chargement : {e}")
    st.stop()



# ─────────────────────────────────────────────
#  SIDEBAR – FILTRES
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 Filtres")

    date_min_data = df["Date"].min().date()
    date_max_data = df["Date"].max().date()
    d1, d2 = st.date_input("📅 Période",
                            value=[date_min_data, date_max_data],
                            min_value=date_min_data, max_value=date_max_data)

    agences  = st.multiselect("🏢 Agence",  sorted(df["Agence"].dropna().unique()),  default=[])
    villes   = st.multiselect("📍 Ville",   sorted(df["Ville"].dropna().unique()),   default=[])
    produits = st.multiselect("📦 Produit", sorted(df["Produit"].dropna().unique()), default=[])
    canaux   = st.multiselect("📡 Canal",   sorted(df["Canal"].dropna().unique()),   default=[])
    segments = st.multiselect("👤 Segment", sorted(df["Segment"].dropna().unique()), default=[])
    statuts  = st.multiselect("✅ Statut",  sorted(df["Statut"].dropna().unique()),  default=[])

    st.divider()
    st.markdown("#### 📊 Granularité temporelle")
    granularite = st.radio("", ["Jour","Semaine","Mois","Trimestre"], index=2, horizontal=True)

# ─── Application des filtres ───
mask = (df["Date"].dt.date >= d1) & (df["Date"].dt.date <= d2)
if agences:  mask &= df["Agence"].isin(agences)
if villes:   mask &= df["Ville"].isin(villes)
if produits: mask &= df["Produit"].isin(produits)
if canaux:   mask &= df["Canal"].isin(canaux)
if segments: mask &= df["Segment"].isin(segments)
if statuts:  mask &= df["Statut"].isin(statuts)

dff = df[mask].copy()
dff_ok = dff[dff["Réussi"]].copy()   # transactions réussies uniquement

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def fmt_fcfa(v):
    """Format FCFA avec séparateurs de milliers."""
    try: return f"{int(v):,} FCFA".replace(",", " ")
    except: return "N/A"

def fmt_pct(v):
    try: return f"{v:.1f} %"
    except: return "N/A"

def kpi_card(label, value, delta=None, color=ORANGE):
    delta_html = ""
    if delta is not None:
        cls = "metric-delta-pos" if delta >= 0 else "metric-delta-neg"
        arrow = "▲" if delta >= 0 else "▼"
        delta_html = f'<div class="{cls}">{arrow} {abs(delta):.1f} % vs période préc.</div>'
    return f"""
    <div class="metric-card" style="border-left-color:{color}">
    <div class="metric-label">{label}</div>
    <div class="metric-value">{value}</div>
    {delta_html}
    </div>"""

def granularite_col(gran):
    mapping = {"Jour":"Date","Semaine":"Semaine","Mois":"Mois_label","Trimestre":"Trimestre"}
    return mapping[gran]

def export_excel(dataframe, nom="export"):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        dataframe.to_excel(w, index=False)
    buf.seek(0)
    return buf

def layout_plotly(fig, titre="", h=420):
    fig.update_layout(
        title=dict(text=titre, font=dict(size=14, color=BLEU), x=0.02),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Segoe UI, sans-serif", color="#333"),
        height=h, margin=dict(l=40,r=20,t=50,b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EEEEEE", zeroline=False)
    return fig

def couleur_atteinte(pct):
    if pct >= 100: return VERT
    if pct >= 80:  return JAUNE
    return ROUGE

# ─────────────────────────────────────────────
#  EN-TÊTE PRINCIPAL
# ─────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,{BLEU} 0%,#005099 60%,{ORANGE} 100%);
        padding:24px 32px;border-radius:16px;margin-bottom:20px;">
    <h1 style="color:white;margin:0;font-size:2rem">BIENVENUE SUR CE DASHBOARD D'ANALYSE ET DE PERFORMANCE DES 
        VENTES ET SERVICES MOBILE MONEY</h1>
    <p style="color:#FFD6B8;margin:4px 0 0">
        Ce tableau de bord sur des données stimulées vous permet d'explorer en profondeur les données de 
        transactions, clients et objectifs. Utilisez les filtres sur la gauche pour personnaliser votre 
        analyse. Découvrez les tendances clés, les performances par agence et commercial, 
        ainsi que l'atteinte des objectifs grâce à des visualisations claires et des indicateurs pertinents.
        Période : {d1.strftime('%d/%m/%Y')} → {d2.strftime('%d/%m/%Y')}
        &nbsp;|&nbsp; {len(dff):,} transactions filtrées
    </p>
    <p style="color:#FFD6B8;margin:10px 0 0;font-size:0.85rem;border-top:1px solid rgba(255,255,255,0.2);padding-top:8px;">
        ✍️ <b style="color:white;">Auteur :</b> Lassina SANOU &nbsp;|&nbsp;
        <a href="https://sanou-lassina.github.io/Ma_Page/" target="_blank"
            style="color:{ORANGE};font-weight:700;text-decoration:none;">
            📩 Pour me contacter, cliquez ici
        </a>
    </p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  CALCUL DES KPI PRINCIPAUX
# ─────────────────────────────────────────────
ca_total       = dff_ok["Montant (FCFA)"].sum()
nb_tx_total    = len(dff)
nb_tx_ok       = len(dff_ok)
taux_reussite  = nb_tx_ok / nb_tx_total * 100 if nb_tx_total > 0 else 0
commission_tot = dff_ok["Commission (FCFA)"].sum()
clients_actifs = dff_ok["ID_Client"].nunique()
panier_moyen   = ca_total / nb_tx_ok if nb_tx_ok > 0 else 0
revenu_client  = ca_total / clients_actifs if clients_actifs > 0 else 0
frequence      = nb_tx_ok / clients_actifs if clients_actifs > 0 else 0

obj_montant  = dff_ok["Objectif_Montant (FCFA)"].sum()
obj_tx       = dff_ok["Objectif_Transactions"].sum()
taux_att_m   = ca_total / obj_montant * 100 if obj_montant > 0 else 0
taux_att_t   = nb_tx_ok / obj_tx * 100 if obj_tx > 0 else 0

# Croissance MoM
mois_uniques = sorted(dff_ok["Mois_label"].drop_duplicates().astype(str))
if len(mois_uniques) >= 2:
    mois_courant = dff_ok[dff_ok["Mois_label"] == mois_uniques[-1]]
    mois_prec    = dff_ok[dff_ok["Mois_label"] == mois_uniques[-2]]
else:
    mois_courant = dff_ok[dff_ok["Mois_label"] == mois_uniques[-1]]
    mois_prec    = mois_courant  # Évite l'erreur si un seul mois

ca_courant   = mois_courant["Montant (FCFA)"].sum()
ca_prec_m    = mois_prec["Montant (FCFA)"].sum()
mom          = (ca_courant - ca_prec_m) / ca_prec_m * 100 if ca_prec_m > 0 else 0

# ─────────────────────────────────────────────
#  ONGLETS
# ─────────────────────────────────────────────
tabs = st.tabs([
    "📌 Vue Générale",
    "📈 Analyse Temporelle",
    "🏢 Agences & Commerciaux",
    "📦 Produits & Canaux",
    "👥 Clients & CRM",
    "⚠️ Qualité & Échecs",
])

# ══════════════════════════════════════════════
#  ONGLET 1 — VUE GÉNÉRALE
# ══════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="section-title">📌 Indicateurs Clés de Performance</div>', unsafe_allow_html=True)

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.markdown(kpi_card("💰 Chiffre d'Affaires", fmt_fcfa(ca_total), mom), unsafe_allow_html=True)
    c2.markdown(kpi_card("🔢 Transactions Réussies", f"{nb_tx_ok:,} / {nb_tx_total:,}", color=VERT), unsafe_allow_html=True)
    c3.markdown(kpi_card("✅ Taux de Réussite", fmt_pct(taux_reussite), color=VERT if taux_reussite>=80 else ROUGE), unsafe_allow_html=True)
    c4.markdown(kpi_card("💵 Commission Totale", fmt_fcfa(commission_tot), color=VIOLET), unsafe_allow_html=True)
    c5.markdown(kpi_card("👥 Clients Actifs", f"{clients_actifs:,}", color=BLEU), unsafe_allow_html=True)

    c6,c7,c8,c9,c10 = st.columns(5)
    c6.markdown(kpi_card("🛒 Panier Moyen", fmt_fcfa(panier_moyen), color=ORANGE), unsafe_allow_html=True)
    c7.markdown(kpi_card("👤 Revenu / Client", fmt_fcfa(revenu_client), color=ORANGE), unsafe_allow_html=True)
    c8.markdown(kpi_card("🔁 Fréquence d'Achat", f"{frequence:.1f} tx/client", color=JAUNE), unsafe_allow_html=True)
    c9.markdown(kpi_card("🎯 Atteinte Montant", fmt_pct(taux_att_m),
                        color=VERT if taux_att_m>=100 else (JAUNE if taux_att_m>=80 else ROUGE)), unsafe_allow_html=True)
    c10.markdown(kpi_card("🎯 Atteinte Transactions", fmt_pct(taux_att_t),
                        color=VERT if taux_att_t>=100 else (JAUNE if taux_att_t>=80 else ROUGE)), unsafe_allow_html=True)

    st.divider()

    # ─── Tableau récapitulatif par agence ───
    st.markdown('<div class="section-title">🏢 Récapitulatif par Agence</div>', unsafe_allow_html=True)

    resume_ag = dff_ok.groupby("Agence").agg(
        CA=("Montant (FCFA)","sum"),
        Transactions=("ID_Transaction","count"),
        Commission=("Commission (FCFA)","sum"),
        Clients=("ID_Client","nunique"),
        Obj_Montant=("Objectif_Montant (FCFA)","sum"),
        Obj_Tx=("Objectif_Transactions","sum"),
    ).reset_index()
    resume_ag["Panier_Moyen"] = resume_ag["CA"] / resume_ag["Transactions"]
    resume_ag["Taux_Montant_%"] = (resume_ag["CA"] / resume_ag["Obj_Montant"] * 100).round(1)
    resume_ag["Taux_Tx_%"]     = (resume_ag["Transactions"] / resume_ag["Obj_Tx"] * 100).round(1)
    resume_ag = resume_ag.sort_values("CA", ascending=False)

    def colorize_pct(val):
        c = VERT if val >= 100 else (JAUNE if val >= 80 else ROUGE)
        return f"background-color:{c};color:white;border-radius:6px;padding:2px 8px;font-weight:700"

    display_ag = resume_ag.copy()
    display_ag["CA"]          = display_ag["CA"].apply(lambda x: f"{x:,.0f}".replace(",", " "))
    display_ag["Commission"]  = display_ag["Commission"].apply(lambda x: f"{x:,.0f}".replace(",", " "))
    display_ag["Panier_Moyen"]= display_ag["Panier_Moyen"].apply(lambda x: f"{x:,.0f}".replace(",", " "))

    st.dataframe(
        display_ag[["Agence","CA","Transactions","Commission","Clients","Panier_Moyen","Taux_Montant_%","Taux_Tx_%"]],
        use_container_width=True, hide_index=True
    )

    buf = export_excel(resume_ag, "recap_agence")
    st.download_button("⬇️ Exporter ce tableau (Excel)", buf, "recap_agences.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ─── Profil Performance par Agence – 5 graphiques ───
    st.markdown('<div class="section-title">📊 Profil Performance par Agence</div>', unsafe_allow_html=True)

    metriques = [
        {"col": "CA",             "label": "CA (M FCFA)",  "diviseur": 1e6, "format": ".2f", "unite": "M FCFA"},
        {"col": "Transactions",   "label": "Transactions", "diviseur": 1,   "format": ",",   "unite": "Tx"},
        {"col": "Clients",        "label": "Clients",      "diviseur": 1,   "format": ",",   "unite": "clients"},
        {"col": "Taux_Montant_%", "label": "Taux M%",      "diviseur": 1,   "format": ".1f", "unite": "%"},
        {"col": "Taux_Tx_%",      "label": "Taux Tx%",     "diviseur": 1,   "format": ".1f", "unite": "%"},
    ]

    agences_list = list(resume_ag["Agence"])
    couleurs_ag  = [PALETTE[i % len(PALETTE)] for i in range(len(agences_list))]

    # ── Ligne 1 : CA | Transactions | Clients ──
    col1, col2, col3 = st.columns(3)
    for idx, (met, col) in enumerate(zip(metriques[:3], [col1, col2, col3])):
        valeurs = resume_ag[met["col"]] / met["diviseur"]
        fig = go.Figure(go.Bar(
            x=agences_list, y=valeurs,
            marker_color=couleurs_ag,
            text=[f"{v:{met['format']}} {met['unite']}" for v in valeurs],
            textposition="outside",
            hovertemplate=f"<b>%{{x}}</b><br>{met['label']}: %{{y:{met['format']}}} {met['unite']}<extra></extra>",
        ))
        fig.update_layout(
            title=dict(text=met["label"], font=dict(size=14, color=BLEU)),
            height=320, paper_bgcolor="white", plot_bgcolor="white",
            font=dict(color=BLEU), margin=dict(l=10, r=10, t=40, b=20),
            yaxis=dict(showgrid=True, gridcolor="#e8ecf4", zeroline=False),
            xaxis=dict(tickangle=-30), showlegend=False,
        )
        with col:
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("<hr style='border:1px solid #e8ecf4;margin:4px 0'>", unsafe_allow_html=True)

    # ── Ligne 2 : Taux M% | Taux Tx% ──
    col4, col5 = st.columns(2)
    for idx, (met, col) in enumerate(zip(metriques[3:], [col4, col5])):
        valeurs = resume_ag[met["col"]] / met["diviseur"]
        fig = go.Figure(go.Bar(
            x=agences_list, y=valeurs,
            marker_color=couleurs_ag,
            text=[f"{v:{met['format']}} {met['unite']}" for v in valeurs],
            textposition="outside",
            hovertemplate=f"<b>%{{x}}</b><br>{met['label']}: %{{y:{met['format']}}} {met['unite']}<extra></extra>",
        ))
        fig.add_hline(y=100, line_dash="dot", line_color=ROUGE,
                      annotation_text="Objectif 100%", annotation_position="top right")
        fig.update_layout(
            title=dict(text=met["label"], font=dict(size=14, color=BLEU)),
            height=340, paper_bgcolor="white", plot_bgcolor="white",
            font=dict(color=BLEU), margin=dict(l=10, r=10, t=40, b=20),
            yaxis=dict(showgrid=True, gridcolor="#e8ecf4", zeroline=False, ticksuffix=" %"),
            xaxis=dict(tickangle=-30), showlegend=False,
        )
        with col:
            st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════
#  ONGLET 2 — ANALYSE TEMPORELLE
# ══════════════════════════════════════════════
with tabs[1]:
    st.markdown('<div class="section-title">📈 Évolution du Chiffre d\'Affaires</div>', unsafe_allow_html=True)

    gcol = granularite_col(granularite)
    ts_ca = dff_ok.groupby(gcol).agg(CA=("Montant (FCFA)","sum"), Tx=("ID_Transaction","count")).reset_index()
    ts_ca = ts_ca.sort_values(gcol)
    ts_ca["CA_Cumulé"] = ts_ca["CA"].cumsum()

    c1, c2 = st.columns(2)
    with c1:
        fig1 = px.area(ts_ca, x=gcol, y="CA", color_discrete_sequence=[ORANGE],
                    labels={"CA":"Montant (FCFA)"})
        fig1.update_traces(line_color=ORANGE, fillcolor=f"rgba(255,107,44,0.15)", line_width=2.5)
        st.plotly_chart(layout_plotly(fig1, f"CA par {granularite}"), use_container_width=True)

    with c2:
        fig2 = px.bar(ts_ca, x=gcol, y="Tx", color_discrete_sequence=[VERT],
                    labels={"Tx":"Nombre de transactions"})
        st.plotly_chart(layout_plotly(fig2, f"Transactions par {granularite}"), use_container_width=True)

    # ─── CA cumulé ───
    fig_cum = px.line(ts_ca, x=gcol, y="CA_Cumulé", color_discrete_sequence=[BLEU],
                    labels={"CA_Cumulé":"CA Cumulé (FCFA)"}, markers=True)
    fig_cum.update_traces(line_width=2.5)
    fig_cum.add_scatter(x=ts_ca[gcol], y=ts_ca["CA_Cumulé"], fill="tozeroy",
                        fillcolor="rgba(0,51,102,0.08)", line_color="rgba(0,0,0,0)", showlegend=False)
    st.plotly_chart(layout_plotly(fig_cum, "📈 Croissance cumulative du CA", h=350), use_container_width=True)

    # ─── CA vs Objectif par mois ───
    st.markdown('<div class="section-title">🎯 CA Réel vs Objectif par Mois & Agence</div>', unsafe_allow_html=True)
    vs_obj = dff_ok.groupby(["Mois_label","Agence"]).agg(
        CA=("Montant (FCFA)","sum"),
        Objectif=("Objectif_Montant (FCFA)","sum")
    ).reset_index().sort_values("Mois_label")

    fig_obj = go.Figure()
    for ag in vs_obj["Agence"].unique():
        sub = vs_obj[vs_obj["Agence"]==ag]
        fig_obj.add_trace(go.Bar(name=f"CA – {ag}", x=sub["Mois_label"], y=sub["CA"],
                                marker_color=PALETTE[list(vs_obj["Agence"].unique()).index(ag)%len(PALETTE)]))
        fig_obj.add_trace(go.Scatter(name=f"Obj – {ag}", x=sub["Mois_label"], y=sub["Objectif"],
                                    mode="lines+markers", line=dict(dash="dot", width=1.5),
                                    marker_symbol="diamond"))
    fig_obj.update_layout(barmode="stack", height=420, paper_bgcolor="white",
                        font=dict(color=BLEU), margin=dict(l=20,r=20,t=40,b=40),
                        xaxis_title="Mois", yaxis_title="FCFA")
    st.plotly_chart(fig_obj, use_container_width=True)

    # ─── Heatmap activité ───
    st.markdown('<div class="section-title">🗓️ Heatmap – Activité par Mois & Jour</div>', unsafe_allow_html=True)
    jours_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    jours_fr    = ["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"]
    heat = dff_ok.groupby(["Mois_label","Jour_sem"]).agg(CA=("Montant (FCFA)","sum")).reset_index()
    heat_pivot = heat.pivot_table(index="Jour_sem", columns="Mois_label", values="CA", fill_value=0)
    heat_pivot = heat_pivot.reindex([j for j in jours_order if j in heat_pivot.index])

    fig_heat = px.imshow(heat_pivot, color_continuous_scale=[[0,"white"],[0.5,JAUNE],[1,ORANGE]],
                        labels={"color":"CA (FCFA)"},
                        y=[jours_fr[jours_order.index(j)] for j in heat_pivot.index
                            if j in jours_order])
    fig_heat.update_layout(height=320, paper_bgcolor="white", margin=dict(l=60,r=20,t=30,b=40))
    st.plotly_chart(fig_heat, use_container_width=True)

    # ─── Saisonnalité ───
    st.markdown('<div class="section-title">📅 Saisonnalité – Mois les plus Performants</div>', unsafe_allow_html=True)
    saison = dff_ok.groupby("Mois_label")["Montant (FCFA)"].sum().reset_index().sort_values("Montant (FCFA)", ascending=True)
    fig_saison = px.bar(saison, x="Montant (FCFA)", y="Mois_label", orientation="h",
                        color="Montant (FCFA)", color_continuous_scale=[GRIS, ORANGE, BLEU],
                        labels={"Montant (FCFA)":"CA (FCFA)","Mois_label":"Mois"})
    st.plotly_chart(layout_plotly(fig_saison, "Classement des Mois par CA", h=380), use_container_width=True)


# ══════════════════════════════════════════════
#  ONGLET 3 — AGENCES & COMMERCIAUX
# ══════════════════════════════════════════════
with tabs[2]:
    st.markdown('<div class="section-title">🏢 Performance des Agences</div>', unsafe_allow_html=True)

    # ─── Bar chart classement agences ───
    ag_rank = dff_ok.groupby("Agence")["Montant (FCFA)"].sum().reset_index().sort_values("Montant (FCFA)")
    fig_ag = px.bar(ag_rank, x="Montant (FCFA)", y="Agence", orientation="h",
                    color="Montant (FCFA)", color_continuous_scale=[VERT, ORANGE, BLEU],
                    labels={"Montant (FCFA)":"CA (FCFA)","Agence":"Agence"})
    st.plotly_chart(layout_plotly(fig_ag, "🏆 Classement des Agences par CA"), use_container_width=True)

    # ─── Taux atteinte ───
    ag_att = dff_ok.groupby("Agence").agg(
        CA=("Montant (FCFA)","sum"), Obj=("Objectif_Montant (FCFA)","sum"),
        Tx=("ID_Transaction","count"), ObjTx=("Objectif_Transactions","sum")
    ).reset_index()
    ag_att["Taux_%"] = (ag_att["CA"] / ag_att["Obj"] * 100).round(1)
    ag_att["Taux_Tx_%"] = (ag_att["Tx"] / ag_att["ObjTx"] * 100).round(1)
    ag_att["Couleur"] = ag_att["Taux_%"].apply(couleur_atteinte)

    c1, c2 = st.columns(2)
    with c1:
        fig_att = go.Figure()
        for _, r in ag_att.iterrows():
            fig_att.add_trace(go.Bar(
                name=r["Agence"], x=[r["Agence"]], y=[r["Taux_%"]],
                marker_color=r["Couleur"], text=f"{r['Taux_%']:.1f}%", textposition="outside"
            ))
        fig_att.add_hline(y=100, line_dash="dash", line_color=BLEU, annotation_text="Objectif 100%")
        fig_att.add_hline(y=80, line_dash="dot", line_color=JAUNE, annotation_text="Seuil 80%")
        fig_att.update_layout(showlegend=False, height=380, paper_bgcolor="white",
                            yaxis_title="Taux d'atteinte (%)", margin=dict(l=20,r=20,t=50,b=40),
                            title=dict(text="🎯 Taux d'Atteinte Objectif Montant", font=dict(color=BLEU)))
        st.plotly_chart(fig_att, use_container_width=True)

    with c2:
        fig_att2 = go.Figure()
        for _, r in ag_att.iterrows():
            fig_att2.add_trace(go.Bar(
                name=r["Agence"], x=[r["Agence"]], y=[r["Taux_Tx_%"]],
                marker_color=couleur_atteinte(r["Taux_Tx_%"]),
                text=f"{r['Taux_Tx_%']:.1f}%", textposition="outside"
            ))
        fig_att2.add_hline(y=100, line_dash="dash", line_color=BLEU, annotation_text="Objectif 100%")
        fig_att2.update_layout(showlegend=False, height=380, paper_bgcolor="white",
                                yaxis_title="Taux d'atteinte (%)", margin=dict(l=20,r=20,t=50,b=40),
                                title=dict(text="🎯 Taux d'Atteinte Objectif Transactions", font=dict(color=BLEU)))
        st.plotly_chart(fig_att2, use_container_width=True)

    # ─── Tableau interactif agences ───
    st.dataframe(ag_att[["Agence","CA","Obj","Tx","ObjTx","Taux_%","Taux_Tx_%"]].rename(columns={
        "CA":"CA Réel (FCFA)","Obj":"Obj. Montant (FCFA)","Tx":"Nb Tx","ObjTx":"Obj. Transactions",
        "Taux_%":"Taux Montant (%)","Taux_Tx_%":"Taux Transactions (%)"}),
        use_container_width=True, hide_index=True)

    st.divider()
    st.markdown('<div class="section-title">👔 Performance des Commerciaux</div>', unsafe_allow_html=True)

    com_stats = dff_ok.groupby("Commercial").agg(
        CA=("Montant (FCFA)","sum"),
        Tx=("ID_Transaction","count"),
        Commission=("Commission (FCFA)","sum"),
        Clients=("ID_Client","nunique")
    ).reset_index().sort_values("CA", ascending=False)

    top10 = com_stats.head(10)
    c1, c2 = st.columns(2)
    with c1:
        fig_com = px.bar(top10.sort_values("CA"), x="CA", y="Commercial", orientation="h",
                        color="CA", color_continuous_scale=[VERT, ORANGE],
                        labels={"CA":"CA (FCFA)","Commercial":"Commercial"})
        st.plotly_chart(layout_plotly(fig_com, "🏆 Top 10 Commerciaux par CA"), use_container_width=True)

    with c2:
        fig_sc = px.scatter(com_stats, x="Tx", y="CA", size="Commission",
                            color="Commission", color_continuous_scale=[VERT, ORANGE, BLEU],
                            hover_data=["Commercial","Clients"],
                            labels={"Tx":"Nb Transactions","CA":"CA (FCFA)","Commission":"Commission (FCFA)"})
        fig_sc.update_traces(marker=dict(opacity=0.8, sizemin=8))
        st.plotly_chart(layout_plotly(fig_sc, "💹 Transactions vs CA (taille = Commission)"), use_container_width=True)

    buf2 = export_excel(com_stats, "commerciaux")
    st.download_button("⬇️ Exporter Commerciaux (Excel)", buf2, "commerciaux.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ══════════════════════════════════════════════
#  ONGLET 4 — PRODUITS & CANAUX
# ══════════════════════════════════════════════
with tabs[3]:
    st.markdown('<div class="section-title">📦 Analyse par Produit</div>', unsafe_allow_html=True)

    prod_stats = dff_ok.groupby("Produit").agg(
        CA=("Montant (FCFA)","sum"),
        Tx=("ID_Transaction","count"),
        Commission=("Commission (FCFA)","sum"),
        Panier_Moyen=("Montant (FCFA)","mean")
    ).reset_index().sort_values("CA", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        fig_pie = px.pie(prod_stats, values="CA", names="Produit",
                        color_discrete_sequence=PALETTE, hole=0.42)
        fig_pie.update_traces(textposition="outside", textinfo="label+percent",
                            pull=[0.04]*len(prod_stats))
        fig_pie.update_layout(height=380, paper_bgcolor="white",
                            title=dict(text="🍩 Répartition du CA par Produit", font=dict(color=BLEU)))
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        fig_prod = px.bar(prod_stats, x="Produit", y=["CA","Panier_Moyen"],
                        barmode="group", color_discrete_sequence=[ORANGE, BLEU],
                        labels={"value":"FCFA","variable":"Indicateur"})
        st.plotly_chart(layout_plotly(fig_prod, "📊 CA & Panier Moyen par Produit"), use_container_width=True)

    # ─── Box plot ───
    fig_box = px.box(dff_ok, x="Produit", y="Montant (FCFA)", color="Produit",
                    color_discrete_sequence=PALETTE, notched=True,
                    labels={"Montant (FCFA)":"Montant (FCFA)"})
    fig_box.update_layout(showlegend=False, height=380, paper_bgcolor="white",
                        font=dict(color=BLEU), margin=dict(l=20,r=20,t=50,b=40),
                        title=dict(text="📦 Distribution des Montants par Produit", font=dict(color=BLEU)))
    st.plotly_chart(fig_box, use_container_width=True)

    # ─── Évolution mensuelle produits ───
    st.markdown('<div class="section-title">📅 Évolution Mensuelle du Mix Produits</div>', unsafe_allow_html=True)
    prod_ts = dff_ok.groupby(["Mois_label","Produit"])["Montant (FCFA)"].sum().reset_index().sort_values("Mois_label")
    fig_area = px.area(prod_ts, x="Mois_label", y="Montant (FCFA)", color="Produit",
                        color_discrete_sequence=PALETTE,
                        labels={"Mois_label":"Mois","Montant (FCFA)":"CA (FCFA)"})
    st.plotly_chart(layout_plotly(fig_area, "📈 Stacked Area – Produits dans le temps", h=400), use_container_width=True)

    st.divider()
    st.markdown('<div class="section-title">📡 Analyse par Canal</div>', unsafe_allow_html=True)

    canal_stats = dff_ok.groupby("Canal").agg(
        CA=("Montant (FCFA)","sum"),
        Tx=("ID_Transaction","count"),
        Taux_Reussite=("Réussi","mean")
    ).reset_index()
    canal_stats["Taux_Reussite"] = (canal_stats["Taux_Reussite"]*100).round(1)

    c1, c2 = st.columns(2)
    with c1:
        fig_canal = px.bar(canal_stats, x="Canal", y="Tx", color="Canal",
                            color_discrete_sequence=PALETTE,
                            labels={"Tx":"Nombre de Transactions"}, text="Tx")
        st.plotly_chart(layout_plotly(fig_canal, "📡 Transactions par Canal"), use_container_width=True)

    with c2:
        fig_canal2 = px.pie(canal_stats, values="CA", names="Canal",
                            color_discrete_sequence=PALETTE, hole=0.35)
        fig_canal2.update_layout(height=380, paper_bgcolor="white",
                                title=dict(text="Répartition CA par Canal", font=dict(color=BLEU)))
        st.plotly_chart(fig_canal2, use_container_width=True)

    # ─── Tableau croisé Produit × Canal ───
    st.markdown('<div class="section-title">🔀 Tableau Croisé Produit × Canal</div>', unsafe_allow_html=True)
    cross = dff_ok.pivot_table(index="Produit", columns="Canal",
                                values="Montant (FCFA)", aggfunc="sum", fill_value=0)
    cross_fmt = cross.map(lambda x: f"{int(x):,}".replace(",", " ") if x > 0 else "–")
    st.dataframe(cross_fmt, use_container_width=True)


# ══════════════════════════════════════════════
#  ONGLET 5 — CLIENTS & CRM
# ══════════════════════════════════════════════
with tabs[4]:
    st.markdown('<div class="section-title">👥 Démographie des Clients</div>', unsafe_allow_html=True)

    cl_tx = dff_ok[["ID_Client","Montant (FCFA)","ID_Transaction","Date"]].merge(
        cl[["ID_Client","Sexe","Age","Segment","Date_Inscription","Ville"]],
        on="ID_Client", how="left"
    )

    c1, c2 = st.columns(2)
    with c1:
        # Distribution âge
        fig_age = px.histogram(cl_tx.drop_duplicates("ID_Client"), x="Age", nbins=20,
                                color="Sexe", color_discrete_map={"M":BLEU,"F":ORANGE,"X":GRIS},
                                labels={"Age":"Âge","count":"Nb Clients"}, barmode="overlay", opacity=0.75)
        st.plotly_chart(layout_plotly(fig_age, "👶 Distribution par Âge et Sexe"), use_container_width=True)

    with c2:
        seg_ca = cl_tx.groupby("Segment").agg(CA=("Montant (FCFA)","sum"), Clients=("ID_Client","nunique")).reset_index()
        fig_seg = px.bar(seg_ca, x="Segment", y="CA", color="Segment",
                        color_discrete_sequence=PALETTE, text=seg_ca["Clients"].apply(lambda x: f"{x} clients"))
        st.plotly_chart(layout_plotly(fig_seg, "👤 CA et Clients par Segment"), use_container_width=True)

    # ─── Clients nouveaux vs récurrents ───
    st.markdown('<div class="section-title">📅 Nouveaux Clients vs Récurrents par Mois</div>', unsafe_allow_html=True)
    premiere_tx = dff_ok.groupby("ID_Client")["Date"].min().reset_index()
    premiere_tx.columns = ["ID_Client","Première_Tx"]
    dff_ok2 = dff_ok.merge(premiere_tx, on="ID_Client")
    dff_ok2["Type_Client"] = np.where(
        dff_ok2["Date"].dt.to_period("M") == dff_ok2["Première_Tx"].dt.to_period("M"),
        "Nouveau", "Récurrent"
    )
    nc_rec = dff_ok2.groupby(["Mois_label","Type_Client"])["ID_Client"].nunique().reset_index().sort_values("Mois_label")
    fig_nc = px.bar(nc_rec, x="Mois_label", y="ID_Client", color="Type_Client",
                    color_discrete_map={"Nouveau":ORANGE,"Récurrent":VERT}, barmode="group",
                    labels={"ID_Client":"Nb Clients","Mois_label":"Mois","Type_Client":"Type"})
    st.plotly_chart(layout_plotly(fig_nc, "🆕 Nouveaux vs Récurrents"), use_container_width=True)

    # ─── Analyse RFM ───
    st.markdown('<div class="section-title">💎 Analyse RFM (Récence – Fréquence – Montant)</div>', unsafe_allow_html=True)
    ref_date = dff_ok["Date"].max()
    rfm = dff_ok.groupby("ID_Client").agg(
        Récence=("Date", lambda x: (ref_date - x.max()).days),
        Fréquence=("ID_Transaction","count"),
        Montant=("Montant (FCFA)","sum")
    ).reset_index()
    rfm = rfm.merge(cl[["ID_Client","Segment","Nom","Prénom"]], on="ID_Client", how="left")

    fig_rfm = px.scatter(rfm, x="Fréquence", y="Montant", color="Segment",
                        size="Récence", hover_data=["Nom","Prénom","Récence"],
                        color_discrete_sequence=PALETTE, opacity=0.75,
                        labels={"Fréquence":"Fréquence d'achat","Montant":"CA Total (FCFA)"})
    fig_rfm.update_traces(marker=dict(sizemin=6))
    st.plotly_chart(layout_plotly(fig_rfm, "💎 Scatter RFM – Fréquence vs Montant (taille = Récence)", h=420),
                    use_container_width=True)

    # ─── Top 10 clients ───
    st.markdown('<div class="section-title">🏆 Top 10 Clients par CA</div>', unsafe_allow_html=True)
    top_clients = rfm.nlargest(10, "Montant")[["Nom","Prénom","Segment","Fréquence","Montant","Récence"]]
    top_clients["Montant"] = top_clients["Montant"].apply(lambda x: f"{x:,.0f}".replace(",", " "))
    st.dataframe(top_clients, use_container_width=True, hide_index=True)

    buf3 = export_excel(rfm, "rfm")
    st.download_button("⬇️ Exporter Analyse RFM (Excel)", buf3, "rfm_clients.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ══════════════════════════════════════════════
#  ONGLET 6 — QUALITÉ & ÉCHECS
# ══════════════════════════════════════════════
with tabs[5]:
    st.markdown('<div class="section-title">⚠️ Rapport Qualité des Données</div>', unsafe_allow_html=True)

    manquants = df.isnull().sum()
    manquants = manquants[manquants > 0].reset_index()
    manquants.columns = ["Colonne","Valeurs Manquantes"]
    manquants["% Manquant"] = (manquants["Valeurs Manquantes"] / len(df) * 100).round(2)
    if len(manquants) > 0:
        st.dataframe(manquants, use_container_width=True, hide_index=True)
    else:
        st.success("✅ Aucune valeur manquante détectée dans les données filtrées !")

    st.divider()
    st.markdown('<div class="section-title">❌ Analyse des Transactions Échouées</div>', unsafe_allow_html=True)

    dff_fail = dff[dff["Statut"].isin(["Échoué","En Attente"])].copy()

    # KPI échecs
    c1,c2,c3 = st.columns(3)
    c1.markdown(kpi_card("❌ Transactions Échouées", f"{len(dff_fail[dff_fail['Statut']=='Échoué']):,}", color=ROUGE), unsafe_allow_html=True)
    c2.markdown(kpi_card("⏳ En Attente", f"{len(dff_fail[dff_fail['Statut']=='En Attente']):,}", color=JAUNE), unsafe_allow_html=True)
    c3.markdown(kpi_card("💸 Montant Potentiel Perdu", fmt_fcfa(dff_fail["Montant (FCFA)"].sum()), color=ROUGE), unsafe_allow_html=True)

    # ─── Taux d'échec par axe ───
    axes = {"Agence":"Agence","Produit":"Produit","Canal":"Canal","Commercial":"Commercial"}
    axe_choisi = st.selectbox("📊 Analyser les échecs par :", list(axes.keys()))
    col = axes[axe_choisi]

    fail_grp = dff.groupby(col).agg(
        Total=("ID_Transaction","count"),
        Echecs=("Statut", lambda x: (x == "Échoué").sum()),
        Attente=("Statut", lambda x: (x == "En Attente").sum()),
        Montant_Perdu=("Montant (FCFA)", lambda x: x[dff.loc[x.index,"Statut"]=="Échoué"].sum())
    ).reset_index()
    fail_grp["Taux_Echec_%"] = (fail_grp["Echecs"] / fail_grp["Total"] * 100).round(1)
    fail_grp = fail_grp.sort_values("Taux_Echec_%", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        fig_fail = px.bar(fail_grp, x=col, y="Taux_Echec_%", color="Taux_Echec_%",
                        color_continuous_scale=[[0,VERT],[0.5,JAUNE],[1,ROUGE]],
                        labels={"Taux_Echec_%":"Taux d'échec (%)"},
                        text=fail_grp["Taux_Echec_%"].apply(lambda x: f"{x:.1f}%"))
        fig_fail.update_traces(textposition="outside")
        st.plotly_chart(layout_plotly(fig_fail, f"Taux d'Échec par {axe_choisi}"), use_container_width=True)

    with c2:
        fig_perdu = px.bar(fail_grp.sort_values("Montant_Perdu", ascending=True),
                            x="Montant_Perdu", y=col, orientation="h",
                            color="Montant_Perdu", color_continuous_scale=[JAUNE, ROUGE],
                            labels={"Montant_Perdu":"Montant Perdu (FCFA)"})
        st.plotly_chart(layout_plotly(fig_perdu, f"💸 Montant Potentiel Perdu par {axe_choisi}"), use_container_width=True)

    # ─── Évolution temporelle du taux d'échec ───
    st.markdown('<div class="section-title">📉 Évolution du Taux d\'Échec par Mois</div>', unsafe_allow_html=True)
    fail_ts = dff.groupby("Mois_label").agg(
        Total=("ID_Transaction","count"),
        Echecs=("Statut", lambda x: (x=="Échoué").sum())
    ).reset_index()
    fail_ts["Taux_%"] = (fail_ts["Echecs"] / fail_ts["Total"] * 100).round(1)
    fail_ts = fail_ts.sort_values("Mois_label")

    fig_fail_ts = go.Figure()
    fig_fail_ts.add_trace(go.Bar(x=fail_ts["Mois_label"], y=fail_ts["Total"],
                                name="Total Transactions", marker_color="lightgray"))
    fig_fail_ts.add_trace(go.Scatter(x=fail_ts["Mois_label"], y=fail_ts["Taux_%"],
                                    name="Taux d'Échec (%)", mode="lines+markers",
                                    line=dict(color=ROUGE, width=2.5), yaxis="y2",
                                    marker=dict(size=8, color=ROUGE)))
    fig_fail_ts.update_layout(
        yaxis=dict(title="Nb Transactions"),
        yaxis2=dict(title="Taux d'Échec (%)", overlaying="y", side="right", showgrid=False),
        height=380, paper_bgcolor="white", font=dict(color=BLEU),
        title=dict(text="Transactions Totales vs Taux d'Échec", font=dict(color=BLEU)),
        legend=dict(x=0.01, y=0.99), margin=dict(l=40,r=50,t=50,b=40)
    )
    st.plotly_chart(fig_fail_ts, use_container_width=True)

    # ─── Tableau détail échecs ───
    st.markdown('<div class="section-title">📋 Détail des Transactions Échouées</div>', unsafe_allow_html=True)
    detail_fail = dff[dff["Statut"]=="Échoué"][
        ["Date","Agence","Commercial","Produit","Canal","Montant (FCFA)","Statut","ID_Client"]
    ].sort_values("Date", ascending=False)
    st.dataframe(detail_fail, use_container_width=True, hide_index=True)
    buf4 = export_excel(detail_fail, "echecs")
    st.download_button("⬇️ Exporter Transactions Échouées (Excel)", buf4, "transactions_echouees.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ─────────────────────────────────────────────
#  FOOTER
# ─────────────────────────────────────────────
st.divider()
st.markdown(f"""
<div style="text-align:center;color:#999;font-size:0.78rem;padding:10px">
    💸 <b>Mobile Money</b> – Dashboard Analytique des Ventes &nbsp;|&nbsp; Burkina Faso &nbsp;|&nbsp;
    Données : {date_min_data.strftime('%d/%m/%Y')} → {date_max_data.strftime('%d/%m/%Y')} &nbsp;|&nbsp;
    Généré avec des données stimulées
</div>
""", unsafe_allow_html=True)
