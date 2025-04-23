import sys  # Importation du module sys pour manipuler des arguments de ligne de commande et interagir avec le système d'exploitation

# Classe définissant des couleurs pour le texte dans le terminal, utilisées pour formater l'affichage des messages
class bcolors:
    OKBLUE = '\033[94m'  # Couleur bleue
    OKGREEN = '\033[92m'  # Couleur verte
    WARNING = '\033[93m'  # Couleur orange pour les avertissements
    FAIL = '\033[91m'  # Couleur rouge pour les erreurs
    ENDC = '\033[0m'  # Code pour réinitialiser les couleurs au format par défaut
    BOLD = '\033[1m'  # Code pour appliquer le gras au texte

# Variables globales contenant des informations relatives au programme
PROGRAM_DESCRIPTION = "Merges multiple CSV data formats given as input to a single format compatible with Capilog for LUMA's accounting"  # Description du programme
SOURCE_TYPES = ["CLORIAN", "SHOPIFY", "STRIPE"]  # Types de sources de données acceptés
PROGRAM_NAME = sys.argv[0]  # Nom du programme exécuté

# Fonctions utilitaires pour formater les textes et les afficher avec différentes couleurs
CLEAN_STR = lambda text: text.strip().replace('\n', '')  # Nettoyage de texte
FORMAT_FAIL = lambda text: bcolors.FAIL + bcolors.BOLD + text + bcolors.ENDC  # Format d'erreur en rouge
FORMAT_OK = lambda text: bcolors.OKGREEN + bcolors.BOLD + text + bcolors.ENDC  # Format de succès en vert
FORMAT_OKBLUE = lambda text: bcolors.OKBLUE + bcolors.BOLD + text + bcolors.ENDC  # Format d'information en bleu
FORMAT_WARNING = lambda text: bcolors.WARNING + bcolors.BOLD + text + bcolors.ENDC  # Format d'avertissement en orange
PRINT_ERR = lambda msg: print((f"{PROGRAM_NAME}: {msg}"), file=sys.stderr)  # Fonction pour afficher un message d'erreur

# Paramètres spécifiques à la gestion des données
# CLORIAN_IGNORED_LIGNES = 6  # Nombre de lignes à ignorer pour le traitement des fichiers Clorian

# Liste des pays membres de l'Union Européenne à l'excxeption de la France pour traitement dans shopify
PAYS_UE = [  
    "Germany", "Austria", "Belgium", "Bulgaria", "Cyprus", "Croatia", "Denmark",
    "Spain", "Estonia", "Finland", "Greece", "Hungary", "Ireland",
    "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland",
    "Portugal", "Czech Republic", "Romania", "Slovakia", "Slovenia", "Sweden"
]

# Dictionnaire pour mapper les méthodes de paiement à leurs paramètres
PAYMENT_METHODS = {
    "Carte bancaire": {"account_number": 467300, "label": "Caisse billeterie CLORIAN CB"},
    "Carte Bancaire (TPE Virtuel)": {"account_number": 467300, "label": "Caisse billeterie CLORIAN CB TPE Virtuel"},
    "Espèces": {"account_number": 531005, "label": "Caisse billeterie CLORIAN"},
    "Voucher": {"account_number": 511200, "label": "Caisse billeterie CLORIAN"},
    "Amex":    {"account_number": 511319, "label": "Caisse billeterie CLORIAN"},
}

# # Lignes supplémentaires à ajouter à la fin
# ADDITIONAL_LINES_TEMPLATE = [
#     {"account_number": 706101, "label": "REVSAPVISIN", "description": "Caisse billeterie CLORIAN", "column_index": 3},
#     {"account_number": 445712, "label": None, "description": "Caisse billeterie CLORIAN", "column_index": 4},
#     {"account_number": 580005, "label": None, "description": "Caisse billeterie CLORIAN", "column_index": 1},
#     {"account_number": 531005, "label": None, "description": "Caisse billeterie CLORIAN", "column_index": 1}
# ]
