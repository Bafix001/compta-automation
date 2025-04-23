import csv  # Importation de la bibliothèque csv pour manipuler les fichiers CSV
from contstants import PAYS_UE, PRINT_ERR  # Importation des constantes liées aux pays de l'UE et des fonctions pour gérer les erreurs
from datetime import datetime  # Importation de datetime pour la gestion des dates
import io
import pandas as pd

# Fonction pour ajouter des informations liées au montant TTC dans les données de sortie
def add_montant_ttc(out_data, Date, amount, Reference):
    # La fonction ajoute une ligne dans la liste de sortie avec des informations de montant total
    out_data.append([
        "VES", Date, None, "411SHOPI", None, "Shopify", Date, amount, None, 
        "", "", "", "", "", "", Reference, "", "", "", "", "" 
    ])


# Fonction utilitaire pour convertir des valeurs en float de manière sécurisée
def safe_float(value, default=0.0):
    # Tente de convertir la valeur en float. Si une erreur se produit, elle retourne une valeur par défaut
    try:
        if isinstance(value, str):  # Si la valeur est une chaîne, on peut utiliser strip()
            value = value.strip()
        
        # Si la valeur est vide après strip(), on retourne la valeur par défaut
        if value == "":
            return default

        # Conversion en float
        return float(value)  
    except (ValueError, TypeError) as e:
        PRINT_ERR(f"[AVERTISSEMENT] Impossible de convertir la valeur '{value}' en float. Valeur par défaut utilisée : {default} -> Erreur : {e}")
        return default  # Retourne la valeur par défaut en cas d'erreur



# Fonction pour formater une date en un format spécifique (jj/mm/aaaa)
def date_format(date_str):
    # Si c'est déjà un datetime, retourne juste le format souhaité
    if isinstance(date_str, datetime):
        return date_str.strftime("%d/%m/%Y")
    formats = ["%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            continue
    raise ValueError(f"Date non valide : {date_str}")




# Fonction principale pour traiter les données provenant d'une source Shopify

def shopify(src) -> list:
    out_data = []  # Liste qui contiendra les données de sortie traitées

    try:
        # Ouverture du fichier Excel pour lecture avec pandas
        df = pd.read_excel(src, engine='openpyxl')

        # Vérification si le DataFrame est vide
        if df.empty:
            PRINT_ERR(f"[AVERTISSEMENT] Le fichier '{src}' est vide.")
            return []

        # Traitement de chaque ligne du DataFrame
        for index, row in df.iloc[:-1].iterrows():
            try:
                # Extraction des valeurs de chaque ligne et application des transformations nécessaires
                Date = row.get('Date', '')
                Date = date_format(Date)  # Formater la date
                amount = safe_float(row.get('Total Sales', '0'))
                country = row.get('Shipping Country', '')
                tva_present = row.get('Note', '0')
                amount_HT_TVA = safe_float(row.get('Net Sales', '0')) 
                Frais_port = safe_float(row.get('Shipping', '0')) 
                Tva_collect = safe_float(row.get('Tax', '0')) 
                Référence = row.get('Order Name', '')

                # Ajout des lignes spécifiques pour la France
                if country == "France":
                    out_data.extend([
                        ["VES", Date, None, 707101, "REVOFFPBOOK", "Shopify", Date, None, amount_HT_TVA, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                        ["VES", Date, None, 708502, "REVOFFPBOOK", "Shopify", Date, None, Frais_port, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                        ["VES", Date, None, 445713, None, "Shopify", Date, None, Tva_collect, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                    ])
                # Ajout des lignes spécifiques pour les pays de l'UE
                elif country in PAYS_UE:
                    if tva_present:
                        out_data.extend([
                            ["VES", Date, None, 707400, "REVOFFPBOOK", "Shopify", Date, None, amount_HT_TVA, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                            ["VES", Date, None, 708500, "REVOFFPBOOK", "Shopify", Date, None, Frais_port, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                        ])
                    else:  
                        out_data.extend([
                            ["VES", Date, None, 707500, "REVOFFPBOOK", "Shopify", Date, None, amount_HT_TVA, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                            ["VES", Date, None, 708503, "REVOFFPBOOK", "Shopify", Date, None, Frais_port, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                            ["VES", Date, None, 445713, None, "Shopify", Date, None, Tva_collect, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                        ])
                # Ajout des lignes pour les pays en dehors de l'UE
                else:  
                    out_data.extend([
                        ["VES", Date, None, 707300, "REVOFFPBOOK", "Shopify", Date, None, amount_HT_TVA, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                        ["VES", Date, None, 708500, "REVOFFPBOOK", "Shopify", Date, None, Frais_port, "", "", "", "", "", "", Référence, "", "", "", "", ""],
                    ])

                # Ajout du montant TTC à la sortie
                add_montant_ttc(out_data, Date, amount, Référence)  

            except ValueError as e:
                # En cas d'erreur de conversion de données, affiche un avertissement
                PRINT_ERR(f"[AVERTISSEMENT] Erreur de conversion dans la ligne : {row} -> {e}")

    except FileNotFoundError:
        # Si le fichier n'est pas trouvé, affiche une erreur
        PRINT_ERR(f"[ERREUR] Le fichier '{src}' est introuvable. Veuillez vérifier le chemin du fichier.")
    except Exception as e:
        # Si une autre erreur survient, affiche un message d'erreur générique
        PRINT_ERR(f"[ERREUR] Une erreur s'est produite lors du traitement du fichier : {e}")        

    return out_data  # Retourne les données transformées prêtes à l'export
