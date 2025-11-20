from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional
from uuid import uuid4

from domain.manifest import Manifest
from domain.packet import Packet
from domain.slot_resolution import SlotResolution, SlotResolver
from integrations.dropbox_client import DropboxClient
from integrations.enqueuer_client import EnqueuerClient
from integrations.sheets_client import SheetsClient
from logger import get_logger
from pdf.pdf_assembler import merge_pdfs_in_order
from services.progress_reporter import ProgressReporter

logger = get_logger(__name__)


class PacketService:
    """
    Coordina la resolución de manifest, descargas, ensamblado y reporte de progreso.
    """

    def __init__(
        self,
        dropbox_client: Optional[DropboxClient] = None,
        sheets_client: Optional[SheetsClient] = None,
        slot_resolver: Optional[SlotResolver] = None,
        enqueuer_client: Optional[EnqueuerClient] = None,
        temp_dir: str = "/tmp",
    ) -> None:
        self.dropbox_client = dropbox_client
        self.sheets_client = sheets_client
        self.slot_resolver = slot_resolver or SlotResolver()
        self.enqueuer_client = enqueuer_client
        self.temp_dir = Path(temp_dir)
        self.progress = ProgressReporter(sheets_client) if sheets_client else None

    def enqueue_packet(self, packet: Packet) -> str:
        """
        Encola un paquete para procesamiento asíncrono a través del servicio enqueuer.

        Returns:
            job_id del trabajo encolado
        """
        if not self.enqueuer_client:
            # Fallback: generar job_id local sin encolar
            job_id = f"job-{uuid4()}"
            logger.warning(
                "EnqueuerClient not available, generated local job_id=%s (not actually enqueued)",
                job_id
            )
            return job_id

        # Serializar packet a dict para enviar al enqueuer
        packet_payload = self._serialize_packet(packet)

        job_id = self.enqueuer_client.enqueue_job(
            service_name="pdf-packet-service",
            endpoint="/api/v1/packets/process",
            payload=packet_payload,
            priority="normal"
        )

        if job_id:
            logger.info("Successfully enqueued packet job_id=%s client=%s", job_id, packet.client_name)
        else:
            # Fallback en caso de error
            job_id = f"job-{uuid4()}"
            logger.error(
                "Failed to enqueue packet, generated fallback job_id=%s client=%s",
                job_id,
                packet.client_name
            )

        return job_id

    def _serialize_packet(self, packet: Packet) -> dict:
        """Serializa un Packet a dict para enviar al enqueuer."""
        return {
            "client_name": packet.client_name,
            "dropbox_url": packet.dropbox_url,
            "sheet_output_config": {
                "spreadsheet_id": packet.sheet_output_config.spreadsheet_id,
                "sheet_name": packet.sheet_output_config.sheet_name,
            } if packet.sheet_output_config else None,
            "sheet_position": {
                "row": packet.sheet_position.row,
                "col_output": packet.sheet_position.col_output,
                "col_status": packet.sheet_position.col_status,
            },
            "manifest": [
                {
                    "slot": slot.slot,
                    "name": slot.name,
                    "required": slot.required,
                    "folder_hint": slot.meta.folder_hint,
                    "filename_patterns": slot.meta.filename_patterns,
                    "tags": slot.meta.tags,
                }
                for slot in packet.manifest.slots
            ]
        }

    def process_packet(self, packet: Packet) -> dict:
        """
        Procesa un paquete completo: resuelve slots, descarga archivos, ensambla PDF.

        Returns:
            dict con status, output_path, mask, missing_required
        """
        logger.info("Starting packet processing client=%s", packet.client_name)

        # Reportar progreso: inicio
        if self.progress and packet.sheet_output_config:
            self.progress.report(packet.sheet_output_config, packet.sheet_position, "10% - Resolviendo archivos")

        # Paso 1: Resolver slots
        folder_path = self._get_dropbox_folder_path(packet.dropbox_url)
        if not folder_path:
            return {"status": "error", "message": "Failed to resolve Dropbox shared link"}

        files_index = self._build_files_index(folder_path)
        resolved = self._resolve_slots(packet.manifest, files_index)

        # Verificar slots requeridos faltantes
        missing_required = [
            res.slot.slot for res in resolved
            if res.missing and res.slot.required
        ]

        if missing_required:
            logger.error("Missing required slots: %s", missing_required)
            if self.progress and packet.sheet_output_config:
                self.progress.report(
                    packet.sheet_output_config,
                    packet.sheet_position,
                    f"ERROR - Faltan slots requeridos: {missing_required}"
                )
            return {
                "status": "error",
                "message": f"Missing required slots: {missing_required}",
                "missing_required": missing_required,
            }

        # Reportar progreso: descargando
        if self.progress and packet.sheet_output_config:
            self.progress.report(packet.sheet_output_config, packet.sheet_position, "40% - Descargando archivos")

        # Paso 2: Descargar archivos resueltos
        downloaded_paths = self._download_resolved(resolved, packet.client_name)

        # Reportar progreso: ensamblando
        if self.progress and packet.sheet_output_config:
            self.progress.report(packet.sheet_output_config, packet.sheet_position, "70% - Ensamblando PDF")

        # Paso 3: Ensamblar PDF
        output_path = self._merge(downloaded_paths, packet.client_name)

        # Reportar progreso: completado
        if self.progress and packet.sheet_output_config:
            self.progress.report(packet.sheet_output_config, packet.sheet_position, "100% - Completado")
            # Escribir URL del PDF final (TODO: subir a GCS/Drive primero)
            if output_path and self.sheets_client:
                self.sheets_client.write_output_url(
                    packet.sheet_output_config,
                    packet.sheet_position,
                    str(output_path)  # TODO: reemplazar con URL pública
                )

        logger.info(
            "Finished packet processing client=%s output=%s files=%d",
            packet.client_name,
            output_path,
            len(downloaded_paths),
        )

        resolved_slot_numbers = [res.slot.slot for res in resolved if not res.missing]
        presence_mask = packet.manifest.presence_mask(resolved_slot_numbers)

        return {
            "status": "ok",
            "output_path": str(output_path) if output_path else None,
            "mask": presence_mask,
            "missing_required": missing_required,
        }

    def _get_dropbox_folder_path(self, shared_url: str) -> Optional[str]:
        """Resuelve la URL compartida de Dropbox a su path interno."""
        if not self.dropbox_client:
            logger.error("DropboxClient not available")
            return None

        folder_path = self.dropbox_client.resolve_shared_link(shared_url)
        if not folder_path:
            logger.error("Failed to resolve Dropbox shared link: %s", shared_url)
            return None

        logger.info("Resolved Dropbox shared link to: %s", folder_path)
        return folder_path

    def _build_files_index(self, folder_path: str) -> list[str]:
        """Construye un índice de todos los archivos en la carpeta (recursivo)."""
        if not self.dropbox_client:
            logger.error("DropboxClient not available")
            return []

        logger.info("Building files index for: %s", folder_path)
        entries = self.dropbox_client.list_folder(folder_path, recursive=True)

        # Filtrar solo archivos (no carpetas) y obtener sus paths
        file_paths = []
        for entry in entries:
            # dropbox entries tienen .path_lower y un atributo para distinguir tipo
            if hasattr(entry, 'path_lower') and not isinstance(entry, type(entry).__bases__[0]):
                # Es un archivo (FileMetadata)
                file_paths.append(entry.path_lower)

        logger.info("Files index built: %d files", len(file_paths))
        return file_paths

    def _resolve_slots(self, manifest: Manifest, files_index: list[str]) -> list[SlotResolution]:
        """Resuelve los slots del manifest contra el índice de archivos."""
        logger.info("Resolving slots count=%d against %d files", len(manifest.slots), len(files_index))
        return self.slot_resolver.resolve(manifest.slots, files_index)

    def _download_resolved(
        self, resolutions: Iterable[SlotResolution], client_name: str
    ) -> list[tuple[int, str]]:
        """
        Descarga los archivos resueltos a disco local.

        Returns:
            Lista de tuplas (slot_number, local_path)
        """
        if not self.dropbox_client:
            logger.error("DropboxClient not available")
            return []

        # Crear carpeta temporal para este cliente
        client_folder = self.temp_dir / client_name.replace(' ', '_')
        client_folder.mkdir(parents=True, exist_ok=True)

        downloaded = []
        for resolution in resolutions:
            if resolution.missing or not resolution.candidate_path:
                logger.debug("Skipping missing slot %d", resolution.slot.slot)
                continue

            local_path = self.dropbox_client.download_file(
                resolution.candidate_path,
                str(client_folder)
            )

            if local_path:
                downloaded.append((resolution.slot.slot, local_path))
                logger.info("Downloaded slot %d: %s", resolution.slot.slot, local_path)
            else:
                logger.error("Failed to download slot %d from %s", resolution.slot.slot, resolution.candidate_path)

        logger.info("Downloaded %d/%d files", len(downloaded), len(list(resolutions)))
        return downloaded

    def _merge(self, downloaded: list[tuple[int, str]], client_name: str) -> Optional[Path]:
        """
        Ensambla los PDFs descargados en orden de slot.

        Args:
            downloaded: Lista de (slot_number, local_path)
            client_name: Nombre del cliente (para nombre de archivo)

        Returns:
            Path del PDF final ensamblado
        """
        if not downloaded:
            logger.warning("No files to merge, skipping PDF assembly")
            return None

        # Ordenar por slot number
        sorted_files = sorted(downloaded, key=lambda x: x[0])
        local_paths = [path for _, path in sorted_files]

        # Nombre del archivo de salida
        safe_client_name = client_name.replace(' ', '_').replace('/', '_')
        output_path = self.temp_dir / f"packet_{safe_client_name}.pdf"

        logger.info("Merging %d PDFs into %s", len(local_paths), output_path)
        merge_pdfs_in_order(local_paths, str(output_path))
        logger.info("Merged PDF written to %s", output_path)

        return output_path
