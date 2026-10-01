"""Tests des calculs métier. Lancer : pytest -q   (le fichier de démonstration est généré si absent)."""
import warnings

import numpy as np
import pandas as pd

from src import cadre, data, dqa, kpis
from src import config as C

warnings.filterwarnings("ignore")


def _donnees():
    return data.charger_donnees(data.fichier_par_defaut())


D = _donnees()
DF, CL, OBJ, AG, DQ = D["df"], D["cl"], D["obj"], D["ag"], D["dq"]
D1, D2 = D["meta"]["date_min"], D["meta"]["date_max"]
OK = DF[DF["Réussi"]]


def test_objectifs_non_multiplies_par_les_transactions():
    """Régression : l'objectif d'un agence-mois ne doit être compté qu'une seule fois."""
    perf = kpis.performance_objectifs(OK, OBJ, D1, D2, sorted(OBJ["Agence"].unique()))
    assert len(perf) == len(OBJ)
    assert np.isclose(perf["Objectif_Montant (FCFA)"].sum(), OBJ["Objectif_Montant (FCFA)"].sum())
    taux, _ = kpis.taux_atteinte(perf)
    assert 70 < taux < 120


def test_jointure_objectifs_par_annee():
    """Un même mois de deux années différentes doit porter deux objectifs distincts."""
    janv = OBJ[(OBJ["Agence"] == OBJ["Agence"].iloc[0]) & (OBJ["Mois_num"] == 1)]
    assert janv["Année"].nunique() == 2


def test_seuls_les_mois_complets_comptent():
    ok = kpis.tranche(OK, "2024-01-15", "2024-03-15")
    perf = kpis.performance_objectifs(ok, OBJ, "2024-01-15", "2024-03-15", sorted(OBJ["Agence"].unique()))
    assert set(perf["Période"]) == {"2024-02"}


def test_agence_sans_vente_compte_zero_pour_cent():
    ok = OK[OK["Agence"] != "Dori"]
    perf = kpis.performance_objectifs(ok, OBJ, D1, D2, ["Dori"])
    assert len(perf) > 0 and (perf["CA"] == 0).all()


def test_decomposition_pvm_somme_exacte():
    a = kpis.tranche(OK, "2024-01-01", "2024-12-31")
    b = kpis.tranche(OK, "2025-01-01", "2025-12-31")
    w = kpis.decomposition_pvm(a, b)
    delta = w["Valeur"].iloc[4] - w["Valeur"].iloc[0]
    assert np.isclose(w["Valeur"].iloc[1:4].sum(), delta)


def test_periodes_distinctes_par_annee():
    """Régression : semaines et trimestres de 2024 et 2025 ne doivent plus être fusionnés."""
    assert DF["Trimestre"].nunique() == 8
    assert DF["Semaine"].nunique() > 100


def test_synthese_coherente():
    s = kpis.synthese(DF)
    assert s["nb_tx"] == len(DF)
    assert np.isclose(s["revenu_net"], s["revenu_brut"] - s["commissions_agents"])
    assert 0 < s["take_rate"] < 5
    assert s["nb_ok"] + s["nb_echec"] + s["nb_attente"] <= s["nb_tx"]


def test_variation_gere_les_bases_nulles():
    assert kpis.variation(10, 0) is None
    assert kpis.variation(110, 100) == 10


def test_periode_precedente():
    p1, p2 = kpis.periode_precedente("2025-03-01", "2025-03-31", "Période précédente")
    assert p2 == pd.Timestamp("2025-02-28") and (p2 - p1).days == 30
    n1, n2 = kpis.periode_precedente("2025-03-01", "2025-03-31", "Même période N-1")
    assert n1 == pd.Timestamp("2024-03-01")
    assert kpis.periode_precedente("2025-03-01", "2025-03-31", "Aucune") is None


def test_nettoyage_et_dqa():
    assert DF["ID_Transaction"].is_unique
    assert (DF["Montant (FCFA)"] > 0).all()
    assert 90 <= DQ["score_global"] <= 100
    assert (DQ["transverses"]["Anomalies"] > 0).any()          # les défauts injectés sont bien détectés
    assert dqa.niveau_dqa(99)[0] == "Fiable" and dqa.niveau_dqa(80)[0] == "À corriger"


def test_cohortes_et_entonnoir():
    c = kpis.cohortes(OK, CL, D2)
    assert c is not None and c.shape[0] <= 12
    e = kpis.entonnoir_activation(OK, CL, D1, D2)
    assert e["Clients"].is_monotonic_decreasing


def test_rfm_masque_les_identites():
    r = kpis.rfm(OK, CL, D2)
    assert set(r["Segment_RFM"]) <= {"Champions", "Fidèles", "Nouveaux / prometteurs", "À risque (à relancer)",
                                     "Dormants / perdus", "Occasionnels"}
    assert r["Identité (masquée)"].str.contains(r"\*\*\*").all()
    assert not {"Nom", "Prénom"} & set(r.columns)


def test_alertes_detectent_les_anomalies_injectees():
    al = kpis.detecter_alertes(DF)
    assert len(al["structuring"]) >= 15 and len(al["velocite"]) >= 8 and len(al["nuit"]) >= 8


def test_incidents_detectent_les_pannes_simulees():
    inc = kpis.jours_incident(DF)
    jours = {str(d) for d in inc["Date"]}
    assert "2024-05-14" in jours and "2025-02-20" in jours


def test_prevision_repli_et_forme():
    ser = OK.groupby("Mois_label")["Montant (FCFA)"].sum()
    p, methode = kpis.prevoir(ser, 6)
    assert len(p) == 6 and (p["Bas"] <= p["Prévision"]).all() and (p["Prévision"] <= p["Haut"]).all() and methode
    assert kpis.prevoir(ser.iloc[:3], 6)[0] is None


def test_indicateurs_du_cadre():
    base, cibles, _ = kpis.baselines_et_cibles(D)
    val = kpis.calculer_indicateurs(DF, CL, OBJ, AG, D1, D2, DQ["score_global"])
    t = kpis.tableau_cadre(val, base, cibles, DQ)
    assert len(t) == len(cadre.DEFS) and t["Score DQA (%)"].between(0, 100).all()
    assert cadre.avancement(70, 50, 100, "hausse") == 40
    assert cadre.avancement(30, 40, 20, "baisse") == 50          # indicateur à la baisse
