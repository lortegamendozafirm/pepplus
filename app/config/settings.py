# app/config/settigs.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 🔧 Configuración del modelo / settings (sustituye a class Config)
    model_config = SettingsConfigDict(
        env_prefix="PACKET_",
        env_file=".env",            # lee automáticamente tu .env en la raíz
        env_file_encoding="utf-8",
        extra="forbid",             # opcional: no permite claves extra
    )

    app_name: str = Field(
        default="pdf-packet-service",
        description="Service name for FastAPI.",
    )

    # Dropbox integration
    dropbox_token_service_url: str | None = Field(
        default=None,
        description="Endpoint to fetch a short-lived Dropbox token.",
    )
    dropbox_service_signature: str = Field(
        default="930xY0dJ0pD",
        description="Signature for Dropbox token service authentication.",
    )

    # Google Sheets integration
    google_credentials_path: str | None = Field(
        default=None,
        description="Path to Google Service Account JSON credentials file.",
    )

    # GCP configuration
    gcp_project_id: str | None = Field(
        default=None,
        description="Optional GCP project id for telemetry.",
    )

    # Storage
    temp_dir: str = Field(
        default="/tmp",
        description="Directory to store temporary downloads and merges.",
    )

    # Enqueuer integration (for future use)
    enqueuer_service_url: str | None = Field(
        default=None,
        description="URL of the enqueuer service for long-running jobs.",
    )
    tesseract_cmd: str | None = Field(
        default=r"C:\Program Files\Tesseract-OCR\tessdata",
        description="ubicación de la paqueteria"
    )
    poppler_path: str | None = Field(
        default=r"C:\poppler\Library\bin",
        description="ruta a bin para usar poppler"
    )

settings = Settings()

if __name__ == "__main__":
    
    print(settings.app_name)
    print(settings.dropbox_service_signature)
    print(settings.dropbox_token_service_url)
    print(settings.gcp_project_id)
    print(settings.google_credentials_path)
    print(settings.model_config)
    print(settings.temp_dir)
    print(settings.enqueuer_service_url)
