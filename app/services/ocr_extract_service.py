# app/services/ocr_extract_service.py
"""
Servicio de orquestación para extracción de páginas basada en OCR.
Coordina: OCR → Filtrado por patrón → Extracción de páginas → Generación de PDF.
"""
import re
from pathlib import Path
from typing import List, Optional

from app.logger import get_logger
from app.pdf.ocr_engine import OcrEngine, create_ocr_engine
from app.pdf.page_extractor import extract_pages_to_new_pdf, generate_output_path

logger = get_logger(__name__)


class OcrExtractResult:
    """
    Resultado de la operación de extracción OCR.
    """

    def __init__(
        self,
        ok: bool,
        message: str,
        input_pdf_path: str,
        output_pdf_path: Optional[str] = None,
        matched_pages: Optional[List[int]] = None,
    ) -> None:
        self.ok = ok
        self.message = message
        self.input_pdf_path = input_pdf_path
        self.output_pdf_path = output_pdf_path
        self.matched_pages = matched_pages or []


class OcrExtractService:
    """
    Servicio que coordina la extracción de páginas de un PDF basándose en
    un patrón de texto detectado mediante OCR.
    """

    def __init__(
        self,
        ocr_engine: Optional[OcrEngine] = None,
        ocr_dpi: int = 300,
        ocr_lang: str = "eng",
        tesseract_cmd: Optional[str] = None,
    ) -> None:
        """
        Inicializa el servicio de extracción OCR.

        Args:
            ocr_engine: Instancia de OcrEngine (si no se provee, se crea una por defecto)
            ocr_dpi: DPI para conversión PDF->imagen (usado si no se provee ocr_engine)
            ocr_lang: Lenguaje para tesseract (usado si no se provee ocr_engine)
            tesseract_cmd: Ruta del ejecutable tesseract (usado si no se provee ocr_engine)
        """
        self.ocr_engine = ocr_engine or create_ocr_engine(
            dpi=ocr_dpi,
            lang=ocr_lang,
            tesseract_cmd=tesseract_cmd,
        )

    def extract_pages_by_pattern(
        self,
        input_pdf_path: str,
        pattern: str,
        use_regex: bool = False,
        suffix: str = "pattern",
        case_sensitive: bool = False,
    ) -> OcrExtractResult:
        """
        Ejecuta la extracción completa:
        1. Aplica OCR al PDF de entrada
        2. Detecta qué páginas contienen el patrón
        3. Extrae esas páginas a un nuevo PDF

        Args:
            input_pdf_path: Ruta del PDF de origen
            pattern: Texto o expresión regular a buscar
            use_regex: Si True, trata 'pattern' como regex; si False, búsqueda literal
            suffix: Sufijo para el archivo de salida (ej: "rapsheet" -> file_rapsheet.pdf)
            case_sensitive: Si True, la búsqueda es case-sensitive

        Returns:
            OcrExtractResult con información del resultado
        """
        logger.info(
            "Starting OCR extraction: input=%s, pattern='%s', use_regex=%s, suffix=%s",
            input_pdf_path,
            pattern,
            use_regex,
            suffix,
        )

        # Validar que el archivo existe
        input_file = Path(input_pdf_path)
        if not input_file.exists():
            error_msg = f"Input PDF not found: {input_pdf_path}"
            logger.error(error_msg)
            return OcrExtractResult(
                ok=False,
                message=error_msg,
                input_pdf_path=input_pdf_path,
            )

        try:
            # Paso 1: Extraer texto por página con OCR
            logger.info("Step 1: Running OCR on PDF")
            page_texts = self.ocr_engine.extract_text_by_page(input_pdf_path)

            if not page_texts:
                error_msg = "OCR extraction returned no pages"
                logger.error(error_msg)
                return OcrExtractResult(
                    ok=False,
                    message=error_msg,
                    input_pdf_path=input_pdf_path,
                )

            logger.info("OCR completed: %d pages processed", len(page_texts))

            # Paso 2: Filtrar páginas que coinciden con el patrón
            logger.info("Step 2: Filtering pages by pattern")
            matched_pages = self._filter_pages_by_pattern(
                page_texts=page_texts,
                pattern=pattern,
                use_regex=use_regex,
                case_sensitive=case_sensitive,
            )

            if not matched_pages:
                warning_msg = f"No pages matched pattern '{pattern}'"
                logger.warning(warning_msg)
                return OcrExtractResult(
                    ok=True,
                    message=warning_msg,
                    input_pdf_path=input_pdf_path,
                    matched_pages=[],
                )

            logger.info("Found %d matching pages: %s", len(matched_pages), matched_pages)

            # Paso 3: Generar ruta de salida
            output_pdf_path = generate_output_path(input_pdf_path, suffix)

            # Paso 4: Extraer páginas al nuevo PDF
            logger.info("Step 3: Extracting matched pages to new PDF")
            extract_pages_to_new_pdf(
                input_pdf_path=input_pdf_path,
                page_numbers=matched_pages,
                output_pdf_path=output_pdf_path,
            )

            success_msg = (
                f"Successfully extracted {len(matched_pages)} pages matching pattern '{pattern}'"
            )
            logger.info(success_msg)

            return OcrExtractResult(
                ok=True,
                message=success_msg,
                input_pdf_path=input_pdf_path,
                output_pdf_path=output_pdf_path,
                matched_pages=matched_pages,
            )

        except FileNotFoundError as e:
            error_msg = f"File not found: {str(e)}"
            logger.error(error_msg)
            return OcrExtractResult(
                ok=False,
                message=error_msg,
                input_pdf_path=input_pdf_path,
            )
        except ValueError as e:
            error_msg = f"Validation error: {str(e)}"
            logger.error(error_msg)
            return OcrExtractResult(
                ok=False,
                message=error_msg,
                input_pdf_path=input_pdf_path,
            )
        except Exception as e:
            error_msg = f"Unexpected error during OCR extraction: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return OcrExtractResult(
                ok=False,
                message=error_msg,
                input_pdf_path=input_pdf_path,
            )

    def _filter_pages_by_pattern(
        self,
        page_texts: dict[int, str],
        pattern: str,
        use_regex: bool,
        case_sensitive: bool,
    ) -> List[int]:
        """
        Filtra las páginas que contienen el patrón especificado.

        Args:
            page_texts: Dict con número de página y texto extraído
            pattern: Texto o regex a buscar
            use_regex: Si True, usa regex; si False, búsqueda literal
            case_sensitive: Si True, búsqueda sensible a mayúsculas

        Returns:
            Lista de números de página que coinciden (1-indexed, ordenados)
        """
        matched_pages: List[int] = []

        for page_num, text in page_texts.items():
            if self._text_matches_pattern(text, pattern, use_regex, case_sensitive):
                matched_pages.append(page_num)
                logger.debug("Page %d matched pattern", page_num)

        return sorted(matched_pages)

    def _text_matches_pattern(
        self,
        text: str,
        pattern: str,
        use_regex: bool,
        case_sensitive: bool,
    ) -> bool:
        """
        Determina si un texto contiene el patrón.

        Args:
            text: Texto donde buscar
            pattern: Patrón a buscar
            use_regex: Si True, trata pattern como regex
            case_sensitive: Si True, búsqueda case-sensitive

        Returns:
            True si el texto contiene el patrón
        """
        try:
            if use_regex:
                # Búsqueda con expresión regular
                flags = 0 if case_sensitive else re.IGNORECASE
                return bool(re.search(pattern, text, flags=flags))
            else:
                # Búsqueda literal
                if case_sensitive:
                    return pattern in text
                else:
                    return pattern.lower() in text.lower()
        except re.error as e:
            logger.error("Invalid regex pattern '%s': %s", pattern, e)
            return False
