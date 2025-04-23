import pandas as pd
import io
import re
from datetime import datetime
import warnings
# from contstants import PAYMENT_METHODS  # Assurez-vous que ce module existe aussi

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

def clorian(file_in_memory, file_path):
    """
    Traite le fichier Clorian à partir d'un objet BytesIO et renvoie les lignes formatées pour un fichier CSV.
    """
    # Vérifier que file_in_memory est bien un objet BytesIO
    if not isinstance(file_in_memory, io.BytesIO):
        print(f"Erreur: 'file_in_memory' n'est pas un objet BytesIO : {file_in_memory}")
        return []  # Retourner une liste vide en cas d'erreur
    
    # Charger le fichier Excel depuis l'objet BytesIO
    try:
        df = pd.read_excel(file_in_memory, engine='openpyxl', sheet_name='Resultado consulta')
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier en mémoire : {e}")
        return []  # Retourner une liste vide en cas d'erreur

    # Extraire la date du nom de fichier
    file_date_pattern = r'clorian_(\d{2})-(\d{2})-(\d{4})\.xlsx'
    match = re.search(file_date_pattern, file_path)

    if match:
        file_date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        try:
            file_date = datetime.strptime(file_date_str, '%d-%m-%Y').strftime('%d/%m/%Y')
        except ValueError as e:
            print(f"Erreur de format de date: {e}")
            file_date = 'date_inconnue'
    else:
        file_date = 'date_inconnue'

    # Vérification des colonnes nécessaires
    columns_needed = {
        "Carte bancaire": False,
        "Carte Bancaire (TPE Virtuel)": False,
        "Espèces": False,
        "Voucher": False,
        "Amex": False,
        "Total": False
    }

    for col in columns_needed.keys():
        if col in df['Méthode de paiement'].values:
            columns_needed[col] = True
        else:
            print(f"[AVERTISSEMENT] Colonne manquante : {col}")
    
    output = []
    
    # Génération des lignes pour chaque méthode de paiement
    if columns_needed["Carte bancaire"]:
        add_payment_line(output, "Carte bancaire", 467300, "Caisse billeterie CLORIAN CB", 
                         df.loc[df['Méthode de paiement'] == 'Carte bancaire', 'Montant (€)'].values[0], file_date)

    if columns_needed["Carte Bancaire (TPE Virtuel)"]:
        add_payment_line(output, "Carte Bancaire (TPE Virtuel)", 467300, "Caisse billeterie CLORIAN CB TPE Virtuel", 
                         df.loc[df['Méthode de paiement'] == 'Carte Bancaire (TPE Virtuel)', 'Montant (€)'].values[0], file_date)

    if columns_needed["Espèces"]:
        add_payment_line(output, "Espèces", 531005, "Caisse billeterie CLORIAN Espèces", 
                         df.loc[df['Méthode de paiement'] == 'Espèces', 'Montant (€)'].values[0], file_date)

    if columns_needed["Voucher"]:
        add_payment_line(output, "Voucher", 445712, "Caisse billeterie CLORIAN Voucher", 
                         df.loc[df['Méthode de paiement'] == 'Voucher', 'Montant (€)'].values[0], file_date)

    if columns_needed["Amex"]:
        add_payment_line(output, "Amex", 511319, "Caisse billeterie CLORIAN Amex", 
                         df.loc[df['Méthode de paiement'] == 'Amex', 'Montant (€)'].values[0], file_date)

    if columns_needed["Total"]:
        add_additional_lines(output, df, file_date)
    
    return output

def add_payment_line(output, method, account_number, label, payment, file_date):
    """
    Ajoute une ligne au tableau de sortie pour une méthode de paiement spécifique.
    """
    output.append(["CA", file_date, None, account_number, None, label, file_date, payment, None])

def add_additional_lines(output, df, file_date):
    """
    Ajoute des lignes supplémentaires basées sur les informations de 'Total' et 'Espèces'.
    """
    total_payment_tva = df.loc[df['Méthode de paiement'] == 'Total', 'Montant (HT)']
    cash_payment = df.loc[df['Méthode de paiement'] == 'Espèces', 'Montant (€)']
    tpe_virtual_payment = df.loc[df['Méthode de paiement'] == 'Total', 'TVA (€)']

    if not total_payment_tva.empty:
        output.append(["CA", file_date, None, 706101, "REVSAPVISIN", "Caisse billeterie CLORIAN", file_date, None, total_payment_tva.values[0]])
        output.append(["CA", file_date, None, 445712, None, "Caisse billeterie CLORIAN", file_date, None, tpe_virtual_payment.values[0]])
        
        if not cash_payment.empty:
            output.append(["CA", file_date, None, 580005, None, "Caisse billeterie CLORIAN", file_date, cash_payment.values[0], None])
            output.append(["CA", file_date, None, 531005, None, "Caisse billeterie CLORIAN", file_date, None, cash_payment.values[0]])
