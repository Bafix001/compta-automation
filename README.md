# luma-compta-automation
# Automatisation Comptable - Traitement Shopify, Stripe, Clorian, Skidata

Ce projet automatise le traitement comptable des fichiers de ventes 
(provenant de Shopify, Stripe, Clorian, Skidata) stockés sur un serveur SFTP. 
Il génère automatiquement des écritures comptables au format CSV, 
prêtes à être intégrées dans un logiciel de comptabilité.

---

## Fonctionnalités

- 🔐 Connexion sécurisée au serveur SFTP (via Paramiko)
- 📊 Lecture et traitement des fichiers Excel/CSV des différentes sources
- 🌍 Gestion spécifique des règles comptables selon pays (France, UE, Hors UE)
- 📅 Formatage et validation des dates multi-formats
- 🔒 Sécurisation des données sensibles via variables d'environnement (`.env`)
- 📈 Génération d'un fichier CSV consolidé des écritures comptables
- 📧 (Optionnel) Envoi automatique du rapport par email

---

## Prérequis

- Python 3.8+
- Modules Python : 
  - `pandas`
  - `openpyxl`
  - `paramiko`
  - `python-dotenv`

---

## Installation

1. **Cloner le dépôt** :
git clone https://github.com/Bafix001/compta-automation.git
cd compta-automation/src


2. **Installer les dépendances** :
pip install -r ../requirements.txt

3. **Créer un fichier `.env` à la racine** avec tes variables sensibles :
SFTP_HOST=ton-serveur-sftp.com
SFTP_USER=ton-username
SFTP_PASS=ton-password
SFTP_DIRS=/all_uploads/shopify,/all_uploads/stripe,/all_uploads/clorian
OUTPUT_FILE=/opt/automation/output.csv

Variables email (optionnel)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_FROM=ton-email@domaine.com
EMAIL_PASSWORD=ton-app-password
EMAIL_TO=comptable@entreprise.com

---

## Utilisation

**Lancer manuellement** :
cd src
python3 main.py

**Avec arguments explicites** (optionnel) :
python3 main.py --sftp-host $SFTP_HOST --sftp-user $SFTP_USER --sftp-pass $SFTP_PASS


---

## Automatisation via cron

**Configurer l'exécution automatique chaque matin à 8h** :

crontab -e


Ajouter :
0 8 * * * cd /opt/compta-automation/src && python3 main.py >> /var/log/compta.log 2>&1


---

## Logique spécifique

- Gestion des ventes par pays (France, UE avec/sans TVA, hors UE)
- Prise en compte de la TVA totale (colonne `Tax`) pour le calcul
- Support multi-format de dates incluant format datetime avec heure

---

## Sécurité

- Les mots de passe et secrets sont stockés uniquement dans `.env` (non versionné)
- `.gitignore` exclut les fichiers sensibles et dossiers temporaires

---

## Contribution

Merci de respecter les bonnes pratiques :

- Pas de secrets en dur dans le code
- Ajoutez les nouveautés avec tests et documentation
- Utiliser Git avec commits clairs

---

## Contact

Pour toute question, contact : ton-email@domaine.com

---

*Ce projet a été développé par Oumorou ZIBO pour le compte de Luma Arles, décembre 2025.*
