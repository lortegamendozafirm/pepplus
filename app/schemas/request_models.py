# app/schemas/request_models.py
from pydantic import BaseModel, Field
from typing import Optional, List

class GoogleSheetOutput(BaseModel):
    spreadsheet_id: str = Field(..., description="ID de la hoja de cálculo")
    worksheet_name: str = Field(..., description="Nombre de la pestaña")
    folder_link_cell: str = Field(..., description="Celda para poner el link de la carpeta")
    missing_files_cell: str = Field(..., description="Celda para poner los faltantes")
    pdf_link_cell: str = Field(..., description="Celda para poner el link del PDF final")

class PacketRequest(BaseModel):
    client_name: str = Field(..., description="Nombre completo del cliente")
    dropbox_url: str = Field(..., description="URL compartida de la carpeta raíz en Dropbox")
    dropbox_token: Optional[str] = Field(None, description="Opcional. Si no se envía, el servicio lo buscará automáticamente.")
    
    sheet_output_config: Optional[GoogleSheetOutput] = None
    drive_parent_folder_id: str = Field(..., description="ID de la carpeta en Google Drive destino")

class PacketResponse(BaseModel):
    status: str
    message: str
    drive_folder_link: Optional[str] = None
    final_pdf_link: Optional[str] = None
    missing_files: List[str] = []