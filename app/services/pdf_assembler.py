# app/services/pdf_assembler.py
"""
Módulo de ensamblado de PDFs.
Backend limpio y simple basado en pypdf para unir PDFs en orden.
NO maneja lógica de negocio, solo operaciones de PDF.
"""

import os
from typing import List, Optional
from pypdf import PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import inch
from app.utils.logger import logger


class PDFAssembler:
    """
    Clase que encapsula las operaciones de ensamblado de PDFs.
    Responsabilidad única: manipulación de archivos PDF.
    """

    def __init__(self):
        """Inicializa el ensamblador de PDFs."""
        pass

    def merge_pdfs_in_order(self, input_paths: List[str], output_path: str) -> None:
        """
        Une múltiples PDFs en un solo archivo en el orden proporcionado.

        Args:
            input_paths: Lista de rutas a archivos PDF para unir (en orden)
            output_path: Ruta donde se guardará el PDF final

        Raises:
            Exception: Si ocurre un error al escribir el PDF final
        """
        merger = PdfWriter()

        logger.info(f"🔗 Uniendo {len(input_paths)} archivos PDF...")

        for pdf_path in input_paths:
            if not pdf_path or not os.path.exists(pdf_path):
                logger.warning(f"⚠️ Archivo no encontrado, omitiendo: {pdf_path}")
                continue

            if not pdf_path.lower().endswith('.pdf'):
                logger.warning(f"⚠️ Archivo no es PDF, omitiendo: {pdf_path}")
                continue

            try:
                merger.append(pdf_path)
                logger.debug(f"✅ Añadido: {os.path.basename(pdf_path)}")
            except Exception as e:
                logger.error(f"❌ Error al añadir PDF '{os.path.basename(pdf_path)}': {e}")
                # Continuamos con los demás archivos

        # Escribir el PDF final
        try:
            with open(output_path, "wb") as output_file:
                merger.write(output_file)
            merger.close()
            logger.info(f"✅ PDF unido guardado exitosamente: {output_path}")
        except Exception as e:
            logger.critical(f"🔥 Error crítico al escribir PDF final: {e}")
            raise

    def create_cover_page(self, output_path: str, title: str, subtitle: Optional[str] = None) -> str:
        """
        Crea una página de portada simple con título y opcional subtítulo.

        Args:
            output_path: Ruta donde guardar el PDF de portada
            title: Título principal
            subtitle: Subtítulo opcional

        Returns:
            Ruta del archivo creado
        """
        try:
            c = Canvas(output_path, pagesize=letter)
            width, height = letter

            # Dibujar borde
            c.setLineWidth(3)
            c.rect(inch, inch, width - 2*inch, height - 2*inch)

            # Título principal
            c.setFont("Helvetica-Bold", 24)
            c.drawCentredString(width / 2, height / 2 + 20, title)

            # Subtítulo (opcional)
            if subtitle:
                c.setFont("Helvetica", 14)
                c.drawCentredString(width / 2, height / 2 - 20, subtitle)

            c.save()
            logger.debug(f"📄 Portada creada: {title}")
            return output_path
        except Exception as e:
            logger.error(f"❌ Error creando portada '{title}': {e}")
            raise

    def append_cover(self, pdf_path: str, cover_title: str, temp_dir: str) -> str:
        """
        Crea una portada temporal y la añade al inicio de un PDF existente.

        Args:
            pdf_path: Ruta del PDF al que añadir portada
            cover_title: Título de la portada
            temp_dir: Directorio para archivos temporales

        Returns:
            Ruta del PDF con portada añadida
        """
        if not os.path.exists(pdf_path):
            logger.warning(f"⚠️ PDF no existe, no se puede añadir portada: {pdf_path}")
            return pdf_path

        # Crear portada temporal
        cover_path = os.path.join(temp_dir, f"cover_{os.path.basename(pdf_path)}")
        self.create_cover_page(cover_path, cover_title)

        # Crear nuevo PDF con portada + contenido
        output_path = pdf_path.replace(".pdf", "_with_cover.pdf")
        self.merge_pdfs_in_order([cover_path, pdf_path], output_path)

        # Limpiar portada temporal
        try:
            os.remove(cover_path)
        except:
            pass

        return output_path

    def append_separator(self, output_path: str, separator_title: str) -> str:
        """
        Crea una página separadora simple.
        Útil para marcar secciones dentro de un PDF.

        Args:
            output_path: Ruta donde guardar el separador
            separator_title: Texto del separador

        Returns:
            Ruta del separador creado
        """
        return self.create_cover_page(output_path, separator_title)
