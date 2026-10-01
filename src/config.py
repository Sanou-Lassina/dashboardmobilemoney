"""Constantes métier, palette et libellés partagés par toute l'application."""
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
FICHIER_DEFAUT = DATA_DIR / "Base_MobileMoney.xlsx"
LOGO = APP_DIR / "assets" / "logo.png"

# ─── Palette ───
ORANGE, VERT, BLEU = "#FF6B2C", "#00B388", "#003366"
GRIS, ROUGE, JAUNE, VIOLET = "#F5F7FA", "#E63946", "#FFB703", "#7B2D8B"
PALETTE = [ORANGE, VERT, BLEU, JAUNE, ROUGE, VIOLET, "#06A77D", "#F4A261"]

# ─── Statuts ───
STATUT_OK, STATUT_KO, STATUT_ATT, STATUT_INCONNU = "Succès", "Échoué", "En Attente", "Inconnu"
STATUTS_CONNUS = [STATUT_OK, STATUT_KO, STATUT_ATT]

# ─── Produits / flux ───
P_DEPOT, P_RETRAIT, P_P2P = "Dépôt (Cash-in)", "Retrait (Cash-out)", "Transfert P2P"
P_FACTURE, P_CREDIT, P_MARCHAND = "Paiement facture", "Achat crédit", "Paiement marchand"
PRODUITS = [P_DEPOT, P_RETRAIT, P_P2P, P_FACTURE, P_CREDIT, P_MARCHAND]
CANAUX = ["Agent", "USSD", "App Mobile", "API Marchand"]
CANAL_AGENT = "Agent"

MOTIFS_ECHEC = [
    "Solde insuffisant", "PIN erroné", "Timeout réseau",
    "Plafond dépassé", "Compte/KYC non conforme", "Float agent insuffisant",
]

# ─── Règles de risque / conformité (paramétrables) ───
PLAFOND_TX = 1_000_000          # plafond unitaire de transaction (FCFA)
SEUIL_STRUCTURING = 0.90        # part du plafond à partir de laquelle une tx est "juste sous le plafond"
SEUIL_VELOCITE = 8              # nb de tx d'un même client dans la même heure
SEUIL_NUIT_MONTANT = 200_000    # montant jugé atypique en tranche nocturne (00h-05h)
ACTIF_JOURS = 30
DORMANT_JOURS = 90

MOIS_FR = {
    "Janvier": 1, "Février": 2, "Fevrier": 2, "Mars": 3, "Avril": 4, "Mai": 5, "Juin": 6,
    "Juillet": 7, "Août": 8, "Aout": 8, "Septembre": 9, "Octobre": 10, "Novembre": 11,
    "Décembre": 12, "Decembre": 12,
}
MOIS_NOMS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
             "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
JOURS_FR = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

# Seuils de lecture (feux tricolores) pour les taux d'atteinte
SEUIL_VERT, SEUIL_ORANGE = 100.0, 80.0
