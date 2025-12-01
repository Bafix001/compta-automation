import argparse
import os
import io
import paramiko
import re
import csv
import logging
from datetime import datetime, timedelta
import warnings
import pandas as pd
from stat import S_ISREG
from clorian import clorian
from stripe import st
from shopify import shopify
from skidata import treat_skidata_file
from dotenv import load_dotenv


# Chargement des variables d'environnement
load_dotenv()


# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation_comptable.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Supprimer les avertissements openpyxl
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


class UsrRequest:
    def __init__(self):
        """Initialisation de la classe avec parsing des arguments et configuration."""
        parser = argparse.ArgumentParser(
            description="Automatisation comptable - Récupération et traitement de fichiers via SFTP"
        )

        parser.add_argument("--sftp-host", default=os.getenv('SFTP_HOST'), 
                          help="Adresse du serveur SFTP")
        parser.add_argument("--sftp-user", default=os.getenv('SFTP_USER'), 
                          help="Nom d'utilisateur SFTP")
        parser.add_argument("--sftp-pass", default=os.getenv('SFTP_PASS'), 
                          help="Mot de passe SFTP")
        parser.add_argument("--sftp-dir", default=os.getenv('SFTP_DIRS', '').split(','), 
                          nargs='*', help="Répertoires distants SFTP à traiter")
        parser.add_argument("-o", "--output", default=os.getenv('OUTPUT_FILE', 'output.csv'), 
                          help="Fichier de sortie CSV")

        self.args = parser.parse_args()
        self._setup_regex()
        self.transport = None
        self.sftp = None
        self.matched_files = []
        
        # Statistiques globales
        self.stats = {
            'clorian': {'files': 0, 'lines': 0, 'errors': 0},
            'stripe': {'files': 0, 'lines': 0, 'errors': 0},
            'shopify': {'files': 0, 'lines': 0, 'errors': 0},
            'skidata': {'files': 0, 'lines': 0, 'errors': 0},
            'total_files': 0,
            'total_lines': 0,
            'total_errors': 0
        }

    def _setup_regex(self):
        """Configuration des expressions régulières pour détecter les types de fichiers."""
        self.regex_clorian = re.compile(r'^clorian_(\d{2})-(\d{2})-(\d{4})\.xlsx$', re.IGNORECASE)
        self.regex_stripe = re.compile(r'^stripe(\d{2})(\d{2})(\d{4})\.csv$', re.IGNORECASE)
        self.regex_shopify = re.compile(r'^export_caisses\.xlsx$', re.IGNORECASE)
        self.regex_skidata = re.compile(r'^rapport_jour_(\d{8})\.(xlsx|xls|csv)$', re.IGNORECASE)
        
        logger.debug("Expressions régulières configurées pour la détection des fichiers")

    def connect_sftp(self):
        """Établit la connexion SFTP et récupère la liste des fichiers."""
        logger.info("="*80)
        logger.info("CONNEXION AU SERVEUR SFTP")
        logger.info("="*80)
        logger.info(f"Hôte: {self.args.sftp_host}")
        logger.info(f"Utilisateur: {self.args.sftp_user}")
        logger.info(f"Répertoires à scanner: {self.args.sftp_dir}")
        
        try:
            self.transport = paramiko.Transport((self.args.sftp_host, 22))
            self.transport.connect(username=self.args.sftp_user, password=self.args.sftp_pass)
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
            
            logger.info("✓ Connexion SFTP établie avec succès")
            logger.info("="*80)

            # Récupération des fichiers de tous les répertoires
            all_files = []
            for dir_path in self.args.sftp_dir:
                files = self._fetch_sftp_files(dir_path)
                all_files.extend(files)
            
            self.matched_files = all_files
            
            # Logs de synthèse
            logger.info("\n" + "="*80)
            logger.info("FICHIERS DÉTECTÉS")
            logger.info("="*80)
            
            file_counts = {'clorian': 0, 'stripe': 0, 'shopify': 0, 'skidata': 0}
            for file_type, path, date in self.matched_files:
                file_counts[file_type] += 1
            
            for file_type, count in file_counts.items():
                logger.info(f"{file_type.upper()}: {count} fichier(s)")
            
            logger.info(f"TOTAL: {len(self.matched_files)} fichier(s) à traiter")
            logger.info("="*80 + "\n")
            
        except paramiko.AuthenticationException:
            logger.error("❌ Échec d'authentification SFTP - Vérifiez vos identifiants")
            raise
        except paramiko.SSHException as e:
            logger.error(f"❌ Erreur SSH: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"❌ Erreur de connexion SFTP: {str(e)}")
            raise

    def _fetch_sftp_files(self, dir_path):
        """
        Récupère et filtre les fichiers d'un répertoire SFTP pour la date du jour uniquement.
        
        Args:
            dir_path: Chemin du répertoire distant
            
        Returns:
            Liste de tuples (type, chemin, date)
        """
        logger.info(f"\n📂 Analyse du répertoire: {dir_path}")
        files_with_dates = []
        today = datetime.now().date()  # Date du jour
        yesterday = today - timedelta(days=1)  # Date de la veille (pour Skidata)
        
        try:
            file_list = self.sftp.listdir_attr(dir_path)
            logger.debug(f"  {len(file_list)} fichier(s) trouvé(s)")
            
            for file_attr in file_list:
                if not S_ISREG(file_attr.st_mode):
                    continue
                
                filename = file_attr.filename
                full_path = f"{dir_path}/{filename}"
                
                # Détection Clorian - Format: clorian_DD-MM-YYYY.xlsx
                match_clorian = self.regex_clorian.match(filename)
                if match_clorian:
                    file_date_str = f"{match_clorian.group(1)}-{match_clorian.group(2)}-{match_clorian.group(3)}"
                    file_date = datetime.strptime(file_date_str, '%d-%m-%Y')
                    
                    if file_date.date() == today:
                        files_with_dates.append(('clorian', full_path, file_date))
                        logger.info(f"  ✓ CLORIAN détecté: {filename} (Date: {file_date.strftime('%d/%m/%Y')})")
                    else:
                        logger.debug(f"  - Ignoré (date: {file_date.date()}): {filename}")
                    continue
                
                # Détection Stripe - Format: stripeDDMMYYYY.csv
                match_stripe = self.regex_stripe.match(filename)
                if match_stripe:
                    # Extraction: DD=group(1), MM=group(2), YYYY=group(3)
                    file_date_str = f"{match_stripe.group(1)}{match_stripe.group(2)}{match_stripe.group(3)}"
                    file_date = datetime.strptime(file_date_str, '%d%m%Y')
                    
                    if file_date.date() == today:
                        files_with_dates.append(('stripe', full_path, file_date))
                        logger.info(f"  ✓ STRIPE détecté: {filename} (Date: {file_date.strftime('%d/%m/%Y')})")
                    else:
                        logger.debug(f"  - Ignoré (date: {file_date.date()}): {filename}")
                    continue
                
                # Détection Skidata - Format: rapport_jour_YYYYMMDD.csv
                # Le fichier du jour contient la date de la veille
                match_skidata = self.regex_skidata.match(filename)
                if match_skidata:
                    # Extraire la date du nom de fichier (groupe 1)
                    date_str = match_skidata.group(1)
                    file_date = datetime.strptime(date_str, '%Y%m%d')
                    
                    # Pour Skidata: on cherche le fichier avec la date d'HIER
                    if file_date.date() == yesterday:
                        files_with_dates.append(('skidata', full_path, file_date))
                        logger.info(f"  ✓ SKIDATA détecté: {filename} (Date fichier: {file_date.strftime('%d/%m/%Y')}, traité aujourd'hui)")
                    else:
                        logger.debug(f"  - Ignoré (date: {file_date.date()}, attendu: {yesterday}): {filename}")
                    continue
                
                # Détection Shopify - Format: export_caisses.xlsx
                # Utiliser la date de modification du fichier
                match_shopify = self.regex_shopify.match(filename)
                if match_shopify:
                    file_mtime = datetime.fromtimestamp(file_attr.st_mtime).date()
                    
                    if file_mtime == today:
                        files_with_dates.append(('shopify', full_path, None))
                        logger.info(f"  ✓ SHOPIFY détecté: {filename} (Modifié le: {file_mtime.strftime('%d/%m/%Y')})")
                    else:
                        logger.debug(f"  - Ignoré (modifié le: {file_mtime}): {filename}")
                    continue
                
                logger.debug(f"  - Ignoré (non reconnu): {filename}")
            
            # Tri par date (plus récent en premier)
            files_with_dates.sort(key=lambda x: x[2] if x[2] else datetime.min, reverse=True)
            
            logger.info(f"\n📋 {len(files_with_dates)} fichier(s) du jour ({today.strftime('%d/%m/%Y')})")
            
            return files_with_dates
            
        except FileNotFoundError:
            logger.error(f"  ❌ Répertoire introuvable: {dir_path}")
            return []
        except Exception as e:
            logger.error(f"  ❌ Erreur lors de la récupération des fichiers dans {dir_path}: {str(e)}")
            return []

    def _download_file(self, remote_path):
        """
        Télécharge un fichier distant en mémoire.
        
        Args:
            remote_path: Chemin du fichier distant
            
        Returns:
            Objet BytesIO contenant le fichier ou None en cas d'erreur
        """
        try:
            byte_io = io.BytesIO()
            self.sftp.getfo(remote_path, byte_io)
            byte_io.seek(0)
            
            file_size = len(byte_io.getvalue())
            logger.debug(f"  Téléchargé: {file_size} octets ({file_size/1024:.2f} KB)")
            
            return byte_io
        except FileNotFoundError:
            logger.error(f"  ❌ Fichier introuvable: {remote_path}")
            return None
        except Exception as e:
            logger.error(f"  ❌ Erreur de téléchargement {remote_path}: {str(e)}")
            return None

    def process_files(self):
        """Traite tous les fichiers détectés et génère les lignes comptables."""
        logger.info("="*80)
        logger.info("DÉBUT DU TRAITEMENT DES FICHIERS")
        logger.info("="*80 + "\n")
        
        all_output = []
        
        for index, (file_type, remote_path, file_date) in enumerate(self.matched_files, 1):
            filename = os.path.basename(remote_path)
            
            logger.info(f"\n{'='*80}")
            logger.info(f"FICHIER {index}/{len(self.matched_files)}: {filename}")
            logger.info(f"Type: {file_type.upper()}")
            if file_date:
                logger.info(f"Date: {file_date.strftime('%d/%m/%Y')}")
            logger.info("="*80)
            
            try:
                # Téléchargement du fichier
                logger.info("⬇️  Téléchargement en cours...")
                file_in_memory = self._download_file(remote_path)
                
                if not file_in_memory:
                    logger.error(f"❌ Échec du téléchargement, fichier ignoré")
                    self.stats[file_type]['errors'] += 1
                    self.stats['total_errors'] += 1
                    continue
                
                logger.info("✓ Téléchargement réussi")
                
                # Traitement selon le type
                logger.info(f"🔄 Traitement {file_type.upper()} en cours...\n")
                
                output_lines = []
                
                if file_type == 'clorian':
                    output_lines = clorian(file_in_memory, remote_path)
                elif file_type == 'stripe':
                    output_lines = st(file_in_memory)
                elif file_type == 'shopify':
                    output_lines = shopify(file_in_memory)
                elif file_type == 'skidata':
                    output_lines = treat_skidata_file(file_in_memory, remote_path)
                else:
                    logger.warning(f"⚠️  Type de fichier non reconnu: {file_type}")
                    output_lines = []
                
                # Mise à jour des statistiques
                if output_lines:
                    all_output.extend(output_lines)
                    self.stats[file_type]['files'] += 1
                    self.stats[file_type]['lines'] += len(output_lines)
                    self.stats['total_files'] += 1
                    self.stats['total_lines'] += len(output_lines)
                    logger.info(f"✅ {len(output_lines)} ligne(s) comptable(s) générée(s)")
                else:
                    logger.warning(f"⚠️  Aucune ligne générée pour ce fichier")
                    self.stats[file_type]['errors'] += 1
                    self.stats['total_errors'] += 1
                
            except Exception as e:
                logger.exception(f"❌ Erreur lors du traitement de {remote_path}")
                self.stats[file_type]['errors'] += 1
                self.stats['total_errors'] += 1
        
        # Sauvegarde des résultats
        if all_output:
            logger.info("\n" + "="*80)
            logger.info("💾 SAUVEGARDE DES DONNÉES")
            logger.info("="*80)
            self._save_output(all_output)
        else:
            logger.warning("\n⚠️  Aucune donnée à sauvegarder")
        
        # Affichage des statistiques finales
        self._display_final_stats()

    def _save_output(self, output_lines):
        """
        Sauvegarde les lignes comptables dans le fichier CSV de sortie.
        
        Args:
            output_lines: Liste des lignes à sauvegarder
        """
        try:
            with open(self.args.output, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(output_lines)
            
            logger.info(f"✅ {len(output_lines)} ligne(s) ajoutée(s) au fichier: {self.args.output}")
            logger.info(f"📄 Chemin complet: {os.path.abspath(self.args.output)}")
            
        except PermissionError:
            logger.error(f"❌ Permission refusée pour écrire dans: {self.args.output}")
            raise
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde: {str(e)}")
            raise

    def _display_final_stats(self):
        """Affiche les statistiques finales du traitement."""
        logger.info("\n" + "="*80)
        logger.info("📊 STATISTIQUES FINALES")
        logger.info("="*80)
        
        for file_type in ['clorian', 'stripe', 'shopify', 'skidata']:
            stats = self.stats[file_type]
            if stats['files'] > 0 or stats['errors'] > 0:
                logger.info(f"\n{file_type.upper()}:")
                logger.info(f"  Fichiers traités: {stats['files']}")
                logger.info(f"  Lignes générées: {stats['lines']}")
                if stats['errors'] > 0:
                    logger.info(f"  Erreurs: {stats['errors']}")
        
        logger.info(f"\n{'─'*80}")
        logger.info(f"TOTAL:")
        logger.info(f"  Fichiers traités: {self.stats['total_files']}/{len(self.matched_files)}")
        logger.info(f"  Lignes comptables générées: {self.stats['total_lines']}")
        
        if self.stats['total_errors'] > 0:
            logger.warning(f"  ⚠️  Erreurs totales: {self.stats['total_errors']}")
        
        logger.info("="*80 + "\n")

    def close_sftp(self):
        """Ferme la connexion SFTP proprement."""
        try:
            if self.sftp:
                self.sftp.close()
                logger.debug("Client SFTP fermé")
            if self.transport:
                self.transport.close()
                logger.debug("Transport SFTP fermé")
            logger.info("✓ Connexion SFTP fermée proprement")
        except Exception as e:
            logger.warning(f"Erreur lors de la fermeture SFTP: {e}")


def main():
    """Fonction principale d'exécution du script."""
    start_time = datetime.now()
    
    logger.info("\n" + "="*80)
    logger.info("🚀 DÉMARRAGE DE L'AUTOMATISATION COMPTABLE")
    logger.info("="*80)
    logger.info(f"Heure de début: {start_time.strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info(f"Date de traitement: {start_time.strftime('%d/%m/%Y')}")
    logger.info("="*80 + "\n")
    
    request = None
    
    try:
        request = UsrRequest()
        
        # Création du fichier de sortie avec en-têtes
        logger.info("📝 Initialisation du fichier de sortie...")
        with open(request.args.output, 'w', newline='', encoding='utf-8') as w:
            csvwriter = csv.writer(w)
            csvwriter.writerow([
                "# Explications Code journal", "Date avec ou sans les /", "Informations", 
                "Numéro de compte", "Code section analytique", "Libellé de la ligne", 
                "Date d'échéance", "Montant débit", "Montant crédit",
                "      ", "      ", "     ", "     ", "    ", "    ", 
                "Référence", "Informations", "    ", "    ", "    ", "    ", "lien"
            ])
        logger.info(f"✓ En-têtes CSV ajoutés à: {request.args.output}\n")
        
        # Types de fichiers à traiter
        file_types = ['clorian', 'stripe', 'shopify', 'skidata']
        
        # Connexion SFTP et récupération des fichiers (déjà filtrés par date du jour)
        request.connect_sftp()
        
        # Filtrage des fichiers par type
        request.matched_files = [
            file for file in request.matched_files 
            if file[0] in file_types
        ]
        
        # Traitement des fichiers
        request.process_files()
        
        # Calcul du temps d'exécution
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("="*80)
        logger.info("✅ TRAITEMENT TERMINÉ AVEC SUCCÈS")
        logger.info("="*80)
        logger.info(f"Heure de fin: {end_time.strftime('%d/%m/%Y %H:%M:%S')}")
        logger.info(f"Durée totale: {duration.total_seconds():.2f} secondes")
        logger.info("="*80 + "\n")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interruption par l'utilisateur (Ctrl+C)")
    except Exception as e:
        logger.exception(f"\n❌ ERREUR CRITIQUE LORS DE L'EXÉCUTION")
        raise
    finally:
        if request:
            try:
                request.close_sftp()
            except Exception as e:
                logger.error(f"Erreur lors de la fermeture: {e}")


if __name__ == "__main__":
    main()
