# app/integrations/google_client.py
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from typing import Tuple
from app.config import settings       # <-- Importar Config
from app.utils.logger import logger   # <-- Importar Logger

# Scopes necesarios
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

class GoogleIntegrator:
    def __init__(self):
        self.creds = None
        try:
            if os.path.exists(settings.GOOGLE_CREDENTIALS_FILE):
                logger.info("🔑 Cargando credenciales de Google desde archivo JSON local.")
                self.creds = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
                )
            else:
                # Fallback para Cloud Run (Default Credentials)
                logger.info("🔑 Intentando cargar Application Default Credentials (Cloud Run Environment).")
                import google.auth
                self.creds, _ = google.auth.default(scopes=SCOPES)

            self.drive_service = build('drive', 'v3', credentials=self.creds)
            self.sheets_service = build('sheets', 'v4', credentials=self.creds)
        except Exception as e:
            logger.critical(f"🔥 Error inicializando servicios de Google: {e}")
            raise e

    def create_folder(self, folder_name: str, parent_id: str) -> str:
        """Crea una carpeta en Drive."""
        try:
            file_metadata = {
                'name': folder_name,
                'parents': [parent_id],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.drive_service.files().create(
                body=file_metadata, fields='id'
            ).execute()
            folder_id = folder.get('id')
            logger.info(f"📁 Carpeta creada en Drive: '{folder_name}' (ID: {folder_id})")
            return folder_id
        except Exception as e:
            logger.error(f"❌ Error creando carpeta Drive '{folder_name}': {e}")
            raise e

    def upload_file(self, local_path: str, folder_id: str, mime_type: str = None) -> Tuple[str, str]:
        """Sube archivo a Drive."""
        file_name = os.path.basename(local_path)
        try:
            logger.info(f"⬆️ Subiendo archivo a Drive: {file_name}")
            
            file_metadata = {'name': file_name, 'parents': [folder_id]}
            media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            # Permisos públicos (Opcional, ajustar según seguridad)
            self.drive_service.permissions().create(
                fileId=file.get('id'),
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()

            logger.info(f"✅ Subida completada: {file_name}")
            return file.get('id'), file.get('webViewLink')
            
        except Exception as e:
            logger.error(f"❌ Error subiendo archivo '{file_name}' a Drive: {e}")
            raise e

    def update_sheet(self, spreadsheet_id: str, worksheet_name: str, cell_updates: dict):
        """Actualiza celdas en Sheets."""
        try:
            data = []
            for cell, value in cell_updates.items():
                data.append({
                    'range': f"{worksheet_name}!{cell}",
                    'values': [[value]]
                })
            
            body = {'valueInputOption': 'RAW', 'data': data}
            
            self.sheets_service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
            
            logger.info(f"📊 Hoja actualizada correctamente (Celdas: {list(cell_updates.keys())})")
            
        except Exception as e:
            logger.error(f"❌ Error actualizando Google Sheet: {e}")
            # No hacemos raise aquí para no interrumpir el flujo si el PDF ya se subió