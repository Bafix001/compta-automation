import argparse
import os
import io
import paramiko
import re
import csv
from datetime import datetime
import warnings
import pandas as pd
from stat import S_ISREG
from clorian import clorian  # Importe la fonction clorian depuis clorian.py
from stripe import st
from shopify import shopify


warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

class UsrRequest:
    def __init__(self):
        parser = argparse.ArgumentParser(description="Récupération automatique de fichiers Clorian via SFTP")
        
        # Configuration SFTP
        parser.add_argument("--sftp-host", required=True, help="Adresse du serveur SFTP")
        parser.add_argument("--sftp-user", required=True, help="Nom d'utilisateur SFTP")
        parser.add_argument("--sftp-pass", help="Mot de passe SFTP")
        parser.add_argument("--sftp-dir", required=True, nargs='+', help="Répertoires distants SFTP à traiter")
        parser.add_argument("-o", "--output", required=True, help="Fichier de sortie")

        self.args = parser.parse_args()
        self._setup_regex()
        self.transport = None
        self.sftp = None
        self.matched_files = []

    def _setup_regex(self):
        self.regex_clorian = re.compile(
            r'^clorian_(\d{2})-(\d{2})-(\d{4})\.xlsx$', 
            re.IGNORECASE
        )

        self.regex_stripe = re.compile(
            r'^stripe(\d{2})(\d{2})(\d{4})\.csv$', 
            re.IGNORECASE
        )

        self.regex_shopify = re.compile(
            r'^export_caisses\.xlsx$',
            re.IGNORECASE)

    def connect_sftp(self):
        self.transport = paramiko.Transport((self.args.sftp_host, 22))
        try:
            self.transport.connect(username=self.args.sftp_user, password=self.args.sftp_pass)
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
            print("Connexion SFTP établie avec succès.")
            
            # Parcourir tous les répertoires spécifiés
            all_files = []
            for dir in self.args.sftp_dir:
                files_in_dir = self._fetch_sftp_files(dir)  # Récupérer les fichiers de chaque répertoire
                all_files.extend(files_in_dir)  # Ajouter les fichiers trouvés
            
            self.matched_files = all_files  # Assignation des fichiers récupérés
        except Exception as e:
            print(f"Erreur de connexion SFTP: {str(e)}")
            raise


    
    def _fetch_sftp_files(self, dir):
        print(f"Traitement du répertoire: {dir}")  # Ajout pour le débogage
        files_with_dates = []
        try:
            for file_attr in self.sftp.listdir_attr(dir):
                if S_ISREG(file_attr.st_mode):
                    file_name = file_attr.filename
                    match_clorian = self.regex_clorian.match(file_name)
                    match_stripe = self.regex_stripe.match(file_name)
                    match_shopify = self.regex_shopify.match(file_name)

                    if match_clorian:
                        file_date_str = f"{match_clorian.group(1)}-{match_clorian.group(2)}-{match_clorian.group(3)}"
                        file_date = datetime.strptime(file_date_str, '%d-%m-%Y')
                        files_with_dates.append(('clorian', f"{dir}/{file_name}", file_date))

                    elif match_stripe:
                        file_date_str = f"{match_stripe.group(1)}-{match_stripe.group(2)}-{match_stripe.group(3)}"
                        file_date = datetime.strptime(file_date_str, '%d-%m-%Y')
                        files_with_dates.append(('stripe', f"{dir}/{file_name}", file_date))

                    elif match_shopify:
                        print(f"Fichier Shopify détecté: {file_name}")  # Ajout debug
                        files_with_dates.append(('shopify', f"{dir}/{file_name}", None))   

            files_with_dates.sort(key=lambda x: x[2] if x[2] is not None else datetime.min, reverse=True)
            return files_with_dates
        except Exception as e:
            print(f"Erreur lors de la récupération des fichiers dans {dir}: {str(e)}")
            return []

    

    def _download_file(self, remote_path):
        try:
            file_in_memory = io.BytesIO()
            self.sftp.getfo(remote_path, file_in_memory)
            file_in_memory.seek(0)
            return file_in_memory
        except Exception as e:
            print(f"Erreur de téléchargement {remote_path}: {str(e)}")
            return None

    def process_files(self):
        all_output = []
        for file_type, remote_path, _ in self.matched_files:
            try:
                file_in_memory = self._download_file(remote_path)
                if file_in_memory:
                    print(f"Téléchargement réussi : {remote_path}")
                    # Appel de la fonction spécifique selon le type de fichier
                    if file_type == 'clorian':
                        output_lines = clorian(file_in_memory, remote_path)  # Traitement spécifique pour Clorian
                    elif file_type == 'stripe':
                        output_lines = st(file_in_memory)  # Traitement spécifique pour Stripe
                    elif file_type == 'shopify':
                        output_lines = shopify(file_in_memory) # Traitement spécifique pour Shopify
                    else:
                        output_lines = []  # Si un autre type est ajouté, traite-le ici
                    all_output.extend(output_lines)  # Ajouter les données traitées
            except Exception as e:
                print(f"Erreur avec {remote_path}: {str(e)}")

        self._save_output(all_output)  # Sauvegarde de toutes les données traitées dans le fichier de sortie


    def _save_output(self, output_lines):
        try:
            with open(self.args.output, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerows(output_lines)
            print(f"Données ajoutées au fichier de sortie {self.args.output}")
        except Exception as e:
            print(f"Erreur lors de l'enregistrement du fichier de sortie: {str(e)}")

    def close_sftp(self):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()
        print("Connexion SFTP fermée.")

def main():
    try:
        request = UsrRequest()

        # Ajouter la logique de vérification de type de fichier dans les arguments
        # La ligne ci-dessous permettra de traiter un type spécifique (ou plusieurs)
        file_types = ['clorian', 'stripe', 'shopify']  # Liste des types de fichiers que tu veux traiter
        # Si tu veux supporter d'autres types comme 'other', ajoute-les ici.

        out_data_fields = [
            "# Explications Code journal", "Date avec ou sans les /", "Informations", "Numéro de compte",
            "Code section analytique", "Libellé de la ligne", "Date d'échéance", "Montant débit", "Montant crédit", 
            "      ", "      ", "     ", "     ", "    ", "    ", "Référence", "Informations", "    ", "    ", "    ", "    ", " lien"
        ]

        # Création du fichier de sortie avec les en-têtes
        with open(request.args.output, 'w', newline='', encoding='utf-8') as w:
            csvwriter = csv.writer(w)
            csvwriter.writerow(out_data_fields)
        print(f"En-têtes ajoutés à {request.args.output}.")

        # Connexion SFTP et traitement des fichiers
        request.connect_sftp()
        
        # Filtrer les fichiers à traiter en fonction des types spécifiés dans les arguments
        request.matched_files = [file for file in request.matched_files if file[0] in file_types]
        
        # Traiter les fichiers filtrés
        request.process_files()

    except Exception as e:
        print(f"Erreur lors de l'exécution du script: {e}")
    finally:
        if hasattr(request, 'close_sftp'):
            request.close_sftp()

if __name__ == "__main__":
    main()
