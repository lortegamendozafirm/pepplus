# app/utils/helpers.py
import re
import os
import shutil

def normalize_text(text: str) -> str:
    """
    Normaliza texto para comparaciones flexibles:
    - Convierte a minúsculas.
    - Elimina caracteres no alfanuméricos (excepto números).
    Ejemplo: "I-360 Prima Facie" -> "i360primafacie"
    """
    if not text:
        return ""
    text = str(text).lower()
    # Mantenemos solo letras y números
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def clean_temp_folder(folder_path: str):
    """
    Elimina una carpeta temporal y todo su contenido de forma segura.
    """
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
            print(f"🧹 Carpeta temporal eliminada: {folder_path}")
        except Exception as e:
            print(f"⚠️ No se pudo eliminar la carpeta {folder_path}: {e}")

def sanitize_filename(filename: str) -> str:
    """
    Limpia nombres de archivo para que sean seguros en cualquier SO.
    """
    return re.sub(r'[\\/*?:"<>|]', "_", filename)