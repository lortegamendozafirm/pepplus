# app/api/schemas.py
from typing import List, Optional

from pydantic import BaseModel, Field


class GoogleSheetOutput(BaseModel):
    spreadsheet_id: str = Field(..., description="ID de la Google Sheet donde se escribirá el resultado.")
    sheet_name: Optional[str] = Field(None, description="Nombre de la pestaña; opcional si hay un default.")


class SheetPosition(BaseModel):
    row: int = Field(..., description="Número de fila a editar en la Sheet.")
    col_output: int = Field(..., description="Número de columna donde se escribirá la URL del PDF final.")
    col_status: int = Field(..., description="Número de columna donde se escribirá el status / porcentaje.")


class ManifestSlot(BaseModel):
    slot: int = Field(..., description="Posición entera en el PDF final.")
    name: str = Field(..., description="Nombre lógico del slot.")
    required: bool = Field(True, description="Indica si el slot es obligatorio.")

    # NUEVO: hint para carpeta y archivo
    folder_hint: Optional[str] = Field(
        None,
        description="Pista de carpeta para resolver el archivo (ej: 'uscis receipts notices', 'vawa').",
    )
    file_hint: Optional[str] = Field(
        None,
        description="Pista de nombre de archivo dentro de la carpeta (ej: 'prima facie renewed', 'pcl carolina').",
    )

    # Legacy / opcional
    filename_patterns: List[str] = Field(
        default_factory=list,
        description="Posibles patrones de archivo (wildcards/regex) para compatibilidad.",
    )
    tags: List[str] = Field(default_factory=list, description="Etiquetas libres.")
    allow_docx: bool = Field(
        False,
        description="Si es True, también se permiten archivos .docx para este slot."
    )


class PacketRequest(BaseModel):
    client_name: str = Field(..., description="Nombre completo del cliente.")
    dropbox_url: str = Field(..., description="URL compartida de la carpeta raíz en Dropbox.")
    sheet_output_config: Optional[GoogleSheetOutput] = Field(
        None, description="Configuración de la Google Sheet donde se escribirá el resultado."
    )
    sheet_position: SheetPosition = Field(..., description="Coordenadas a editar en la Sheet.")
    manifest: List[ManifestSlot] = Field(..., description="Lista ordenada de slots a ensamblar.")


class PacketResponse(BaseModel):
    status: str
    message: str
    job_id: Optional[str] = None


# ========================================
# OCR Extract Endpoint Schemas
# ========================================


class OcrExtractRequest(BaseModel):
    """
    Request schema para el endpoint de extracción OCR.
    """
    input_pdf_path: str = Field(
        ...,
        description="Ruta absoluta o relativa del PDF ya descargado en el servidor.",
    )
    pattern: str = Field(
        ...,
        description="Texto o expresión regular a buscar en las páginas del PDF.",
        min_length=1,
    )
    use_regex: bool = Field(
        default=False,
        description="Si es True, 'pattern' se interpreta como expresión regular; si es False, búsqueda literal.",
    )
    suffix: str = Field(
        default="pattern",
        description="Sufijo para el archivo de salida (ej: 'rapsheet' -> archivo_rapsheet.pdf).",
    )
    case_sensitive: bool = Field(
        default=False,
        description="Si es True, la búsqueda es sensible a mayúsculas/minúsculas.",
    )
    ocr_dpi: int = Field(
        default=300,
        description="Resolución DPI para conversión PDF a imagen (mayor calidad = más lento).",
        ge=100,
        le=600,
    )
    ocr_lang: str = Field(
        default="eng",
        description="Código de lenguaje para Tesseract OCR (ej: 'eng', 'spa', 'fra').",
    )


class OcrExtractResponse(BaseModel):
    """
    Response schema para el endpoint de extracción OCR.
    """
    ok: bool = Field(
        ...,
        description="True si la operación fue exitosa, False en caso de error.",
    )
    message: str = Field(
        ...,
        description="Mensaje descriptivo del resultado de la operación.",
    )
    input_pdf_path: str = Field(
        ...,
        description="Ruta del PDF de entrada procesado.",
    )
    output_pdf_path: Optional[str] = Field(
        default=None,
        description="Ruta del PDF generado con las páginas filtradas (null si no hubo coincidencias).",
    )
    matched_pages: List[int] = Field(
        default_factory=list,
        description="Lista de números de página (1-indexed) que coincidieron con el patrón.",
    )
