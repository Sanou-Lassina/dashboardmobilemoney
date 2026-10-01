"""Chargement, nettoyage et enrichissement des données (sans dépendance à Streamlit).

Le classeur attendu contient les feuilles Transactions, Clients, Objectifs (obligatoires)
et Agents, Indicateurs (facultatives). Les colonnes facultatives absentes sont
reconstruites ou neutralisées, et chaque correction est tracée dans le journal.
"""
import io
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .dqa import controles_qualite

FEUILLES_OBLIGATOIRES = ["Transactions", "Clients", "Objectifs"]
ALIAS_STATUT = {
    "succès": C.STATUT_OK, "succes": C.STATUT_OK, "réussi": C.STATUT_OK, "reussi": C.STATUT_OK,
    "success": C.STATUT_OK, "échoué": C.STATUT_KO, "echoue": C.STATUT_KO, "échec": C.STATUT_KO,
    "echec": C.STATUT_KO, "failed": C.STATUT_KO, "en attente": C.STATUT_ATT,
    "attente": C.STATUT_ATT, "pending": C.STATUT_ATT,
}


class ErreurDonnees(Exception):
    """Fichier inutilisable (feuille ou colonne obligatoire manquante)."""


# ─────────────────────────────────────────────
#  Lecture
# ─────────────────────────────────────────────
def lire_classeur(source) -> dict[str, pd.DataFrame]:
    """source : chemin (str/Path) ou contenu binaire du fichier."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    xl = pd.ExcelFile(source)
    feuilles = {}
    for nom in xl.sheet_names:
        f = pd.read_excel(xl, sheet_name=nom)
        f.columns = f.columns.astype(str).str.strip()
        feuilles[nom.strip()] = f
    manquantes = [f for f in FEUILLES_OBLIGATOIRES if f not in feuilles]
    if manquantes:
        raise ErreurDonnees(f"Feuille(s) obligatoire(s) absente(s) : {', '.join(manquantes)}")
    colonnes_tx = ["Date", "ID_Transaction", "ID_Client", "Agence", "Produit", "Canal",
                   "Montant (FCFA)", "Commission (FCFA)", "Statut"]
    absentes = [c for c in colonnes_tx if c not in feuilles["Transactions"].columns]
    if absentes:
        raise ErreurDonnees(f"Colonne(s) absente(s) dans Transactions : {', '.join(absentes)}")
    return feuilles


# ─────────────────────────────────────────────
#  Nettoyage
# ─────────────────────────────────────────────
def _statut(serie: pd.Series) -> pd.Series:
    def f(x):
        return C.STATUT_INCONNU if pd.isna(x) else ALIAS_STATUT.get(str(x).strip().lower(), C.STATUT_INCONNU)
    return serie.astype(object).map(f)


def _nettoyer_transactions(tx: pd.DataFrame, journal: list) -> pd.DataFrame:
    tx = tx.copy()
    n0 = len(tx)
    tx["Date"] = pd.to_datetime(tx["Date"], errors="coerce")
    tx["Montant (FCFA)"] = pd.to_numeric(tx["Montant (FCFA)"], errors="coerce")
    tx["Commission (FCFA)"] = pd.to_numeric(tx["Commission (FCFA)"], errors="coerce")

    # doublons d'identifiant (on garde la 1re occurrence)
    avec_id = tx["ID_Transaction"].notna()
    dup = tx.duplicated(subset="ID_Transaction", keep="first") & avec_id
    if dup.any():
        journal.append(("warning", f"{int(dup.sum())} transaction(s) en doublon d'ID supprimée(s)."))
        tx = tx[~dup]

    # lignes inexploitables : date illisible, montant manquant / négatif / nul
    mauvais = tx["Date"].isna() | tx["Montant (FCFA)"].isna() | (tx["Montant (FCFA)"] <= 0)
    if mauvais.any():
        journal.append(("warning", f"{int(mauvais.sum())} ligne(s) supprimée(s) : date illisible ou montant manquant/nul/négatif."))
        tx = tx[~mauvais]

    tx["Statut"] = _statut(tx["Statut"])
    n_inc = int((tx["Statut"] == C.STATUT_INCONNU).sum())
    if n_inc:
        journal.append(("info", f"{n_inc} transaction(s) au statut manquant/inconnu : conservées (statut « Inconnu »), exclues des KPI de succès."))

    # commission
    tx["Commission (FCFA)"] = tx["Commission (FCFA)"].fillna(0).clip(lower=0)
    incoh = tx["Commission (FCFA)"] > tx["Montant (FCFA)"]
    if incoh.any():
        journal.append(("warning", f"{int(incoh.sum())} commission(s) supérieure(s) au montant : ramenée(s) à 0."))
        tx.loc[incoh, "Commission (FCFA)"] = 0
    if "Commission_Agent (FCFA)" not in tx.columns:
        tx["Commission_Agent (FCFA)"] = 0.0
        journal.append(("info", "Colonne Commission_Agent (FCFA) absente : revenu net = revenu brut."))
    tx["Commission_Agent (FCFA)"] = pd.to_numeric(tx["Commission_Agent (FCFA)"], errors="coerce").fillna(0)

    # colonnes facultatives
    if "Motif_Echec" not in tx.columns:
        tx["Motif_Echec"] = np.nan
    tx["Motif_Echec"] = tx["Motif_Echec"].astype(object)
    sans_motif = (tx["Statut"] == C.STATUT_KO) & tx["Motif_Echec"].isna()
    tx.loc[sans_motif, "Motif_Echec"] = "Non renseigné"
    if "ID_Agent" not in tx.columns:
        tx["ID_Agent"] = np.nan
    if "Commercial" not in tx.columns:
        tx["Commercial"] = np.nan
    tx["Commercial"] = tx["Commercial"].fillna("Non attribué")

    # imputation Ville via Agence (mapping majoritaire), puis libellés manquants
    if "Ville" not in tx.columns:
        tx["Ville"] = np.nan
    carte = (tx.dropna(subset=["Ville", "Agence"]).groupby("Agence")["Ville"]
               .agg(lambda s: s.mode().iat[0]))
    manq_ville = tx["Ville"].isna() & tx["Agence"].notna()
    if manq_ville.any():
        tx.loc[manq_ville, "Ville"] = tx.loc[manq_ville, "Agence"].map(carte)
        journal.append(("info", f"{int(manq_ville.sum())} ville(s) manquante(s) imputée(s) depuis l'agence."))
    for col in ["Agence", "Ville", "Produit", "Canal"]:
        tx[col] = tx[col].astype(object).fillna("Non renseigné")

    # champs dérivés
    d = tx["Date"]
    tx["Date_jour"] = d.dt.normalize()
    tx["Année"] = d.dt.year.astype(int)
    tx["Mois_num"] = d.dt.month.astype(int)
    tx["Mois_label"] = d.dt.strftime("%Y-%m")
    tx["Semaine"] = d.dt.to_period("W").dt.start_time.dt.strftime("%Y-%m-%d")
    tx["Trimestre"] = d.dt.year.astype(str) + "-T" + d.dt.quarter.astype(str)
    tx["Jour_sem"] = d.dt.dayofweek.astype(int)
    tx["Heure"] = d.dt.hour.astype(int)
    tx["Réussi"] = tx["Statut"] == C.STATUT_OK
    tx["Est_Echec"] = tx["Statut"] == C.STATUT_KO
    tx["Est_Attente"] = tx["Statut"] == C.STATUT_ATT
    tx["Commission_Nette (FCFA)"] = tx["Commission (FCFA)"] - tx["Commission_Agent (FCFA)"]
    tx["Type_Flux"] = np.select(
        [tx["Produit"] == C.P_DEPOT, tx["Produit"] == C.P_RETRAIT], ["Cash-in", "Cash-out"], "Autre")
    n1 = len(tx)
    if n1 != n0:
        journal.append(("info", f"Transactions : {n0:,} lues → {n1:,} conservées.".replace(",", " ")))
    return tx.sort_values("Date").reset_index(drop=True)


def _nettoyer_clients(cl: pd.DataFrame, tx: pd.DataFrame, journal: list) -> pd.DataFrame:
    cl = cl.copy()
    dup = cl.duplicated(subset="ID_Client", keep="first")
    if dup.any():
        journal.append(("warning", f"{int(dup.sum())} client(s) en doublon supprimé(s)."))
        cl = cl[~dup]
    vide = pd.Series(np.nan, index=cl.index)
    cl["Date_Inscription"] = pd.to_datetime(cl.get("Date_Inscription", vide), errors="coerce")
    cl["Age"] = pd.to_numeric(cl.get("Age", vide), errors="coerce")
    hors = ~cl["Age"].between(16, 100) & cl["Age"].notna()
    if hors.any():
        journal.append(("warning", f"{int(hors.sum())} âge(s) aberrant(s) (hors 16-100 ans) mis à vide."))
        cl.loc[hors, "Age"] = np.nan
    sexe = cl["Sexe"].astype(object) if "Sexe" in cl.columns else pd.Series(np.nan, index=cl.index, dtype=object)
    cl["Sexe"] = sexe.map(lambda x: x if x in ("M", "F") else "NR")
    for col, defaut in [("Segment", "Non référencé"), ("KYC_Niveau", "Non renseigné"), ("Nom", "—"), ("Prénom", "—")]:
        cl[col] = (cl[col].astype(object) if col in cl.columns else pd.Series(np.nan, index=cl.index, dtype=object)).fillna(defaut)
    if "Ville" not in cl.columns:
        cl["Ville"] = np.nan
    if "Agence" not in cl.columns:  # client rattaché à son agence la plus fréquente
        top = (tx.groupby(["ID_Client", "Agence"]).size().reset_index(name="n")
                 .sort_values("n").drop_duplicates("ID_Client", keep="last"))
        cl = cl.merge(top[["ID_Client", "Agence"]], on="ID_Client", how="left")
        journal.append(("info", "Colonne Agence absente des Clients : déduite de l'agence la plus fréquente."))
    cl["Agence"] = cl["Agence"].astype(object).fillna("Non renseigné")
    cl["Ville"] = cl["Ville"].astype(object).fillna("Non renseigné")
    return cl.reset_index(drop=True)


def _nettoyer_objectifs(obj: pd.DataFrame, annees: list[int], journal: list) -> pd.DataFrame:
    obj = obj.copy()
    if pd.api.types.is_numeric_dtype(obj["Mois"]):
        obj["Mois_num"] = obj["Mois"]
    else:
        obj["Mois_num"] = obj["Mois"].astype(str).str.strip().str.capitalize().map(C.MOIS_FR)
    if "N° Mois" in obj.columns:
        obj["Mois_num"] = obj["Mois_num"].fillna(pd.to_numeric(obj["N° Mois"], errors="coerce"))
    obj["Mois_num"] = obj["Mois_num"].astype("Int64")
    if "Année" not in obj.columns:
        journal.append(("error", "Feuille Objectifs sans colonne « Année » : objectifs répliqués sur chaque année "
                                 f"{annees}. À corriger dans la source (jointure Agence × Année × Mois)."))
        obj = pd.concat([obj.assign(Année=a) for a in annees], ignore_index=True)
    obj["Année"] = pd.to_numeric(obj["Année"], errors="coerce").astype("Int64")
    for col in ["Objectif_Montant (FCFA)", "Objectif_Transactions"]:
        obj[col] = pd.to_numeric(obj[col], errors="coerce")
    obj = obj.dropna(subset=["Agence", "Année", "Mois_num", "Objectif_Montant (FCFA)"])
    dup = obj.duplicated(subset=["Agence", "Année", "Mois_num"], keep="last")
    if dup.any():
        journal.append(("warning", f"{int(dup.sum())} objectif(s) en doublon (Agence, Année, Mois) : dernier conservé."))
        obj = obj[~dup]
    if "Région" not in obj.columns:
        obj["Région"] = "Non renseignée"
    if "Taux_Commission_Cible (%)" not in obj.columns:
        obj["Taux_Commission_Cible (%)"] = np.nan
    if "Objectif_Transactions" not in obj.columns:
        obj["Objectif_Transactions"] = np.nan
    return obj.reset_index(drop=True)


def _nettoyer_agents(ag: pd.DataFrame | None, tx: pd.DataFrame, journal: list) -> pd.DataFrame:
    if ag is None or ag.empty:
        t = tx[tx["ID_Agent"].notna()]
        ag = (t.groupby("ID_Agent").agg(Agence=("Agence", "first"), Commercial=("Commercial", "first"),
                                        Date_Activation=("Date", "min")).reset_index())
        ag["Latitude"] = np.nan
        ag["Longitude"] = np.nan
        journal.append(("info", "Feuille Agents absente : liste reconstruite depuis les transactions (activité uniquement)."))
    ag = ag.copy()
    ag["Date_Activation"] = pd.to_datetime(ag["Date_Activation"], errors="coerce")
    for c in ["Latitude", "Longitude"]:
        ag[c] = pd.to_numeric(ag.get(c, pd.Series(np.nan, index=ag.index)), errors="coerce")
    return ag.drop_duplicates("ID_Agent").reset_index(drop=True)


def charger_donnees(source) -> dict:
    """Pipeline complet : lecture → contrôle qualité brut → nettoyage → enrichissement."""
    feuilles = lire_classeur(source)
    tx_brut, cl_brut, obj_brut = feuilles["Transactions"], feuilles["Clients"], feuilles["Objectifs"]
    ag_brut = feuilles.get("Agents")

    dq = controles_qualite(tx_brut, cl_brut, obj_brut, ag_brut)  # sur les données BRUTES

    journal: list = []
    tx = _nettoyer_transactions(tx_brut, journal)
    if tx.empty:
        raise ErreurDonnees("Aucune transaction exploitable après nettoyage.")
    cl = _nettoyer_clients(cl_brut, tx, journal)
    obj = _nettoyer_objectifs(obj_brut, sorted(tx["Année"].unique().tolist()), journal)
    ag = _nettoyer_agents(ag_brut, tx, journal)

    # Segment client porté sur chaque transaction (pour filtrer sans jointure répétée)
    tx["Segment"] = tx["ID_Client"].map(cl.drop_duplicates("ID_Client").set_index("ID_Client")["Segment"]).fillna("Non référencé")

    # Région et coordonnées par agence
    region = obj.drop_duplicates("Agence").set_index("Agence")["Région"]
    tx["Région"] = tx["Agence"].map(region).fillna("Non renseignée")
    geo = (ag.dropna(subset=["Latitude", "Longitude"]).groupby("Agence")[["Latitude", "Longitude"]].mean().reset_index()
           if ag[["Latitude", "Longitude"]].notna().any().any() else pd.DataFrame(columns=["Agence", "Latitude", "Longitude"]))
    geo["Région"] = geo["Agence"].map(region)

    ind = feuilles.get("Indicateurs")
    meta = {"date_min": tx["Date"].min().normalize(), "date_max": tx["Date"].max().normalize(),
            "a_heures": bool(tx["Heure"].nunique() > 1), "geo": geo}
    return {"df": tx, "cl": cl, "obj": obj, "ag": ag, "ind": ind, "dq": dq, "journal": journal, "meta": meta}


def fichier_par_defaut() -> Path:
    """Retourne le classeur de démonstration, en le générant s'il n'existe pas."""
    if not C.FICHIER_DEFAUT.exists():
        from .generate_data import generer
        generer(C.FICHIER_DEFAUT)
    return C.FICHIER_DEFAUT
