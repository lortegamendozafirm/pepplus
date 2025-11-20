# app/services/slot_resolver.py
"""
Resuelve slots basándose en su estrategia de búsqueda.
Conecta el manifest con las integraciones de Dropbox.
"""
import os
from typing import List, Optional
from app.services.slot_models import (
    Slot,
    SlotResult,
    SearchStrategyType,
    SearchMode
)
from app.integrations.dropbox_client import DropboxIntegrator
from app.utils.logger import logger


class SlotResolver:
    """
    Resuelve un slot ejecutando su estrategia de búsqueda.
    Descarga archivos desde Dropbox y retorna un SlotResult.
    """

    def __init__(self, dropbox_client: DropboxIntegrator, local_work_dir: str):
        """
        Args:
            dropbox_client: Cliente de Dropbox configurado
            local_work_dir: Directorio local donde descargar archivos
        """
        self.dbx = dropbox_client
        self.local_work_dir = local_work_dir

    def resolve_slot(self, slot: Slot, dropbox_base_path: str) -> SlotResult:
        """
        Resuelve un slot completo ejecutando su estrategia.

        Args:
            slot: Slot a resolver
            dropbox_base_path: Ruta base en Dropbox donde buscar

        Returns:
            SlotResult con archivos encontrados y estado
        """
        logger.info(f"🔍 Resolviendo Slot {slot.slot_id}: {slot.name}")

        strategy = slot.search_strategy

        try:
            # Ejecutar estrategia según tipo
            if strategy.type == SearchStrategyType.GENERATED:
                return self._resolve_generated(slot)

            elif strategy.type == SearchStrategyType.FOLDER_SEARCH:
                return self._resolve_folder_search(slot, dropbox_base_path)

            elif strategy.type == SearchStrategyType.RECURSIVE_DOWNLOAD:
                return self._resolve_recursive_download(slot, dropbox_base_path)

            elif strategy.type == SearchStrategyType.PRIORITIZED_SEARCH:
                return self._resolve_prioritized_search(slot, dropbox_base_path)

            else:
                return SlotResult(
                    slot_id=slot.slot_id,
                    name=slot.name,
                    status="missing",
                    error_message=f"Estrategia no soportada: {strategy.type}",
                    required=slot.required
                )

        except Exception as e:
            logger.error(f"❌ Error resolviendo slot {slot.slot_id}: {e}")
            return SlotResult(
                slot_id=slot.slot_id,
                name=slot.name,
                status="missing",
                error_message=str(e),
                required=slot.required
            )

    def _resolve_generated(self, slot: Slot) -> SlotResult:
        """
        Slot con contenido generado (placeholder).
        El contenido real se genera después en el orquestador.
        """
        logger.info(f"📝 Slot generado: {slot.name} (se generará después)")
        return SlotResult(
            slot_id=slot.slot_id,
            name=slot.name,
            status="success",
            files_found=[],  # Se llenará después
            required=slot.required
        )

    def _resolve_folder_search(self, slot: Slot, base_path: str) -> SlotResult:
        """
        Busca archivos en una carpeta específica usando keywords.
        """
        strategy = slot.search_strategy
        local_slot_dir = os.path.join(self.local_work_dir, f"slot_{slot.slot_id}")

        # 1. Buscar carpeta
        if not strategy.folder_keywords:
            return SlotResult(
                slot_id=slot.slot_id,
                name=slot.name,
                status="missing",
                error_message="No se especificaron folder_keywords",
                required=slot.required
            )

        folder_path = self.dbx.find_folder_fuzzy(base_path, strategy.folder_keywords)

        if not folder_path:
            logger.warning(f"⚠️ Carpeta no encontrada con keywords: {strategy.folder_keywords}")
            return SlotResult(
                slot_id=slot.slot_id,
                name=slot.name,
                status="missing",
                error_message=f"Carpeta no encontrada: {strategy.folder_keywords}",
                required=slot.required
            )

        # 2. Buscar archivos dentro de la carpeta
        if not strategy.file_keywords:
            strategy.file_keywords = [""]  # Wildcard

        stop_on_first = (strategy.mode == SearchMode.SINGLE)
        found_metas = self.dbx.find_files_recursive_fuzzy(
            folder_path,
            strategy.file_keywords,
            stop_on_first=stop_on_first
        )

        if not found_metas:
            logger.warning(f"⚠️ No se encontraron archivos en {folder_path}")
            return SlotResult(
                slot_id=slot.slot_id,
                name=slot.name,
                status="missing",
                error_message="No se encontraron archivos en la carpeta",
                required=slot.required
            )

        # 3. Descargar archivos encontrados
        local_files = []
        for meta in found_metas:
            local_path = self.dbx.download_file(meta.path_lower, local_slot_dir)
            if local_path:
                local_files.append(local_path)

        status = "success" if local_files else "missing"
        return SlotResult(
            slot_id=slot.slot_id,
            name=slot.name,
            files_found=local_files,
            status=status,
            required=slot.required
        )

    def _resolve_recursive_download(self, slot: Slot, base_path: str) -> SlotResult:
        """
        Descarga recursivamente todo el contenido de una carpeta.
        """
        strategy = slot.search_strategy
        local_slot_dir = os.path.join(self.local_work_dir, f"slot_{slot.slot_id}")

        # Navegar por la jerarquía de carpetas
        current_path = base_path
        if strategy.folder_path:
            for folder_name in strategy.folder_path:
                found_folder = self.dbx.find_folder_fuzzy(current_path, [folder_name])
                if not found_folder:
                    return SlotResult(
                        slot_id=slot.slot_id,
                        name=slot.name,
                        status="missing",
                        error_message=f"Carpeta '{folder_name}' no encontrada en ruta",
                        required=slot.required
                    )
                current_path = found_folder

        # Descargar todo recursivamente
        file_keywords = strategy.file_keywords or [""]
        all_metas = self.dbx.find_files_recursive_fuzzy(
            current_path,
            file_keywords,
            stop_on_first=False
        )

        if not all_metas:
            return SlotResult(
                slot_id=slot.slot_id,
                name=slot.name,
                status="missing",
                error_message="No se encontraron archivos en la carpeta",
                required=slot.required
            )

        local_files = []
        for meta in all_metas:
            local_path = self.dbx.download_file(meta.path_lower, local_slot_dir)
            if local_path:
                local_files.append(local_path)

        status = "success" if local_files else "missing"
        return SlotResult(
            slot_id=slot.slot_id,
            name=slot.name,
            files_found=local_files,
            status=status,
            required=slot.required
        )

    def _resolve_prioritized_search(self, slot: Slot, base_path: str) -> SlotResult:
        """
        Busca archivos con prioridad: intenta keywords en orden hasta encontrar uno.
        """
        strategy = slot.search_strategy
        local_slot_dir = os.path.join(self.local_work_dir, f"slot_{slot.slot_id}")

        # 1. Buscar carpeta
        if not strategy.folder_keywords:
            return SlotResult(
                slot_id=slot.slot_id,
                name=slot.name,
                status="missing",
                error_message="No se especificaron folder_keywords",
                required=slot.required
            )

        folder_path = self.dbx.find_folder_fuzzy(base_path, strategy.folder_keywords)

        if not folder_path:
            return SlotResult(
                slot_id=slot.slot_id,
                name=slot.name,
                status="missing",
                error_message=f"Carpeta no encontrada: {strategy.folder_keywords}",
                required=slot.required
            )

        # 2. Buscar archivo con prioridad
        priority_keywords = strategy.file_keywords_priority or strategy.file_keywords or []

        for keyword in priority_keywords:
            found_metas = self.dbx.find_files_recursive_fuzzy(
                folder_path,
                [keyword],
                stop_on_first=True
            )

            if found_metas:
                # Descargar el primero encontrado
                local_path = self.dbx.download_file(found_metas[0].path_lower, local_slot_dir)
                if local_path:
                    logger.info(f"✅ Archivo encontrado con prioridad: {keyword}")
                    return SlotResult(
                        slot_id=slot.slot_id,
                        name=slot.name,
                        files_found=[local_path],
                        status="success",
                        required=slot.required
                    )

        # No se encontró nada con ningún keyword
        return SlotResult(
            slot_id=slot.slot_id,
            name=slot.name,
            status="missing",
            error_message="No se encontró archivo con ninguna prioridad",
            required=slot.required
        )
