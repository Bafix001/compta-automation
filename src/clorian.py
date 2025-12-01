import pandas as pd
import io
import re
import logging
from datetime import datetime
import warnings

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Supprimer les avertissements openpyxl
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


def clorian(file_in_memory, file_path):
    """
    Traite un fichier Excel Clorian en mémoire et génère les écritures comptables.
    
    Args:
        file_in_memory: Objet BytesIO contenant le fichier Excel Clorian
        file_path: Chemin ou nom du fichier pour extraction de la date
    
    Returns:
        Liste des lignes comptables générées
    """
    output = []
    stats = {
        'methods_found': {},
        'methods_missing': [],
        'total_lines': 0,
        'total_amount': 0.0
    }
    
    try:
        logger.info("="*80)
        logger.info("DÉBUT DU TRAITEMENT CLORIAN")
        logger.info("="*80)
        logger.info(f"Fichier: {file_path}")
        
        # Validation de l'objet file_in_memory
        if not isinstance(file_in_memory, io.BytesIO):
            logger.error(f"L'objet file_in_memory n'est pas un BytesIO: {type(file_in_memory)}")
            return []
        
        logger.debug("✓ Objet BytesIO valide")
        
        # Extraction de la date du nom de fichier
        file_date_pattern = r'clorian_(\d{2})-(\d{2})-(\d{4})\.xlsx'
        match = re.search(file_date_pattern, file_path)
        
        if match:
            file_date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            try:
                file_date = datetime.strptime(file_date_str, '%d-%m-%Y').strftime('%d/%m/%Y')
                logger.info(f"✓ Date extraite du nom de fichier: {file_date}")
            except ValueError as e:
                logger.error(f"Erreur de format de date '{file_date_str}': {e}")
                file_date = 'date_inconnue'
        else:
            logger.warning(f"Format de nom de fichier non reconnu, impossible d'extraire la date: {file_path}")
            file_date = 'date_inconnue'
        
        # Lecture du fichier Excel depuis BytesIO
        try:
            df = pd.read_excel(file_in_memory, engine='openpyxl', sheet_name='Resultado consulta')
            logger.info(f"✓ Fichier Excel chargé avec {len(df)} lignes")
            logger.info(f"✓ Colonnes détectées: {list(df.columns)}")
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du fichier Excel: {e}")
            return []
        
        # Vérification des colonnes nécessaires
        if 'Méthode de paiement' not in df.columns:
            logger.error("Colonne 'Méthode de paiement' manquante dans le fichier")
            return []
        
        if 'Montant (€)' not in df.columns:
            logger.error("Colonne 'Montant (€)' manquante dans le fichier")
            return []
        
        logger.info("✓ Colonnes requises présentes")
        
        # Afficher les méthodes de paiement disponibles
        available_methods = df['Méthode de paiement'].unique().tolist()
        logger.info(f"\nMéthodes de paiement disponibles dans le fichier:")
        for method in available_methods:
            logger.info(f"  - {method}")
        
        # Aperçu des données
        logger.info(f"\nAperçu des données:")
        logger.info(f"\n{df.to_string()}")
        logger.info("="*80)
        
        # Définition des méthodes de paiement à traiter
        payment_methods_config = {
            "Carte bancaire": {
                "account": 467300,
                "label": "Caisse billeterie CLORIAN CB"
            },
            "Carte Bancaire (TPE Virtuel)": {
                "account": 467300,
                "label": "Caisse billeterie CLORIAN CB TPE Virtuel"
            },
            "Espèces": {
                "account": 531005,
                "label": "Caisse billeterie CLORIAN Espèces"
            },
            "Voucher": {
                "account": 445712,
                "label": "Caisse billeterie CLORIAN Voucher"
            },
            "Amex": {
                "account": 511319,
                "label": "Caisse billeterie CLORIAN Amex"
            }
        }
        
        # Traitement de chaque méthode de paiement
        logger.info("\nTraitement des méthodes de paiement:")
        
        for method, config in payment_methods_config.items():
            method_data = df.loc[df['Méthode de paiement'] == method, 'Montant (€)']
            
            if not method_data.empty:
                amount = method_data.values[0]
                logger.info(f"\n✓ {method}: {amount:.2f} €")
                
                add_payment_line(
                    output, 
                    method, 
                    config["account"], 
                    config["label"], 
                    amount, 
                    file_date
                )
                
                stats['methods_found'][method] = amount
                stats['total_amount'] += amount
                logger.debug(f"  Ligne ajoutée: Compte {config['account']}, Montant {amount:.2f}€")
            else:
                logger.warning(f"✗ {method}: Non trouvé dans le fichier")
                stats['methods_missing'].append(method)
        
        # Traitement des lignes supplémentaires (Total)
        logger.info("\n" + "-"*80)
        logger.info("Traitement des lignes complémentaires:")
        
        total_data = df.loc[df['Méthode de paiement'] == 'Total']
        
        if not total_data.empty:
            logger.info("✓ Ligne 'Total' trouvée")
            additional_lines = add_additional_lines(output, df, file_date)
            stats['total_lines'] += additional_lines
            logger.info(f"✓ {additional_lines} lignes comptables supplémentaires ajoutées")
        else:
            logger.warning("✗ Ligne 'Total' non trouvée, lignes complémentaires ignorées")
        
        # Logs de synthèse
        logger.info("\n" + "="*80)
        logger.info("SYNTHÈSE DU TRAITEMENT CLORIAN")
        logger.info("="*80)
        logger.info(f"Date du fichier: {file_date}")
        logger.info(f"---")
        logger.info(f"Méthodes de paiement trouvées: {len(stats['methods_found'])}")
        for method, amount in stats['methods_found'].items():
            logger.info(f"  • {method}: {amount:.2f} €")
        
        if stats['methods_missing']:
            logger.info(f"\nMéthodes de paiement manquantes: {len(stats['methods_missing'])}")
            for method in stats['methods_missing']:
                logger.info(f"  • {method}")
        
        logger.info(f"---")
        logger.info(f"Montant total traité: {stats['total_amount']:.2f} €")
        logger.info(f"✓ {len(output)} lignes comptables générées au total")
        logger.info("="*80 + "\n")
        
        return output
    
    except FileNotFoundError as e:
        logger.error(f"Fichier introuvable: {e}")
        return []
    
    except KeyError as e:
        logger.error(f"Colonne manquante dans le fichier: {e}")
        return []
    
    except Exception as e:
        logger.exception("Erreur critique lors du traitement du fichier Clorian")
        return []


def add_payment_line(output, method, account_number, label, payment, file_date):
    """
    Ajoute une ligne au tableau de sortie pour une méthode de paiement spécifique.
    
    Args:
        output: Liste de sortie où ajouter la ligne
        method: Nom de la méthode de paiement
        account_number: Numéro de compte comptable
        label: Libellé de l'écriture
        payment: Montant du paiement
        file_date: Date de l'écriture
    """
    output.append([
        "CA", file_date, None, account_number, None, label, file_date, 
        payment, None, "", "", "", "", "", "", "", "", "", "", "", ""
    ])
    logger.debug(f"  Ligne ajoutée pour {method}: Compte {account_number}, {payment:.2f}€")


def add_additional_lines(output, df, file_date):
    """
    Ajoute des lignes supplémentaires basées sur les informations de 'Total' et 'Espèces'.
    
    Args:
        output: Liste de sortie où ajouter les lignes
        df: DataFrame contenant les données
        file_date: Date de l'écriture
    
    Returns:
        Nombre de lignes ajoutées
    """
    lines_added = 0
    
    try:
        # Récupération des données du Total
        total_payment_ht = df.loc[df['Méthode de paiement'] == 'Total', 'Montant (HT)']
        total_tva = df.loc[df['Méthode de paiement'] == 'Total', 'TVA (€)']
        cash_payment = df.loc[df['Méthode de paiement'] == 'Espèces', 'Montant (€)']
        
        # Ligne HT (706101)
        if not total_payment_ht.empty:
            ht_amount = total_payment_ht.values[0]
            output.append([
                "CA", file_date, None, 706101, "REVSAPVISIN", 
                "Caisse billeterie CLORIAN", file_date, None, ht_amount,
                "", "", "", "", "", "", "", "", "", "", "", ""
            ])
            logger.debug(f"  Ligne HT ajoutée: 706101, {ht_amount:.2f}€")
            lines_added += 1
        else:
            logger.warning("  Montant HT (Total) non trouvé")
        
        # Ligne TVA (445712)
        if not total_tva.empty:
            tva_amount = total_tva.values[0]
            output.append([
                "CA", file_date, None, 445712, None, 
                "Caisse billeterie CLORIAN", file_date, None, tva_amount,
                "", "", "", "", "", "", "", "", "", "", "", ""
            ])
            logger.debug(f"  Ligne TVA ajoutée: 445712, {tva_amount:.2f}€")
            lines_added += 1
        else:
            logger.warning("  Montant TVA (Total) non trouvé")
        
        # Lignes Espèces (580005 et 531005)
        if not cash_payment.empty:
            cash_amount = cash_payment.values[0]
            
            output.append([
                "CA", file_date, None, 580005, None, 
                "Caisse billeterie CLORIAN", file_date, cash_amount, None,
                "", "", "", "", "", "", "", "", "", "", "", ""
            ])
            logger.debug(f"  Ligne Espèces débit ajoutée: 580005, {cash_amount:.2f}€")
            lines_added += 1
            
            output.append([
                "CA", file_date, None, 531005, None, 
                "Caisse billeterie CLORIAN", file_date, None, cash_amount,
                "", "", "", "", "", "", "", "", "", "", "", ""
            ])
            logger.debug(f"  Ligne Espèces crédit ajoutée: 531005, {cash_amount:.2f}€")
            lines_added += 1
        else:
            logger.warning("  Montant Espèces non trouvé, lignes 580005/531005 non générées")
        
        return lines_added
    
    except IndexError as e:
        logger.error(f"Erreur d'index lors de l'ajout des lignes supplémentaires: {e}")
        return lines_added
    
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout des lignes supplémentaires: {e}")
        return lines_added
