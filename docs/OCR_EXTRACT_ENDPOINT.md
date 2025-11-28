# OCR Extract Endpoint - Documentación Técnica

## Resumen

El endpoint `POST /api/v1/packets/ocr-extract` permite extraer páginas específicas de un PDF basándose en un patrón de texto detectado mediante OCR (Optical Character Recognition).

Esta funcionalidad es útil para:
- Filtrar páginas que contienen información específica (ej: "rap sheet", "criminal record")
- Crear PDFs reducidos con solo las secciones relevantes
- Automatizar la separación de documentos grandes en partes específicas

## Arquitectura de la Solución

La implementación sigue la arquitectura en capas del PDF Packet Service:

```
app/
├── api/
│   ├── routes.py              # Endpoint POST /packets/ocr-extract
│   └── schemas.py             # OcrExtractRequest, OcrExtractResponse
├── services/
│   └── ocr_extract_service.py # Orquestación: OCR + Filtrado + Extracción
├── pdf/
│   ├── ocr_engine.py          # Motor OCR (pytesseract + pdf2image)
│   └── page_extractor.py      # Extracción de páginas con pypdf
└── config/
    └── settings.py            # Configuración (sin cambios necesarios)
```

### Flujo de Procesamiento

1. **API Layer** (`routes.py`): Recibe request, valida, delega a servicio
2. **Service Layer** (`ocr_extract_service.py`): Orquesta el proceso completo
3. **PDF Layer - OCR** (`ocr_engine.py`): Extrae texto página por página
4. **PDF Layer - Extraction** (`page_extractor.py`): Crea nuevo PDF con páginas filtradas

## Módulos Creados

### 1. `app/pdf/ocr_engine.py`

**Responsabilidad**: Encapsular la lógica de OCR

**Clase principal**: `OcrEngine`

**Métodos**:
- `extract_text_by_page(pdf_path: str) -> dict[int, str]`
  - Convierte cada página del PDF a imagen (usando `pdf2image`)
  - Aplica OCR con `pytesseract`
  - Retorna dict: `{1: "texto pág 1", 2: "texto pág 2", ...}`

**Configuración**:
- `dpi`: Resolución de conversión (default: 300)
- `lang`: Lenguaje Tesseract (default: "eng")
- `tesseract_cmd`: Ruta ejecutable Tesseract (opcional)

**Manejo de errores**:
- Si una página falla OCR, se registra en logs y se continúa con el resto
- La página fallida se marca con texto vacío `""`

### 2. `app/pdf/page_extractor.py`

**Responsabilidad**: Extraer páginas específicas de un PDF

**Funciones principales**:

- `extract_pages_to_new_pdf(input_pdf_path, page_numbers, output_pdf_path)`
  - Usa `pypdf.PdfReader` y `PdfWriter`
  - Extrae solo las páginas especificadas (1-indexed)
  - Crea un nuevo PDF con esas páginas

- `generate_output_path(input_pdf_path, suffix) -> str`
  - Convención: `original.pdf` → `original_<suffix>.pdf`
  - Ejemplo: `vawa_packet.pdf` + `"rapsheet"` → `vawa_packet_rapsheet.pdf`
  - Mantiene el archivo en la misma carpeta del original

**Validaciones**:
- Valida que el PDF de entrada existe
- Valida que los números de página son válidos (dentro del rango del PDF)
- Lanza excepciones claras si hay errores

### 3. `app/services/ocr_extract_service.py`

**Responsabilidad**: Orquestar el flujo completo de extracción

**Clase principal**: `OcrExtractService`

**Método principal**:
```python
def extract_pages_by_pattern(
    input_pdf_path: str,
    pattern: str,
    use_regex: bool = False,
    suffix: str = "pattern",
    case_sensitive: bool = False,
) -> OcrExtractResult
```

**Flujo interno**:
1. Valida que el PDF existe
2. Ejecuta OCR con `ocr_engine.extract_text_by_page()`
3. Filtra páginas que coinciden con el patrón usando `_filter_pages_by_pattern()`
4. Si no hay coincidencias: retorna `ok=True` pero `matched_pages=[]`
5. Si hay coincidencias: genera ruta de salida y crea PDF con `extract_pages_to_new_pdf()`
6. Retorna `OcrExtractResult` con toda la información

**Búsqueda de patrones**:
- **Literal** (`use_regex=False`): Busca substring exacta
- **Regex** (`use_regex=True`): Usa `re.search()` para matching avanzado
- **Case sensitivity**: Configurable con parámetro `case_sensitive`

### 4. API Schemas (`app/api/schemas.py`)

**`OcrExtractRequest`**:
```python
{
    "input_pdf_path": str,        # Ruta del PDF en el servidor
    "pattern": str,               # Texto o regex a buscar
    "use_regex": bool,            # Default: False
    "suffix": str,                # Default: "pattern"
    "case_sensitive": bool,       # Default: False
    "ocr_dpi": int,               # Default: 300, rango: 100-600
    "ocr_lang": str               # Default: "eng"
}
```

**`OcrExtractResponse`**:
```python
{
    "ok": bool,                   # True si exitoso
    "message": str,               # Mensaje descriptivo
    "input_pdf_path": str,        # Path del PDF procesado
    "output_pdf_path": str?,      # Path del PDF generado (null si no hubo matches)
    "matched_pages": [int]        # Lista de páginas que coincidieron (1-indexed)
}
```

### 5. Endpoint (`app/api/routes.py`)

**Ruta**: `POST /api/v1/packets/ocr-extract`

**Características**:
- No requiere autenticación (consistente con otros endpoints del servicio)
- Manejo robusto de errores con códigos HTTP apropiados:
  - `404 NOT_FOUND`: Archivo no existe
  - `400 BAD_REQUEST`: Parámetros inválidos
  - `500 INTERNAL_SERVER_ERROR`: Errores inesperados
- Logging detallado en cada paso
- Timeout: Puede tardar varios minutos (dependiendo del tamaño del PDF y DPI)

## Dependencias Agregadas

En `requirements.txt`:

```txt
# OCR dependencies
pytesseract>=0.3.10      # Wrapper Python para Tesseract
pdf2image>=1.17.0        # Conversión PDF -> imágenes
Pillow>=10.0.0           # Procesamiento de imágenes
```

**Dependencias del sistema**:
- **Tesseract OCR**: Debe estar instalado en el sistema operativo
  - Linux: `apt-get install tesseract-ocr`
  - macOS: `brew install tesseract`
  - Windows: Descargar instalador desde [GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
- **Poppler**: Requerido por pdf2image
  - Linux: `apt-get install poppler-utils`
  - macOS: `brew install poppler`
  - Windows: Descargar desde [poppler releases](https://github.com/oschwartz10612/poppler-windows/releases/)

## Ejemplos de Uso

### Ejemplo 1: Búsqueda literal simple

**Request**:
```bash
curl -X POST "http://localhost:8000/api/v1/packets/ocr-extract" \
  -H "Content-Type: application/json" \
  -d '{
    "input_pdf_path": "/tmp/john_doe/packet_full.pdf",
    "pattern": "rap sheet",
    "suffix": "rapsheet"
  }'
```

**Response** (éxito):
```json
{
  "ok": true,
  "message": "Successfully extracted 3 pages matching pattern 'rap sheet'",
  "input_pdf_path": "/tmp/john_doe/packet_full.pdf",
  "output_pdf_path": "/tmp/john_doe/packet_full_rapsheet.pdf",
  "matched_pages": [5, 12, 18]
}
```

### Ejemplo 2: Búsqueda con regex

**Request**:
```bash
curl -X POST "http://localhost:8000/api/v1/packets/ocr-extract" \
  -H "Content-Type: application/json" \
  -d '{
    "input_pdf_path": "/tmp/jane_smith/vawa_packet.pdf",
    "pattern": "criminal.*record|rap.*sheet",
    "use_regex": true,
    "suffix": "criminal_records",
    "case_sensitive": false
  }'
```

**Response** (éxito):
```json
{
  "ok": true,
  "message": "Successfully extracted 2 pages matching pattern 'criminal.*record|rap.*sheet'",
  "input_pdf_path": "/tmp/jane_smith/vawa_packet.pdf",
  "output_pdf_path": "/tmp/jane_smith/vawa_packet_criminal_records.pdf",
  "matched_pages": [8, 9]
}
```

### Ejemplo 3: Sin coincidencias

**Request**:
```bash
curl -X POST "http://localhost:8000/api/v1/packets/ocr-extract" \
  -H "Content-Type: application/json" \
  -d '{
    "input_pdf_path": "/tmp/alice/document.pdf",
    "pattern": "nonexistent text"
  }'
```

**Response** (sin error, pero sin matches):
```json
{
  "ok": true,
  "message": "No pages matched pattern 'nonexistent text'",
  "input_pdf_path": "/tmp/alice/document.pdf",
  "output_pdf_path": null,
  "matched_pages": []
}
```

### Ejemplo 4: Archivo no encontrado

**Response** (error 404):
```json
{
  "detail": "Input PDF not found: /tmp/invalid/path.pdf"
}
```

### Ejemplo 5: OCR con configuración avanzada

**Request**:
```bash
curl -X POST "http://localhost:8000/api/v1/packets/ocr-extract" \
  -H "Content-Type: application/json" \
  -d '{
    "input_pdf_path": "/tmp/spanish_doc.pdf",
    "pattern": "certificado",
    "ocr_dpi": 400,
    "ocr_lang": "spa",
    "case_sensitive": true
  }'
```

## Integración con FastAPI

El endpoint está automáticamente documentado en:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

La documentación interactiva incluye:
- Descripción completa del endpoint
- Schemas de request/response
- Validaciones de Pydantic
- Posibilidad de probar directamente desde el navegador

## Consideraciones de Performance

### Tiempos de Ejecución

| PDF Size | Pages | DPI | Approximate Time |
|----------|-------|-----|------------------|
| 5 MB     | 10    | 300 | 30-60 segundos   |
| 20 MB    | 50    | 300 | 3-5 minutos      |
| 50 MB    | 100   | 300 | 8-12 minutos     |
| 20 MB    | 50    | 150 | 1-2 minutos      |
| 20 MB    | 50    | 600 | 10-15 minutos    |

**Factores que afectan el tiempo**:
1. **DPI**: Mayor resolución = mejor OCR pero más lento
2. **Número de páginas**: Crecimiento lineal
3. **Complejidad de imágenes**: PDFs escaneados vs nativos
4. **Hardware**: CPU, memoria RAM

### Recomendaciones de Optimización

1. **DPI óptimo**:
   - 150 DPI: Rápido, calidad aceptable para texto claro
   - 300 DPI: Balance ideal (recomendado por defecto)
   - 400-600 DPI: Solo para documentos de baja calidad o texto pequeño

2. **Para Cloud Run**:
   - Configurar timeout alto (ej: 15 minutos)
   - Asignar suficiente CPU y memoria (2 vCPU, 2GB RAM mínimo)
   - Considerar procesamiento asíncrono para PDFs grandes

3. **Caché de OCR** (mejora futura):
   - Guardar resultados OCR en DB/cache
   - Reutilizar si el mismo PDF se procesa múltiples veces

## Limitaciones y Casos Límite

### Limitaciones Actuales

1. **OCR Síncrono**: El endpoint es bloqueante (puede tardar minutos)
   - **Mejora futura**: Implementar cola asíncrona con `/enqueue`

2. **Calidad de OCR**: Depende de la calidad del PDF original
   - PDFs nativos (no escaneados): Mejor usar extracción de texto directo (pypdf)
   - PDFs escaneados: OCR necesario pero puede tener errores

3. **Idiomas**: Requiere paquetes de lenguaje de Tesseract instalados
   - Default: inglés (`eng`)
   - Otros idiomas: Instalar paquetes adicionales (ej: `tesseract-ocr-spa`)

4. **Memoria**: PDFs muy grandes pueden causar OOM
   - Procesar página por página ayuda, pero las imágenes temporales consumen RAM

### Casos Límite Manejados

1. **PDF sin texto (imágenes puras)**: OCR funciona correctamente
2. **Página individual falla OCR**: Se registra y continúa con las demás
3. **Patrón regex inválido**: Se captura `re.error` y se retorna False
4. **Sin coincidencias**: Retorna `ok=True` con `matched_pages=[]` (no es error)
5. **Archivo no existe**: Retorna HTTP 404 con mensaje claro

## Errores Comunes y Soluciones

### Error: "Tesseract not found"

**Causa**: Tesseract no está instalado o no está en el PATH

**Solución**:
```python
# Opción 1: Instalar Tesseract en el sistema
apt-get install tesseract-ocr

# Opción 2: Especificar ruta en el código (config/settings.py)
tesseract_cmd: str = "/usr/bin/tesseract"
```

### Error: "Unable to get page count. Is poppler installed?"

**Causa**: Poppler no está instalado

**Solución**:
```bash
# Linux
apt-get install poppler-utils

# macOS
brew install poppler
```

### Error: "PDF page extraction failed"

**Causa**: PDF corrupto o protegido

**Solución**:
- Validar integridad del PDF con `pypdf.PdfReader`
- Remover protección si es necesario
- Intentar reparar PDF con herramientas externas

### Warning: "No pages matched pattern"

**Causa**: Patrón no encontrado en ninguna página

**No es un error**: Esto es un resultado válido

**Posibles razones**:
- Pattern incorrecto (revisar typos)
- OCR no detectó el texto (calidad baja, incrementar DPI)
- Case sensitivity (ajustar `case_sensitive`)

## Testing

### Testing Manual

```bash
# 1. Crear PDF de prueba con texto
echo "This is a test page with keyword RAPSHEET" | \
  enscript -B -o - | ps2pdf - test.pdf

# 2. Ejecutar endpoint
curl -X POST "http://localhost:8000/api/v1/packets/ocr-extract" \
  -H "Content-Type: application/json" \
  -d '{
    "input_pdf_path": "./test.pdf",
    "pattern": "RAPSHEET"
  }'

# 3. Verificar output
ls -la test_pattern.pdf
```

### Testing Automatizado (Sugerido)

Crear `tests/test_ocr_extract.py`:

```python
import pytest
from app.services.ocr_extract_service import OcrExtractService

def test_extract_pages_simple_pattern():
    service = OcrExtractService()
    result = service.extract_pages_by_pattern(
        input_pdf_path="tests/fixtures/sample.pdf",
        pattern="test keyword",
        suffix="filtered"
    )
    assert result.ok is True
    assert len(result.matched_pages) > 0
```

## Deployment en Cloud Run

### Variables de Entorno Requeridas

Ninguna adicional (las existentes del PDF Packet Service son suficientes)

### Dockerfile - Agregar Dependencias

```dockerfile
# Instalar Tesseract y Poppler
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*
```

### Cloud Run Config

```yaml
service:
  timeout: 900s              # 15 minutos (OCR puede tardar)
  memory: 2Gi                # Suficiente para imágenes temporales
  cpu: 2                     # Acelera conversión PDF->imagen
  concurrency: 1             # Evitar OOM con múltiples requests
```

## Próximos Pasos y Mejoras Futuras

1. **Procesamiento Asíncrono**:
   - Integrar con `enqueuer_client` existente
   - Crear `/packets/ocr-extract/enqueue` para jobs largos

2. **Caché de Resultados OCR**:
   - Guardar hash del PDF + resultados OCR en DB
   - Evitar re-procesar el mismo PDF

3. **Extracción de Texto Directo**:
   - Intentar `pypdf.PdfReader.extract_text()` primero
   - Solo usar OCR si no hay texto nativo (más rápido)

4. **Mejoras de OCR**:
   - Pre-procesamiento de imágenes (binarización, deskew)
   - Múltiples pasadas con diferentes configuraciones

5. **Paralelización**:
   - Procesar páginas en paralelo con ThreadPoolExecutor
   - Reducir tiempo de OCR en PDFs grandes

6. **Webhooks/Notificaciones**:
   - Notificar cuando termine el procesamiento (para jobs async)

7. **Metrics y Telemetría**:
   - Tiempo de OCR por página
   - Tasa de aciertos de patrones
   - Memoria/CPU consumidos

## Soporte y Contacto

Para dudas o issues relacionados con este endpoint:
1. Revisar logs del servicio: `LOG_LEVEL=DEBUG`
2. Verificar instalación de dependencias del sistema (Tesseract, Poppler)
3. Consultar esta documentación para ejemplos de uso

---

**Versión**: 1.0
**Fecha**: 2025-01-26
**Autor**: Arquitecto Senior Python / FastAPI
