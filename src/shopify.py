import csv
import io
import logging
from datetime import datetime
import pandas as pd
from contstants import PAYS_UE, PRINT_ERR

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def safe_float(value, default=0.0):
    """
    Convertit une valeur en float de manière sécurisée.
    Gère les chaînes vides, espaces, et valeurs non numériques.
    """
    try:
        if isinstance(value, str):
            value = value.strip()
        
        if value == "" or pd.isna(value):
            return default
        
        return float(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Impossible de convertir '{value}' en float. Valeur par défaut: {default} - Erreur: {e}")
        return default


def date_format(date_str):
    """
    Formate une date en format jj/mm/aaaa.
    Supporte plusieurs formats d'entrée courants.
    """
    if isinstance(date_str, datetime):
        return date_str.strftime("%d/%m/%Y")
    
    if pd.isna(date_str) or date_str == "":
        raise ValueError("Date vide ou invalide")
    
    formats = [
        "%Y-%m-%d %H:%M:%S",  # ← AJOUTE CETTE LIGNE EN PREMIER
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%d/%m/%Y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(str(date_str), fmt).strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            continue
    
    raise ValueError(f"Format de date non reconnu : {date_str}")


def add_montant_ttc(out_data, Date, amount, Reference):
    """
    Ajoute une ligne de montant TTC dans les données de sortie.
    """
    out_data.append([
        "VES", Date, None, "411SHOPI", None, "Shopify", Date, amount, None, 
        "", "", "", "", "", "", Reference, "", "", "", "", ""
    ])
    logger.debug(f"  Ligne TTC ajoutée: {amount:.2f}€")


def shopify(src) -> list:
    """
    Traite un fichier Excel Shopify et génère les écritures comptables.
    
    Args:
        src: Chemin du fichier Excel ou objet file-like (BytesIO)
    
    Returns:
        Liste des lignes comptables générées
    """
    out_data = []
    stats = {
        'total_rows': 0,
        'processed_rows': 0,
        'skipped_rows': 0,
        'france': 0,
        'ue_avec_tva': 0,
        'ue_sans_tva': 0,
        'hors_ue': 0,
        'errors': 0
    }

    try:
        logger.info("="*80)
        logger.info("DÉBUT DU TRAITEMENT SHOPIFY")
        logger.info("="*80)
        
        # Lecture du fichier Excel
        df = pd.read_excel(src, engine='openpyxl', dtype=str)
        logger.info(f"✓ Fichier Excel chargé avec {len(df)} lignes")
        logger.info(f"✓ Colonnes détectées: {list(df.columns)}")
        
        # Vérification des colonnes requises
        required_columns = [
            'Date', 'Total Sales', 'Shipping Country', 
            'Net Sales', 'Shipping', 'Tax', 'Order Name'
        ]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Colonnes manquantes: {missing_columns}")
        
        logger.info(f"✓ Toutes les colonnes requises sont présentes")
        
        # Vérification si le DataFrame est vide
        if df.empty:
            logger.warning("Le fichier est vide (aucune ligne de données)")
            return []
        
        # Afficher un aperçu des premières lignes
        logger.info(f"\nAperçu des premières lignes:\n{df.head(3)}")
        logger.info("="*80)
        
        stats['total_rows'] = len(df)
        
        # Traitement ligne par ligne (exclure la dernière ligne qui peut être un total)
        for index, row in df.iloc[:-1].iterrows():
            logger.debug(f"\n--- Traitement ligne {index + 1} ---")
            
            try:
                # Extraction et validation des données
                date_raw = row.get('Date', '')
                amount_raw = row.get('Total Sales', '0')
                country = str(row.get('Shipping Country', '')).strip()
                tva_present = row.get('Note', '0')
                amount_HT_TVA_raw = row.get('Net Sales', '0')
                Frais_port_raw = row.get('Shipping', '0')
                Tva_collect_raw = row.get('Tax', '0')
                Reference = str(row.get('Order Name', '')).strip()
                
                logger.debug(f"Données brutes: Date={date_raw}, Country={country}, Total={amount_raw}, Ref={Reference}")
                
                # Formatage de la date
                try:
                    Date = date_format(date_raw)
                except ValueError as e:
                    logger.error(f"Ligne {index + 1}: Date invalide '{date_raw}' - {e}")
                    stats['errors'] += 1
                    stats['skipped_rows'] += 1
                    continue
                
                # Conversion des montants
                amount = safe_float(amount_raw)
                amount_HT_TVA = safe_float(amount_HT_TVA_raw)
                Frais_port = safe_float(Frais_port_raw)
                Tva_collect = safe_float(Tva_collect_raw)
                
                logger.debug(f"Montants: TTC={amount:.2f}, HT={amount_HT_TVA:.2f}, Port={Frais_port:.2f}, TVA={Tva_collect:.2f}")
                
                # Vérification des montants négatifs ou nuls
                if amount <= 0:
                    logger.warning(f"Ligne {index + 1}: Montant total <= 0 ({amount}), ligne ignorée")
                    stats['skipped_rows'] += 1
                    continue
                
                # Validation du pays
                if not country:
                    logger.warning(f"Ligne {index + 1}: Pays non spécifié, ligne ignorée")
                    stats['skipped_rows'] += 1
                    continue
                
                # Traitement selon le pays
                lines_added = 0
                
                if country == "France":
                    logger.debug(f"  → Catégorie: FRANCE")
                    out_data.extend([
                        ["VES", Date, None, 707101, "REVOFFPBOOK", "Shopify", Date, None, amount_HT_TVA, 
                         "", "", "", "", "", "", Reference, "", "", "", "", ""],
                        ["VES", Date, None, 708502, "REVOFFPBOOK", "Shopify", Date, None, Frais_port, 
                         "", "", "", "", "", "", Reference, "", "", "", "", ""],
                        ["VES", Date, None, 445713, None, "Shopify", Date, None, Tva_collect, 
                         "", "", "", "", "", "", Reference, "", "", "", "", ""],
                    ])
                    lines_added = 3
                    stats['france'] += 1
                
                elif country in PAYS_UE:
                    if tva_present:
                        logger.debug(f"  → Catégorie: UE AVEC TVA")
                        out_data.extend([
                            ["VES", Date, None, 707400, "REVOFFPBOOK", "Shopify", Date, None, amount_HT_TVA, 
                             "", "", "", "", "", "", Reference, "", "", "", "", ""],
                            ["VES", Date, None, 708500, "REVOFFPBOOK", "Shopify", Date, None, Frais_port, 
                             "", "", "", "", "", "", Reference, "", "", "", "", ""],
                        ])
                        lines_added = 2
                        stats['ue_avec_tva'] += 1
                    else:
                        logger.debug(f"  → Catégorie: UE SANS TVA")
                        out_data.extend([
                            ["VES", Date, None, 707500, "REVOFFPBOOK", "Shopify", Date, None, amount_HT_TVA, 
                             "", "", "", "", "", "", Reference, "", "", "", "", ""],
                            ["VES", Date, None, 708503, "REVOFFPBOOK", "Shopify", Date, None, Frais_port, 
                             "", "", "", "", "", "", Reference, "", "", "", "", ""],
                            ["VES", Date, None, 445713, None, "Shopify", Date, None, Tva_collect, 
                             "", "", "", "", "", "", Reference, "", "", "", "", ""],
                        ])
                        lines_added = 3
                        stats['ue_sans_tva'] += 1
                
                else:
                    logger.debug(f"  → Catégorie: HORS UE ({country})")
                    out_data.extend([
                        ["VES", Date, None, 707300, "REVOFFPBOOK", "Shopify", Date, None, amount_HT_TVA, 
                         "", "", "", "", "", "", Reference, "", "", "", "", ""],
                        ["VES", Date, None, 708500, "REVOFFPBOOK", "Shopify", Date, None, Frais_port, 
                         "", "", "", "", "", "", Reference, "", "", "", "", ""],
                    ])
                    lines_added = 2
                    stats['hors_ue'] += 1
                
                # Ajout du montant TTC
                add_montant_ttc(out_data, Date, amount, Reference)
                lines_added += 1
                
                stats['processed_rows'] += 1
                logger.debug(f"  ✓ {lines_added} lignes comptables ajoutées")
                
            except ValueError as e:
                logger.error(f"Ligne {index + 1}: Erreur de conversion - {e}")
                stats['errors'] += 1
                stats['skipped_rows'] += 1
                continue
            except Exception as e:
                logger.error(f"Ligne {index + 1}: Erreur inattendue - {e}")
                stats['errors'] += 1
                stats['skipped_rows'] += 1
                continue
        
        # Logs de synthèse
        logger.info("\n" + "="*80)
        logger.info("SYNTHÈSE DU TRAITEMENT SHOPIFY")
        logger.info("="*80)
        logger.info(f"Lignes totales dans le fichier: {stats['total_rows']}")
        logger.info(f"Lignes traitées avec succès: {stats['processed_rows']}")
        logger.info(f"Lignes ignorées: {stats['skipped_rows']}")
        logger.info(f"Erreurs rencontrées: {stats['errors']}")
        logger.info(f"---")
        logger.info(f"Ventes France: {stats['france']}")
        logger.info(f"Ventes UE avec TVA: {stats['ue_avec_tva']}")
        logger.info(f"Ventes UE sans TVA: {stats['ue_sans_tva']}")
        logger.info(f"Ventes Hors UE: {stats['hors_ue']}")
        logger.info(f"---")
        logger.info(f"✓ {len(out_data)} lignes comptables générées au total")
        logger.info("="*80 + "\n")
        
    except FileNotFoundError:
        logger.error(f"Fichier introuvable: {src}")
        PRINT_ERR(f"[ERREUR] Le fichier '{src}' est introuvable. Veuillez vérifier le chemin du fichier.")
        return []
    
    except ValueError as e:
        logger.error(f"Erreur de validation: {e}")
        PRINT_ERR(f"[ERREUR] Erreur de validation des données: {e}")
        return []
    
    except Exception as e:
        logger.exception(f"Erreur critique lors du traitement du fichier Shopify")
        PRINT_ERR(f"[ERREUR] Une erreur s'est produite lors du traitement du fichier : {e}")
        return []

    return out_data
