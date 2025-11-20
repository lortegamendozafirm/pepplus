# app/services/slot_orchestrator.py
"""
Orquestador basado en slots para ensamblado de paquetes.
Reemplaza la lógica ad-hoc por un sistema configurable basado en manifests.
"""
import os
import uuid
import shutil
from typing import Optional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER

from app.schemas.request_models import PacketRequest, PacketResponse
from app.services.slot_models import PacketManifest, SlotResult, AssemblyReport
from app.services.slot_resolver import SlotResolver
from app.services.pdf_assembler import PDFAssembler
from app.services.vawa_default_manifest import get_vawa_default_manifest
from app.integrations.dropbox_client import DropboxIntegrator
from app.integrations.google_client import GoogleIntegrator
from app.integrations.token_client import TokenServiceClient
from app.services.pdf_engine import PDFEngine
from app.utils.logger import logger
from app.config import settings


class SlotBasedOrchestrator:
    """
    Orquestador que ensambla paquetes usando un sistema de slots configurable.

    Flujo:
    1. Cargar manifest (o usar el default)
    2. Para cada slot: resolver archivos usando SlotResolver
    3. Convertir imágenes a PDF
    4. Generar contenido para slots "generated"
    5. Ensamblar PDF final con portadas
    6. Subir a Drive y reportar
    """

    def __init__(self, manifest: Optional[PacketManifest] = None):
        """
        Args:
            manifest: Manifest personalizado. Si es None, usa el default de VAWA
        """
        self.manifest = manifest or get_vawa_default_manifest()
        self.pdf_assembler = PDFAssembler()
        self.pdf_engine = PDFEngine()  # Para conversión de imágenes (reusamos)
        self.token_provider = TokenServiceClient()
        self.base_temp_dir = settings.TEMP_DIR

    async def process_request(self, request: PacketRequest) -> PacketResponse:
        """
        Procesa una solicitud de ensamblado usando el sistema de slots.

        Args:
            request: Solicitud con datos del cliente y configuración

        Returns:
            PacketResponse con resultado del proceso
        """
        run_id = str(uuid.uuid4())[:8]
        safe_client_name = request.client_name.replace(" ", "_")
        local_work_dir = os.path.join(self.base_temp_dir, f"{safe_client_name}_{run_id}")

        logger.info(f"🚀 [RUN ID: {run_id}] Iniciando proceso SLOT-BASED para: {request.client_name}")
        logger.info(f"📋 Usando manifest: {self.manifest.name} v{self.manifest.version}")

        try:
            # --- PASO 0: GESTIÓN DE TOKEN ---
            current_token = request.dropbox_token
            if not current_token:
                logger.info("🔄 Token no proporcionado. Solicitando a AccessTokenDropbox...")
                current_token = self.token_provider.get_valid_token()

            # Inicializar clientes
            dbx = DropboxIntegrator(current_token)
            google = GoogleIntegrator()

            # --- PASO 1: RESOLUCIÓN DE DROPBOX PATH ---
            dropbox_path = dbx.get_path_from_link(request.dropbox_url)
            if not dropbox_path:
                return PacketResponse(
                    status="error",
                    message="Link de Dropbox inválido o inaccesible"
                )

            # Preparar directorio de trabajo
            os.makedirs(local_work_dir, exist_ok=True)

            # --- PASO 2: RESOLVER SLOTS ---
            logger.info("🔍 Iniciando resolución de slots...")
            resolver = SlotResolver(dbx, local_work_dir)
            slot_results = []

            for slot in self.manifest.get_ordered_slots():
                result = resolver.resolve_slot(slot, dropbox_path)
                slot_results.append(result)

                if result.has_files:
                    logger.info(f"✅ Slot {slot.slot_id} resuelto: {len(result.files_found)} archivo(s)")
                elif result.required:
                    logger.warning(f"⚠️ Slot REQUERIDO {slot.slot_id} faltante: {result.error_message}")
                else:
                    logger.info(f"ℹ️ Slot opcional {slot.slot_id} vacío")

            # --- PASO 3: CONVERTIR IMÁGENES A PDF ---
            logger.info("🖼️ Convirtiendo imágenes a PDF...")
            self.pdf_engine.convert_images_to_pdf_recursive(local_work_dir)

            # Actualizar rutas de archivos después de conversión
            for result in slot_results:
                result.files_found = self._fix_image_paths(result.files_found)

            # --- PASO 4: GENERAR CONTENIDO PARA SLOTS "GENERATED" ---
            missing_items = self._collect_missing_items(slot_results)
            self._generate_missing_report(slot_results, local_work_dir, missing_items)

            # --- PASO 5: ENSAMBLAR PDF FINAL ---
            logger.info("📚 Ensamblando PDF final con sistema de slots...")
            final_pdf_name = f"PAQUETE_ENSAMBLADO_{safe_client_name}.pdf"
            final_pdf_path = os.path.join(local_work_dir, final_pdf_name)

            assembly_success = self._assemble_final_pdf(
                slot_results,
                final_pdf_path,
                local_work_dir,
                request.client_name
            )

            if not assembly_success:
                return PacketResponse(
                    status="error",
                    message="Error al ensamblar el PDF final"
                )

            # --- PASO 6: SUBIR A DRIVE ---
            logger.info("☁️ Subiendo resultados a Google Drive...")
            client_drive_folder_id = google.create_folder(safe_client_name, request.drive_parent_folder_id)
            _, pdf_link = google.upload_file(final_pdf_path, client_drive_folder_id, mime_type='application/pdf')
            folder_link = f"https://drive.google.com/drive/folders/{client_drive_folder_id}"

            # --- PASO 7: ACTUALIZAR SHEET ---
            if request.sheet_output_config:
                logger.info("📝 Actualizando Google Sheet...")
                google.update_sheet(
                    request.sheet_output_config.spreadsheet_id,
                    request.sheet_output_config.worksheet_name,
                    {
                        request.sheet_output_config.folder_link_cell: folder_link,
                        request.sheet_output_config.missing_files_cell: ", ".join(missing_items) if missing_items else "Ninguno",
                        request.sheet_output_config.pdf_link_cell: pdf_link
                    }
                )

            # --- PASO 8: GENERAR REPORTE ---
            report = self._create_assembly_report(slot_results, final_pdf_path)

            logger.info(f"✅ Proceso completado. Slots exitosos: {report.completed_slots}/{report.total_slots}")

            return PacketResponse(
                status="success",
                message="Paquete generado correctamente usando sistema de slots",
                drive_folder_link=folder_link,
                final_pdf_link=pdf_link,
                missing_files=missing_items
            )

        except Exception as e:
            logger.critical(f"🔥 Error crítico en SlotBasedOrchestrator: {e}", exc_info=True)
            return PacketResponse(status="error", message=str(e))

        finally:
            # Limpiar archivos temporales
            self._cleanup(local_work_dir)

    def _fix_image_paths(self, file_paths: list) -> list:
        """Corrige rutas de imágenes convertidas a PDF."""
        img_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif')
        fixed = []
        for path in file_paths:
            if any(path.lower().endswith(ext) for ext in img_exts):
                pdf_path = os.path.splitext(path)[0] + ".pdf"
                fixed.append(pdf_path)
            else:
                fixed.append(path)
        return fixed

    def _collect_missing_items(self, slot_results: list) -> list:
        """Recopila items faltantes de todos los slots."""
        missing = []
        for result in slot_results:
            if result.required and not result.has_files:
                missing.append(f"{result.name} (required)")
            elif result.status == "partial":
                missing.append(f"{result.name} (incomplete)")
        return missing

    def _generate_missing_report(self, slot_results: list, work_dir: str, missing_items: list):
        """Genera el reporte de faltantes para slots tipo 'generated'."""
        for result in slot_results:
            slot = self.manifest.get_slot_by_id(result.slot_id)
            if slot and slot.search_strategy.generator == "missing_report":
                report_path = os.path.join(work_dir, f"slot_{result.slot_id}_missing_report.pdf")
                self._create_missing_report_pdf(report_path, missing_items)
                result.files_found = [report_path]
                result.status = "success"
                logger.info(f"📄 Reporte de faltantes generado para slot {result.slot_id}")

    def _create_missing_report_pdf(self, file_path: str, missing_items: list):
        """Crea el PDF del reporte de faltantes."""
        try:
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()

            title_style = styles['Heading1']
            title_style.alignment = TA_CENTER
            story.append(Paragraph("REPORTE DE DOCUMENTOS FALTANTES", title_style))
            story.append(Paragraph("<br/><br/>", styles['Normal']))

            if not missing_items:
                story.append(Paragraph("✅ No se detectaron documentos faltantes.", styles['Normal']))
            else:
                story.append(Paragraph("El sistema no pudo localizar los siguientes documentos:", styles['Normal']))
                story.append(Paragraph("<br/>", styles['Normal']))
                for item in missing_items:
                    story.append(Paragraph(f"• {item}", styles['Bullet']))

            doc.build(story)
        except Exception as e:
            logger.error(f"❌ Error creando reporte de faltantes: {e}")

    def _assemble_final_pdf(self, slot_results: list, output_path: str, work_dir: str, client_name: str) -> bool:
        """Ensambla el PDF final con todas las portadas y documentos."""
        try:
            all_pdfs_in_order = []
            covers_dir = os.path.join(work_dir, "covers")
            os.makedirs(covers_dir, exist_ok=True)

            for result in slot_results:
                slot = self.manifest.get_slot_by_id(result.slot_id)

                # Crear portada si está configurada
                if slot and slot.cover_page:
                    cover_title = slot.cover_title or slot.name
                    # Si es el primer slot, incluir nombre del cliente
                    if result.slot_id == 1:
                        cover_title = f"{cover_title} – {client_name}"

                    cover_path = os.path.join(covers_dir, f"cover_{result.slot_id}.pdf")
                    self.pdf_assembler.create_cover_page(cover_path, cover_title)
                    all_pdfs_in_order.append(cover_path)

                # Añadir archivos del slot
                for file_path in result.files_found:
                    if os.path.exists(file_path):
                        all_pdfs_in_order.append(file_path)

            # Unir todo
            self.pdf_assembler.merge_pdfs_in_order(all_pdfs_in_order, output_path)

            # Limpiar portadas temporales
            shutil.rmtree(covers_dir, ignore_errors=True)

            return True

        except Exception as e:
            logger.error(f"❌ Error ensamblando PDF final: {e}")
            return False

    def _create_assembly_report(self, slot_results: list, final_pdf_path: str) -> AssemblyReport:
        """Crea un reporte de ensamblado."""
        completed = sum(1 for r in slot_results if r.has_files)
        missing_required = [r.name for r in slot_results if r.required and not r.has_files]

        return AssemblyReport(
            success=(len(missing_required) == 0),
            total_slots=len(slot_results),
            completed_slots=completed,
            missing_required_slots=missing_required,
            slot_results=slot_results,
            final_pdf_path=final_pdf_path
        )

    def _cleanup(self, work_dir: str):
        """Limpia archivos temporales."""
        try:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
                logger.info(f"🗑️ Archivos temporales eliminados: {work_dir}")
        except Exception as e:
            logger.warning(f"⚠️ No se pudieron eliminar temporales: {e}")
