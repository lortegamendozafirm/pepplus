# app/api/routes.py
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import (
    PacketRequest,
    PacketResponse,
    OcrExtractRequest,
    OcrExtractResponse,
)
from app.config.settings import Settings
from app.domain.manifest import Manifest
from app.domain.packet import Packet, SheetOutputConfig, SheetPosition
from app.domain.slot import Slot, SlotMeta
from app.integrations.dropbox_client import DropboxClient
from app.integrations.enqueuer_client import EnqueuerClient
from app.integrations.sheets_client import SheetsClient
from app.logger import get_logger
from app.services.packet_service import PacketService
from app.services.ocr_extract_service import OcrExtractService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/packets", tags=["packets"])


def get_packet_service() -> PacketService:
    """Dependency injection para PacketService con todas las integraciones."""
    settings = Settings()

    # Inicializar enqueuer client si está configurado
    enqueuer_client = None
    if settings.enqueuer_service_url:
        enqueuer_client = EnqueuerClient(service_url=settings.enqueuer_service_url)

    return PacketService(
        dropbox_client=DropboxClient(),
        sheets_client=SheetsClient(credentials_path=settings.google_credentials_path),
        enqueuer_client=enqueuer_client,
        temp_dir=settings.temp_dir,
    )


@router.post("/enqueue", response_model=PacketResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_packet(
    request: PacketRequest,
    service: PacketService = Depends(get_packet_service),
) -> PacketResponse:
    """
    Encola un paquete de PDFs para procesamiento asíncrono.

    Retorna inmediatamente con un job_id que puede usarse para consultar el estado.
    El procesamiento real se delega al servicio enqueuer.
    """
    try:
        logger.info("Received enqueue request client=%s", request.client_name)
        packet = build_domain_packet(request)
        job_id = service.enqueue_packet(packet)

        return PacketResponse(
            status="enqueued",
            message=f"Job enqueued successfully for client {packet.client_name}",
            job_id=job_id
        )

    except ValueError as e:
        logger.error("Validation error in enqueue request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error("Unexpected error enqueuing packet: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while enqueuing packet"
        )


@router.post("/process", response_model=PacketResponse)
async def process_packet(
    request: PacketRequest,
    service: PacketService = Depends(get_packet_service),
) -> PacketResponse:
    """
    Procesa un paquete de PDFs de forma síncrona.

    Este endpoint es llamado típicamente por el servicio enqueuer.
    Para uso directo desde Apps Script, usar /enqueue en su lugar.

    NOTA: Este endpoint puede tardar varios minutos en responder.
    """
    try:
        logger.info("Received process request client=%s", request.client_name)
        packet = build_domain_packet(request)
        result = service.process_packet(packet)

        # Verificar si hubo errores
        if result.get("status") == "error":
            return PacketResponse(
                status="error",
                message=result.get("message", "Processing failed"),
                job_id=None
            )

        # Éxito
        output_path = result.get("output_path")
        mask = result.get("mask", "")
        missing = result.get("missing_required", [])

        message = f"Processed packet for {packet.client_name}. Output: {output_path}"
        if missing:
            message += f" (missing required slots: {missing})"

        return PacketResponse(
            status="completed",
            message=message,
            job_id=None
        )

    except ValueError as e:
        logger.error("Validation error in process request: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except FileNotFoundError as e:
        logger.error("File not found during processing: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Required file not found: {str(e)}"
        )
    except Exception as e:
        logger.error("Unexpected error processing packet: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while processing packet"
        )


@router.post("/ocr-extract", response_model=OcrExtractResponse)
async def ocr_extract_pages(
    request: OcrExtractRequest,
) -> OcrExtractResponse:
    """
    Extrae páginas de un PDF basándose en un patrón de texto detectado mediante OCR.

    Este endpoint:
    1. Aplica OCR al PDF de entrada página por página
    2. Identifica qué páginas contienen el patrón especificado (texto literal o regex)
    3. Crea un nuevo PDF con solo las páginas que coinciden
    4. Guarda el archivo en la misma carpeta con sufijo configurable

    Ejemplo de uso:
    - Input: /tmp/client/vawa_packet.pdf
    - Pattern: "rap sheet" (o regex: "rap.*sheet")
    - Output: /tmp/client/vawa_packet_rapsheet.pdf

    NOTA: Este endpoint puede tardar varios minutos dependiendo del tamaño
    del PDF y la calidad/DPI configurada para el OCR.
    """
    try:
        logger.info(
            "Received OCR extract request: input=%s, pattern='%s', use_regex=%s",
            request.input_pdf_path,
            request.pattern,
            request.use_regex,
        )

        # Crear servicio OCR con configuración del request
        ocr_service = OcrExtractService(
            ocr_dpi=request.ocr_dpi,
            ocr_lang=request.ocr_lang,
        )

        # Ejecutar extracción
        result = ocr_service.extract_pages_by_pattern(
            input_pdf_path=request.input_pdf_path,
            pattern=request.pattern,
            use_regex=request.use_regex,
            suffix=request.suffix,
            case_sensitive=request.case_sensitive,
        )

        # Convertir resultado a response schema
        response = OcrExtractResponse(
            ok=result.ok,
            message=result.message,
            input_pdf_path=result.input_pdf_path,
            output_pdf_path=result.output_pdf_path,
            matched_pages=result.matched_pages,
        )

        # Si hubo error, devolver HTTP 400 o 500
        if not result.ok:
            # Determinar código de error apropiado
            if "not found" in result.message.lower():
                status_code = status.HTTP_404_NOT_FOUND
            elif "validation" in result.message.lower() or "invalid" in result.message.lower():
                status_code = status.HTTP_400_BAD_REQUEST
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            logger.error("OCR extraction failed: %s", result.message)
            raise HTTPException(status_code=status_code, detail=result.message)

        logger.info(
            "OCR extraction completed successfully: matched_pages=%d, output=%s",
            len(result.matched_pages),
            result.output_pdf_path,
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in OCR extract endpoint: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during OCR extraction: {str(e)}",
        )


def build_domain_packet(api_request: PacketRequest) -> Packet:
    """
    Convierte un PacketRequest (API schema) a un Packet (domain model).

    Raises:
        ValueError: Si hay errores de validación en los datos
    """
    try:
        # Validar que el manifest no esté vacío
        if not api_request.manifest:
            raise ValueError("Manifest cannot be empty")

        # Construir slots del manifest
        manifest_slots = []
        seen_slot_numbers = set()

        for slot in api_request.manifest:
            # Validar slots duplicados
            if slot.slot in seen_slot_numbers:
                raise ValueError(f"Duplicate slot number: {slot.slot}")
            seen_slot_numbers.add(slot.slot)

            meta = SlotMeta(
                folder_hint=slot.folder_hint,
                file_hint=getattr(slot, "file_hint", None),  # ⬅️ NUEVO
                filename_patterns=slot.filename_patterns,
                tags=slot.tags,
                allow_docx=slot.allow_docx,
            )

            manifest_slots.append(
                Slot(
                    slot=slot.slot,
                    name=slot.name,
                    required=slot.required,
                    meta=meta,
                )
            )

        manifest = Manifest(manifest_slots)

        # Construir sheet output config
        sheet_output_config = None
        if api_request.sheet_output_config:
            sheet_output_config = SheetOutputConfig(
                spreadsheet_id=api_request.sheet_output_config.spreadsheet_id,
                sheet_name=api_request.sheet_output_config.sheet_name,
            )

        sheet_position = SheetPosition(
            row=api_request.sheet_position.row,
            col_output=api_request.sheet_position.col_output,
            col_status=api_request.sheet_position.col_status,
        )

        return Packet(
            client_name=api_request.client_name,
            dropbox_url=api_request.dropbox_url,
            manifest=manifest,
            sheet_output_config=sheet_output_config,
            sheet_position=sheet_position,
        )

    except ValueError:
        raise
    except Exception as e:
        logger.error("Error building domain packet: %s", e)
        raise ValueError(f"Failed to build packet: {str(e)}")
