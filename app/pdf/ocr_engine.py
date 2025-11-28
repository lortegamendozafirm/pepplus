# app/pdf/ocr_engine.py
"""
Módulo de OCR para extracción de texto de PDFs.
Utiliza pdf2image + pytesseract para procesamiento página por página.
"""
from pathlib import Path
from typing import Optional

from pdf2image import convert_from_path
import pytesseract

from app.config.settings import settings
from app.logger import get_logger

logger = get_logger(__name__)


class OcrEngine:
    """
    Motor de OCR para procesar PDFs y extraer texto por página.
    """

    def __init__(
        self,
        dpi: int = 300,
        lang: str = "eng",
        tesseract_cmd: Optional[str] = None,
        poppler_path: str | None = None,
    ) -> None:
        self.dpi = dpi
        self.lang = lang
        self.poppler_path = poppler_path or settings.poppler_path

        if tesseract_cmd or settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = (
                tesseract_cmd or settings.tesseract_cmd
            )

        logger.info(
            f"OcrEngine initialized (dpi={self.dpi}, lang={self.lang}, poppler_path={self.poppler_path})"
        )

    def extract_text_by_page(self, pdf_path: str) -> dict[int, str]:
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            logger.error("PDF file not found: %s", pdf_path)
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        logger.info(
            "Starting OCR extraction for: %s (dpi=%d, lang=%s, poppler_path=%s)",
            pdf_path,
            self.dpi,
            self.lang,
            self.poppler_path,
        )

        try:
            # 👇 AQUÍ ES LA CLAVE: usar poppler_path
            images = convert_from_path(
                pdf_path,
                dpi=self.dpi,
                fmt="png",
                poppler_path=self.poppler_path,
            )

            logger.info("Converted PDF to %d images", len(images))

            page_texts: dict[int, str] = {}
            for page_num, image in enumerate(images, start=1):
                try:
                    text = pytesseract.image_to_string(image, lang=self.lang)
                    page_texts[page_num] = text
                    logger.debug(
                        "OCR completed for page %d: %d chars", page_num, len(text)
                    )
                except Exception as e:
                    logger.error("OCR failed for page %d: %s", page_num, e)
                    page_texts[page_num] = ""

            logger.info(
                "OCR extraction completed: %d pages processed", len(page_texts)
            )
            return page_texts

        except Exception as e:
            logger.error(
                "Failed to extract text from PDF %s: %s", pdf_path, e, exc_info=True
            )
            raise



def create_ocr_engine(
    dpi: int = 300,
    lang: str = "eng",
    tesseract_cmd: Optional[str] = None,
) -> OcrEngine:
    return OcrEngine(dpi=dpi, lang=lang, tesseract_cmd=tesseract_cmd)

