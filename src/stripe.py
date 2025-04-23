import csv  # Importation de la bibliothèque csv pour manipuler les fichiers CSV
import io  # Pour travailler avec les fichiers en mémoire
from contstants import PRINT_ERR  # Importation des fonctions pour gérer les erreurs
from datetime import datetime  # Importation de datetime pour la gestion des dates
from shopify import safe_float, date_format


# Fonction principale pour traiter les données provenant d'une source Stripe
def st(file_in_memory) -> list:
    out_data = []  # Liste qui contiendra les données de sortie traitées
    try:
        # Conversion du fichier en mémoire (BytesIO) en un format lisible par csv.DictReader
        file_in_memory.seek(0)  # Assurez-vous que le curseur est au début du fichier
        csvreader = csv.DictReader(io.StringIO(file_in_memory.getvalue().decode('utf-8')))  # Lire le CSV depuis la mémoire
        rows = list(csvreader)  # Transformation des lignes en une liste

        # Si le fichier est vide, un avertissement est affiché
        if not rows:
            PRINT_ERR(f"[AVERTISSEMENT] Le fichier est vide")
            return []

        # Traitement de chaque ligne du fichier
        for row in rows:
            try:
                # Extraction des valeurs de chaque ligne et application des transformations nécessaires
                Date = row.get('created_date')
                if Date:
                    Date = date_format(Date)
                else:
                    PRINT_ERR(f"[AVERTISSEMENT] La date est manquante pour la ligne {row}")
                    continue

                mail = row.get('customer_email')
                amount = safe_float(row.get('amount_decimal', '0'))
                if not amount:
                    PRINT_ERR(f"[AVERTISSEMENT] Montant invalide ou manquant pour la ligne {row}")
                    continue

                amount_ht = round(amount / 1.10, 2)
                Tva_collect = round(amount - amount_ht, 2)

                # Ajout des données dans `out_data`
                out_data.append([
                    "B5", Date, None, "411SAP", None, mail, Date, amount, None
                ])
                out_data.append([
                    "B5", Date, None, 512500, None, mail, Date, None, amount
                ])
                out_data.append([
                    "VE", Date, None, "411SAP", None, mail, Date, amount, None
                ])
                out_data.append([
                    "VE", Date, None, 706101, "REVSAPVISGR", mail, Date, None, amount_ht
                ])
                out_data.append([
                    "VE", Date, None, 445712, None, mail, Date, None, Tva_collect
                ])

            except Exception as e:
                PRINT_ERR(f"[ERREUR] Impossible de traiter la ligne {row}: {e}")
                continue

        # Trier les données par date (si nécessaire)
        try:
            out_data.sort(key=lambda x: datetime.strptime(x[1], "%d/%m/%Y"))
        except ValueError as e:
            PRINT_ERR(f"[ERREUR] Problème de format de date lors du tri: {e}")
            return []

        return out_data if out_data else []

    except Exception as e:
        PRINT_ERR(f"[ERREUR] Problème avec l'ouverture du fichier en mémoire: {e}")
        return []
