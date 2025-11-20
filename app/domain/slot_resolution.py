from dataclasses import dataclass
from typing import Iterable, List, Optional
import re

from domain.slot import Slot
from logger import get_logger

logger = get_logger(__name__)


@dataclass
class SlotResolution:
    slot: Slot
    candidate_path: Optional[str]
    missing: bool
    reason: Optional[str] = None


class SlotResolver:
    """
    Aplica heurísticas de carpeta/patrones para mapear un manifest a un árbol de archivos.

    Estrategia de resolución:
    1. Si el slot tiene folder_hint, buscar archivos dentro de carpetas que coincidan
    2. Si el slot tiene filename_patterns, filtrar por nombre de archivo
    3. Si hay múltiples candidatos, tomar el primero (o usar lógica de prioridad)
    4. Marcar como missing si no se encuentra ningún candidato
    """

    def __init__(self, prefer_first_match: bool = True):
        """
        Args:
            prefer_first_match: Si hay múltiples candidatos, tomar el primero
        """
        self.prefer_first_match = prefer_first_match

    def resolve(self, manifest: Iterable[Slot], files_index: Iterable[str]) -> List[SlotResolution]:
        """
        Resuelve cada slot del manifest contra un índice de archivos.

        Args:
            manifest: Lista de slots a resolver
            files_index: Lista de rutas de archivos disponibles (ej: paths de Dropbox)

        Returns:
            Lista de SlotResolution con el resultado de cada slot
        """
        slots = list(manifest)
        files = list(files_index)

        logger.info("Resolving %d slots against %d files", len(slots), len(files))

        resolutions = []
        for slot in slots:
            resolution = self._resolve_single_slot(slot, files)
            resolutions.append(resolution)

            if resolution.missing:
                logger.warning(
                    "Slot %d (%s) MISSING: %s",
                    slot.slot,
                    slot.name,
                    resolution.reason or "No candidate found"
                )
            else:
                logger.debug(
                    "Slot %d (%s) resolved to: %s",
                    slot.slot,
                    slot.name,
                    resolution.candidate_path
                )

        return resolutions

    def _resolve_single_slot(self, slot: Slot, files: List[str]) -> SlotResolution:
        """
        Resuelve un slot individual contra la lista de archivos.

        Lógica de resolución:
        1. Filtrar por folder_hint si existe
        2. Filtrar por filename_patterns si existe
        3. Filtrar por extensión .pdf
        4. Seleccionar primer candidato o marcar como missing
        """
        candidates = files

        # Paso 1: Filtrar por folder_hint
        if slot.meta.folder_hint:
            folder_hint = slot.meta.folder_hint.lower()
            candidates = [
                f for f in candidates
                if self._matches_folder_hint(f, folder_hint)
            ]
            logger.debug("After folder_hint filter (%s): %d candidates", folder_hint, len(candidates))

        # Paso 2: Filtrar por filename_patterns
        if slot.meta.filename_patterns:
            candidates = [
                f for f in candidates
                if self._matches_any_pattern(f, slot.meta.filename_patterns)
            ]
            logger.debug("After filename_patterns filter: %d candidates", len(candidates))

        # Paso 3: Solo PDFs
        candidates = [f for f in candidates if f.lower().endswith('.pdf')]
        logger.debug("After .pdf filter: %d candidates", len(candidates))

        # Paso 4: Seleccionar candidato
        if not candidates:
            return SlotResolution(
                slot=slot,
                candidate_path=None,
                missing=True,
                reason=self._generate_missing_reason(slot)
            )

        # Si hay múltiples candidatos, log warning y tomar el primero
        if len(candidates) > 1:
            logger.warning(
                "Multiple candidates for slot %d (%s): %d files. Taking first.",
                slot.slot,
                slot.name,
                len(candidates)
            )

        selected_path = candidates[0] if self.prefer_first_match else candidates[0]

        return SlotResolution(
            slot=slot,
            candidate_path=selected_path,
            missing=False,
            reason=None
        )

    def _matches_folder_hint(self, file_path: str, folder_hint: str) -> bool:
        """
        Verifica si el path del archivo contiene el folder_hint.

        Ejemplos:
            file_path = "/EXHIBIT 1/archivo.pdf"
            folder_hint = "exhibit 1"
            -> True

            file_path = "/EXHIBIT 2/ABUSE/doc.pdf"
            folder_hint = "exhibit 2"
            -> True
        """
        file_path_lower = file_path.lower()
        folder_hint_lower = folder_hint.lower()

        # Normalizar separadores
        file_path_normalized = file_path_lower.replace('\\', '/')

        # Buscar el folder_hint en cualquier parte del path
        return folder_hint_lower in file_path_normalized

    def _matches_any_pattern(self, file_path: str, patterns: List[str]) -> bool:
        """
        Verifica si el nombre del archivo coincide con algún pattern.

        Patterns pueden ser:
        - Strings literales: "petition.pdf"
        - Wildcards simples: "petition*.pdf"
        - Regex si empieza con "regex:"

        Ejemplos:
            patterns = ["petition.pdf", "petition*.pdf"]
            file_path = "/folder/petition_v2.pdf"
            -> True (match con "petition*.pdf")
        """
        file_name = file_path.split('/')[-1].split('\\')[-1]  # Obtener solo el nombre
        file_name_lower = file_name.lower()

        for pattern in patterns:
            pattern_lower = pattern.lower()

            # Regex pattern
            if pattern_lower.startswith("regex:"):
                regex = pattern_lower[6:]
                if re.search(regex, file_name_lower):
                    return True

            # Wildcard pattern (convertir a regex simple)
            elif '*' in pattern_lower or '?' in pattern_lower:
                regex_pattern = pattern_lower.replace('.', r'\\.').replace('*', '.*').replace('?', '.')
                if re.match(f"^{regex_pattern}$", file_name_lower):
                    return True

            # Literal match
            elif pattern_lower in file_name_lower:
                return True

        return False

    def _generate_missing_reason(self, slot: Slot) -> str:
        """Genera un mensaje descriptivo de por qué no se encontró el slot."""
        reasons = []

        if slot.meta.folder_hint:
            reasons.append(f"folder_hint='{slot.meta.folder_hint}'")

        if slot.meta.filename_patterns:
            reasons.append(f"patterns={slot.meta.filename_patterns}")

        if not reasons:
            return "No matching PDF found"

        return f"No PDF matching criteria: {', '.join(reasons)}"
