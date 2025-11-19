# test_integration.py
from app.integrations.dropbox_client import DropboxIntegrator
from dotenv import load_dotenv
import os

load_dotenv() # Carga variables de entorno si usas .env

# Pega un token real aquí temporalmente para probar
TOKEN = "TU_TOKEN_DE_DROPBOX_AQUI" 
LINK = "LINK_DE_CARPETA_DE_PRUEBA"

dbx = DropboxIntegrator(TOKEN)
path = dbx.get_path_from_link(LINK)
print(f"Ruta encontrada: {path}")

if path:
    es_valido, faltantes = dbx.validate_vawa_structure(path)
    print(f"¿Estructura Válida?: {es_valido}")
    print(f"Faltantes: {faltantes}")