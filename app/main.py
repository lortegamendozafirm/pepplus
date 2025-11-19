from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import packet
from app.config import settings
from app.utils.logger import logger

# --- DEFINICIÓN DEL CICLO DE VIDA (LIFESPAN) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Maneja el ciclo de vida de la aplicación.
    Todo lo que está ANTES del yield se ejecuta al iniciar (Startup).
    Todo lo que está DESPUÉS del yield se ejecuta al apagar (Shutdown).
    """
    # 1. Lógica de Inicio (Startup)
    logger.info(f"🚀 Iniciando {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"📂 Directorio temporal configurado en: {settings.TEMP_DIR}")
    
    yield  # <-- Aquí la aplicación se queda "corriendo" y recibiendo peticiones
    
    # 2. Lógica de Apagado (Shutdown)
    logger.info("🛑 Apagando servicio...")

def create_app() -> FastAPI:
    """Fábrica de la aplicación FastAPI."""
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        description="Microservicio para ensamblaje automatizado de expedientes VAWA.",
        lifespan=lifespan  # <-- AQUÍ SE VINCULA EL NUEVO MANEJADOR
    )

    # --- Configuración de CORS ---
    origins = [
        "*", 
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Incluir Rutas (Routers) ---
    app.include_router(packet.router, prefix="/api/v1", tags=["Packet Processing"])

    # --- Root Endpoint (Health Check) ---
    @app.get("/", tags=["Health"])
    def read_root():
        return {
            "status": "active", 
            "service": settings.APP_NAME, 
            "version": settings.VERSION
        }

    return app

app = create_app()

# Para ejecutar en local: uvicorn app.main:app --reload