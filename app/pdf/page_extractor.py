# app/pdf/page_extractor.py
"""
Módulo para extraer páginas específicas de un PDF y crear un nuevo PDF.
Utiliza pypdf para manipulación de PDFs.
"""
from pathlib import Path
from typing import List

from pypdf import PdfReader, PdfWriter

from app.logger import get_logger

logger = get_logger(__name__)


def extract_pages_to_new_pdf(
    input_pdf_path: str,
    page_numbers: List[int],
    output_pdf_path: str,
) -> None:
    """
    Extrae páginas específicas de un PDF y las escribe en un nuevo PDF.

    Args:
        input_pdf_path: Ruta del PDF de origen
        page_numbers: Lista de números de página a extraer (1-indexed)
        output_pdf_path: Ruta donde se escribirá el nuevo PDF

    Raises:
        FileNotFoundError: Si el PDF de entrada no existe
        ValueError: Si la lista de páginas está vacía o contiene números inválidos
        Exception: Si falla la lectura o escritura del PDF
    """
    input_file = Path(input_pdf_path)
    if not input_file.exists():
        logger.error("Input PDF not found: %s", input_pdf_path)
        raise FileNotFoundError(f"Input PDF not found: {input_pdf_path}")

    if not page_numbers:
        logger.error("Page numbers list is empty")
        raise ValueError("Page numbers list cannot be empty")

    logger.info(
        "Extracting %d pages from %s to %s",
        len(page_numbers),
        input_pdf_path,
        output_pdf_path,
    )

    try:
        # Leer PDF de origen
        reader = PdfReader(input_pdf_path)
        total_pages = len(reader.pages)

        logger.info("Input PDF has %d total pages", total_pages)

        # Validar que los números de página sean válidos
        for page_num in page_numbers:
            if page_num < 1 or page_num > total_pages:
                logger.error("Invalid page number %d (PDF has %d pages)", page_num, total_pages)
                raise ValueError(f"Invalid page number {page_num} (PDF has {total_pages} pages)")

        # Crear writer y agregar páginas seleccionadas
        writer = PdfWriter()
        for page_num in page_numbers:
            # pypdf usa índices 0-based internamente
            page_index = page_num - 1
            writer.add_page(reader.pages[page_index])
            logger.debug("Added page %d to output PDF", page_num)

        # Crear directorio de salida si no existe
        output_file = Path(output_pdf_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Escribir PDF de salida
        with output_file.open("wb") as fh:
            writer.write(fh)

        logger.info("Successfully created PDF with %d pages: %s", len(page_numbers), output_pdf_path)

    except (FileNotFoundError, ValueError):
        raise
    except Exception as e:
        logger.error("Failed to extract pages from PDF: %s", e, exc_info=True)
        raise


def generate_output_path(input_pdf_path: str, suffix: str) -> str:
    """
    Genera la ruta del archivo de salida basado en la entrada y un sufijo.

    La convención es:
    - Input: /path/to/original_file.pdf
    - Output: /path/to/original_file_<suffix>.pdf

    Args:
        input_pdf_path: Ruta del PDF original
        suffix: Sufijo a agregar al nombre del archivo

    Returns:
        Ruta del archivo de salida

    Examples:
        >>> generate_output_path("/tmp/vawa_packet.pdf", "rapsheet")
        "/tmp/vawa_packet_rapsheet.pdf"
    """
    input_file = Path(input_pdf_path)
    # Obtener nombre sin extensión
    stem = input_file.stem
    # Agregar sufijo y extensión
    new_name = f"{stem}_{suffix}.pdf"
    # Mantener mismo directorio
    output_path = input_file.parent / new_name

    logger.debug("Generated output path: %s -> %s", input_pdf_path, output_path)

    return str(output_path)
