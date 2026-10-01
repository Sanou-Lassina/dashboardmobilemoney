# 💸 Mobile Money — Dashboard de pilotage (Burkina Faso)

Application Streamlit multi-pages pour piloter un opérateur Mobile Money : ventes, réseau d'agents, clients,
qualité de service, risques, et **cadre de suivi des indicateurs avec score de qualité des données (DQA)**.
Les données fournies sont **simulées** mais construites pour être plausibles (voir `src/generate_data.py`).

## Lancer

```bash
pip install -r requirements.txt
streamlit run app.py
```

Le classeur `data/Base_MobileMoney.xlsx` est fourni (il est régénéré automatiquement s'il manque).
Pour en produire un nouveau : `python -m src.generate_data --graine 7 --transactions 60000`.
Tests : `pip install -r requirements-dev.txt && pytest -q`.

## Pages

| Page | Question à laquelle elle répond |
|---|---|
| 📌 Résumé exécutif | Où en est-on ? Quels signaux exigent une décision ? (messages automatiques, export Excel et note HTML) |
| 📈 Ventes & Tendances | Quelle trajectoire ? Réalisé vs objectif, cascade volume/mix/panier, saisonnalité, prévision |
| 📦 Produits & Canaux | Quels produits et canaux créent du revenu net ? Où en est la digitalisation ? |
| 🏢 Réseau & Agences | Quelles agences / quels agents performent ? Liquidité cash-in/out, carte, Pareto |
| 👥 Clients & Rétention | Qui est actif, qui part ? Cohortes, entonnoir d'activation, RFM avec listes d'action |
| ⚠️ Qualité de service & Risques | Pourquoi les transactions échouent-elles ? Pannes probables, fraude et conformité |
| 🎯 Cadre de suivi & DQA | 14 indicateurs : définition, source, fréquence, baseline, cible, valeur actuelle, score DQA |

## Modèle de données (classeur Excel)

* **Transactions** : `Date` (avec heure), `ID_Transaction`, `ID_Client`, `Agence`, `Ville`, `Commercial`, `ID_Agent`, `Produit`, `Canal`,
  `Montant (FCFA)`, `Commission (FCFA)`, `Commission_Agent (FCFA)`, `Statut` (Succès / Échoué / En Attente), `Motif_Echec`.
* **Clients** : `ID_Client`, `Nom`, `Prénom`, `Sexe`, `Age`, `Segment`, `KYC_Niveau`, `Date_Inscription`, `Agence`, `Ville`, `Commercial`.
* **Objectifs** : une ligne par **Agence × Année × Mois** : `Agence`, `Région`, `Année`, `Mois`, `N° Mois`,
  `Objectif_Montant (FCFA)`, `Objectif_Transactions`, `Taux_Commission_Cible (%)`.
* **Agents** (facultative) : `ID_Agent`, `Nom_Point`, `Agence`, `Ville`, `Commercial`, `Date_Activation`, `Latitude`, `Longitude`.
* **Indicateurs** (facultative) : `ID_Indicateur`, `Baseline`, `Cible` (sinon : baseline = 1er trimestre des données, cibles par défaut).

Un **ancien classeur** (sans `Année`, sans `Agents`, sans les colonnes récentes) reste chargeable : chaque correction ou
reconstruction est tracée dans le *Journal du nettoyage* (page Cadre de suivi & DQA).

## Définitions des KPI

* **GTV** : Σ montants des transactions réussies. **Revenu brut** : Σ commissions. **Revenu net** : brut − commissions agents.
* **Take rate** : revenu brut ÷ GTV. **ARPU mensuel** : revenu brut mensuel ÷ clients actifs du mois, moyenné.
* **Actifs 30 j / 90 j** : clients distincts avec ≥ 1 transaction réussie. **Churn 30 j** : actifs de la fenêtre précédente absents de la courante.
* **Dormant** : inscrit depuis plus de 90 jours, aucune transaction réussie sur 90 jours.
* **Atteinte d'objectif** : Σ réalisé ÷ Σ objectif, **uniquement sur les mois complets** de la période, agrégé **agence × mois avant jointure**.
  Non calculée si un filtre Produit, Canal, Segment ou Commercial est actif (l'objectif est fixé par agence).
* **Ratio cash-in ÷ cash-out** : > 1,3 → e-float des agents sous tension ; < 0,7 → cash sous tension (seuils indicatifs).

## Qualité des données (DQA)

Contrôles sur les données **brutes** : complétude, validité (règles par champ), unicité, intégrité référentielle, cohérence
chronologique et couverture des objectifs. Score d'un indicateur = 70 % qualité des champs sources + 30 % contrôles transverses.
Niveaux : ≥ 95 % *Fiable* · 85-95 % *Acceptable* · < 85 % *À corriger*.

## Corrections apportées à la version initiale

1. Objectifs agrégés **avant** jointure (ils étaient additionnés autant de fois qu'il y avait de transactions) et jointure sur Agence × Année × Mois.
2. `date_input` robuste à la sélection d'une seule date ; garde-fou si aucune donnée.
3. Semaines et trimestres de 2024 et 2025 ne sont plus fusionnés.
4. Delta MoM remplacé par une vraie comparaison (période précédente ou N-1) ; médiane ajoutée au panier moyen.
5. Navigation `st.navigation` (une seule page calculée à la fois), filtres en cascade, bouton de réinitialisation, `st.fragment` pour les contrôles locaux.
6. Identités clients masquées ; « données stimulées » corrigé en « simulées ».

## Limites connues

* Volumes simulés à l'échelle d'un **échantillon** (≈ 54 M FCFA de GTV mensuel) : ne pas les lire comme ceux d'un opérateur réel.
* Seuils de risque, de liquidité et de statut (`src/config.py`, `src/cadre.py`) : valeurs de départ à calibrer avec les équipes métier.
* La prévision (Holt-Winters dès 24 mois d'historique, sinon tendance) est indicative.
* Export PDF : la note de synthèse est en HTML, à imprimer en PDF depuis le navigateur (Ctrl+P).

## Déploiement

Pousser le dépôt sur GitHub puis, dans Streamlit Community Cloud, choisir `app.py` comme fichier principal.
