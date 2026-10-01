"""
╔══════════════════════════════════════════════════════════════════════╗
║      MOBILE MONEY – DASHBOARD DE PILOTAGE (Burkina Faso)             ║
║      Point d'entrée : streamlit run app.py                           ║
╚══════════════════════════════════════════════════════════════════════╝
"""
import streamlit as st

from src import config as C
from src import data, ui

st.set_page_config(page_title="Mobile Money – Dashboard de pilotage", page_icon="💸", layout="wide",
                   initial_sidebar_state="expanded")
ui.appliquer_style()


@st.cache_resource(show_spinner="Chargement, contrôle qualité et nettoyage des données…")
def charger(octets: bytes | None, chemin: str, mtime: float):
    """Résultat partagé en lecture seule entre les sessions : ne jamais le modifier en place."""
    return data.charger_donnees(octets if octets is not None else chemin)


with st.sidebar:
    if C.LOGO.exists():
        st.image(str(C.LOGO), width=220)
    else:
        st.markdown("## 💸 Mobile Money")
    with st.expander("📂 Source des données"):
        fichier = st.file_uploader("Charger un autre classeur Excel (.xlsx)", type=["xlsx"],
                                   help="Feuilles attendues : Transactions, Clients, Objectifs (+ Agents, Indicateurs facultatives).")
    st.divider()

try:
    if fichier is not None:
        donnees = charger(fichier.getvalue(), fichier.name, 0.0)
    else:
        with st.spinner("Première exécution : génération du classeur de démonstration (≈ 30 s)…"):
            chemin = data.fichier_par_defaut()
        donnees = charger(None, str(chemin), chemin.stat().st_mtime)
except data.ErreurDonnees as e:
    st.error(f"❌ Fichier inutilisable : {e}")
    st.stop()
except Exception as e:  # noqa: BLE001
    st.error(f"❌ Erreur de chargement : {e}")
    st.stop()

ctx = ui.construire_contexte(donnees)          # filtres + garde-fou « aucune donnée »
st.session_state["_ctx"] = ctx

pages = [
    st.Page("vues/1_resume.py", title="Résumé exécutif", icon="📌", default=True),
    st.Page("vues/2_ventes.py", title="Ventes & Tendances", icon="📈"),
    st.Page("vues/3_produits.py", title="Produits & Canaux", icon="📦"),
    st.Page("vues/4_reseau.py", title="Réseau & Agences", icon="🏢"),
    st.Page("vues/5_clients.py", title="Clients & Rétention", icon="👥"),
    st.Page("vues/6_risques.py", title="Qualité de service & Risques", icon="⚠️"),
    st.Page("vues/7_cadre_suivi.py", title="Cadre de suivi & DQA", icon="🎯"),
]
try:
    navigation = st.navigation(pages, position="top")
except TypeError:                               # versions sans navigation horizontale
    navigation = st.navigation(pages)
navigation.run()
