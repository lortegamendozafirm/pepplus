# app/service/pdf_engine.pdf
import os
import img2pdf
from pypdf import PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from typing import List, Tuple
from app.utils.logger import logger  # <-- IMPORTAR LOGGER

class PDFEngine:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        
    def create_cover_page(self, file_path: str, title: str):
        """Crea una página de portada simple."""
        try:
            c = Canvas(file_path, pagesize=letter)
            width, height = letter
            c.setFont("Helvetica-Bold", 24)
            c.drawCentredString(width / 2, height / 2, title)
            c.setLineWidth(3)
            c.rect(inch, inch, width - 2*inch, height - 2*inch)
            c.save()
            # logger.debug(f"Portada creada: {title}") # Opcional, nivel debug
        except Exception as e:
            logger.error(f"❌ Error creando portada '{title}': {e}")

    def create_missing_report(self, file_path: str, missing_items: List[str]):
        """Crea una página PDF listando los documentos faltantes."""
        try:
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            story = []
            title_style = self.styles['Heading1']
            title_style.alignment = TA_CENTER
            story.append(Paragraph("REPORTE DE DOCUMENTOS FALTANTES", title_style))
            story.append(Paragraph("<br/><br/>", self.styles['Normal']))
            
            if not missing_items:
                story.append(Paragraph("✅ No se detectaron documentos faltantes.", self.styles['Normal']))
            else:
                story.append(Paragraph("El sistema no pudo localizar los siguientes documentos:", self.styles['Normal']))
                for item in missing_items:
                    story.append(Paragraph(f"• {item}", self.styles['Bullet']))
                    
            doc.build(story)
            logger.info(f"📄 Reporte de faltantes generado en: {os.path.basename(file_path)}")
        except Exception as e:
            logger.error(f"❌ Error generando reporte de faltantes: {e}")

    def convert_images_to_pdf_recursive(self, folder_path: str):
        """Busca imágenes y las convierte a PDF."""
        img_exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
        converted_count = 0
        errors_count = 0
        
        logger.info(f"🖼️ Iniciando conversión de imágenes en: {folder_path}")

        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(img_exts):
                    full_path = os.path.join(root, file)
                    pdf_path = os.path.splitext(full_path)[0] + ".pdf"
                    try:
                        with open(pdf_path, "wb") as f:
                            f.write(img2pdf.convert(full_path))
                        os.remove(full_path)
                        converted_count += 1
                        # logger.debug(f"Transformado: {file} -> PDF")
                    except Exception as e:
                        errors_count += 1
                        logger.warning(f"⚠️ No se pudo convertir la imagen {file}: {e}")
        
        logger.info(f"🏁 Conversión finalizada. Éxitos: {converted_count}, Fallos: {errors_count}")

    def merge_packets(self, output_path: str, components: List[Tuple[str, List[str]]]):
        """Une todo en un solo PDF."""
        merger = PdfWriter()
        
        logger.info("📚 Iniciando ensamblaje del PDF maestro...")
        
        try:
            for title, file_paths in components:
                # 1. Portada
                if title:
                    cover_temp = output_path.replace(".pdf", f"_cover_{title[:5]}.pdf")
                    self.create_cover_page(cover_temp, title)
                    merger.append(cover_temp)
                
                # 2. Documentos
                for path in file_paths:
                    if path and os.path.exists(path) and path.endswith('.pdf'):
                        try:
                            merger.append(path)
                        except Exception as e:
                            logger.error(f"❌ PDF Corrupto omitido: {os.path.basename(path)} - Error: {e}")
                    elif path:
                        logger.warning(f"⚠️ Archivo no válido o no encontrado para unir: {path}")
            
            with open(output_path, "wb") as f:
                merger.write(f)
            
            logger.info(f"✅ PDF Maestro guardado exitosamente: {os.path.basename(output_path)}")
            return output_path
            
        except Exception as e:
            logger.critical(f"🔥 Fallo crítico al unir el PDF final: {e}")
            raise e