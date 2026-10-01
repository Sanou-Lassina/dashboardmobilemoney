"""Génération automatique de messages de synthèse pour les décideurs (« so what »)."""
import numpy as np
import pandas as pd

from . import config as C

ORDRE = {"critique": 0, "attention": 1, "positif": 2, "info": 3}


def _fr(x, nd=1):
    return f"{x:,.{nd}f}".replace(",", "\u202f").replace(".", ",")


def _mfcfa(x):
    return f"{_fr(x / 1e6, 1)} M FCFA"


def generer(m: dict, max_messages: int = 8) -> list[tuple[str, str]]:
    """m : dictionnaire de métriques déjà calculées (voir pages/1_resume.py). Retourne [(niveau, texte)]."""
    out: list[tuple[str, str]] = []
    syn, prev = m["syn"], m.get("syn_prev")

    # 1) Dynamique du volume
    if prev:
        v = (syn["gtv"] - prev["gtv"]) / prev["gtv"] * 100 if prev["gtv"] else None
        if v is not None:
            niv = "positif" if v >= 3 else ("critique" if v <= -5 else "attention" if v < 0 else "info")
            out.append((niv, f"Le volume traité (GTV) est de {_mfcfa(syn['gtv'])}, soit {_fr(v, 1)} % par rapport à la période de comparaison."))

    # 2) Objectifs par agence
    pa = m.get("par_agence")
    if m.get("objectifs_pertinents") and pa is not None and len(pa):
        bas = pa[pa["Taux_Montant_%"] < C.SEUIL_ORANGE]
        if len(bas):
            noms = ", ".join(f"{r.Agence} ({_fr(r['Taux_Montant_%'], 0)} %)" for _, r in bas.head(3).iterrows())
            out.append(("critique", f"{len(bas)} agence(s) sous 80 % de leur objectif de montant : {noms}."))
        sous100 = pa[(pa["Taux_Montant_%"] >= C.SEUIL_ORANGE) & (pa["Taux_Montant_%"] < 100)]
        if len(sous100):
            out.append(("attention", f"{len(sous100)} agence(s) entre 80 % et 100 % de l'objectif : {', '.join(sous100['Agence'].head(4))}."))
        haut = pa.iloc[-1]
        if haut["Taux_Montant_%"] >= 100:
            out.append(("positif", f"{haut['Agence']} dépasse son objectif ({_fr(haut['Taux_Montant_%'], 1)} %)."))

    # 3) Projection de fin de mois
    pj = m.get("proj")
    if pj and pj.get("taux_projete") == pj.get("taux_projete"):
        niv = "positif" if pj["taux_projete"] >= 100 else ("attention" if pj["taux_projete"] >= 90 else "critique")
        out.append((niv, f"Au rythme actuel ({pj['jours_ecoules']} jours sur {pj['jours_mois']}), {pj['mois']} finirait à "
                         f"{_mfcfa(pj['projection'])}, soit {_fr(pj['taux_projete'], 0)} % de l'objectif ({_mfcfa(pj['objectif'])})."))

    # 4) Liquidité du réseau
    rc = m.get("ratio_cash")
    if rc is not None and len(rc):
        tens = rc[rc["Lecture"] != "Équilibré"]
        if len(tens):
            t = tens.iloc[(tens["Ratio"] - 1).abs().argsort()[::-1]].head(3)
            noms = ", ".join(f"{r.Agence} ({_fr(r.Ratio, 2)})" for _, r in t.iterrows())
            out.append(("attention", f"Déséquilibre cash-in / cash-out dans {len(tens)} agence(s) (ratio cash-in ÷ cash-out) : {noms}. "
                                     "Prévoir un rééquilibrage de liquidité."))

    # 5) Réseau d'agents
    ag = m.get("agents")
    if ag is not None and len(ag):
        inactifs = int((~ag["Actif_30j"]).sum())
        part = inactifs / len(ag) * 100
        if part >= 10:
            out.append(("attention", f"{inactifs} agents sur {len(ag)} ({_fr(part, 0)} %) n'ont traité aucune transaction réussie sur 30 jours."))

    # 6) Qualité de service
    if syn["taux_succes"] == syn["taux_succes"] and syn["nb_tx"] > 0:
        niv = "positif" if syn["taux_succes"] >= 97 else ("attention" if syn["taux_succes"] >= 94 else "critique")
        motif = m.get("motif_top")
        suite = f" Premier motif d'échec : {motif[0]} ({_fr(motif[1], 0)} % des échecs)." if motif else ""
        out.append((niv, f"Taux de succès des transactions : {_fr(syn['taux_succes'], 1)} % (référence 97 %).{suite}"))
    inc = m.get("incidents")
    if inc is not None and len(inc):
        jours = inc["Date"].nunique()
        out.append(("attention", f"{jours} jour(s) d'incident probable détecté(s) (pics d'échecs) ; le plus récent : {inc['Date'].max()}."))

    # 7) Risque
    al = m.get("alertes")
    if al is not None and len(al):
        fort = int((al["Score_risque"] >= 70).sum())
        if fort:
            out.append(("critique", f"{fort} client(s) présentent un score de risque ≥ 70 (fractionnement sous plafond, rafales, gros montants nocturnes) : à instruire par la conformité."))

    # 8) Clients
    act = m.get("activite")
    if act:
        if act["churn30"] == act["churn30"] and act["churn30"] >= 40:
            out.append(("attention", f"Churn 30 jours élevé : {_fr(act['churn30'], 0)} % des clients actifs le mois précédent ne le sont plus."))
        if act["dormants"]:
            out.append(("info", f"{act['dormants']:,} clients inscrits depuis plus de 90 jours sont dormants : cible de campagne de réactivation.".replace(",", "\u202f")))

    # 9) Données
    if m.get("dq_global") is not None and m["dq_global"] < 95:
        out.append(("attention", f"Score global de qualité des données : {_fr(m['dq_global'], 1)} % (< 95 %). Les chiffres sont à lire avec prudence."))

    out.sort(key=lambda t: ORDRE[t[0]])
    return out[:max_messages]
