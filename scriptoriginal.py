# ESTE PROGRAMA VA A LA SPREADSHEET: https://docs.google.com/spreadsheets/d/1UY6aPIkfapY5T_GOQ57Qv8_4L103RUgGoNbdX7khCfQ/edit
# VA A LA HOJA 'PREENSAMBLADO'

#LIBRERIAS##################################################################################################
import dropbox
import os
import json
import shutil
import re 
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image
import img2pdf
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
from reportlab.lib.colors import black
from reportlab.graphics.shapes import Line
from reportlab.pdfgen.canvas import Canvas
import gspread
from pypdf import PdfWriter
import time

#########################################################################################################

# --- CONFIGURACIÓN E INSTANCIACIÓN ---
class DropboxHandler:
    """
    Maneja la conexión y las operaciones básicas con la API de Dropbox.
    (Lógica de __init__ y get_folder_path... tomada de tu script de referencia)
    """
    def __init__(self, access_token):
        """
        Inicializa el cliente de Dropbox (Usando la lógica de tu script de referencia)
        """
        if not access_token:
            raise ValueError("El token de acceso de Dropbox no puede estar vacío.")
        
        try:
            self.dbx = dropbox.Dropbox(access_token)
            cuenta = self.dbx.users_get_current_account()
            print(f"Conexión exitosa a Dropbox. Conectado como: {cuenta.name.display_name} 😊")
            
            # --- LÓGICA DE TU SCRIPT DE REFERENCIA ---
            if hasattr(cuenta, 'team'):
                print(f"Detectada cuenta de Equipo: {cuenta.team.name}")
                root_namespace_id = cuenta.root_info.root_namespace_id
                print("Cambiando contexto al Espacio de Equipo para realizar búsquedas.")
                self.dbx = self.dbx.with_path_root(dropbox.common.PathRoot.namespace_id(root_namespace_id))
            # --- FIN DE LA LÓGICA DE REFERENCIA ---

        except dropbox.exceptions.AuthError as e:
            print(f"Error Crítico de Autenticación en Dropbox: {e}")
            print("Verifica que tu TOKEN_DE_ACCESO sea válido y no haya expirado.")
            raise
        except Exception as e:
            print(f"Error Crítico al conectar a Dropbox: {e}")
            raise

    def get_folder_path_from_shared_link(self, shared_link_url):
        """
        Obtiene la ruta de la carpeta (Usando la lógica de tu script de referencia)
        """
        try:
            print(f"Obteniendo metadata para el link: {shared_link_url}")
            metadata = self.dbx.sharing_get_shared_link_metadata(shared_link_url)
            
            path = getattr(metadata, 'path_lower', None)
            
            if path is None:
                # Este es el error que estabas viendo.
                print(f"❌ El link '{shared_link_url}' no devolvió una ruta ('path_lower' está ausente). Verifica el contexto de la cuenta (Personal/Equipo).")
                return None
            
            # Devolvemos la ruta tal cual la da la API.
            # (El script de referencia no diferencia entre archivo/carpeta aquí, 
            # asume que el link es a una carpeta, lo cual es correcto para /scl/fo/)
            return path

        except dropbox.exceptions.ApiError as e:
            print(f"No se pudo obtener la ruta para el link '{shared_link_url}': {e}")
            return None
        except Exception as e:
            print(f"Error inesperado obteniendo metadata del link: {e}")
            return None

    def list_folder_contents(self, folder_path):
        """
        Lista el contenido (archivos y carpetas) de una carpeta específica en Dropbox.
        (Versión mejorada con paginación)
        """
        try:
            result = self.dbx.files_list_folder(folder_path, limit=2000)
            entries = result.entries
            
            # Manejar paginación
            while result.has_more:
                print(f"Paginando... Obteniendo más archivos de {folder_path}")
                result = self.dbx.files_list_folder_continue(result.cursor)
                entries.extend(result.entries)
                
            return entries
        except dropbox.exceptions.ApiError as e:
            print(f"No se pudo listar el contenido de la carpeta '{folder_path}': {e}")
            return []

    def download_file(self, file_path, local_folder):
        """
        Descarga un archivo de Dropbox a una carpeta local.
        (Versión mejorada con nombres de archivo seguros)
        """
        try:
            if not os.path.exists(local_folder):
                os.makedirs(local_folder)
            
            file_name = os.path.basename(file_path)
            # Sanitizar nombre de archivo para Windows/Mac/Linux
            safe_file_name = re.sub(r'[\\/*?:"<>|]',"_", file_name)
            local_path = os.path.join(local_folder, safe_file_name)

            print(f"Descargando: {file_name}...")
            # Usamos path_display o file_path (que debería ser path_lower)
            self.dbx.files_download_to_file(local_path, file_path)
            print(f"✅ ¡Descarga completa! Archivo guardado en: {local_path}")
            return local_path
        except dropbox.exceptions.ApiError as e:
            print(f"❌ Error al descargar el archivo '{file_path}': {e}")
            return None
        except Exception as e:
            print(f"❌ Error inesperado al guardar el archivo '{file_path}' en '{local_path}': {e}")
            return None

# --- NUEVAS Funciones de Búsqueda y Descarga Flexible ---

def normalize_text(text):
    """
    Normaliza el texto para búsquedas flexibles: minúsculas, sin espacios ni símbolos.
    """
    text = str(text).lower()
    # Mantenemos números y letras
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def find_remote_folder(handler, base_folder_path, keywords):
    """
    Busca una carpeta (NO recursivo) dentro de 'base_folder_path' que coincida 
    con alguna de las 'keywords' (case-insensitive).
    """
    print(f"Buscando carpeta con palabras clave: {keywords} en {base_folder_path}")
    norm_keywords = [normalize_text(kw) for kw in keywords]
    try:
        entries = handler.list_folder_contents(base_folder_path)
        for entry in entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                norm_entry_name = normalize_text(entry.name)
                # Buscamos que *alguna* de las palabras clave esté en el nombre de la carpeta
                if any(kw in norm_entry_name for kw in norm_keywords):
                    print(f"✅ Carpeta encontrada: '{entry.name}' (Ruta: {entry.path_lower})")
                    return entry.path_lower
    except Exception as e:
        print(f"❌ Error buscando carpeta: {e}")
    print(f"⚠️ No se encontró ninguna carpeta con las palabras clave: {keywords} en {base_folder_path}")
    return None

def find_files_recursively(handler, folder_path, prioritized_patterns_norm, stop_on_first_match, local_dest_folder):
    """
    Busca archivos recursivamente.
    - Si stop_on_first_match es True: Busca usando la lista de prioridad y se detiene y devuelve 
      el path del *primer* archivo que encuentra y descarga.
    - Si stop_on_first_match es False: Busca todos los archivos que coincidan con *cualquier* patrón y devuelve un dict {patron_encontrado: path_local}.
    """
    
    if stop_on_first_match:
        # --- Lógica para EXHIBIT 4 (Prioridad) ---
        print(f"Buscando (con prioridad) en: {folder_path}")
        for pattern in prioritized_patterns_norm:
            print(f"--- Intentando con prioridad: '{pattern}'")
            try:
                entries = handler.list_folder_contents(folder_path)
                for entry in entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        norm_file_name = normalize_text(entry.name)
                        if pattern in norm_file_name:
                            print(f"✅ ¡Encontrado (Prioridad)!: {entry.name}")
                            return handler.download_file(entry.path_lower, local_dest_folder)
                
                # Si no se encontró en este nivel, buscar en subcarpetas
                for entry in entries:
                    if isinstance(entry, dropbox.files.FolderMetadata):
                        found_path = find_files_recursively(handler, entry.path_lower, [pattern], True, local_dest_folder)
                        if found_path:
                            return found_path # Encontrado en recursión
            except Exception as e:
                print(f"Error buscando con prioridad en {folder_path}: {e}")
                continue # Probar siguiente patrón
        return None # No se encontró con ningún patrón en esta rama

    else:
        # --- Lógica para EXHIBIT 1 (Encontrar todos) ---
        print(f"Buscando (todos) en: {folder_path}")
        found_files_dict = {}
        try:
            entries = handler.list_folder_contents(folder_path)
            for entry in entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    norm_file_name = normalize_text(entry.name)
                    for pattern in prioritized_patterns_norm:
                        if pattern in norm_file_name and pattern not in found_files_dict:
                            print(f"✅ ¡Encontrado!: {entry.name} (Coincide con: {pattern})")
                            local_path = handler.download_file(entry.path_lower, local_dest_folder)
                            if local_path:
                                found_files_dict[pattern] = local_path
                
                elif isinstance(entry, dropbox.files.FolderMetadata):
                    # Recurso y fusiono resultados
                    recursive_results = find_files_recursively(handler, entry.path_lower, prioritized_patterns_norm, False, local_dest_folder)
                    # Fusionar, dando prioridad a los ya encontrados (por si hay duplicados)
                    for pattern, path in recursive_results.items():
                        if pattern not in found_files_dict:
                            found_files_dict[pattern] = path
                            
        except Exception as e:
            print(f"Error en búsqueda recursiva (todos) en {folder_path}: {e}")
            
        return found_files_dict

def find_folder_recursively(handler, base_folder_path, folder_keyword_normalized):
    """
    Busca recursivamente desde 'base_folder_path' una carpeta que contenga 'folder_keyword_normalized'.
    Se detiene en la primera coincidencia.
    """
    print(f"Buscando recursivamente '{folder_keyword_normalized}' en {base_folder_path}...")
    try:
        entries = handler.list_folder_contents(base_folder_path)
        for entry in entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                norm_entry_name = normalize_text(entry.name)
                if folder_keyword_normalized in norm_entry_name:
                    print(f"✅ Carpeta recursiva encontrada: '{entry.name}'")
                    return entry.path_lower # ¡Encontrada!
        
        # Si no está en este nivel, buscar en subcarpetas
        for entry in entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                result_path = find_folder_recursively(handler, entry.path_lower, folder_keyword_normalized)
                if result_path:
                    return result_path # Encontrada en nivel inferior
                    
    except Exception as e:
        print(f"Error en búsqueda recursiva de carpeta: {e}")
        
    return None # No se encontró en esta rama

def download_folder_recursively(handler, remote_path, local_path):
    """
    Descarga TODO el contenido de una carpeta de Dropbox recursivamente.
    """
    print(f"📁 Descargando TODO de: {remote_path} -> {local_path}")
    try:
        os.makedirs(local_path, exist_ok=True)
        entries = handler.list_folder_contents(remote_path)
        
        downloaded_file_paths = []
        
        for entry in entries:
            entry_local_path = os.path.join(local_path, entry.name)
            
            if isinstance(entry, dropbox.files.FolderMetadata):
                # Es una carpeta, llamamos recursivamente
                downloaded_file_paths.extend(
                    download_folder_recursively(handler, entry.path_lower, entry_local_path)
                )
            
            elif isinstance(entry, dropbox.files.FileMetadata):
                # Es un archivo, descargar
                downloaded_file = handler.download_file(entry.path_lower, local_path)
                if downloaded_file:
                    downloaded_file_paths.append(downloaded_file)

        return downloaded_file_paths

    except Exception as e:
        print(f"❌ Error en la descarga recursiva de {remote_path}: {e}")
        return []

# --- Funciones de Google Sheets y Drive ---
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

# --- ¡CONSTANTES MODIFICADAS! ---
SPREADSHEET_ID = '1UY6aPIkfapY5T_GOQ57Qv8_4L103RUgGoNbdX7khCfQ'
WORKSHEET_NAME = 'PREENSAMBLADO'
DRIVE_DESTINATION_FOLDER_ID = '1QBrlti0mpJ_XFWif2_S5HkLUkR-2LmXY' # Carpeta "PREENSAMBLADOS"
# ---

FAILS_LOG_FILE = 'linksfails.json'

def get_google_creds():
    """
    Maneja el flujo de autenticación de Google OAuth2.0.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"Archivo '{CREDENTIALS_FILE}' no encontrado. Necesitas tus credenciales de Google API.")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return creds

def create_drive_folder(drive_service, folder_name, parent_folder_id):
    """
    Crea una nueva carpeta en Google Drive si no existe.
    """
    try:
        # Sanitizar nombre para Drive
        safe_folder_name = folder_name.replace("'", "\\'")
        query = f"name='{safe_folder_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_folder_id}' in parents and trashed=false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        
        if not items:
            file_metadata = {
                'name': folder_name,
                'parents': [parent_folder_id],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = drive_service.files().create(body=file_metadata, fields='id').execute()
            print(f"✅ Carpeta de Drive creada para '{folder_name}'. ID: {folder.get('id')}")
            return folder.get('id')
        else:
            print(f"ℹ️ La carpeta de Drive para '{folder_name}' ya existe. Usando la carpeta existente.")
            return items[0].get('id')
    except Exception as e:
        print(f"❌ Error al crear/encontrar la carpeta en Google Drive: {e}")
        return None

def upload_folder_to_drive(drive_service, local_path, parent_drive_folder_id):
    """
    Sube un directorio local a Google Drive de forma recursiva.
    """
    print(f"Subiendo carpeta local '{local_path}' a Drive (ID: {parent_drive_folder_id})...")
    drive_folder_map = {local_path: parent_drive_folder_id}

    for root, dirs, files in os.walk(local_path):
        current_drive_parent_id = drive_folder_map[root]

        # Sube las subcarpetas
        for directory in dirs:
            local_subfolder_path = os.path.join(root, directory)
            file_metadata = {
                'name': directory,
                'parents': [current_drive_parent_id],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            try:
                folder = drive_service.files().create(body=file_metadata, fields='id').execute()
                new_folder_id = folder.get('id')
                print(f"Sub-carpeta '{directory}' creada en Drive. ID: {new_folder_id}")
                drive_folder_map[local_subfolder_path] = new_folder_id
            except Exception as e:
                print(f"❌ Error creando subcarpeta '{directory}' en Drive: {e}")
                continue
        
        # Sube los archivos
        for filename in files:
            local_file_path = os.path.join(root, filename)
            
            file_metadata = {
                'name': filename,
                'parents': [current_drive_parent_id]
            }
            media = MediaFileUpload(local_file_path, resumable=True)
            
            print(f"📤 Subiendo archivo: {filename}")
            try:
                drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                print(f"✅ Archivo '{filename}' subido a Drive.")
            except Exception as e:
                print(f"❌ Error al subir el archivo '{filename}': {e}")

def get_drive_folder_link(drive_service, folder_id):
    """
    Obtiene el enlace compartible de una carpeta de Google Drive.
    """
    try:
        # Crear permiso para "cualquiera con el enlace"
        permission = { 'type': 'anyone', 'role': 'reader' }
        try:
            drive_service.permissions().create(
                fileId=folder_id,
                body=permission,
                fields='id'
            ).execute()
        except Exception as e:
            # Si el permiso ya existe, puede dar error, lo ignoramos
            print(f"Info: Permiso de Drive (Carpeta) posiblemente ya existía.")
            
        file_metadata = drive_service.files().get(
            fileId=folder_id,
            fields='webViewLink'
        ).execute()
        
        return file_metadata.get('webViewLink')
    except Exception as e:
        print(f"❌ Error al obtener el enlace compartible de la carpeta de Drive: {e}")
        return None

def get_drive_file_link(drive_service, file_name, parent_folder_id):
    """
    Busca un archivo por nombre en una carpeta de Drive y obtiene su enlace.
    """
    try:
        # Sanitizar nombre para la query
        safe_file_name = file_name.replace("'", "\\'")
        query = f"name='{safe_file_name}' and '{parent_folder_id}' in parents and trashed=false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name, webViewLink)').execute()
        items = results.get('files', [])

        if not items:
            print(f"❌ No se encontró el archivo '{file_name}' en Drive (ID Carpeta: {parent_folder_id}).")
            return None
        
        file_id = items[0].get('id')
        
        # Asegurarse de que el archivo sea legible por cualquiera
        permission = { 'type': 'anyone', 'role': 'reader' }
        try:
            drive_service.permissions().create(
                fileId=file_id,
                body=permission,
                fields='id'
            ).execute()
        except Exception as e:
            print(f"Info: Permiso de Drive (Archivo) posiblemente ya existía.")

        return items[0].get('webViewLink')

    except Exception as e:
        print(f"❌ Error al obtener el enlace del archivo '{file_name}': {e}")
        return None
    
def log_fail(row_data, error_message):
    """
    Registra una fila fallida en un archivo JSON.
    (Actualizado a los nuevos índices de columna)
    """
    fail_data = {
        "fila": row_data[0],      # Número de fila (asumido)
        "cliente": row_data[1],   # Columna B (índice 1)
        "link": row_data[2],      # Columna C (índice 2)
        "error": error_message
    }
    fails = []
    if os.path.exists(FAILS_LOG_FILE):
        try:
            with open(FAILS_LOG_FILE, 'r') as f:
                fails = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass 
    
    fails.append(fail_data)
    
    with open(FAILS_LOG_FILE, 'w') as f:
        json.dump(fails, f, indent=4)
    print(f"⚠️ Error registrado en '{FAILS_LOG_FILE}'.")

# --- FUNCIÓN DE CONVERSIÓN RECURSIVA ---
def convert_images_to_pdf_recursively(local_folder_path):
    """
    Busca archivos de imagen en un directorio y sus subdirectorios y los convierte a PDF.
    """
    print("\n--- Convirtiendo imágenes a PDF (recursivo) ---")
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')
    
    for root, _, files in os.walk(local_folder_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            if filename.lower().endswith(image_extensions):
                # Convertir esta imagen
                pdf_filename = os.path.splitext(filename)[0] + ".pdf"
                pdf_path = os.path.join(root, pdf_filename)
                
                print(f"Convirtiendo imagen: {filename}")
                try:
                    with open(pdf_path, "wb") as f:
                        f.write(img2pdf.convert(file_path))
                    print(f"✅ Imagen convertida a PDF: {pdf_path}")
                    # Eliminar la imagen original para no subir duplicados
                    os.remove(file_path)
                    print(f"🗑️ Imagen original eliminada: {filename}")
                except Exception as e:
                    print(f"❌ Error al convertir la imagen '{filename}': {e}")

# --- NUEVA FUNCIÓN DE CORRECCIÓN DE RUTAS ---
def fix_paths_after_conversion(doc_paths_dict):
    """
    Revisa las rutas en el diccionario de documentos y actualiza las
    extensiones de imagen a .pdf si fueron convertidas.
    """
    print("Corrigiendo rutas de archivos después de la conversión de imágenes...")
    image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')
    fixed_paths = {}
    
    # Exhibit 1
    fixed_ex1 = []
    for path in doc_paths_dict.get('exhibit_1', []):
        base, ext = os.path.splitext(path)
        if ext.lower() in image_extensions:
            fixed_ex1.append(base + ".pdf")
        else:
            fixed_ex1.append(path)
    fixed_paths['exhibit_1'] = fixed_ex1
    
    # Exhibit 3
    fixed_ex3 = []
    for path in doc_paths_dict.get('exhibit_3', []):
        base, ext = os.path.splitext(path)
        if ext.lower() in image_extensions:
            fixed_ex3.append(base + ".pdf")
        else:
            fixed_ex3.append(path)
    fixed_paths['exhibit_3'] = fixed_ex3
    
    # Exhibit 4
    path = doc_paths_dict.get('exhibit_4')
    if path:
        base, ext = os.path.splitext(path)
        if ext.lower() in image_extensions:
            fixed_paths['exhibit_4'] = base + ".pdf"
        else:
            fixed_paths['exhibit_4'] = path
    else:
        fixed_paths['exhibit_4'] = None
        
    return fixed_paths


# --- FUNCIONES DE CREACIÓN DE PDF (MODIFICADAS) ---

def create_cover_page(path, title):
    """
    Crea un PDF de una sola página con un título (para usar como portada de sección).
    """
    c = Canvas(path, pagesize=letter)
    width, height = letter
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name='Title',
        parent=styles['h1'],
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    # Dibujar borde
    c.setStrokeColor(black)
    c.setLineWidth(3)
    c.rect(inch, inch, width - 2 * inch, height - 2 * inch)
    
    # Título
    p = Paragraph(title, title_style)
    p.wrapOn(c, width - 4 * inch, height)
    p.drawOn(c, 2 * inch, height / 2)
    
    c.showPage()
    c.save()


def create_final_merged_pdf(client_name, local_folder_path, doc_paths, missing_files):
    """
    Crea el PDF final uniendo los documentos encontrados según la NUEVA lógica de Exhibits.
    """
    merger = PdfWriter()
    safe_client_name = "".join(c for c in client_name if c.isalnum() or c in (' ', '_')).rstrip()
    output_pdf_path = os.path.join(local_folder_path, f"PAQUETE_ENSAMBLADO_{safe_client_name}.pdf")
    temp_cover_dir = os.path.join(local_folder_path, "temp_covers")
    os.makedirs(temp_cover_dir, exist_ok=True)
    
    print(f"--- Creando PDF unido para: {client_name} ---")

    def append_pdf_to_merger(pdf_path):
        """Función interna para añadir PDF al merger de forma segura."""
        if pdf_path and os.path.exists(pdf_path) and pdf_path.lower().endswith('.pdf'):
            try:
                merger.append(pdf_path)
                print(f"Añadiendo al PDF: {os.path.basename(pdf_path)}")
            except Exception as e:
                print(f"❌ Error al intentar añadir '{pdf_path}' al PDF unido. Archivo corrupto o inválido. {e}")
        elif not pdf_path or not os.path.exists(pdf_path):
            print(f"⚠️ Archivo no encontrado localmente, no se puede añadir: {pdf_path}")
        else:
            print(f"⚠️ Omitiendo archivo (no es PDF): {pdf_path}")

    # 1. EXHIBIT – NOMBRE DEL CLIENTE
    cover_path_1 = os.path.join(temp_cover_dir, "cover_1.pdf")
    create_cover_page(cover_path_1, f"1. EXHIBIT – {client_name}")
    merger.append(cover_path_1)
    
    # Añadir los archivos de USCIS (Exhibit 1)
    for path in doc_paths.get('exhibit_1', []):
        append_pdf_to_merger(path)

    # 2. EXHIBIT – SI NO SE ENCONTRO...
    cover_path_2 = os.path.join(temp_cover_dir, "cover_2.pdf")
    create_cover_page(cover_path_2, "2. EXHIBIT – INFORMACIÓN FALTANTE")
    merger.append(cover_path_2)
    
    # Crear una página con la lista de archivos faltantes
    notes_path = os.path.join(temp_cover_dir, "notes.pdf")
    doc = SimpleDocTemplate(notes_path, pagesize=letter, topMargin=inch*2, leftMargin=inch*2, rightMargin=inch*2, bottomMargin=inch*2)
    story = [Paragraph("Documentación Faltante Detectada:", getSampleStyleSheet()['h2'])]
    if missing_files:
        for item in missing_files:
            story.append(Paragraph(f"- {item}", getSampleStyleSheet()['BodyText']))
    else:
        story.append(Paragraph("No se detectaron documentos faltantes en esta ejecución.", getSampleStyleSheet()['BodyText']))
    doc.build(story)
    merger.append(notes_path)

    # 3. EXHIBIT 3 (VAWA/EVIDENCE)
    cover_path_3 = os.path.join(temp_cover_dir, "cover_3.pdf")
    create_cover_page(cover_path_3, "3. EXHIBIT – EVIDENCE (de VAWA)")
    merger.append(cover_path_3)
    
    # Añadir los archivos de EVIDENCE (Exhibit 3)
    for path in doc_paths.get('exhibit_3', []):
        append_pdf_to_merger(path)

    # 4. EXHIBIT FILED COPY
    cover_path_4 = os.path.join(temp_cover_dir, "cover_4.pdf")
    create_cover_page(cover_path_4, "4. EXHIBIT – FILED COPY")
    merger.append(cover_path_4)
    
    # Añadir el archivo de FILED COPY (Exhibit 4)
    append_pdf_to_merger(doc_paths.get('exhibit_4'))

    # Guardar el PDF final
    try:
        with open(output_pdf_path, "wb") as f:
            merger.write(f)
        merger.close()
        print(f"✅ PDF de ensamblaje unido creado en: {output_pdf_path}")
    except Exception as e:
        print(f"❌ Error al escribir el PDF unido final: {e}")
        return None, missing_files
        
    # Limpiar portadas temporales
    try:
        shutil.rmtree(temp_cover_dir)
    except Exception as e:
        print(f"⚠️ No se pudo eliminar la carpeta de portadas temporales: {e}")

    return output_pdf_path, missing_files

# --- Bloque de ejecución principal (REESTRUCTURADO) ---
if __name__ == "__main__":
    TOKEN_DE_ACCESO = 'sl.u.AGHFrSeSwrulnBv8oy3Vd2E-BxC_uYf2kSk_PAQnzZUlPT7txqR_xvd4_n2VAf4fsO0eMzroy_cbglRQL0ckXmMVOSS72QKM9jpTEAk4DdggM3iXHtbynayJkXyrgrqMHMM8lqwf4_Hqz758w7hZOT04P1KulY-U0Rny8fA2ApiB4aXdQCL5dp0Hs9iIFrZcYX0OEJR0_c6GK4oaTX124NLZ6x0YGRTR2OUACU0KyUrP2zQKwLvYdbxUDNdb_uGRA_ZBlLhIIBNOA0mdgMoK5wdf4Cip0FTO5AMAkbH5sGU6ktROBkMvr1aHnMfdWTnQxi0bufbdc1YOit3CETuyWddKyt-x1x2N0cr8JhXaVOETt31qoM_UYdfzaw-eESW9eNelZWiUcOIJbn0vQvBaaUev-euvgM22LHt039Jgz-fGT8JrQ7Iwy2QPo_TKvpkOF1RYiVDIzaIEpsFxTr0jSDTqdA-b8D0Y3gWXQDWmcnMIyyKV3MeCqjYlRRGlvbGbJVx2-qLdU_knSbqcvX7YRVEg0_eaqEjatWzhJNgTbdusCDmOM5eHijsdSrw-tW97zEatA-LW_y-2sYayqJDZ_-m6TDOSPYArPuigtyFt18g8yv8_JEjXMrgwlNC2IIUXwStdsvVCDyFzvjgO6crsYI57yle-TsOVMyu2ja9NS7X7wcoX9ve1yowM5HwxJufMEBboXVn4RBF54pL7TpqUyqpl-jhwlL2oKIBRdOQ5sVpka8WeXLwepLfJzMqzYBoN9YKxOCzGVY2ldF9qvorcax1Ugzp6XM2L6vCKcQYNphR6mhGTtZUSciSq27WuqNvlRVosZMaZM4gsbi26WhWDFbeU7Kau9leh8Ma3rqI_IW63Zq1qAOCfGlZOni674EL1sg99a4w47DhquOC9brIfIHeCNHJ7eRrdthrux-FUUNE_iWh7ilP9frHiPKpLIXvXhgrZrhv1ksUe8lPJNv_ukTOdWyTxrTVKylH74SGG9l9Ev7JCmYaFfo7M1AOMP5vhgasoSJI6Kl3mW5YKaZDyzbQCFZI6lPAQjWRQxN5_Q3rPAeOkqKPjYomNLfJjYVK5K8bDhRQ7qxRtyqYZvBJhQW_ExboZ6eNa09hn25Ok_AvY0v9alQoWFRyagf6fX8rzM9miWOlo8aYllSXDxWzwe2-9rgcxUV0z5tsgkGv7VidFW2vmCvdrE0HkkDGbqab1p9AWJaaLgkyR4KqjDvaAsZlSrwQrwTuFidKJDXtDKE1pBqNjt0wbnpElfDznfGCQ3Kl9BKpZpETjO4knOnbqMRp6cZ6JUsJNgLH4zaTm1tcJHyzkam4aD18foLjmbmU81-SO7z9Ly5mltpLLRF1w06vF3VPhnokVmMH1oDKAZxB17HUBFPXL8O99rZOuLNTleGs' # PEGA TU TOKEN AQUÍ
    
    # Directorios de trabajo
    TEMP_DOWNLOAD_DIR = 'temp_dropbox_downloads'

    # --- NÚMERO DE FILA DESDE DONDE INICIAR ---
    STARTING_ROW_NUMBER = 3
    
    try:
        # --- 1. Autenticación Google Sheets y Drive ---
        print("--- PASO 1: Autenticación con Google APIs ---")
        creds = get_google_creds()
        sheets_service = build('sheets', 'v4', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        
        # --- 2. Conectar a Google Sheets ---
        print("\n--- PASO 2: Conectando a Google Sheets ---")
        gc = gspread.authorize(creds)
        worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
        all_values = worksheet.get_all_values()
        
        # --- 3. Conectar a Dropbox ---
        print("\n--- PASO 3: Conectando a Dropbox ---")
        handler = DropboxHandler(TOKEN_DE_ACCESO)

        # --- 4. Procesamiento de filas (LÓGICA REESTRUCTURADA) ---
        print("\n--- PASO 4: Procesando filas de la hoja de cálculo ---")
        
        # El índice de la lista es 0-based.
        for row_idx, row_data in enumerate(all_values):
            current_row_number = row_idx + 1
            
            # Saltar filas de encabezado y las filas antes del punto de inicio
            if current_row_number < STARTING_ROW_NUMBER:
                continue

            print(f"\n{'-'*50}\n--- Procesando Fila {current_row_number} ---")
            
            local_temp_folder = None
            # Declaramos variables para el bloque finally
            drive_folder_link = "ERROR"
            drive_pdf_link = "ERROR"
            missing_files = []
            
            try:
                # REQUISITOS: Col B (Cliente, idx 1), Col C (Link, idx 2)
                # SALIDA: Col E (Link Carpeta), Col F (Faltantes), Col G (Link PDF)
                
                # Check si la Columna G (índice 6) está presente y tiene datos
                if len(row_data) > 6 and row_data[6].strip(): 
                    print(f"✅ Fila {current_row_number}: Ya tiene un link en la columna G. Saltando.")
                    continue

                # Si la fila tiene menos de 3 elementos (índices 0 a 2), no tiene el link.
                if len(row_data) < 3:
                    print(f"❌ Fila {current_row_number} incompleta. No hay datos suficientes (Mínimo Columna C). Saltando.")
                    continue

                nombre_cliente = row_data[1].strip() # Columna B (índice 1)
                link_dropbox = row_data[2].strip()   # Columna C (índice 2)
                
                if not nombre_cliente:
                    print(f"⚠️ Fila {current_row_number}: Nombre del cliente vacío. Saltando.")
                    log_fail([current_row_number, nombre_cliente, link_dropbox], "Nombre del cliente vacío")
                    continue
                
                if not link_dropbox or not (link_dropbox.startswith('http') and 'dropbox.com' in link_dropbox):
                    print(f"⚠️ Fila {current_row_number}: Link de Dropbox vacío o inválido. Saltando.")
                    log_fail([current_row_number, nombre_cliente, link_dropbox], "Link de Dropbox inválido")
                    continue
                
                safe_client_name = "".join(c for c in nombre_cliente if c.isalnum() or c in (' ', '_')).rstrip()
                
                # 4.1 Crear carpeta en Google Drive para el cliente
                client_drive_folder_id = create_drive_folder(drive_service, safe_client_name, DRIVE_DESTINATION_FOLDER_ID)
                if not client_drive_folder_id:
                    raise Exception("No se pudo crear la carpeta de Google Drive.")
                
                # Crear carpeta de descarga temporal local
                local_temp_folder = os.path.join(TEMP_DOWNLOAD_DIR, safe_client_name)
                if os.path.exists(local_temp_folder):
                    shutil.rmtree(local_temp_folder) # Limpiar corridas anteriores
                os.makedirs(local_temp_folder, exist_ok=True)
                
                # 4.2 Obtener la ruta de la carpeta de Dropbox a partir del link
                ruta_base = handler.get_folder_path_from_shared_link(link_dropbox)
                
                if not ruta_base:
                    print(f"❌ No se pudo obtener la ruta base para el link de Dropbox. Saltando la fila {current_row_number}.")
                    raise Exception("Link de Dropbox inválido o inaccesible")
                
                # --- INICIO DE LÓGICA DE EXHIBITS ---
                
                all_doc_paths = {} # Aquí guardaremos las listas de rutas locales
                missing_files = [] # Aquí los nombres de los que falten

                # --- EXHIBIT 1: USCIS ---
                print("\n--- Procesando Exhibit 1 (USCIS) ---")
                uscis_folder_path = find_remote_folder(handler, ruta_base, ['USCIS', 'UCIS', 'USIS'])
                ex1_patterns_pristine = ['I-360 Prima facie', 'I-360 TRANSFER NOTICE', 'I-485 TRANSFER NOTICE']
                ex1_patterns_norm = {normalize_text(p): p for p in ex1_patterns_pristine}
                local_ex1_folder = os.path.join(local_temp_folder, "EXHIBIT_1_USCIS")
                
                if uscis_folder_path:
                    found_ex1_files = find_files_recursively(
                        handler, 
                        uscis_folder_path, 
                        list(ex1_patterns_norm.keys()), 
                        stop_on_first_match=False, 
                        local_dest_folder=local_ex1_folder
                    )
                    all_doc_paths['exhibit_1'] = list(found_ex1_files.values())
                    # Comprobar faltantes
                    for norm_pattern, pristine_name in ex1_patterns_norm.items():
                        if norm_pattern not in found_ex1_files:
                            missing_files.append(pristine_name)
                else:
                    print("⚠️ No se encontró la carpeta USCIS.")
                    missing_files.extend(ex1_patterns_pristine) # Faltan todos
                    all_doc_paths['exhibit_1'] = []

                # --- EXHIBIT 3: VAWA -> EVIDENCE ---
                print("\n--- Procesando Exhibit 3 (VAWA/EVIDENCE) ---")
                vawa_folder_path = find_remote_folder(handler, ruta_base, ['VAWA'])
                local_ex3_folder = os.path.join(local_temp_folder, "EXHIBIT_3_EVIDENCE")
                
                if vawa_folder_path:
                    evidence_folder_path = find_folder_recursively(handler, vawa_folder_path, 'evidence')
                    if evidence_folder_path:
                        # Descargar TODO el contenido de la carpeta EVIDENCE
                        downloaded_ex3_paths = download_folder_recursively(
                            handler, 
                            evidence_folder_path, 
                            local_ex3_folder
                        )
                        all_doc_paths['exhibit_3'] = downloaded_ex3_paths
                    else:
                        print("⚠️ No se encontró la carpeta 'EVIDENCE' dentro de 'VAWA'.")
                        missing_files.append("Carpeta 'EVIDENCE' (dentro de VAWA)")
                        all_doc_paths['exhibit_3'] = []
                else:
                    print("⚠️ No se encontró la carpeta 'VAWA'.")
                    missing_files.append("Carpeta 'VAWA' (y su contenido 'EVIDENCE')")
                    all_doc_paths['exhibit_3'] = []

                # --- EXHIBIT 4: FILED COPY ---
                print("\n--- Procesando Exhibit 4 (FILED COPY) ---")
                folder_7_path = find_remote_folder(handler, ruta_base, ['7'])
                ex4_patterns_pristine = [
                    'FILED COPY', 'FILE COPY', 'FC', 'READY TO PRINT', 
                    'READYTOPRINT', 'READY-TO-PRINT', 'FILED-COPY', 'RTP', 'SIGNED'
                ]
                ex4_patterns_norm = [normalize_text(p) for p in ex4_patterns_pristine]
                local_ex4_folder = os.path.join(local_temp_folder, "EXHIBIT_4_FILED_COPY")

                if folder_7_path:
                    found_ex4_file_path = find_files_recursively(
                        handler, 
                        folder_7_path, 
                        ex4_patterns_norm, 
                        stop_on_first_match=True, 
                        local_dest_folder=local_ex4_folder
                    )
                    all_doc_paths['exhibit_4'] = found_ex4_file_path # Será un string o None
                    if not found_ex4_file_path:
                        print("⚠️ No se encontró ningún archivo de 'FILED COPY' en la carpeta 7.")
                        missing_files.append("Documento 'FILED COPY' (o similar en carpeta 7)")
                else:
                    print("⚠️ No se encontró la carpeta '7'.")
                    missing_files.append("Carpeta '7' (y su contenido 'FILED COPY')")
                    all_doc_paths['exhibit_4'] = None

                # --- POST-PROCESADO: Convertir imágenes ---
                # Convertimos todas las imágenes descargadas a PDF
                convert_images_to_pdf_recursively(local_temp_folder)

                # --- Corregir rutas (de .jpg a .pdf) ---
                final_doc_paths = fix_paths_after_conversion(all_doc_paths)

                # --- Ensamblaje de PDF ---
                print("\n--- Ensamblando PDF final ---")
                final_pdf_path, _ = create_final_merged_pdf(
                    safe_client_name, 
                    local_temp_folder, 
                    final_doc_paths, 
                    missing_files
                )

                if not final_pdf_path:
                    raise Exception("No se pudo crear el PDF final unido.")

                # 4.4 Subir todo a Google Drive
                print("\n--- Subiendo archivos a Google Drive ---")
                upload_folder_to_drive(drive_service, local_temp_folder, client_drive_folder_id)
                
                # 4.5 Obtener links y actualizar la hoja
                print("\n--- Actualizando Google Sheet ---")
                
                # Link de la CARPETA (Col E)
                drive_folder_link = get_drive_folder_link(drive_service, client_drive_folder_id)
                if not drive_folder_link:
                    drive_folder_link = "Error al obtener link de carpeta"
                
                # Lista de FALTANTES (Col F)
                missing_files_str = ", ".join(missing_files)
                if not missing_files_str:
                    missing_files_str = "Ninguno"
                
                # Link del PDF UNIDO (Col G)
                final_pdf_filename = os.path.basename(final_pdf_path)
                drive_pdf_link = get_drive_file_link(drive_service, final_pdf_filename, client_drive_folder_id)
                if not drive_pdf_link:
                    drive_pdf_link = "Error al obtener link de PDF"

                # Actualizar celdas E, F y G en un solo lote
                cell_range = f'E{current_row_number}:G{current_row_number}'
                cell_list = worksheet.range(cell_range)
                cell_list[0].value = drive_folder_link
                cell_list[1].value = missing_files_str
                cell_list[2].value = drive_pdf_link
                
                worksheet.update_cells(cell_list)
                
                print(f"✅ Celda '{cell_range}' actualizada.")
                print(f"✅ Proceso completo para la fila {current_row_number} y cliente '{safe_client_name}'.")
                        
            except Exception as e:
                # Captura cualquier otro error, registra el fallo y actualiza la hoja
                print(f"❌ Ocurrió un error inesperado al procesar la fila {current_row_number}: {e}")
                
                # Intentamos obtener los datos disponibles para el log
                nombre_log = row_data[1].strip() if len(row_data) > 1 else 'N/A'
                link_log = row_data[2].strip() if len(row_data) > 2 else 'N/A'
                log_fail([current_row_number, nombre_log, link_log], str(e))
                
                # Actualizar celdas E, F y G con el error
                try:
                    cell_range = f'E{current_row_number}:G{current_row_number}'
                    cell_list = worksheet.range(cell_range)
                    cell_list[0].value = drive_folder_link # Puede ser "ERROR" o el link de la carpeta si se creó
                    cell_list[1].value = ", ".join(missing_files) if missing_files else "ERROR"
                    cell_list[2].value = f"ERROR: {str(e)[:450]}" # Límite de celda
                    worksheet.update_cells(cell_list)
                except Exception as gspread_e:
                    print(f"FALLO AL ACTUALIZAR HOJA CON ERROR: {gspread_e}")
                
            finally:
                # Lógica de limpieza
                if local_temp_folder and os.path.exists(local_temp_folder):
                    try:
                        shutil.rmtree(local_temp_folder)
                        print(f"🗑️ Carpeta temporal eliminada: {local_temp_folder}")
                    except Exception as e:
                        print(f"⚠️ No se pudo eliminar la carpeta temporal '{local_temp_folder}': {e}")
                
                # Pausa para no saturar las APIs
                print("--- Pausando 2 segundos ---")
                time.sleep(2)
                        
    except ValueError as ve:
        print(f"Error de configuración: {ve}")
    except FileNotFoundError as fnfe:
        print(f"Error de archivo: {fnfe}")
    except Exception as e:
        # Este es el bloque de error del programa principal
        print(f"Ocurrió un error inesperado en el programa principal: {e}")