# app/domain/slot_resolution.py
from __future__ import annotations

import os
import re
import fnmatch
from dataclasses import dataclass
from typing import Iterable, List, Optional

from app.domain.slot import Slot
from app.logger import get_logger

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
    1. Si el slot tiene folder_hint, filtra archivos cuyo path contenga ese texto
       (substring, case-insensitive).
    2. Si el slot tiene file_hint, filtra por nombre de archivo (basename) usando
       matching "fuzzy" por palabras.
    3. Si el slot tiene filename_patterns, filtra por nombre de archivo
       (basename) usando wildcards / regex / literal.
    4. Siempre se queda sólo con PDFs (.pdf).
    5. Si hay múltiples candidatos, toma el primero (y loggea warning).
    6. Si no hay candidatos, marca el slot como missing con razón descriptiva.
    """

    def __init__(self, prefer_first_match: bool = True) -> None:
        """
        Args:
            prefer_first_match: Si hay múltiples candidatos, tomar el primero.
        """
        self.prefer_first_match = prefer_first_match

    def resolve(self, manifest: Iterable[Slot], files_index: Iterable[str]) -> List[SlotResolution]:
        """
        Resuelve cada slot del manifest contra un índice de archivos.

        Args:
            manifest: Iterable de slots a resolver.
            files_index: Iterable de rutas de archivos disponibles (paths de Dropbox).

        Returns:
            Lista de SlotResolution con el resultado de cada slot.
        """
        slots = list(manifest)
        files = list(files_index)

        logger.info("Resolving %d slots against %d files", len(slots), len(files))

        resolutions: List[SlotResolution] = []
        for slot in slots:
            resolution = self._resolve_single_slot(slot, files)
            resolutions.append(resolution)

            if resolution.missing:
                logger.warning(
                    "Slot %d (%s) MISSING: %s",
                    slot.slot,
                    slot.name,
                    resolution.reason or "No candidate found",
                )
            else:
                logger.debug(
                    "Slot %d (%s) resolved to: %s",
                    slot.slot,
                    slot.name,
                    resolution.candidate_path,
                )

        return resolutions

    # ------------------------
    # Lógica principal por slot
    # ------------------------
    def _resolve_single_slot(self, slot: Slot, files: List[str]) -> SlotResolution:
        """
        Resuelve un slot individual contra la lista de archivos.

        Lógica de resolución:
        1. Filtrar por folder_hint (si existe).
        2. Filtrar por file_hint (si existe).
        3. Filtrar por filename_patterns (si existe).
        4. Filtrar a sólo PDFs (.pdf).
        5. Seleccionar candidato o marcar como missing.
        """
        candidates = files

        folder_hint = getattr(slot.meta, "folder_hint", None)
        file_hint = getattr(slot.meta, "file_hint", None)
        patterns = getattr(slot.meta, "filename_patterns", []) or []
        allow_docx = getattr(slot.meta, "allow_docx", False)

        # Paso 1: Filtrar por folder_hint (substring en el path, case-insensitive)
        if folder_hint:
            candidates = [
                f for f in candidates
                if self._matches_folder_hint(f, folder_hint)
            ]
            logger.debug(
                "Slot %d (%s) - After folder_hint '%s': %d candidates",
                slot.slot,
                slot.name,
                folder_hint,
                len(candidates),
            )

        # Paso 2: Filtrar por file_hint (sobre basename, fuzzy por palabras)
        if file_hint:
            candidates = [
                f for f in candidates
                if self._matches_file_hint(os.path.basename(f), file_hint)
            ]
            logger.debug(
                "Slot %d (%s) - After file_hint '%s': %d candidates",
                slot.slot,
                slot.name,
                file_hint,
                len(candidates),
            )

        # Paso 3: Filtrar por filename_patterns (sobre basename)
        if patterns:
            candidates = [
                f for f in candidates
                if self._matches_any_pattern(os.path.basename(f), patterns)
            ]
            logger.debug(
                "Slot %d (%s) - After filename_patterns %s: %d candidates",
                slot.slot,
                slot.name,
                patterns,
                len(candidates),
            )

        # Paso 4: Filtrar por extensión (pdf y opcionalmente docx)
        if allow_docx:
            candidates = [
                f for f in candidates
                if f.lower().endswith(".pdf") or f.lower().endswith(".docx")
            ]
        else:
            candidates = [f for f in candidates if f.lower().endswith(".pdf")]

        logger.debug(
            "Slot %d (%s) - After extension filter (allow_docx=%s): %d candidates",
            slot.slot,
            slot.name,
            allow_docx,
            len(candidates),
        )


        # Paso 5: Selección
        if not candidates:
            return SlotResolution(
                slot=slot,
                candidate_path=None,
                missing=True,
                reason=self._generate_missing_reason(slot),
            )

        if len(candidates) > 1:
            logger.warning(
                "Multiple candidates for slot %d (%s): %d files. Taking first.",
                slot.slot,
                slot.name,
                len(candidates),
            )

        selected_path = candidates[0] if self.prefer_first_match else candidates[0]

        return SlotResolution(
            slot=slot,
            candidate_path=selected_path,
            missing=False,
            reason=None,
        )

    # ------------------------
    # Helpers de matching
    # ------------------------
    def _normalize(self, text: str) -> str:
        """
        Normaliza texto para matching "fuzzy":
        - minúsculas
        - reemplaza '_' y '-' por espacio
        - colapsa espacios múltiples
        """
        t = text.lower()
        t = t.replace("_", " ").replace("-", " ")
        t = re.sub(r"\s+", " ", t)
        return t.strip()

    def _matches_folder_hint(self, file_path: str, folder_hint: str) -> bool:
        """
        Verifica si el path del archivo contiene el folder_hint (substring).

        Normaliza:
        - minúsculas
        - separadores / y \
        """
        normalized_path = file_path.replace("\\", "/").lower()
        normalized_hint = folder_hint.replace("\\", "/").lower()
        return normalized_hint in normalized_path

    def _matches_file_hint(self, file_name: str, file_hint: str) -> bool:
        """
        Verifica si el nombre del archivo coincide de forma "fuzzy" con el file_hint.

        Regla: todas las palabras del hint deben estar presentes en el nombre normalizado.
        Ejemplos:
            file_name = "Carolina Alvarez Garcia I-360 Prima Facie Renewed (06-25-2025).pdf"
            file_hint = "prima facie renewed"
            -> True

            file_name = "FBI RESULTS- CAROLINA ALVAREZ GARCIA.pdf"
            file_hint = "fbi results carolina"
            -> True
        """
        name_norm = self._normalize(file_name)
        hint_norm = self._normalize(file_hint)

        words = [w for w in hint_norm.split(" ") if w]
        return all(w in name_norm for w in words)

    def _matches_any_pattern(self, file_name: str, patterns: List[str]) -> bool:
        """
        Verifica si el nombre del archivo coincide con algún pattern.

        `file_name` debe ser sólo el basename (ej: "vawa filed copy - alberto.pdf")

        Soporta:
        - Wildcards (fnmatch): "*prima facie*.pdf", "id alberto*.pdf"
        - Regex: "regex:.*prima facie.*\\.pdf"
        - Literales: "petition.pdf" (se trata como subcadena case-insensitive)
        """
        name = file_name.lower()

        for pattern in patterns:
            if not pattern:
                continue

            # Mantener el patrón original para regex, pero hacer matching case-insensitive
            if pattern.lower().startswith("regex:"):
                regex = pattern[6:]  # conservar tal cual después de "regex:"
                try:
                    if re.search(regex, name, flags=re.IGNORECASE):
                        return True
                except re.error as e:
                    logger.error("Invalid regex pattern '%s': %s", pattern, e)
                    continue
                continue

            pat = pattern.lower()

            # Wildcards: usar fnmatch
            if any(ch in pat for ch in ("*", "?")):
                if fnmatch.fnmatch(name, pat):
                    return True

            # Literal como "contiene"
            else:
                if pat in name:
                    return True

        return False

    def _generate_missing_reason(self, slot: Slot) -> str:
        """Genera un mensaje descriptivo de por qué no se encontró el slot."""
        parts: list[str] = []

        folder_hint = getattr(slot.meta, "folder_hint", None)
        file_hint = getattr(slot.meta, "file_hint", None)
        patterns = getattr(slot.meta, "filename_patterns", None)

        if folder_hint:
            parts.append(f"folder_hint='{folder_hint}'")
        if file_hint:
            parts.append(f"file_hint='{file_hint}'")
        if patterns:
            parts.append(f"patterns={patterns}")

        if not parts:
            return "No matching file found (pdf/docx)"

        return f"No PDF matching criteria: {', '.join(parts)}"
