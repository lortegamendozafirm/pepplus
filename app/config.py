import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- Información General ---
    APP_NAME: str = "VAWA Packet Assembler Service"
    VERSION: str = "1.1.0" # Bump de versión
    LOG_LEVEL: str = "INFO"

    # --- Google Credentials ---
    GOOGLE_CREDENTIALS_FILE: str = "credentials.json"
    
    # --- Directorios ---
    TEMP_DIR: str = "/tmp/vawa_processing"

    # --- NUEVO: Integración con AccessTokenDropbox ---
    TOKEN_SERVICE_URL: str
    TOKEN_SERVICE_SIGNATURE: str
    TOKEN_SERVICE_CLIENT_NAME: str = "vawa_assembler"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore" # Ignora variables extra en el .env si las hay

settings = Settings()
os.makedirs(settings.TEMP_DIR, exist_ok=True)