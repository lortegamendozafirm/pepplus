# app/services/slot_models.py
"""
Modelos de datos para la arquitectura de slots.
Define las estructuras para manifests, slots y estrategias de búsqueda.
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


class SearchStrategyType(str, Enum):
    """Tipos de estrategias de búsqueda soportadas."""
    FOLDER_SEARCH = "folder_search"  # Buscar en carpeta específica
    RECURSIVE_DOWNLOAD = "recursive_download"  # Descargar todo recursivamente
    PRIORITIZED_SEARCH = "prioritized_search"  # Buscar con prioridad
    GENERATED = "generated"  # Contenido generado (ej: reportes)


class SearchMode(str, Enum):
    """Modo de búsqueda de archivos."""
    SINGLE = "single"  # Detener en el primer archivo encontrado
    MULTIPLE = "multiple"  # Encontrar todos los archivos que coincidan


class SearchStrategy(BaseModel):
    """
    Define cómo buscar y resolver archivos para un slot.
    """
    type: SearchStrategyType = Field(..., description="Tipo de estrategia de búsqueda")

    # Configuración para búsquedas en carpetas
    folder_keywords: Optional[List[str]] = Field(None, description="Keywords para encontrar la carpeta")
    folder_path: Optional[List[str]] = Field(None, description="Ruta jerárquica de carpetas")

    # Configuración para búsquedas de archivos
    file_keywords: Optional[List[str]] = Field(None, description="Keywords para encontrar archivos")
    file_keywords_priority: Optional[List[str]] = Field(None, description="Keywords priorizadas")

    # Modo de búsqueda
    mode: SearchMode = Field(SearchMode.MULTIPLE, description="Modo de búsqueda")

    # Para contenido generado
    generator: Optional[str] = Field(None, description="Nombre del generador a usar")

    # Metadatos adicionales
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos adicionales")


class Slot(BaseModel):
    """
    Representa un slot en el manifest.
    Un slot es una posición en el documento final que puede contener uno o más archivos.
    """
    slot_id: int = Field(..., description="ID único del slot (define el orden)")
    name: str = Field(..., description="Nombre descriptivo del slot")
    required: bool = Field(True, description="Si es obligatorio que el slot contenga archivos")
    search_strategy: SearchStrategy = Field(..., description="Estrategia para resolver este slot")

    # Metadata opcional
    description: Optional[str] = Field(None, description="Descripción detallada del slot")
    cover_page: bool = Field(True, description="Si debe incluir una página de portada")
    cover_title: Optional[str] = Field(None, description="Título personalizado para la portada (usa 'name' si None)")


class SlotResult(BaseModel):
    """
    Resultado de resolver un slot.
    Contiene los archivos encontrados y su estado.
    """
    slot_id: int
    name: str
    files_found: List[str] = Field(default_factory=list, description="Rutas locales de archivos encontrados")
    status: Literal["success", "partial", "missing"] = Field(..., description="Estado de resolución")
    error_message: Optional[str] = Field(None, description="Mensaje de error si falló")
    required: bool

    @property
    def is_complete(self) -> bool:
        """Retorna True si el slot se resolvió satisfactoriamente."""
        return self.status == "success" or (not self.required and self.status == "missing")

    @property
    def has_files(self) -> bool:
        """Retorna True si se encontraron archivos."""
        return len(self.files_found) > 0


class PacketManifest(BaseModel):
    """
    Manifest completo que define la estructura del paquete.
    """
    name: str = Field(..., description="Nombre del manifest")
    version: str = Field("1.0.0", description="Versión del manifest")
    description: Optional[str] = Field(None, description="Descripción del propósito del manifest")
    slots: List[Slot] = Field(..., description="Lista de slots ordenados")

    def get_slot_by_id(self, slot_id: int) -> Optional[Slot]:
        """Obtiene un slot por su ID."""
        for slot in self.slots:
            if slot.slot_id == slot_id:
                return slot
        return None

    def get_ordered_slots(self) -> List[Slot]:
        """Retorna los slots ordenados por slot_id."""
        return sorted(self.slots, key=lambda s: s.slot_id)


class AssemblyReport(BaseModel):
    """
    Reporte final del proceso de ensamblado.
    """
    success: bool
    total_slots: int
    completed_slots: int
    missing_required_slots: List[str] = Field(default_factory=list)
    slot_results: List[SlotResult] = Field(default_factory=list)
    final_pdf_path: Optional[str] = None
    error_message: Optional[str] = None

    def get_missing_items(self) -> List[str]:
        """Retorna lista de items faltantes para reporte."""
        missing = []
        for result in self.slot_results:
            if result.required and not result.has_files:
                missing.append(f"{result.name} (required)")
            elif result.status == "partial":
                missing.append(f"{result.name} (incomplete)")
        return missing
