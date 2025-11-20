# app/api/v1/packet.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.schemas.request_models import PacketRequest, PacketResponse
from app.services.orchestrator import PacketOrchestrator
from app.services.slot_orchestrator import SlotBasedOrchestrator  # NUEVO
from app.utils.logger import logger

router = APIRouter()


@router.post("/generate-packet", response_model=PacketResponse)
async def generate_packet_endpoint(request: PacketRequest, use_legacy: bool = False):
    """
    Endpoint principal para generar paquetes VAWA.

    Args:
        request: Datos del paquete a generar
        use_legacy: Si True, usa el orquestador legacy (default: False = usa slot-based)

    Returns:
        PacketResponse con el resultado del proceso
    """
    # IMPORTANTE: Nunca loguear el token completo por seguridad
    masked_token = f"{request.dropbox_token[:5]}...{request.dropbox_token[-5:]}" if request.dropbox_token else "None"

    logger.info(f"🔵 [API] Solicitud recibida. Cliente: '{request.client_name}'. Token: {masked_token}")
    logger.info(f"🔧 [API] Modo: {'LEGACY' if use_legacy else 'SLOT-BASED (NEW)'}")

    # Seleccionar orquestador
    if use_legacy:
        orchestrator = PacketOrchestrator()
        logger.info("⚙️ Usando orquestador LEGACY (orchestrator.py)")
    else:
        orchestrator = SlotBasedOrchestrator()
        logger.info("⚙️ Usando orquestador SLOT-BASED (slot_orchestrator.py)")

    try:
        # Ejecución
        result = await orchestrator.process_request(request)

        if result.status == "success":
            logger.info(f"🟢 [API] Respuesta exitosa para '{request.client_name}'")
        else:
            logger.warning(f"🟠 [API] Respuesta con errores para '{request.client_name}': {result.message}")

        return result

    except Exception as e:
        logger.critical(f"🔴 [API] Error interno del servidor (500): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor al procesar el paquete.")