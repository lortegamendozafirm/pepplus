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
    folder_hint: Optional[str] = Field(None, description="Pista de carpeta para resolver el archivo.")
    filename_patterns: List[str] = Field(default_factory=list, description="Posibles patrones de archivo.")
    tags: List[str] = Field(default_factory=list, description="Etiquetas libres.")


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
