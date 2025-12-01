import csv
import io
import logging
from datetime import datetime
from contstants import PRINT_ERR
from shopify import safe_float, date_format

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def st(file_in_memory) -> list:
    """
    Traite un fichier CSV Stripe en mémoire et génère les écritures comptables.
    
    Args:
        file_in_memory: Objet BytesIO contenant le fichier CSV Stripe
    
    Returns:
        Liste des lignes comptables générées, triées par date
    """
    out_data = []
    stats = {
        'total_rows': 0,
        'processed_rows': 0,
        'skipped_rows': 0,
        'errors': 0,
        'total_amount': 0.0,
        'total_ht': 0.0,
        'total_tva': 0.0
    }
    
    try:
        logger.info("="*80)
        logger.info("DÉBUT DU TRAITEMENT STRIPE")
        logger.info("="*80)
        
        # Repositionner le curseur au début du fichier
        file_in_memory.seek(0)
        logger.debug("Curseur du fichier repositionné au début")
        
        # Lecture du fichier CSV depuis la mémoire
        try:
            file_content = file_in_memory.getvalue().decode('utf-8')
            logger.debug(f"Fichier décodé en UTF-8 ({len(file_content)} caractères)")
        except UnicodeDecodeError:
            logger.warning("Échec du décodage UTF-8, tentative avec latin-1")
            file_in_memory.seek(0)
            file_content = file_in_memory.getvalue().decode('latin-1')
        
        # Création du lecteur CSV
        csvreader = csv.DictReader(io.StringIO(file_content))
        rows = list(csvreader)
        
        stats['total_rows'] = len(rows)
        logger.info(f"✓ Fichier CSV chargé avec {stats['total_rows']} lignes")
        
        # Afficher les colonnes détectées
        if rows:
            logger.info(f"✓ Colonnes détectées: {list(rows[0].keys())}")
        
        # Vérification des colonnes requises
        if rows:
            required_columns = ['created_date', 'customer_email', 'amount_decimal']
            missing_columns = [col for col in required_columns if col not in rows[0].keys()]
            
            if missing_columns:
                logger.error(f"Colonnes manquantes: {missing_columns}")
                raise ValueError(f"Colonnes manquantes dans le fichier Stripe: {missing_columns}")
            
            logger.info(f"✓ Toutes les colonnes requises sont présentes")
        
        # Vérification si le fichier est vide
        if not rows:
            logger.warning("Le fichier est vide (aucune ligne de données)")
            PRINT_ERR(f"[AVERTISSEMENT] Le fichier Stripe est vide")
            return []
        
        # Afficher un aperçu des premières lignes
        logger.info(f"\nAperçu des premières lignes:")
        for i, row in enumerate(rows[:3], 1):
            logger.info(f"  Ligne {i}: Date={row.get('created_date')}, Email={row.get('customer_email')}, Montant={row.get('amount_decimal')}")
        
        logger.info("="*80)
        
        # Traitement de chaque ligne
        for index, row in enumerate(rows, 1):
            logger.debug(f"\n--- Traitement ligne {index}/{stats['total_rows']} ---")
            
            try:
                # Extraction de la date
                date_raw = row.get('created_date', '').strip()
                
                if not date_raw:
                    logger.warning(f"Ligne {index}: Date manquante, ligne ignorée")
                    stats['skipped_rows'] += 1
                    continue
                
                try:
                    Date = date_format(date_raw)
                    logger.debug(f"  Date formatée: {Date}")
                except ValueError as e:
                    logger.error(f"Ligne {index}: Date invalide '{date_raw}' - {e}")
                    stats['errors'] += 1
                    stats['skipped_rows'] += 1
                    continue
                
                # Extraction de l'email
                mail = row.get('customer_email', '').strip()
                
                if not mail:
                    logger.warning(f"Ligne {index}: Email client manquant, ligne ignorée")
                    stats['skipped_rows'] += 1
                    continue
                
                logger.debug(f"  Email client: {mail}")
                
                # Extraction et conversion du montant
                amount_raw = row.get('amount_decimal', '0').strip()
                amount = safe_float(amount_raw, 0.0)
                
                if amount <= 0:
                    logger.warning(f"Ligne {index}: Montant invalide ou nul ({amount}), ligne ignorée")
                    stats['skipped_rows'] += 1
                    continue
                
                # Calcul HT et TVA (TVA 10%)
                amount_ht = round(amount / 1.10, 2)
                Tva_collect = round(amount - amount_ht, 2)
                
                logger.debug(f"  Montants: TTC={amount:.2f}€, HT={amount_ht:.2f}€, TVA={Tva_collect:.2f}€")
                
                # Ajout des 5 lignes comptables pour chaque transaction
                out_data.extend([
                    ["B5", Date, None, "411SAP", None, mail, Date, amount, None, 
                     "", "", "", "", "", "", "", "", "", "", "", ""],
                    ["B5", Date, None, 512500, None, mail, Date, None, amount, 
                     "", "", "", "", "", "", "", "", "", "", "", ""],
                    ["VE", Date, None, "411SAP", None, mail, Date, amount, None, 
                     "", "", "", "", "", "", "", "", "", "", "", ""],
                    ["VE", Date, None, 706101, "REVSAPVISGR", mail, Date, None, amount_ht, 
                     "", "", "", "", "", "", "", "", "", "", "", ""],
                    ["VE", Date, None, 445712, None, mail, Date, None, Tva_collect, 
                     "", "", "", "", "", "", "", "", "", "", "", ""],
                ])
                
                logger.debug(f"  ✓ 5 lignes comptables ajoutées")
                
                # Mise à jour des statistiques
                stats['processed_rows'] += 1
                stats['total_amount'] += amount
                stats['total_ht'] += amount_ht
                stats['total_tva'] += Tva_collect
                
            except ValueError as e:
                logger.error(f"Ligne {index}: Erreur de conversion - {e}")
                PRINT_ERR(f"[ERREUR] Ligne {index}: Impossible de traiter la ligne {row}: {e}")
                stats['errors'] += 1
                stats['skipped_rows'] += 1
                continue
            
            except Exception as e:
                logger.error(f"Ligne {index}: Erreur inattendue - {e}")
                PRINT_ERR(f"[ERREUR] Ligne {index}: Erreur inattendue: {e}")
                stats['errors'] += 1
                stats['skipped_rows'] += 1
                continue
        
        # Tri des données par date
        if out_data:
            logger.info("\nTri des données par date...")
            try:
                out_data.sort(key=lambda x: datetime.strptime(x[1], "%d/%m/%Y"))
                logger.info("✓ Données triées avec succès")
            except ValueError as e:
                logger.error(f"Erreur lors du tri par date: {e}")
                PRINT_ERR(f"[ERREUR] Problème de format de date lors du tri: {e}")
                return []
        
        # Logs de synthèse
        logger.info("\n" + "="*80)
        logger.info("SYNTHÈSE DU TRAITEMENT STRIPE")
        logger.info("="*80)
        logger.info(f"Lignes totales dans le fichier: {stats['total_rows']}")
        logger.info(f"Lignes traitées avec succès: {stats['processed_rows']}")
        logger.info(f"Lignes ignorées: {stats['skipped_rows']}")
        logger.info(f"Erreurs rencontrées: {stats['errors']}")
        logger.info(f"---")
        logger.info(f"Montant total TTC: {stats['total_amount']:.2f} €")
        logger.info(f"Montant total HT: {stats['total_ht']:.2f} €")
        logger.info(f"TVA collectée totale: {stats['total_tva']:.2f} €")
        logger.info(f"---")
        logger.info(f"✓ {len(out_data)} lignes comptables générées au total")
        logger.info(f"  ({stats['processed_rows']} transactions × 5 lignes)")
        logger.info("="*80 + "\n")
        
        return out_data if out_data else []
    
    except UnicodeDecodeError as e:
        logger.error(f"Erreur de décodage du fichier: {e}")
        PRINT_ERR(f"[ERREUR] Impossible de décoder le fichier Stripe: {e}")
        return []
    
    except ValueError as e:
        logger.error(f"Erreur de validation: {e}")
        PRINT_ERR(f"[ERREUR] Erreur de validation des données Stripe: {e}")
        return []
    
    except Exception as e:
        logger.exception("Erreur critique lors du traitement du fichier Stripe")
        PRINT_ERR(f"[ERREUR] Problème avec le traitement du fichier Stripe: {e}")
        return []
