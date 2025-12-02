import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class EmailSender:
    """Classe pour envoyer des rapports comptables par email."""
    
    def __init__(self):
        """Initialise les paramètres SMTP depuis les variables d'environnement."""
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.email_from = os.getenv('EMAIL_FROM')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.email_to = os.getenv('EMAIL_TO')
        
        # Validation des paramètres requis
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Valide que tous les paramètres requis sont présents."""
        required_params = {
            'EMAIL_FROM': self.email_from,
            'EMAIL_PASSWORD': self.email_password,
            'EMAIL_TO': self.email_to
        }
        
        missing = [key for key, value in required_params.items() if not value]
        if missing:
            raise ValueError(
                f"Paramètres manquants dans .env : {', '.join(missing)}"
            )
    
    def _create_email_body(self, stats: Dict[str, int]) -> str:
        """
        Génère le corps du message email.
        
        Args:
            stats: Dictionnaire avec les statistiques du rapport
            
        Returns:
            Corps du message formaté
        """
        now = datetime.now()
        date_str = now.strftime('%d/%m/%Y')
        datetime_str = now.strftime('%d/%m/%Y à %H:%M')
        
        return f"""Bonjour,

Voici le rapport comptable automatisé du {datetime_str}.

📈 Statistiques :
- Nombre total d'écritures : {stats.get('total_lines', 0)}
- Shopify : {stats.get('shopify', 0)} lignes
- Stripe : {stats.get('stripe', 0)} lignes
- Clorian : {stats.get('clorian', 0)} lignes
- Skidata : {stats.get('skidata', 0)} lignes

Le fichier CSV est en pièce jointe.

Cordialement,
Système d'automatisation comptable Luma Arles
"""
    
    def _attach_csv_file(self, msg: MIMEMultipart, csv_file_path: str) -> None:
        """
        Attache le fichier CSV au message email.
        
        Args:
            msg: Message email
            csv_file_path: Chemin vers le fichier CSV
            
        Raises:
            FileNotFoundError: Si le fichier CSV n'existe pas
        """
        file_path = Path(csv_file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Le fichier {csv_file_path} n'existe pas")
        
        with open(file_path, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            
            filename = f"rapport_compta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{filename}"'
            )
            msg.attach(part)
    
    def send_report(self, csv_file_path: str, stats: Dict[str, int]) -> bool:
        """
        Envoie le rapport CSV par email.
        
        Args:
            csv_file_path: Chemin vers le fichier CSV généré
            stats: Dictionnaire avec statistiques (total_lines, shopify, stripe, etc.)
            
        Returns:
            True si l'envoi a réussi, False sinon
        """
        try:
            # Créer le message
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = f"📊 Rapport Comptable - {datetime.now().strftime('%d/%m/%Y')}"
            
            # Ajouter le corps du message
            body = self._create_email_body(stats)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Attacher le fichier CSV
            self._attach_csv_file(msg, csv_file_path)
            
            # Connexion et envoi
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)
            
            print(f"✅ Email envoyé avec succès à {self.email_to}")
            return True
            
        except FileNotFoundError as e:
            print(f"❌ Fichier introuvable : {e}")
            return False
        except smtplib.SMTPAuthenticationError:
            print("❌ Erreur d'authentification SMTP. Vérifiez vos identifiants.")
            return False
        except smtplib.SMTPException as e:
            print(f"❌ Erreur SMTP : {e}")
            return False
        except Exception as e:
            print(f"❌ Erreur inattendue lors de l'envoi de l'email : {e}")
            return False


