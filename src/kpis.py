"""Calculs métier (purs, testables) : KPI, objectifs, clients, réseau, risques, prévision."""
import warnings

import numpy as np
import pandas as pd

from . import config as C
from . import cadre

JOUR = pd.Timedelta(days=1)


# ─────────────────────────────────────────────
#  Utilitaires
# ─────────────────────────────────────────────
def mois_equivalents(d1, d2) -> float:
    return max(((pd.Timestamp(d2) - pd.Timestamp(d1)).days + 1) / 30.4375, 1 / 30.4375)


def tranche(df: pd.DataFrame, d1, d2) -> pd.DataFrame:
    """Sous-ensemble [d1 ; d2] inclusif (les dates contiennent l'heure)."""
    d1, d2 = pd.Timestamp(d1), pd.Timestamp(d2)
    return df[(df["Date"] >= d1) & (df["Date"] < d2 + JOUR)]


def variation(actuel, precedent):
    """Variation en % (None si la base de comparaison est nulle ou absente)."""
    try:
        if precedent is None or precedent == 0 or pd.isna(precedent) or pd.isna(actuel):
            return None
        return (actuel - precedent) / abs(precedent) * 100
    except TypeError:
        return None


def periode_precedente(d1, d2, mode: str):
    d1, d2 = pd.Timestamp(d1), pd.Timestamp(d2)
    if mode == "Même période N-1":
        return d1 - pd.DateOffset(years=1), d2 - pd.DateOffset(years=1)
    if mode == "Période précédente":
        duree = d2 - d1
        p2 = d1 - JOUR
        return p2 - duree, p2
    return None


# ─────────────────────────────────────────────
#  Synthèse des KPI
# ─────────────────────────────────────────────
def synthese(dff: pd.DataFrame) -> dict:
    ok = dff[dff["Réussi"]]
    n, n_ok = len(dff), len(ok)
    ca = float(ok["Montant (FCFA)"].sum())
    rev_brut = float(ok["Commission (FCFA)"].sum())
    com_ag = float(ok["Commission_Agent (FCFA)"].sum())
    return {
        "gtv": ca, "nb_tx": n, "nb_ok": n_ok,
        "nb_echec": int(dff["Est_Echec"].sum()), "nb_attente": int(dff["Est_Attente"].sum()),
        "taux_succes": n_ok / n * 100 if n else np.nan,
        "taux_echec": dff["Est_Echec"].sum() / n * 100 if n else np.nan,
        "revenu_brut": rev_brut, "commissions_agents": com_ag, "revenu_net": rev_brut - com_ag,
        "take_rate": rev_brut / ca * 100 if ca else np.nan,
        "panier_moyen": ca / n_ok if n_ok else np.nan,
        "panier_median": float(ok["Montant (FCFA)"].median()) if n_ok else np.nan,
        "clients_periode": int(ok["ID_Client"].nunique()),
        "tx_par_client": n_ok / ok["ID_Client"].nunique() if n_ok else np.nan,
    }


def arpu_mensuel(ok: pd.DataFrame) -> float:
    """ARPU = revenu brut mensuel ÷ clients actifs du mois, moyenné sur les mois de la période."""
    if ok.empty:
        return np.nan
    g = ok.groupby("Mois_label").agg(rev=("Commission (FCFA)", "sum"), act=("ID_Client", "nunique"))
    return float((g["rev"] / g["act"]).mean())


# ─────────────────────────────────────────────
#  Objectifs : agrégation agence × mois AVANT jointure
# ─────────────────────────────────────────────
def mois_complets(d1, d2) -> list[tuple[int, int]]:
    """Couples (année, mois) entièrement couverts par [d1 ; d2]."""
    d1, d2 = pd.Timestamp(d1), pd.Timestamp(d2)
    res = []
    for p in pd.period_range(d1, d2, freq="M"):
        if p.start_time >= d1 and p.end_time.normalize() <= d2:
            res.append((p.year, p.month))
    return res


def performance_objectifs(ok: pd.DataFrame, obj: pd.DataFrame, d1, d2, agences: list[str]) -> pd.DataFrame:
    """Une ligne par (agence, mois complet) : réalisé vs objectif. Jointure DEPUIS les objectifs
    pour qu'une agence sans vente compte à 0 % au lieu de disparaître."""
    complets = mois_complets(d1, d2)
    cols = ["Agence", "Année", "Mois_num", "CA", "Tx", "Objectif_Montant (FCFA)", "Objectif_Transactions"]
    if not complets or not agences:
        return pd.DataFrame(columns=cols)
    cle = pd.MultiIndex.from_frame(obj[["Année", "Mois_num"]].astype(int))
    sel = obj[obj["Agence"].isin(agences) & cle.isin(complets)]
    reel = (ok.groupby(["Agence", "Année", "Mois_num"])
              .agg(CA=("Montant (FCFA)", "sum"), Tx=("ID_Transaction", "count")).reset_index())
    reel["Année"] = reel["Année"].astype("Int64")
    reel["Mois_num"] = reel["Mois_num"].astype("Int64")
    perf = sel.merge(reel, on=["Agence", "Année", "Mois_num"], how="left")
    perf[["CA", "Tx"]] = perf[["CA", "Tx"]].fillna(0)
    perf["Période"] = perf["Année"].astype(str) + "-" + perf["Mois_num"].astype(str).str.zfill(2)
    return perf[cols + ["Période"]]


def taux_atteinte(perf: pd.DataFrame) -> tuple[float, float]:
    if perf.empty:
        return np.nan, np.nan
    om, ot = perf["Objectif_Montant (FCFA)"].sum(), perf["Objectif_Transactions"].sum()
    return (perf["CA"].sum() / om * 100 if om else np.nan,
            perf["Tx"].sum() / ot * 100 if ot else np.nan)


def par_agence(perf: pd.DataFrame) -> pd.DataFrame:
    if perf.empty:
        return pd.DataFrame(columns=["Agence", "CA", "Tx", "Objectif", "Obj_Tx", "Taux_Montant_%", "Taux_Tx_%"])
    g = perf.groupby("Agence").agg(CA=("CA", "sum"), Tx=("Tx", "sum"),
                                   Objectif=("Objectif_Montant (FCFA)", "sum"),
                                   Obj_Tx=("Objectif_Transactions", "sum")).reset_index()
    g["Taux_Montant_%"] = np.where(g["Objectif"] > 0, g["CA"] / g["Objectif"] * 100, np.nan)
    g["Taux_Tx_%"] = np.where(g["Obj_Tx"] > 0, g["Tx"] / g["Obj_Tx"] * 100, np.nan)
    return g.sort_values("Taux_Montant_%")


def projection_fin_de_mois(ok: pd.DataFrame, obj: pd.DataFrame, d2, agences: list[str]):
    """Si la période s'arrête en cours de mois : projection « run-rate » vs objectif du mois."""
    d2 = pd.Timestamp(d2)
    fin_mois = d2 + pd.offsets.MonthEnd(0)
    if d2.normalize() >= fin_mois.normalize():
        return None
    debut = d2.replace(day=1)
    mois = ok[(ok["Date"] >= debut) & (ok["Date"] < d2 + JOUR)]
    jours_ecoules, jours_mois = d2.day, fin_mois.day
    if mois.empty or jours_ecoules < 5:
        return None
    ca = float(mois["Montant (FCFA)"].sum())
    proj = ca / jours_ecoules * jours_mois
    o = obj[obj["Agence"].isin(agences) & (obj["Année"] == d2.year) & (obj["Mois_num"] == d2.month)]
    objectif = float(o["Objectif_Montant (FCFA)"].sum()) or np.nan
    return {"mois": debut.strftime("%Y-%m"), "ca_cumul": ca, "projection": proj, "objectif": objectif,
            "taux_projete": proj / objectif * 100 if objectif == objectif else np.nan,
            "jours_ecoules": jours_ecoules, "jours_mois": jours_mois}


# ─────────────────────────────────────────────
#  Séries temporelles
# ─────────────────────────────────────────────
COL_GRAN = {"Jour": "Date_jour", "Semaine": "Semaine", "Mois": "Mois_label", "Trimestre": "Trimestre"}


def serie(ok: pd.DataFrame, gran: str) -> pd.DataFrame:
    c = COL_GRAN[gran]
    s = (ok.groupby(c).agg(GTV=("Montant (FCFA)", "sum"), Tx=("ID_Transaction", "count"),
                           Revenu=("Commission (FCFA)", "sum"),
                           Revenu_net=("Commission_Nette (FCFA)", "sum"),
                           Actifs=("ID_Client", "nunique")).reset_index().rename(columns={c: "Période"}))
    s = s.sort_values("Période").reset_index(drop=True)
    s["GTV_cumul"] = s["GTV"].cumsum()
    return s


def decomposition_pvm(prev_ok: pd.DataFrame, cur_ok: pd.DataFrame) -> pd.DataFrame | None:
    """Cascade Volume / Mix produits / Panier (prix) entre deux périodes. Σ effets = ΔGTV exactement."""
    if prev_ok.empty or cur_ok.empty:
        return None
    def agg(d):
        return d.groupby("Produit")["Montant (FCFA)"].agg(n="count", total="sum")
    p, c = agg(prev_ok), agg(cur_ok)
    t = p.join(c, how="outer", lsuffix="0", rsuffix="1").fillna(0)
    t["a0"] = np.where(t["n0"] > 0, t["total0"] / t["n0"].replace(0, np.nan), np.nan)
    t["a1"] = np.where(t["n1"] > 0, t["total1"] / t["n1"].replace(0, np.nan), np.nan)
    t["a0"] = t["a0"].fillna(t["a1"])        # produit nouveau : pas d'effet prix
    t["a1"] = t["a1"].fillna(t["a0"])
    N0, N1 = t["n0"].sum(), t["n1"].sum()
    T0, T1 = t["total0"].sum(), t["total1"].sum()
    A0 = T0 / N0
    volume = (N1 - N0) * A0
    mix = float((t["n1"] * t["a0"]).sum() - N1 * A0)
    prix = float((t["n1"] * (t["a1"] - t["a0"])).sum())
    return pd.DataFrame({
        "Étape": ["GTV période de comparaison", "Effet volume", "Effet mix produits", "Effet panier", "GTV période actuelle"],
        "Valeur": [T0, volume, mix, prix, T1],
        "Type": ["total", "relative", "relative", "relative", "total"],
    })


# ─────────────────────────────────────────────
#  Produits, canaux, liquidité
# ─────────────────────────────────────────────
def stats_produit(ok: pd.DataFrame) -> pd.DataFrame:
    g = ok.groupby("Produit").agg(GTV=("Montant (FCFA)", "sum"), Tx=("ID_Transaction", "count"),
                                  Revenu=("Commission (FCFA)", "sum"), Revenu_net=("Commission_Nette (FCFA)", "sum"),
                                  Panier_moyen=("Montant (FCFA)", "mean"),
                                  Panier_median=("Montant (FCFA)", "median")).reset_index()
    g["Part_GTV_%"] = g["GTV"] / g["GTV"].sum() * 100 if g["GTV"].sum() else 0
    g["Take_rate_%"] = np.where(g["GTV"] > 0, g["Revenu"] / g["GTV"] * 100, np.nan)
    return g.sort_values("GTV", ascending=False)


def taux_succes_par(dff: pd.DataFrame, col: str) -> pd.DataFrame:
    g = dff.groupby(col).agg(Total=("ID_Transaction", "count"), Succes=("Réussi", "sum"),
                             Echecs=("Est_Echec", "sum"), Attente=("Est_Attente", "sum")).reset_index()
    g["Taux_succes_%"] = g["Succes"] / g["Total"] * 100
    g["Taux_echec_%"] = g["Echecs"] / g["Total"] * 100
    return g


def ratio_cash(ok: pd.DataFrame, par: str = "Agence", seuil_bas: float = 0.7, seuil_haut: float = 1.3) -> pd.DataFrame:
    """Cash-in ÷ cash-out. > seuil_haut : le e-float des agents se vide ; < seuil_bas : leur cash se vide."""
    p = ok[ok["Type_Flux"] != "Autre"].pivot_table(index=par, columns="Type_Flux", values="Montant (FCFA)",
                                                     aggfunc="sum", fill_value=0)
    for c in ("Cash-in", "Cash-out"):
        if c not in p.columns:
            p[c] = 0.0
    p = p.reset_index()
    p["Ratio"] = np.where(p["Cash-out"] > 0, p["Cash-in"] / p["Cash-out"], np.nan)
    p["Position nette"] = p["Cash-in"] - p["Cash-out"]
    p["Lecture"] = np.select([p["Ratio"] > seuil_haut, p["Ratio"] < seuil_bas],
                             ["Tension e-float (trop de dépôts)", "Tension cash (trop de retraits)"], "Équilibré")
    return p


# ─────────────────────────────────────────────
#  Réseau d'agents
# ─────────────────────────────────────────────
def stats_agents(ok: pd.DataFrame, ag: pd.DataFrame, d2, agences: list[str], hist_ok: pd.DataFrame | None = None) -> pd.DataFrame:
    """Une ligne par agent activé (même sans transaction). Volumes sur `ok` (période) ; activité 30 j sur `hist_ok`
    (historique jusqu'à d2) pour ne pas déclarer « inactif » un agent actif juste avant le début de la période."""
    d2 = pd.Timestamp(d2)
    a = ag[ag["Agence"].isin(agences) & (ag["Date_Activation"].isna() | (ag["Date_Activation"] <= d2 + JOUR))].copy()
    t = ok[ok["ID_Agent"].notna()]
    g = t.groupby("ID_Agent").agg(GTV=("Montant (FCFA)", "sum"), Tx=("ID_Transaction", "count"),
                                  Clients=("ID_Client", "nunique"), Revenu_net=("Commission_Nette (FCFA)", "sum")).reset_index()
    h = (hist_ok if hist_ok is not None else ok)
    h = h[h["ID_Agent"].notna()].groupby("ID_Agent")["Date"].max().rename("Derniere_activite").reset_index()
    a = a.merge(g, on="ID_Agent", how="left").merge(h, on="ID_Agent", how="left")
    for c in ["GTV", "Tx", "Clients", "Revenu_net"]:
        a[c] = a[c].fillna(0)
    a["Actif_30j"] = a["Derniere_activite"].notna() & (a["Derniere_activite"] >= d2 + JOUR - pd.Timedelta(days=C.ACTIF_JOURS))
    return a.sort_values("GTV", ascending=False)


def pareto(df: pd.DataFrame, col_val: str, col_nom: str) -> pd.DataFrame:
    p = df[[col_nom, col_val]].sort_values(col_val, ascending=False).reset_index(drop=True)
    tot = p[col_val].sum()
    p["Part_%"] = p[col_val] / tot * 100 if tot else 0
    p["Cumul_%"] = p["Part_%"].cumsum()
    p["Rang_%"] = (p.index + 1) / len(p) * 100
    return p


# ─────────────────────────────────────────────
#  Clients : activité, churn, dormants, cohortes, entonnoir, RFM
# ─────────────────────────────────────────────
def _fenetre(hist_ok: pd.DataFrame, fin, jours: int, decalage: int = 0) -> set:
    fin = pd.Timestamp(fin) + JOUR - pd.Timedelta(days=decalage)
    deb = fin - pd.Timedelta(days=jours)
    return set(hist_ok.loc[(hist_ok["Date"] >= deb) & (hist_ok["Date"] < fin), "ID_Client"])


def activite_clients(hist_ok: pd.DataFrame, cl: pd.DataFrame, d2) -> dict:
    d2 = pd.Timestamp(d2)
    inscrits = cl[cl["Date_Inscription"].isna() | (cl["Date_Inscription"] < d2 + JOUR)]
    ids_inscrits = set(inscrits["ID_Client"])
    a30 = _fenetre(hist_ok, d2, C.ACTIF_JOURS) & ids_inscrits
    a90 = _fenetre(hist_ok, d2, 90) & ids_inscrits
    prec = _fenetre(hist_ok, d2, C.ACTIF_JOURS, decalage=C.ACTIF_JOURS) & ids_inscrits
    anciens = inscrits[inscrits["Date_Inscription"] < d2 + JOUR - pd.Timedelta(days=90)]
    dormants = set(anciens["ID_Client"]) - a90
    n_ins = len(inscrits)
    return {
        "inscrits": n_ins, "actifs30": len(a30), "actifs90": len(a90),
        "taux_activite30": len(a30) / n_ins * 100 if n_ins else np.nan,
        "churn30": len(prec - a30) / len(prec) * 100 if prec else np.nan,
        "dormants": len(dormants), "ids_actifs30": a30, "ids_dormants": dormants,
        "part_kyc2": float(inscrits["KYC_Niveau"].isin(["Niveau 2", "Niveau 3"]).mean() * 100) if n_ins else np.nan,
    }


def mau_mensuel(hist_ok: pd.DataFrame) -> pd.DataFrame:
    return (hist_ok.groupby("Mois_label")["ID_Client"].nunique().reset_index(name="Actifs").sort_values("Mois_label"))


def cohortes(hist_ok: pd.DataFrame, cl: pd.DataFrame, d2, n_cohortes: int = 12) -> pd.DataFrame | None:
    """Rétention par cohorte d'inscription : % de la cohorte active (≥ 1 succès) au mois M+k."""
    d2 = pd.Timestamp(d2)
    dernier_complet = (d2.year * 12 + d2.month) if d2.normalize() >= (d2 + pd.offsets.MonthEnd(0)).normalize() \
        else (d2.year * 12 + d2.month - 1)
    c = cl.dropna(subset=["Date_Inscription"]).copy()
    c["coh"] = c["Date_Inscription"].dt.year * 12 + c["Date_Inscription"].dt.month
    c = c[(c["coh"] <= dernier_complet) & (c["coh"] > dernier_complet - n_cohortes)]
    if c.empty:
        return None
    taille = c.groupby("coh")["ID_Client"].nunique()
    act = hist_ok[["ID_Client", "Année", "Mois_num"]].drop_duplicates()
    act["m"] = act["Année"] * 12 + act["Mois_num"]
    j = act.merge(c[["ID_Client", "coh"]], on="ID_Client")
    j["k"] = j["m"] - j["coh"]
    j = j[(j["k"] >= 0) & (j["m"] <= dernier_complet)]
    mat = j.groupby(["coh", "k"])["ID_Client"].nunique().unstack(fill_value=0)
    mat = mat.reindex(taille.index, fill_value=0)
    ret = mat.div(taille, axis=0) * 100
    for coh in ret.index:                      # cellules futures = vides, pas 0 %
        max_k = dernier_complet - coh
        ret.loc[coh, [k for k in ret.columns if k > max_k]] = np.nan
    ret.index = [f"{(o - 1) // 12}-{(o - 1) % 12 + 1:02d} (n={int(taille[o])})" for o in ret.index]
    ret.columns = [f"M+{k}" for k in ret.columns]
    return ret


def entonnoir_activation(hist_ok: pd.DataFrame, cl: pd.DataFrame, d1, d2) -> pd.DataFrame | None:
    """Inscrits → 1re transaction réussie → ≥3 transactions en 30 j → encore actifs. Uniquement les clients
    inscrits depuis ≥ 30 jours (sinon censure à droite)."""
    d1, d2 = pd.Timestamp(d1), pd.Timestamp(d2)
    nouveaux = cl[(cl["Date_Inscription"] >= d1) & (cl["Date_Inscription"] <= d2 - pd.Timedelta(days=30))]
    if nouveaux.empty:
        return None
    j = hist_ok[["ID_Client", "Date"]].merge(nouveaux[["ID_Client", "Date_Inscription"]], on="ID_Client")
    j = j[j["Date"] >= j["Date_Inscription"]]
    s2 = set(j["ID_Client"])
    en30 = j[j["Date"] < j["Date_Inscription"] + pd.Timedelta(days=30)].groupby("ID_Client").size()
    s3 = set(en30[en30 >= 3].index)
    s4 = s3 & _fenetre(hist_ok, d2, C.ACTIF_JOURS)
    n = len(nouveaux)
    etapes = [("Inscrits (≥ 30 j d'ancienneté)", n), ("1re transaction réussie", len(s2)),
              ("≥ 3 transactions en 30 j", len(s3)), (f"Encore actifs ({C.ACTIF_JOURS} derniers jours)", len(s4))]
    return pd.DataFrame({"Étape": [e for e, _ in etapes], "Clients": [v for _, v in etapes],
                         "% des inscrits": [v / n * 100 for _, v in etapes]})


def masque_nom(prenom, nom) -> str:
    p = str(prenom).strip() or "—"
    n = str(nom).strip() or "—"
    return f"{p[0]}. {n[0]}***"


def rfm(ok: pd.DataFrame, cl: pd.DataFrame, d2) -> pd.DataFrame | None:
    """Scores R, F, M de 1 à 5 (quintiles par rang) et segments d'action marketing."""
    if ok["ID_Client"].nunique() < 10:
        return None
    ref = pd.Timestamp(d2).normalize()
    g = ok.groupby("ID_Client").agg(Récence=("Date", lambda x: (ref - x.max().normalize()).days),
                                    Fréquence=("ID_Transaction", "count"),
                                    Montant=("Montant (FCFA)", "sum")).reset_index()
    def q(s, inverse=False):
        r = s.rank(method="first", ascending=not inverse)
        return pd.qcut(r, 5, labels=[1, 2, 3, 4, 5]).astype(int)
    g["R"] = q(g["Récence"], inverse=True)   # récence faible = meilleur score
    g["F"] = q(g["Fréquence"])
    g["M"] = q(g["Montant"])
    g["Segment_RFM"] = np.select(
        [(g.R >= 4) & (g.F >= 4), (g.R >= 3) & (g.F >= 3), (g.R >= 4) & (g.F <= 2),
         (g.R <= 2) & (g.F >= 4), g.R <= 2],
        ["Champions", "Fidèles", "Nouveaux / prometteurs", "À risque (à relancer)", "Dormants / perdus"],
        default="Occasionnels")
    g = g.merge(cl[["ID_Client", "Segment", "Prénom", "Nom", "Agence"]], on="ID_Client", how="left")
    g["Identité (masquée)"] = [masque_nom(p, n) for p, n in zip(g["Prénom"], g["Nom"])]
    return g.drop(columns=["Prénom", "Nom"])


# ─────────────────────────────────────────────
#  Risques : fraude / conformité / incidents
# ─────────────────────────────────────────────
def detecter_alertes(dff: pd.DataFrame) -> dict:
    ok = dff[dff["Réussi"]]
    res = {}
    # 1) Fractionnement juste sous le plafond (structuring)
    seuil = C.PLAFOND_TX * C.SEUIL_STRUCTURING
    s = ok[(ok["Montant (FCFA)"] >= seuil) & (ok["Montant (FCFA)"] < C.PLAFOND_TX)].sort_values("Date")
    if len(s):
        glis = (s.set_index("Date").groupby("ID_Client")["Montant (FCFA)"].rolling("7D").count()
                 .groupby(level=0).max())
        agg = s.groupby("ID_Client").agg(Nb=("ID_Transaction", "count"), Montant=("Montant (FCFA)", "sum"))
        agg["Max_7j"] = glis
        res["structuring"] = agg[agg["Max_7j"] >= 3].reset_index().sort_values("Montant", ascending=False)
    else:
        res["structuring"] = pd.DataFrame(columns=["ID_Client", "Nb", "Montant", "Max_7j"])
    # 2) Vélocité : rafales de transactions dans la même heure
    if dff["Heure"].nunique() > 1:
        h = dff.assign(h=dff["Date"].dt.floor("h")).groupby(["ID_Client", "h"]).size()
        h = h[h >= C.SEUIL_VELOCITE].reset_index(name="Nb_tx_heure")
        res["velocite"] = (h.groupby("ID_Client").agg(Nb_heures=("h", "count"), Max_tx_heure=("Nb_tx_heure", "max"))
                            .reset_index().sort_values("Max_tx_heure", ascending=False))
        # 3) Gros montants de nuit
        n = ok[(ok["Heure"] < 5) & (ok["Montant (FCFA)"] >= C.SEUIL_NUIT_MONTANT)]
        res["nuit"] = (n.groupby("ID_Client").agg(Nb=("ID_Transaction", "count"), Montant=("Montant (FCFA)", "sum"))
                        .reset_index().sort_values("Montant", ascending=False))
    else:
        res["velocite"] = pd.DataFrame(columns=["ID_Client", "Nb_heures", "Max_tx_heure"])
        res["nuit"] = pd.DataFrame(columns=["ID_Client", "Nb", "Montant"])
    # 4) Montants atypiques par produit (z-score robuste sur log-montant)
    lm = np.log(ok["Montant (FCFA)"].clip(lower=1))
    med = lm.groupby(ok["Produit"]).transform("median")
    mad = (lm - med).abs().groupby(ok["Produit"]).transform("median").replace(0, np.nan)
    z = 0.6745 * (lm - med) / mad
    atyp = ok[(z > 3) & (ok["Montant (FCFA)"] >= 100_000)]
    res["atypiques"] = (atyp.groupby("ID_Client").agg(Nb=("ID_Transaction", "count"), Montant=("Montant (FCFA)", "sum"))
                            .reset_index().sort_values("Montant", ascending=False))
    # Synthèse : score de risque par client
    lignes = []
    for type_, df_, f in [("Fractionnement sous plafond", res["structuring"], lambda r: min(100, 40 + 15 * r["Nb"])),
                          ("Rafale de transactions", res["velocite"], lambda r: min(100, 30 + 10 * (r["Max_tx_heure"] - C.SEUIL_VELOCITE + 1))),
                          ("Gros montant nocturne", res["nuit"], lambda r: min(100, 25 + 10 * r["Nb"])),
                          ("Montant atypique", res["atypiques"], lambda r: min(100, 15 + 5 * r["Nb"]))]:
        for _, r in df_.iterrows():
            lignes.append({"ID_Client": r["ID_Client"], "Type d'alerte": type_, "Points": f(r)})
    if lignes:
        l = pd.DataFrame(lignes)
        s = l.groupby("ID_Client").agg(Score_risque=("Points", lambda x: min(100, x.sum())),
                                       Alertes=("Type d'alerte", lambda x: " + ".join(sorted(set(x)))),
                                       Nb_types=("Type d'alerte", "nunique")).reset_index()
        tot = ok.groupby("ID_Client")["Montant (FCFA)"].sum().rename("GTV_période")
        res["synthese"] = s.merge(tot, on="ID_Client", how="left").sort_values(["Score_risque", "GTV_période"], ascending=False)
    else:
        res["synthese"] = pd.DataFrame(columns=["ID_Client", "Score_risque", "Alertes", "Nb_types", "GTV_période"])
    return res


def jours_incident(dff: pd.DataFrame, z_seuil: float = 5.0) -> pd.DataFrame:
    """Jours où le taux d'échec d'un périmètre (global, canal ou agence) dépasse nettement son niveau habituel.
    Test binomial : écart ≥ 5 écarts-types, ≥ 4 échecs, ≥ 6 transactions et taux ≥ 3× le taux habituel."""
    cols = ["Date", "Périmètre", "Transactions", "Échecs", "Taux d'échec (%)", "Taux habituel (%)"]
    lignes = []
    for dim in [None, "Canal", "Agence"]:
        d = dff.assign(_g="Global") if dim is None else dff.assign(_g=dff[dim])
        g = d.groupby(["_g", "Date_jour"]).agg(n=("ID_Transaction", "count"), k=("Est_Echec", "sum")).reset_index()
        tot = g.groupby("_g")[["n", "k"]].sum()
        p0 = (tot["k"] / tot["n"]).clip(lower=0.005)
        g["p0"] = g["_g"].map(p0)
        g["z"] = (g["k"] - g["n"] * g["p0"]) / np.sqrt(g["n"] * g["p0"] * (1 - g["p0"]))
        bad = g[(g["z"] >= z_seuil) & (g["k"] >= 4) & (g["n"] >= 6) & (g["k"] / g["n"] >= 3 * g["p0"])]
        for _, r in bad.iterrows():
            lbl = "Tous canaux et agences" if dim is None else f"{dim} : {r['_g']}"
            lignes.append({"Date": r["Date_jour"].date(), "Périmètre": lbl, "Transactions": int(r["n"]),
                           "Échecs": int(r["k"]), "Taux d'échec (%)": round(r["k"] / r["n"] * 100, 1),
                           "Taux habituel (%)": round(r["p0"] * 100, 1)})
    if not lignes:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(lignes)[cols].sort_values(["Date", "Périmètre"]).reset_index(drop=True)


# ─────────────────────────────────────────────
#  Prévision
# ─────────────────────────────────────────────
def prevoir(serie_mensuelle: pd.Series, horizon: int = 6):
    """Prévision du GTV mensuel (Holt-Winters si ≥ 24 mois, sinon tendance). Retourne (df, méthode)."""
    y = serie_mensuelle.astype(float)
    n = len(y)
    if n < 6:
        return None, None
    methode = "Tendance linéaire"
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if n >= 24:
                fit = ExponentialSmoothing(y.values, trend="add", seasonal="add", seasonal_periods=12,
                                           initialization_method="estimated").fit()
                methode = "Holt-Winters (tendance + saisonnalité annuelle)"
            else:
                fit = ExponentialSmoothing(y.values, trend="add", initialization_method="estimated").fit()
                methode = "Lissage exponentiel avec tendance"
        pred, resid = np.asarray(fit.forecast(horizon)), y.values - np.asarray(fit.fittedvalues)
        if not np.isfinite(pred).all():
            raise ValueError("prévision non finie")
    except Exception:  # noqa: BLE001 - repli sans statsmodels
        x = np.arange(n)
        coef = np.polyfit(x, y.values, 1)
        pred = np.polyval(coef, np.arange(n, n + horizon))
        resid = y.values - np.polyval(coef, x)
        methode = "Tendance linéaire"
    sigma = float(np.nanstd(resid, ddof=1)) if n > 2 else 0.0
    marge = 1.28 * sigma * np.sqrt(np.arange(1, horizon + 1))   # intervalle à 80 %
    dernier = pd.Period(y.index[-1], freq="M")
    mois = [str(dernier + k) for k in range(1, horizon + 1)]
    pred = np.clip(pred, 0, None)
    return pd.DataFrame({"Période": mois, "Prévision": pred, "Bas": np.clip(pred - marge, 0, None), "Haut": pred + marge}), methode


# ─────────────────────────────────────────────
#  Indicateurs du cadre de suivi
# ─────────────────────────────────────────────
def calculer_indicateurs(df: pd.DataFrame, cl: pd.DataFrame, obj: pd.DataFrame, ag: pd.DataFrame,
                         d1, d2, dq_global: float) -> dict:
    """Valeur de chaque indicateur sur [d1 ; d2], sur l'ensemble du périmètre (aucun filtre dimensionnel)."""
    d1, d2 = pd.Timestamp(d1), pd.Timestamp(d2)
    dfp = tranche(df, d1, d2)
    ok = dfp[dfp["Réussi"]]
    hist_ok = df[df["Réussi"] & (df["Date"] < d2 + JOUR)]
    me = mois_equivalents(d1, d2)
    s = synthese(dfp)
    act = activite_clients(hist_ok, cl, d2)
    v = {"IND01": s["gtv"] / 1e6 / me, "IND02": s["revenu_net"] / 1e6 / me, "IND03": s["take_rate"],
         "IND04": s["taux_succes"]}
    perf = performance_objectifs(ok, obj, d1, d2, sorted(obj["Agence"].unique()))
    v["IND05"] = taux_atteinte(perf)[0]
    v["IND06"] = act["actifs30"]
    v["IND07"] = act["taux_activite30"]
    v["IND08"] = act["churn30"]
    a = ag[ag["Date_Activation"].isna() | (ag["Date_Activation"] < d2 + JOUR)]
    actifs_ag = _agents_actifs(hist_ok, d2)
    v["IND09"] = len(actifs_ag & set(a["ID_Agent"])) / len(a) * 100 if len(a) else np.nan
    v["IND10"] = (ok["Canal"] != C.CANAL_AGENT).mean() * 100 if len(ok) else np.nan
    cla = cl[cl["ID_Client"].isin(act["ids_actifs30"])]
    sx = cla[cla["Sexe"].isin(["M", "F"])]
    v["IND11"] = (sx["Sexe"] == "F").mean() * 100 if len(sx) else np.nan
    v["IND12"] = (~cla["Ville"].isin(["Ouagadougou", "Bobo-Dioulasso"])).mean() * 100 if len(cla) else np.nan
    v["IND13"] = (dfp["Motif_Echec"] == "Timeout réseau").mean() * 100 if len(dfp) else np.nan
    v["IND14"] = dq_global
    return v


def _agents_actifs(hist_ok: pd.DataFrame, d2) -> set:
    fin = pd.Timestamp(d2) + JOUR
    t = hist_ok[hist_ok["ID_Agent"].notna() & (hist_ok["Date"] >= fin - pd.Timedelta(days=C.ACTIF_JOURS)) & (hist_ok["Date"] < fin)]
    return set(t["ID_Agent"])


def tableau_cadre(valeurs: dict, baselines: dict, cibles: dict, dq: dict) -> pd.DataFrame:
    from .dqa import score_indicateur
    lignes = []
    for d in cadre.DEFS:
        i = d["id"]
        act, base, cib = valeurs.get(i), baselines.get(i), cibles.get(i)
        av = cadre.avancement(act, base, cib, d["sens"])
        sc = score_indicateur(d["champs"], dq)
        lignes.append({
            "ID": i, "Catégorie": d["categorie"], "Indicateur": d["nom"], "Unité": d["unite"], "Sens": d["sens"],
            "Définition": d["definition"], "Formule": d["formule"], "Source": d["source"],
            "Fréquence": d["frequence"], "Responsable": d["responsable"],
            "Baseline": base, "Cible": cib, "Valeur actuelle": act, "Avancement (%)": av,
            "Statut": cadre.feu(av), "Score DQA (%)": sc, "fmt": d["fmt"],
        })
    return pd.DataFrame(lignes)


def baselines_et_cibles(donnees: dict):
    """Baselines et cibles : feuille « Indicateurs » si présente, sinon calcul sur le 1er trimestre des données."""
    ind = donnees.get("ind")
    if ind is not None and {"ID_Indicateur", "Baseline", "Cible"} <= set(ind.columns):
        ids = ind["ID_Indicateur"].astype(str)
        return (dict(zip(ids, pd.to_numeric(ind["Baseline"], errors="coerce"))),
                dict(zip(ids, pd.to_numeric(ind["Cible"], errors="coerce"))), "Feuille « Indicateurs » du classeur")
    m = donnees["meta"]
    d1 = m["date_min"]
    d2 = min(d1 + pd.Timedelta(days=89), m["date_max"])
    base = calculer_indicateurs(donnees["df"], donnees["cl"], donnees["obj"], donnees["ag"], d1, d2,
                                donnees["dq"]["score_global"])
    return base, cadre.cibles_par_defaut(base), "Calculées automatiquement sur le 1er trimestre des données"
