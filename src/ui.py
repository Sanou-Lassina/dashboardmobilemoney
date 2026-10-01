"""Interface partagée : style, formats, filtres de la barre latérale, contexte d'analyse, exports."""
import io
from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st

from . import config as C
from . import kpis

CSS = f"""
<style>
  .block-container {{padding-top: 2.2rem;}}
  h1, h2, h3 {{color: {C.BLEU};}}
  [data-testid="stSidebar"] {{background: #F0F2F6;}}
  div[data-testid="stMetricValue"] {{color: {C.BLEU}; font-weight: 800;}}
  div[data-testid="stMetricLabel"] p {{font-size: .82rem; color: #4B5563;}}
  .section-title {{font-size: 1.2rem; font-weight: 800; color: {C.BLEU};
        border-bottom: 3px solid {C.ORANGE}; padding-bottom: 5px; margin: 22px 0 12px 0;}}
  .bandeau {{background: linear-gradient(135deg, {C.BLEU} 0%, #005099 65%, {C.ORANGE} 100%);
        padding: 14px 22px; border-radius: 14px; margin-bottom: 14px; color: white;}}
  .bandeau b {{color: white;}} .bandeau span {{color: #FFD6B8; font-size: .88rem;}}
  .pied {{text-align: center; color: #8A93A0; font-size: .78rem; padding: 6px;}}
  .pied a {{color: {C.ORANGE}; font-weight: 700; text-decoration: none;}}
  .stTabs [data-baseweb="tab"] {{font-weight: 600;}}
  .stTabs [aria-selected="true"] {{color: {C.ORANGE} !important;}}
</style>
"""


def appliquer_style():
    st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  Formats français
# ─────────────────────────────────────────────
def fr(x, nd: int = 0) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/d"
    return f"{x:,.{nd}f}".replace(",", "\u202f").replace(".", ",")


def fmt_fcfa(v, compact: bool = True) -> str:
    if v is None or pd.isna(v):
        return "n/d"
    a = abs(v)
    if compact and a >= 1e9:
        return f"{fr(v / 1e9, 2)} Md FCFA"
    if compact and a >= 1e6:
        return f"{fr(v / 1e6, 1)} M FCFA"
    return f"{fr(v, 0)} FCFA"


def fmt_pct(v, nd: int = 1) -> str:
    return "n/d" if v is None or pd.isna(v) else f"{fr(v, nd)} %"


def metrique(col, label: str, valeur: str, delta=None, bon_si_hausse: bool = True, aide: str | None = None):
    """Carte KPI native Streamlit ; delta en % (None = pas de comparaison)."""
    d = None
    if delta is not None and not pd.isna(delta):
        d = f"{'+' if delta >= 0 else '−'}{fr(abs(delta), 1)} %"
    col.metric(label, valeur, delta=d, delta_color="normal" if bon_si_hausse else "inverse", help=aide, border=True)


def titre_section(texte: str):
    st.markdown(f'<div class="section-title">{texte}</div>', unsafe_allow_html=True)


def export_excel(feuilles: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for nom, d in feuilles.items():
            d.to_excel(w, sheet_name=nom[:31], index=False)
    return buf.getvalue()


def bouton_export(label: str, feuilles: dict[str, pd.DataFrame], fichier: str, cle: str):
    st.download_button(f"⬇️ {label}", export_excel(feuilles), fichier, key=cle,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ─────────────────────────────────────────────
#  Contexte d'analyse (calculé une fois par exécution, lu par toutes les pages)
# ─────────────────────────────────────────────
@dataclass
class Contexte:
    donnees: dict
    filtres: dict
    d1: pd.Timestamp
    d2: pd.Timestamp
    mode_comp: str
    p1: pd.Timestamp | None
    p2: pd.Timestamp | None
    dimf: pd.DataFrame        # filtres dimensionnels appliqués, TOUTES dates
    dff: pd.DataFrame         # + période
    dff_ok: pd.DataFrame      # transactions réussies de la période
    prev: pd.DataFrame        # période de comparaison (vide si indisponible)
    prev_ok: pd.DataFrame
    agences_scope: list
    objectifs_pertinents: bool
    cl_f: pd.DataFrame        # clients filtrés (agence / ville / segment)
    hist_ok: pd.DataFrame     # succès de ces clients jusqu'à d2 (cycle de vie)

    @property
    def has_prev(self) -> bool:
        return len(self.prev) > 0

    @property
    def df(self): return self.donnees["df"]
    @property
    def cl(self): return self.donnees["cl"]
    @property
    def obj(self): return self.donnees["obj"]
    @property
    def ag(self): return self.donnees["ag"]
    @property
    def dq(self): return self.donnees["dq"]
    @property
    def meta(self): return self.donnees["meta"]

    @property
    def libelle_periode(self) -> str:
        return f"{self.d1:%d/%m/%Y} → {self.d2:%d/%m/%Y}"


def get_ctx() -> Contexte:
    ctx = st.session_state.get("_ctx")
    if ctx is None:
        st.warning("Contexte non initialisé : ouvrez l'application depuis app.py.")
        st.stop()
    return ctx


# ─────────────────────────────────────────────
#  Filtres
# ─────────────────────────────────────────────
PRESETS = ["Toute la période", "12 derniers mois", "6 derniers mois", "3 derniers mois",
           "Dernier mois complet", "Personnalisée"]
MODES_COMP = ["Période précédente", "Même période N-1", "Aucune"]
CLES_MULTI = ["f_agences", "f_villes", "f_commerciaux", "f_produits", "f_canaux", "f_segments"]


def bornes_preset(preset: str, dmin: pd.Timestamp, dmax: pd.Timestamp):
    if preset == "Dernier mois complet":
        if dmax.normalize() == (dmax + pd.offsets.MonthEnd(0)).normalize():
            return dmax.replace(day=1), dmax
        fin = dmax.replace(day=1) - pd.Timedelta(days=1)
        return fin.replace(day=1), fin
    mois = {"12 derniers mois": 12, "6 derniers mois": 6, "3 derniers mois": 3}.get(preset)
    if mois:
        return max((dmax + pd.Timedelta(days=1)) - pd.DateOffset(months=mois), dmin), dmax
    return dmin, dmax


def _reinit():
    for k in CLES_MULTI:
        st.session_state[k] = []
    st.session_state["f_preset"] = PRESETS[0]
    st.session_state["f_comp"] = MODES_COMP[0]


def _multi(label: str, options: list, cle: str):
    st.session_state[cle] = [x for x in st.session_state.get(cle, []) if x in options]  # filtres en cascade
    return st.multiselect(label, options, key=cle, placeholder="Tous")


def filtrer_dimensions(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    m = pd.Series(True, index=df.index)
    for col, cle in [("Agence", "agences"), ("Ville", "villes"), ("Commercial", "commerciaux"),
                     ("Produit", "produits"), ("Canal", "canaux"), ("Segment", "segments")]:
        if f[cle]:
            m &= df[col].isin(f[cle])
    return df[m]


def construire_contexte(donnees: dict) -> Contexte:
    df, cl, meta = donnees["df"], donnees["cl"], donnees["meta"]
    dmin, dmax = meta["date_min"], meta["date_max"]
    st.session_state.setdefault("f_preset", PRESETS[0])
    st.session_state.setdefault("f_comp", MODES_COMP[0])

    with st.sidebar:
        st.markdown("### 🔍 Filtres")
        preset = st.selectbox("📅 Période", PRESETS, key="f_preset")
        if preset == "Personnalisée":
            sel = st.date_input("Dates", value=(dmin.date(), dmax.date()), min_value=dmin.date(),
                                max_value=dmax.date(), key="f_dates")
            if not (isinstance(sel, (list, tuple)) and len(sel) == 2):
                st.info("Choisissez une date de fin pour appliquer la période.")
                st.stop()
            d1, d2 = pd.Timestamp(sel[0]), pd.Timestamp(sel[1])
        else:
            d1, d2 = bornes_preset(preset, dmin, dmax)
        st.caption(f"{d1:%d/%m/%Y} → {d2:%d/%m/%Y}")
        mode = st.radio("🔁 Comparer à", MODES_COMP, key="f_comp")

        ag_sel = _multi("🏢 Agence", sorted(df["Agence"].unique()), "f_agences")
        base = df[df["Agence"].isin(ag_sel)] if ag_sel else df
        vi_sel = _multi("📍 Ville", sorted(base["Ville"].unique()), "f_villes")
        if vi_sel:
            base = base[base["Ville"].isin(vi_sel)]
        co_sel = _multi("👔 Commercial", sorted(base["Commercial"].unique()), "f_commerciaux")
        pr_sel = _multi("📦 Produit", sorted(df["Produit"].unique()), "f_produits")
        ca_sel = _multi("📡 Canal", sorted(df["Canal"].unique()), "f_canaux")
        se_sel = _multi("👤 Segment client", sorted(df["Segment"].unique()), "f_segments")
        st.button("↺ Réinitialiser les filtres", on_click=_reinit)

    f = {"agences": ag_sel, "villes": vi_sel, "commerciaux": co_sel, "produits": pr_sel, "canaux": ca_sel, "segments": se_sel}
    dimf = filtrer_dimensions(df, f)
    dff = kpis.tranche(dimf, d1, d2)
    if dff.empty or not dff["Réussi"].any():
        st.warning("Aucune transaction réussie pour ces filtres. Élargissez la période ou retirez un filtre.")
        st.stop()

    p1 = p2 = None
    prev = dimf.iloc[0:0]
    pp = kpis.periode_precedente(d1, d2, mode)
    if pp:
        p1, p2 = pd.Timestamp(pp[0]), pd.Timestamp(pp[1])
        if p1 >= dmin:
            prev = kpis.tranche(dimf, p1, p2)
        else:
            with st.sidebar:
                st.caption("ℹ️ Comparaison indisponible : la période de référence précède le début des données.")

    cl_f = cl
    if ag_sel:
        cl_f = cl_f[cl_f["Agence"].isin(ag_sel)]
    if vi_sel:
        cl_f = cl_f[cl_f["Ville"].isin(vi_sel)]
    if se_sel:
        cl_f = cl_f[cl_f["Segment"].isin(se_sel)]
    hist = df[df["Réussi"] & (df["Date"] < d2 + pd.Timedelta(days=1))]
    if len(cl_f) != len(cl):
        hist = hist[hist["ID_Client"].isin(cl_f["ID_Client"])]

    return Contexte(
        donnees=donnees, filtres=f, d1=d1, d2=d2, mode_comp=mode, p1=p1, p2=p2, dimf=dimf, dff=dff,
        dff_ok=dff[dff["Réussi"]], prev=prev, prev_ok=prev[prev["Réussi"]] if len(prev) else prev,
        agences_scope=sorted(dimf["Agence"].unique()),
        objectifs_pertinents=not (pr_sel or ca_sel or se_sel or co_sel), cl_f=cl_f, hist_ok=hist)


def avertissement_objectifs(ctx: Contexte):
    if not ctx.objectifs_pertinents:
        st.info("🎯 Les objectifs sont fixés par agence : avec un filtre Produit, Canal, Segment ou Commercial, "
                "les taux d'atteinte ne sont pas calculés (comparaison non pertinente).")


def bandeau(ctx: Contexte):
    comp = f" · comparé à {ctx.p1:%d/%m/%Y} → {ctx.p2:%d/%m/%Y}" if ctx.has_prev else ""
    st.markdown(f'<div class="bandeau"><b>💸 Dashboard Mobile Money – Pilotage des ventes et du réseau</b><br>'
                f'<span>Données simulées · {ctx.libelle_periode}{comp} · {fr(len(ctx.dff))} transactions filtrées</span></div>',
                unsafe_allow_html=True)


def pied_de_page():
    st.divider()
    st.markdown(
        '<div class="pied">💸 <b>Mobile Money</b> – Dashboard analytique · Burkina Faso · Données simulées · '
        'Auteur : Lassina SANOU – Data Analyst · '
        '<a href="https://sanou-lassina.github.io/Ma_Page/" target="_blank">Me contacter</a></div>',
        unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  Compatibilité entre versions de Streamlit (use_container_width → width="stretch")
# ─────────────────────────────────────────────
import inspect  # noqa: E402

_LARGEUR_PLOT = "width" in inspect.signature(st.plotly_chart).parameters
_LARGEUR_DF = "width" in inspect.signature(st.dataframe).parameters


def plot(fig, **kw):
    if _LARGEUR_PLOT:
        st.plotly_chart(fig, width="stretch", **kw)
    else:
        st.plotly_chart(fig, use_container_width=True, **kw)


def tableau(df, **kw):
    kw.setdefault("hide_index", True)
    if _LARGEUR_DF:
        st.dataframe(df, width="stretch", **kw)
    else:
        st.dataframe(df, use_container_width=True, **kw)
