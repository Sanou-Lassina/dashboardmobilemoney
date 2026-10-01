"""Contrôles qualité des données (DQA) : complétude, validité, unicité, cohérence.

Les contrôles portent sur les données BRUTES (avant nettoyage) afin de mesurer
la vraie qualité de la source, pas celle du jeu déjà corrigé.
"""
import numpy as np
import pandas as pd

from . import config as C

BORNE_DATE_MIN = pd.Timestamp("2015-01-01")


def _vide(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "")


def _ligne(table, champ, regle, total, non_nuls, valides):
    comp = non_nuls / total if total else np.nan
    val = valides / non_nuls if non_nuls else (0.0 if total else np.nan)
    score = comp * val if total else np.nan
    return {
        "Table": table, "Champ": champ, "Règle de validité": regle,
        "Observations": int(total), "Complétude (%)": round(comp * 100, 2) if total else np.nan,
        "Validité (%)": round(val * 100, 2) if total else np.nan,
        "Score (%)": round(score * 100, 2) if total else np.nan,
    }


def _texte(table, champ, serie):
    total, nn = len(serie), int((~_vide(serie)).sum())
    return _ligne(table, champ, "Non vide", total, int(serie.notna().sum()), nn)


def controles_qualite(tx: pd.DataFrame, cl: pd.DataFrame, obj: pd.DataFrame,
                      ag: pd.DataFrame | None = None) -> dict:
    lignes, trans = [], []
    maintenant = pd.Timestamp.now() + pd.Timedelta(days=1)

    # ─────────── Transactions ───────────
    n = len(tx)
    d = pd.to_datetime(tx["Date"], errors="coerce")
    lignes.append(_ligne("Transactions", "Date", "Date lisible entre 2015 et aujourd'hui",
                         n, int(tx["Date"].notna().sum()),
                         int(d.between(BORNE_DATE_MIN, maintenant).sum())))
    lignes.append(_texte("Transactions", "ID_Transaction", tx["ID_Transaction"]))
    ids_cl = set(cl["ID_Client"].dropna())
    lignes.append(_ligne("Transactions", "ID_Client", "Client présent dans la table Clients",
                         n, int(tx["ID_Client"].notna().sum()),
                         int(tx["ID_Client"].isin(ids_cl).sum())))
    m = pd.to_numeric(tx["Montant (FCFA)"], errors="coerce")
    lignes.append(_ligne("Transactions", "Montant (FCFA)", f"Numérique, > 0 et ≤ {C.PLAFOND_TX:,} FCFA".replace(",", " "),
                         n, int(tx["Montant (FCFA)"].notna().sum()),
                         int(((m > 0) & (m <= C.PLAFOND_TX)).sum())))
    c = pd.to_numeric(tx["Commission (FCFA)"], errors="coerce")
    lignes.append(_ligne("Transactions", "Commission (FCFA)", "Numérique, ≥ 0 et ≤ montant",
                         n, int(tx["Commission (FCFA)"].notna().sum()),
                         int(((c >= 0) & (c <= m.fillna(np.inf))).sum())))
    st = tx["Statut"].astype("string").str.strip()
    lignes.append(_ligne("Transactions", "Statut", "Succès / Échoué / En Attente",
                         n, int(st.notna().sum()), int(st.isin(C.STATUTS_CONNUS).sum())))
    for champ in ["Agence", "Ville", "Produit", "Canal", "Commercial"]:
        if champ in tx.columns:
            lignes.append(_texte("Transactions", champ, tx[champ]))
    if "Motif_Echec" in tx.columns:
        ech = tx[st == C.STATUT_KO]
        lignes.append(_ligne("Transactions", "Motif_Echec", "Motif renseigné et reconnu pour chaque échec",
                             len(ech), int(ech["Motif_Echec"].notna().sum()),
                             int(ech["Motif_Echec"].isin(C.MOTIFS_ECHEC).sum())))
    if "ID_Agent" in tx.columns:
        ag_tx = tx[tx["Canal"] == C.CANAL_AGENT]
        lignes.append(_ligne("Transactions", "ID_Agent", "Renseigné pour toute transaction via agent",
                             len(ag_tx), int(ag_tx["ID_Agent"].notna().sum()),
                             int((~_vide(ag_tx["ID_Agent"])).sum())))

    # ─────────── Clients ───────────
    nc = len(cl)
    a = pd.to_numeric(cl["Age"], errors="coerce") if "Age" in cl.columns else pd.Series(dtype=float)
    if "Age" in cl.columns:
        lignes.append(_ligne("Clients", "Age", "Entre 16 et 100 ans", nc, int(cl["Age"].notna().sum()),
                             int(a.between(16, 100).sum())))
    if "Sexe" in cl.columns:
        lignes.append(_ligne("Clients", "Sexe", "M ou F", nc, int(cl["Sexe"].notna().sum()),
                             int(cl["Sexe"].isin(["M", "F"]).sum())))
    if "Date_Inscription" in cl.columns:
        di = pd.to_datetime(cl["Date_Inscription"], errors="coerce")
        lignes.append(_ligne("Clients", "Date_Inscription", "Date lisible, non future", nc,
                             int(cl["Date_Inscription"].notna().sum()),
                             int(di.between(BORNE_DATE_MIN, maintenant).sum())))
    for champ in ["Segment", "Ville"]:
        if champ in cl.columns:
            lignes.append(_texte("Clients", champ, cl[champ]))

    # ─────────── Objectifs ───────────
    no = len(obj)
    mo = pd.to_numeric(obj["Objectif_Montant (FCFA)"], errors="coerce")
    lignes.append(_ligne("Objectifs", "Objectif_Montant (FCFA)", "Numérique > 0", no,
                         int(obj["Objectif_Montant (FCFA)"].notna().sum()), int((mo > 0).sum())))
    if "Objectif_Transactions" in obj.columns:
        ot = pd.to_numeric(obj["Objectif_Transactions"], errors="coerce")
        lignes.append(_ligne("Objectifs", "Objectif_Transactions", "Numérique > 0", no,
                             int(obj["Objectif_Transactions"].notna().sum()), int((ot > 0).sum())))
    if "Année" in obj.columns:
        an = pd.to_numeric(obj["Année"], errors="coerce")
        lignes.append(_ligne("Objectifs", "Année", "Entre 2000 et 2100", no, int(obj["Année"].notna().sum()),
                             int(an.between(2000, 2100).sum())))
    else:  # colonne absente = défaut majeur, score nul
        lignes.append(_ligne("Objectifs", "Année", "Colonne obligatoire (Agence × Année × Mois)", no, 0, 0))

    champs = pd.DataFrame(lignes)

    # ─────────── Contrôles transverses ───────────
    def _t(nom, anomalies, total, detail):
        res = 100 * (1 - anomalies / total) if total else np.nan
        trans.append({"Contrôle": nom, "Résultat (%)": round(res, 2),
                      "Anomalies": int(anomalies), "Détail": detail})

    idt = tx["ID_Transaction"].dropna()
    _t("Unicité des ID_Transaction", int(idt.duplicated().sum()), len(idt), "Doublons d'identifiant de transaction")
    _t("Unicité des ID_Client", int(cl["ID_Client"].dropna().duplicated().sum()), len(cl), "Doublons dans la table Clients")
    cli = tx["ID_Client"].dropna()
    _t("Intégrité référentielle client", int((~cli.isin(ids_cl)).sum()), len(cli),
       "Transactions dont le client est absent de la table Clients")
    ok = (c.notna() & m.notna())
    _t("Cohérence commission ≤ montant", int((c[ok] > m[ok]).sum()), int(ok.sum()),
       "Commission supérieure au montant de la transaction")
    if "Date_Inscription" in cl.columns:
        j = pd.DataFrame({"id": tx["ID_Client"], "d": d}).merge(
            pd.DataFrame({"id": cl["ID_Client"], "ins": pd.to_datetime(cl["Date_Inscription"], errors="coerce")}),
            on="id", how="inner").dropna()
        _t("Cohérence chronologique", int((j["d"].dt.normalize() < j["ins"].dt.normalize()).sum()), len(j),
           "Transaction antérieure à l'inscription du client")
    # couverture des objectifs (Agence, [Année], Mois)
    try:
        t2 = pd.DataFrame({"Agence": tx["Agence"], "d": d}).dropna()
        t2["Mois_num"] = t2["d"].dt.month
        o2 = obj.copy()
        if "Mois" in o2.columns:
            o2["Mois_num"] = o2["Mois"].map(C.MOIS_FR)
            if "N° Mois" in o2.columns:
                o2["Mois_num"] = o2["Mois_num"].fillna(o2["N° Mois"])
        cles = ["Agence", "Mois_num"]
        if "Année" in o2.columns:
            t2["Année"] = t2["d"].dt.year
            cles = ["Agence", "Année", "Mois_num"]
        combos = t2[cles].drop_duplicates()
        connus = o2[cles].drop_duplicates()
        manq = combos.merge(connus, on=cles, how="left", indicator=True)
        _t("Couverture des objectifs", int((manq["_merge"] == "left_only").sum()), len(combos),
           "Combinaisons Agence × Mois réalisées sans objectif défini")
    except Exception:  # noqa: BLE001 - le contrôle ne doit jamais bloquer le chargement
        pass

    transverses = pd.DataFrame(trans)
    sc = float(champs["Score (%)"].mean())
    st_ = float(transverses["Résultat (%)"].mean())
    return {"champs": champs, "transverses": transverses,
            "score_champs": sc, "score_transverse": st_, "score_global": round(0.5 * sc + 0.5 * st_, 1)}


def score_indicateur(champs_sources: str, dq: dict) -> float:
    """Score DQA d'un indicateur = 70 % qualité des champs sources + 30 % contrôles transverses."""
    champs = dq["champs"]
    cles = [s.strip() for s in str(champs_sources).split(";") if s.strip()]
    sel = champs[(champs["Table"] + "." + champs["Champ"]).isin(cles)]
    base = float(sel["Score (%)"].mean()) if len(sel) else dq["score_champs"]
    return round(0.7 * base + 0.3 * dq["score_transverse"], 1)


def niveau_dqa(score: float) -> tuple[str, str]:
    if score >= 95:
        return "Fiable", C.VERT
    if score >= 85:
        return "Acceptable", C.JAUNE
    return "À corriger", C.ROUGE
