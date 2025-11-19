# app/services/orchestrator.py
import os
import uuid
from typing import List
from app.schemas.request_models import PacketRequest, PacketResponse
from app.integrations.dropbox_client import DropboxIntegrator
from app.integrations.google_client import GoogleIntegrator
from app.integrations.token_client import TokenServiceClient # <-- Cliente de Tokens
from app.services.pdf_engine import PDFEngine
from app.utils.helpers import clean_temp_folder
from app.utils.logger import logger
from app.config import settings

class PacketOrchestrator:
    def __init__(self):
        self.pdf_engine = PDFEngine()
        self.base_temp_dir = settings.TEMP_DIR
        self.token_provider = TokenServiceClient() # Inicializamos el proveedor de tokens

    async def process_request(self, request: PacketRequest) -> PacketResponse:
        # Identificador único para trazar esta ejecución en los logs
        run_id = str(uuid.uuid4())[:8]
        safe_client_name = request.client_name.replace(" ", "_")
        local_work_dir = os.path.join(self.base_temp_dir, f"{safe_client_name}_{run_id}")
        
        logger.info(f"🚀 [RUN ID: {run_id}] Iniciando proceso para: {request.client_name}")
        
        # Listas para organizar archivos
        ex1_files = []
        ex3_files = []
        ex4_files = []
        missing_files = []
        
        try:
            # --- PASO 0: GESTIÓN DE TOKEN ---
            # Si el request no trae token, lo pedimos al microservicio externo
            current_token = request.dropbox_token
            if not current_token:
                logger.info("🔄 Token no proporcionado. Solicitando a AccessTokenDropbox...")
                current_token = self.token_provider.get_valid_token()
            else:
                logger.info("ℹ️ Usando token manual proporcionado en la petición.")

            # Inicializar clientes con el token válido
            dbx = DropboxIntegrator(current_token)
            google = GoogleIntegrator()

            # --- PASO 1: RESOLUCIÓN Y VALIDACIÓN ---
            dropbox_path = dbx.get_path_from_link(request.dropbox_url)
            if not dropbox_path:
                logger.error(f"Link inválido: {request.dropbox_url}")
                return PacketResponse(status="error", message="Link de Dropbox inválido o no es una carpeta.")

            # Validar estructura crítica (Regla de Negocio)
            is_valid, structure_missing = dbx.validate_vawa_structure(dropbox_path)
            
            if not is_valid:
                msg = f"Validación fallida. Faltan carpetas: {', '.join(structure_missing)}"
                logger.warning(msg)
                
                # Reportar error en Sheet si corresponde y terminar
                if request.sheet_output_config:
                    google.update_sheet(
                        request.sheet_output_config.spreadsheet_id,
                        request.sheet_output_config.worksheet_name,
                        {request.sheet_output_config.missing_files_cell: msg}
                    )
                return PacketResponse(status="error", message=msg, missing_files=structure_missing)

            # Preparar carpetas locales
            os.makedirs(local_work_dir, exist_ok=True)

            # --- PASO 2: DESCARGA DE EVIDENCIAS (Lógica Completa) ---
            logger.info("⬇️ Iniciando descargas de evidencias...")

            # A. Exhibit 1: USCIS / Receipts
            # -----------------------------------------------------------
            uscis_path = dbx.find_folder_fuzzy(dropbox_path, ['USCIS', 'Receipts', 'UCIS'])
            local_ex1_dir = os.path.join(local_work_dir, "EX1")
            
            if uscis_path:
                # Buscamos archivos clave
                keywords_ex1 = ['Prima', 'Transfer', 'I-360', 'I-485', 'Receipt']
                found_metas = dbx.find_files_recursive_fuzzy(uscis_path, keywords_ex1)
                
                if not found_metas:
                    missing_files.append("Documentos en carpeta USCIS")
                
                for meta in found_metas:
                    path = dbx.download_file(meta.path_lower, local_ex1_dir)
                    if path: ex1_files.append(path)
            else:
                # Esto teóricamente no pasa si validamos estructura, pero por seguridad:
                missing_files.append("Carpeta USCIS")

            # B. Exhibit 3: VAWA -> Evidence (Descarga masiva)
            # -----------------------------------------------------------
            vawa_path = dbx.find_folder_fuzzy(dropbox_path, ['VAWA'])
            local_ex3_dir = os.path.join(local_work_dir, "EX3")
            
            if vawa_path:
                evidence_path = dbx.find_folder_fuzzy(vawa_path, ['Evidence'])
                if evidence_path:
                    # [''] significa "trae todo lo que encuentres"
                    all_evidence_metas = dbx.find_files_recursive_fuzzy(evidence_path, [''], stop_on_first=False)
                    
                    if not all_evidence_metas:
                        missing_files.append("Archivos dentro de Evidence")
                    
                    for meta in all_evidence_metas:
                        path = dbx.download_file(meta.path_lower, local_ex3_dir)
                        if path: ex3_files.append(path)
                else:
                    missing_files.append("Subcarpeta Evidence")
            
            # C. Exhibit 4: Filed Copy (Carpeta 7)
            # -----------------------------------------------------------
            folder7_path = dbx.find_folder_fuzzy(dropbox_path, ['7', 'Folder7'])
            local_ex4_dir = os.path.join(local_work_dir, "EX4")
            
            if folder7_path:
                # Prioridad: Filed Copy > Ready to Print > Signed
                keywords_ex4 = ['Filed Copy', 'FILED_COPY', 'FC', 'Ready to print', 'Signed']
                # stop_on_first=True porque solo queremos UN archivo maestro
                found_metas = dbx.find_files_recursive_fuzzy(folder7_path, keywords_ex4, stop_on_first=True)
                
                if found_metas:
                    path = dbx.download_file(found_metas[0].path_lower, local_ex4_dir)
                    if path: ex4_files.append(path)
                else:
                    missing_files.append("Documento Filed Copy (o Ready to Print)")

            # --- PASO 3: PROCESAMIENTO Y ENSAMBLAJE ---
            logger.info("⚙️ Procesando archivos y convirtiendo imágenes...")
            
            # 1. Convertir imágenes descargadas a PDF
            self.pdf_engine.convert_images_to_pdf_recursive(local_work_dir)
            
            # 2. Re-escanear carpetas locales para actualizar rutas (ahora .pdf)
            # (Esto es implícito porque ex1_files ya tiene las rutas, pero si convertimos in-situ, 
            #  la extensión cambia. Un pequeño ajuste de rutas es necesario).
            ex1_files = [p.replace(os.path.splitext(p)[1], ".pdf") if p.lower().endswith(('.jpg','.png','.jpeg')) else p for p in ex1_files]
            ex3_files = [p.replace(os.path.splitext(p)[1], ".pdf") if p.lower().endswith(('.jpg','.png','.jpeg')) else p for p in ex3_files]
            ex4_files = [p.replace(os.path.splitext(p)[1], ".pdf") if p.lower().endswith(('.jpg','.png','.jpeg')) else p for p in ex4_files]

            # 3. Generar reporte de faltantes
            missing_report_path = os.path.join(local_work_dir, "missing_report.pdf")
            self.pdf_engine.create_missing_report(missing_report_path, missing_files)

            # 4. Definir estructura del paquete
            packet_structure = [
                (f"1. EXHIBIT – {request.client_name}", ex1_files),
                ("2. EXHIBIT – INFORMACIÓN FALTANTE", [missing_report_path]),
                ("3. EXHIBIT – EVIDENCE", ex3_files),
                ("4. EXHIBIT – FILED COPY", ex4_files)
            ]

            # 5. Merge final
            final_pdf_name = f"PAQUETE_ENSAMBLADO_{safe_client_name}.pdf"
            final_pdf_path = os.path.join(local_work_dir, final_pdf_name)
            
            logger.info(f"📚 Uniendo PDF final en: {final_pdf_path}")
            self.pdf_engine.merge_packets(final_pdf_path, packet_structure)
            
            # --- PASO 4: SUBIDA Y ENTREGA ---
            logger.info("☁️ Subiendo resultados a Google Drive...")
            
            client_drive_folder_id = google.create_folder(safe_client_name, request.drive_parent_folder_id)
            
            _, pdf_link = google.upload_file(final_pdf_path, client_drive_folder_id, mime_type='application/pdf')
            folder_link = "https://drive.google.com/drive/folders/" + client_drive_folder_id

            # Actualizar Sheet si se requiere
            if request.sheet_output_config:
                logger.info("📝 Actualizando Google Sheet con resultados exitosos...")
                google.update_sheet(
                    request.sheet_output_config.spreadsheet_id,
                    request.sheet_output_config.worksheet_name,
                    {
                        request.sheet_output_config.folder_link_cell: folder_link,
                        request.sheet_output_config.missing_files_cell: ", ".join(missing_files) if missing_files else "Ninguno",
                        request.sheet_output_config.pdf_link_cell: pdf_link
                    }
                )

            logger.info("✅ Proceso finalizado con éxito.")
            return PacketResponse(
                status="success",
                message="Paquete generado correctamente.",
                drive_folder_link=folder_link,
                final_pdf_link=pdf_link,
                missing_files=missing_files
            )

        except Exception as e:
            logger.critical(f"🔥 Error crítico no controlado en orquestador: {e}", exc_info=True)
            return PacketResponse(status="error", message=str(e))
        
        finally:
            # Siempre limpiar temporales
            clean_temp_folder(local_work_dir)