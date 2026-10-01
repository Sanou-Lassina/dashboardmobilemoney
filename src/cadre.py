"""Cadre de suivi des indicateurs : définitions, sources, fréquence, cibles par défaut."""

DEFS = [
    dict(id="IND01", categorie="Volume", nom="GTV mensuel moyen", unite="M FCFA", sens="hausse", fmt=".1f",
         definition="Valeur brute des transactions réussies, ramenée à un mois moyen sur la période.",
         formule="Σ Montant (Statut = Succès) ÷ nombre de mois de la période",
         source="Transactions", frequence="Mensuelle", responsable="Direction Commerciale",
         champs="Transactions.Date;Transactions.Montant (FCFA);Transactions.Statut"),
    dict(id="IND02", categorie="Rentabilité", nom="Revenu net mensuel moyen", unite="M FCFA", sens="hausse", fmt=".2f",
         definition="Commissions perçues moins commissions reversées aux agents, en moyenne mensuelle.",
         formule="Σ (Commission − Commission_Agent) des transactions réussies ÷ nombre de mois",
         source="Transactions", frequence="Mensuelle", responsable="Finance",
         champs="Transactions.Date;Transactions.Commission (FCFA);Transactions.Montant (FCFA);Transactions.Statut"),
    dict(id="IND03", categorie="Rentabilité", nom="Take rate (revenu brut / GTV)", unite="%", sens="hausse", fmt=".2f",
         definition="Part du volume traité transformée en commissions brutes.",
         formule="Σ Commission ÷ Σ Montant (transactions réussies) × 100",
         source="Transactions", frequence="Mensuelle", responsable="Finance",
         champs="Transactions.Commission (FCFA);Transactions.Montant (FCFA);Transactions.Statut"),
    dict(id="IND04", categorie="Qualité de service", nom="Taux de succès des transactions", unite="%", sens="hausse", fmt=".1f",
         definition="Part des transactions initiées qui aboutissent.",
         formule="Transactions Succès ÷ toutes les transactions × 100",
         source="Transactions", frequence="Hebdomadaire", responsable="Opérations / SI",
         champs="Transactions.Statut;Transactions.Date"),
    dict(id="IND05", categorie="Performance commerciale", nom="Taux d'atteinte de l'objectif de montant", unite="%", sens="hausse", fmt=".1f",
         definition="CA réalisé rapporté à l'objectif, sur les mois complets de la période, toutes agences.",
         formule="Σ CA (agence × mois complet) ÷ Σ Objectif (agence × année × mois) × 100",
         source="Transactions + Objectifs", frequence="Mensuelle", responsable="Direction Commerciale",
         champs="Transactions.Montant (FCFA);Transactions.Statut;Transactions.Agence;Objectifs.Objectif_Montant (FCFA);Objectifs.Année"),
    dict(id="IND06", categorie="Base clients", nom="Clients actifs sur 30 jours", unite="clients", sens="hausse", fmt=",.0f",
         definition="Clients distincts ayant réalisé au moins une transaction réussie dans les 30 derniers jours de la période.",
         formule="Nombre de ID_Client distincts (Succès) sur [fin − 29 j ; fin]",
         source="Transactions", frequence="Mensuelle", responsable="Marketing / CRM",
         champs="Transactions.ID_Client;Transactions.Statut;Transactions.Date"),
    dict(id="IND07", categorie="Base clients", nom="Taux d'activité 30 jours", unite="%", sens="hausse", fmt=".1f",
         definition="Part des clients inscrits qui sont actifs sur 30 jours.",
         formule="Clients actifs 30 j ÷ clients inscrits à la date de fin × 100",
         source="Transactions + Clients", frequence="Mensuelle", responsable="Marketing / CRM",
         champs="Transactions.ID_Client;Transactions.Statut;Clients.Date_Inscription"),
    dict(id="IND08", categorie="Base clients", nom="Churn 30 jours", unite="%", sens="baisse", fmt=".1f",
         definition="Part des clients actifs sur la fenêtre précédente qui ne le sont plus sur la fenêtre courante.",
         formule="Actifs [fin−59 ; fin−30] absents de [fin−29 ; fin] ÷ Actifs [fin−59 ; fin−30] × 100",
         source="Transactions", frequence="Mensuelle", responsable="Marketing / CRM",
         champs="Transactions.ID_Client;Transactions.Statut;Transactions.Date"),
    dict(id="IND09", categorie="Réseau", nom="Taux d'activité des agents (30 j)", unite="%", sens="hausse", fmt=".1f",
         definition="Part des agents activés qui ont traité au moins une transaction réussie sur 30 jours.",
         formule="Agents actifs 30 j ÷ agents activés à la date de fin × 100",
         source="Transactions + Agents", frequence="Mensuelle", responsable="Réseau de distribution",
         champs="Transactions.ID_Agent;Transactions.Statut;Transactions.Date"),
    dict(id="IND10", categorie="Inclusion / digitalisation", nom="Part des transactions digitales", unite="%", sens="hausse", fmt=".1f",
         definition="Part des transactions réussies réalisées hors canal Agent (USSD, application, API marchand).",
         formule="Transactions réussies hors canal Agent ÷ transactions réussies × 100",
         source="Transactions", frequence="Trimestrielle", responsable="Produits & Digital",
         champs="Transactions.Canal;Transactions.Statut"),
    dict(id="IND11", categorie="Inclusion / genre", nom="Part des femmes parmi les clients actifs", unite="%", sens="hausse", fmt=".1f",
         definition="Proportion de femmes parmi les clients actifs sur 30 jours (sexe renseigné).",
         formule="Clientes actives 30 j ÷ clients actifs 30 j (sexe connu) × 100",
         source="Transactions + Clients", frequence="Trimestrielle", responsable="Inclusion financière",
         champs="Clients.Sexe;Transactions.ID_Client;Transactions.Statut"),
    dict(id="IND12", categorie="Inclusion / territoire", nom="Part des clients actifs hors Ouagadougou et Bobo-Dioulasso", unite="%", sens="hausse", fmt=".1f",
         definition="Mesure la pénétration en dehors des deux grandes métropoles.",
         formule="Clients actifs 30 j (ville ≠ Ouagadougou, Bobo-Dioulasso) ÷ clients actifs 30 j × 100",
         source="Transactions + Clients", frequence="Trimestrielle", responsable="Inclusion financière",
         champs="Clients.Ville;Transactions.ID_Client;Transactions.Statut"),
    dict(id="IND13", categorie="Qualité de service", nom="Part des transactions en échec réseau", unite="%", sens="baisse", fmt=".2f",
         definition="Transactions échouées ou bloquées pour cause de timeout réseau.",
         formule="Transactions (Motif = Timeout réseau) ÷ toutes les transactions × 100",
         source="Transactions", frequence="Hebdomadaire", responsable="Opérations / SI",
         champs="Transactions.Motif_Echec;Transactions.Statut"),
    dict(id="IND14", categorie="Gouvernance des données", nom="Score global de qualité des données (DQA)", unite="%", sens="hausse", fmt=".1f",
         definition="Synthèse de la complétude, de la validité, de l'unicité et de la cohérence des données sources.",
         formule="50 % moyenne des scores de champs + 50 % moyenne des contrôles transverses",
         source="Toutes les feuilles", frequence="À chaque chargement", responsable="Data & SI",
         champs=""),
]

DEF_PAR_ID = {d["id"]: d for d in DEFS}


def cibles_par_defaut(base: dict) -> dict:
    """Cibles proposées à partir de la valeur de référence (à valider avec les parties prenantes)."""
    b = lambda k: base.get(k)  # noqa: E731
    def sûr(k, f, repli):
        v = b(k)
        return f(v) if v is not None and v == v else repli
    return {
        "IND01": sûr("IND01", lambda v: v * 1.6, None),
        "IND02": sûr("IND02", lambda v: v * 1.6, None),
        "IND03": sûr("IND03", lambda v: v * 1.05, None),
        "IND04": sûr("IND04", lambda v: max(98.0, v + 1), 98.0),
        "IND05": 100.0,
        "IND06": sûr("IND06", lambda v: v * 1.8, None),
        "IND07": sûr("IND07", lambda v: min(95.0, v + 10), None),
        "IND08": sûr("IND08", lambda v: v * 0.8, None),
        "IND09": sûr("IND09", lambda v: min(98.0, max(90.0, v + 5)), 90.0),
        "IND10": sûr("IND10", lambda v: min(95.0, v + 15), None),
        "IND11": sûr("IND11", lambda v: max(45.0, v + 3), 45.0),
        "IND12": sûr("IND12", lambda v: min(95.0, v + 8), None),
        "IND13": sûr("IND13", lambda v: v * 0.6, None),
        "IND14": sûr("IND14", lambda v: max(95.0, v), 95.0),
    }


def avancement(actuel, baseline, cible, sens):
    """Avancement vers la cible en % : 0 = baseline, 100 = cible atteinte (valable hausse comme baisse)."""
    try:
        if any(x is None or x != x for x in (actuel, baseline, cible)):
            return None
        if cible == baseline:
            return 100.0 if ((actuel >= cible) if sens == "hausse" else (actuel <= cible)) else 0.0
        return (actuel - baseline) / (cible - baseline) * 100
    except TypeError:
        return None


def feu(av):
    """Feu tricolore selon l'avancement."""
    if av is None:
        return "Non évalué"
    if av >= 100:
        return "Atteint"
    if av >= 60:
        return "En bonne voie"
    return "En retard"
