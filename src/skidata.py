import os
import io
import re
from datetime import datetime
import pandas as pd
import logging
from contstants import PRINT_ERR
from shopify import safe_float

# Configuration du logging pour débogage
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

FILENAME_REGEX = re.compile(r'rapport_jour_(\d{8})\.(xlsx|xls|csv)$', re.IGNORECASE)


def treat_skidata_file(file_in_memory, filename, reference="SKIDATA_REF"):
    """
    Traite un fichier Skidata sans en-têtes.
    Colonnes: A=code produit/secteur, B=type paiement, C=montant TTC, D=TVA
    """
    out_data = []
    
    # Cumuls des montants TTC
    espece_total = 0.0
    encaissement_cb_caisse_auto = 0.0
    encaissement_cb_borne_sortie = 0.0
    
    # Cumul de la TVA (colonne D)
    tva_collectee = 0.0

    try:
        # 1. Extraction de la date du fichier
        filename_only = os.path.basename(filename)
        match = FILENAME_REGEX.match(filename_only)
        if match:
            file_date = datetime.strptime(match.group(1), "%Y%m%d").strftime("%d/%m/%Y")
            logger.info(f"Date extraite du fichier: {file_date}")
        else:
            PRINT_ERR(f"[AVERTISSEMENT] Nom fichier hors format : {filename}")
            return []

        ext = filename_only.split('.')[-1].lower()
        logger.info(f"Extension détectée: {ext}")

        # 2. Lecture du fichier avec détection automatique du séparateur
        if ext in ['xlsx', 'xls']:
            df = pd.read_excel(file_in_memory, header=None, dtype=str)
            logger.info(f"Fichier Excel lu avec {len(df)} lignes")
        else:
            # Essayer d'abord avec le séparateur déclaré, puis auto-détection
            try:
                df = pd.read_csv(file_in_memory, sep=';', header=None, dtype=str, encoding='utf-8')
                logger.info(f"CSV lu avec séparateur ';' - {len(df)} lignes")
            except Exception as e1:
                logger.warning(f"Échec avec ';', tentative auto-détection: {e1}")
                file_in_memory.seek(0)  # Repositionner le curseur
                try:
                    df = pd.read_csv(file_in_memory, sep=None, header=None, dtype=str, 
                                   encoding='utf-8', engine='python')
                    logger.info(f"CSV lu avec auto-détection - {len(df)} lignes")
                except Exception as e2:
                    logger.error(f"Échec auto-détection: {e2}")
                    # Dernier essai avec virgule
                    file_in_memory.seek(0)
                    df = pd.read_csv(file_in_memory, sep=',', header=None, dtype=str, encoding='utf-8')
                    logger.info(f"CSV lu avec séparateur ',' - {len(df)} lignes")

        # 3. Vérifications de base
        if df.empty:
            PRINT_ERR(f"[AVERTISSEMENT] Fichier vide : {filename}")
            return []

        logger.info(f"Colonnes détectées: {df.shape[1]}")
        logger.info(f"Premières lignes du DataFrame:\n{df.head()}")
        
        # 4. Traitement ligne par ligne
        lignes_valides = 0
        lignes_ignorees = 0
        
        for idx, row in df.iterrows():
            try:
                # Vérifier le nombre de colonnes
                if len(row) < 4:
                    logger.warning(f"Ligne {idx} incomplète ({len(row)} colonnes): {row.values}")
                    lignes_ignorees += 1
                    continue

                # Extraction et nettoyage des valeurs
                col_a = str(row[0]).strip() if pd.notna(row[0]) else ""
                col_b = str(row[1]).strip() if pd.notna(row[1]) else ""
                col_c_raw = str(row[2]).strip() if pd.notna(row[2]) else "0"
                col_d_raw = str(row[3]).strip() if pd.notna(row[3]) else "0"

                logger.debug(f"Ligne {idx} - A:{col_a} | B:{col_b} | C:{col_c_raw} | D:{col_d_raw}")

                # Vérifier si ce sont des données valides (pas d'en-tête caché)
                if col_a.lower() in ['code', 'produit', 'secteur'] or col_b.lower() in ['type', 'paiement']:
                    logger.info(f"Ligne {idx} ignorée (probable en-tête): {row.values}")
                    lignes_ignorees += 1
                    continue

                # Conversion des montants avec gestion des formats français/anglais
                montant_ttc_str = col_c_raw.replace(',', '.').replace(' ', '')
                montant_tva_str = col_d_raw.replace(',', '.').replace(' ', '')
                
                montant_ttc = safe_float(montant_ttc_str, 0.0)
                montant_tva = safe_float(montant_tva_str, 0.0)

                logger.debug(f"  Montants convertis - TTC: {montant_ttc} | TVA: {montant_tva}")

                # Ignorer les lignes avec montant nul ou négatif
                if montant_ttc <= 0:
                    logger.warning(f"Ligne {idx} ignorée (montant <= 0): TTC={montant_ttc}")
                    lignes_ignorees += 1
                    continue

                # 5. Application des règles de catégorisation
                ligne_traitee = False
                
                # Règle 1: Espèces (type paiement = '1')
                if col_b == '1':
                    espece_total += montant_ttc
                    logger.debug(f"  → ESPÈCES: +{montant_ttc} (total: {espece_total})")
                    ligne_traitee = True
                
                # Règle 2: CB caisse auto (codes 11 ou 12, type paiement = '3')
                elif col_a in ['11', '12'] and col_b == '3':
                    encaissement_cb_caisse_auto += montant_ttc
                    logger.debug(f"  → CB CAISSE AUTO: +{montant_ttc} (total: {encaissement_cb_caisse_auto})")
                    ligne_traitee = True
                
                # Règle 3: CB borne sortie (codes 41, 42, 43, type paiement = '3')
                elif col_a in ['41', '42', '43'] and col_b == '3':
                    encaissement_cb_borne_sortie += montant_ttc
                    logger.debug(f"  → CB BORNE SORTIE: +{montant_ttc} (total: {encaissement_cb_borne_sortie})")
                    ligne_traitee = True
                
                else:
                    logger.warning(f"Ligne {idx} ne correspond à aucune règle: A={col_a}, B={col_b}")
                    lignes_ignorees += 1

                # Cumul TVA pour TOUTES les lignes valides (peu importe la catégorie)
                if ligne_traitee:
                    tva_collectee += montant_tva
                    lignes_valides += 1

            except Exception as e:
                logger.error(f"[ERREUR] Ligne {idx}: {e} - Données: {row.values}")
                lignes_ignorees += 1
                continue

        # 6. Logs de synthèse
        logger.info(f"\n{'='*60}")
        logger.info(f"SYNTHÈSE DU TRAITEMENT - {filename_only}")
        logger.info(f"{'='*60}")
        logger.info(f"Lignes totales: {len(df)}")
        logger.info(f"Lignes valides traitées: {lignes_valides}")
        logger.info(f"Lignes ignorées: {lignes_ignorees}")
        logger.info(f"---")
        logger.info(f"Total ESPÈCES (TTC): {espece_total:.2f} €")
        logger.info(f"Total CB CAISSE AUTO (TTC): {encaissement_cb_caisse_auto:.2f} €")
        logger.info(f"Total CB BORNE SORTIE (TTC): {encaissement_cb_borne_sortie:.2f} €")
        logger.info(f"Total TVA COLLECTÉE (Colonne D): {tva_collectee:.2f} €")
        logger.info(f"{'='*60}\n")

        # 7. Construction des lignes comptables (montants TTC directement)
        out_data.extend([
            ["CAIS", file_date, None, 511311, None, "Caisse Parking mois/année", file_date, 
             encaissement_cb_caisse_auto, "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["CAIS", file_date, None, 511312, None, "Caisse Parking mois/année", file_date, 
             encaissement_cb_borne_sortie, "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["CAIS", file_date, None, 539002, None, "Caisse Parking mois/année", file_date, 
             espece_total, "", "", "", "", "", "", "", "", "", "", "", "", ""],
            ["CAIS", file_date, None, 445711, None, "Caisse Parking mois/année", file_date, 
             None, tva_collectee, "", "", "", "", "", "", "", "", "", "", "", ""],
        ])

        logger.info(f"Lignes comptables générées:")
        logger.info(f"  511311 (CB Caisse Auto): {encaissement_cb_caisse_auto:.2f} €")
        logger.info(f"  511312 (CB Borne Sortie): {encaissement_cb_borne_sortie:.2f} €")
        logger.info(f"  539002 (Espèces): {espece_total:.2f} €")
        logger.info(f"  445711 (TVA): {tva_collectee:.2f} €")
        logger.info(f"\n✓ Fichier traité avec succès: {len(out_data)} lignes comptables générées\n")
        
        return out_data

    except Exception as e:
        PRINT_ERR(f"[ERREUR CRITIQUE] Fichier Skidata {filename}: {e}")
        logger.exception("Détails de l'erreur:")
        return []
