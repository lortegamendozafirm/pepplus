# app/utils/logger.py
import logging
import sys
from app.config import settings

# Formato del log: Tiempo - Nivel - Mensaje
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

def setup_logger():
    """Configura el logger principal de la aplicación."""
    # 1. Crear el logger
    logger = logging.getLogger("vawa_service")
    
    # 2. Configurar el nivel (DEBUG, INFO, WARNING, ERROR)
    # Lo tomamos de la configuración global
    level = logging.INFO
    if settings.LOG_LEVEL.upper() == "DEBUG":
        level = logging.DEBUG
        
    logger.setLevel(level)

    # 3. Configurar el Handler (Salida a consola/stdout para que Cloud Run lo lea)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)
    
    # Evitar duplicados si se llama varias veces
    if not logger.handlers:
        logger.addHandler(handler)
        
    return logger

# Instancia global lista para importar en otros archivos
logger = setup_logger()