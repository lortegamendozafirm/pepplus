# REFACTOR: Sistema de Ensamblado Basado en Slots

**Fecha:** Noviembre 2025
**Versión:** 2.0.0
**Estado:** ✅ Completado

---

## 📋 Tabla de Contenidos

1. [Introducción](#introducción)
2. [Problema que Resuelve](#problema-que-resuelve)
3. [Diseño Previo vs Diseño Nuevo](#diseño-previo-vs-diseño-nuevo)
4. [Arquitectura Nueva](#arquitectura-nueva)
5. [Componentes Principales](#componentes-principales)
6. [Manifest de Slots](#manifest-de-slots)
7. [Ejemplos de Uso](#ejemplos-de-uso)
8. [Migración y Compatibilidad](#migración-y-compatibilidad)
9. [Breaking Changes](#breaking-changes)
10. [TODOs y Mejoras Futuras](#todos-y-mejoras-futuras)

---

## 📖 Introducción

Este documento describe el refactor del sistema de ensamblado de PDFs del microservicio VAWA Packet Assembler, migrando de una arquitectura ad-hoc a un **sistema configurable basado en slots y manifests**.

### Objetivos del Refactor

- ✅ **Separación de responsabilidades:** Lógica de negocio vs operaciones de PDF
- ✅ **Configurabilidad:** Cambiar orden/estructura sin modificar código
- ✅ **Extensibilidad:** Agregar nuevos tipos de exhibits fácilmente
- ✅ **Mantenibilidad:** Código más limpio, testeable y documentado
- ✅ **Robustez:** Manejo de errores y reportes más claros

---

## ❓ Problema que Resuelve

### Limitaciones del Sistema Anterior

1. **Orden hardcodeado:** El orden de los exhibits estaba mezclado con la lógica de negocio en `orchestrator.py`
2. **Búsqueda ad-hoc:** Keywords y estrategias de búsqueda dispersas en el código
3. **Difícil de extender:** Agregar un nuevo exhibit requería modificar múltiples funciones
4. **Testing complejo:** Lógica entrelazada dificulta las pruebas unitarias
5. **Falta de visibilidad:** No quedaba claro qué slots existían y su estado

### Caso de Uso Problemático

```python
# ANTES: Lógica mezclada en orchestrator.py
packet_structure = [
    (f"1. EXHIBIT – {request.client_name}", ex1_files),
    ("2. EXHIBIT – INFORMACIÓN FALTANTE", [missing_report_path]),
    ("3. EXHIBIT – EVIDENCE", ex3_files),
    ("4. EXHIBIT – FILED COPY", ex4_files)
]
# ¿Cómo cambiar el orden? ¿Cómo agregar un nuevo exhibit?
```

---

## 🔄 Diseño Previo vs Diseño Nuevo

### Arquitectura Previa (Legacy)

```
┌──────────────────────────────────────┐
│   FastAPI Endpoint (packet.py)      │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│  PacketOrchestrator (orchestrator.py)│
│  • Búsqueda hardcodeada              │
│  • Orden fijo de exhibits            │
│  • Keywords dispersas en el código   │
│  • Lógica de PDF mezclada            │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│      PDFEngine (pdf_engine.py)       │
│  • merge_packets()                   │
│  • Conversión de imágenes            │
└──────────────────────────────────────┘
```

**Problemas:**
- 🔴 Lógica de negocio acoplada al orden de ensamblado
- 🔴 Difícil agregar/quitar exhibits
- 🔴 No hay visibilidad del estado de cada slot

---

### Arquitectura Nueva (Slot-Based)

```
┌──────────────────────────────────────────────────────┐
│       FastAPI Endpoint (packet.py)                   │
│  • Soporta legacy y nuevo sistema (flag use_legacy)  │
└─────────────┬────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────┐
│   SlotBasedOrchestrator (slot_orchestrator.py)       │
│  • Lee manifest de slots                             │
│  • Itera sobre slots ordenados                       │
│  • Delega resolución a SlotResolver                  │
│  • Delega ensamblado a PDFAssembler                 │
└───────┬─────────────────────────────┬────────────────┘
        │                             │
        ▼                             ▼
┌──────────────────┐        ┌──────────────────────┐
│  SlotResolver    │        │   PDFAssembler       │
│  (slot_resolver) │        │  (pdf_assembler)     │
│                  │        │                      │
│ • Ejecuta        │        │ • merge_pdfs()       │
│   estrategias    │        │ • create_cover()     │
│ • Descarga       │        │ • Backend limpio     │
│   archivos       │        │   (solo PDF ops)     │
└──────────────────┘        └──────────────────────┘
         │
         │ usa
         ▼
┌──────────────────────────────────────┐
│  PacketManifest + Slot Models        │
│  (slot_models.py)                    │
│  • Define estructura de slots        │
│  • Define estrategias de búsqueda    │
└──────────────────────────────────────┘
         │
         │ implementación default
         ▼
┌──────────────────────────────────────┐
│  VAWA Default Manifest               │
│  (vawa_default_manifest.py)          │
│  • 4 slots estándar                  │
│  • Configurable vía código o JSON    │
└──────────────────────────────────────┘
```

**Ventajas:**
- ✅ Separación clara de responsabilidades
- ✅ Configuración declarativa (manifest)
- ✅ Fácil de extender y testear
- ✅ Reportes detallados por slot

---

## 🏗️ Arquitectura Nueva

### Principios de Diseño

1. **Single Responsibility Principle (SRP)**
   - `PDFAssembler`: Solo operaciones de PDF
   - `SlotResolver`: Solo resolución de archivos
   - `SlotBasedOrchestrator`: Solo coordinación

2. **Open/Closed Principle**
   - Abierto a extensión (nuevos tipos de estrategias)
   - Cerrado a modificación (no tocar código core)

3. **Dependency Inversion**
   - Componentes dependen de abstracciones (modelos)
   - No de implementaciones concretas

---

## 🧩 Componentes Principales

### 1. PDFAssembler (`app/services/pdf_assembler.py`)

**Propósito:** Backend limpio para operaciones de PDF usando `pypdf`.

**Métodos principales:**

```python
class PDFAssembler:
    def merge_pdfs_in_order(input_paths: List[str], output_path: str) -> None
    def create_cover_page(output_path: str, title: str, subtitle: str = None) -> str
    def append_cover(pdf_path: str, cover_title: str, temp_dir: str) -> str
```

**Ubicación:** [`app/services/pdf_assembler.py`](../app/services/pdf_assembler.py)

---

### 2. Slot Models (`app/services/slot_models.py`)

**Propósito:** Define las estructuras de datos para slots, manifests y resultados.

**Modelos principales:**

```python
class SearchStrategyType(Enum):
    FOLDER_SEARCH = "folder_search"
    RECURSIVE_DOWNLOAD = "recursive_download"
    PRIORITIZED_SEARCH = "prioritized_search"
    GENERATED = "generated"

class SearchStrategy(BaseModel):
    type: SearchStrategyType
    folder_keywords: Optional[List[str]]
    file_keywords: Optional[List[str]]
    mode: SearchMode  # SINGLE | MULTIPLE

class Slot(BaseModel):
    slot_id: int
    name: str
    required: bool
    search_strategy: SearchStrategy
    cover_page: bool = True

class PacketManifest(BaseModel):
    name: str
    version: str
    slots: List[Slot]
```

**Ubicación:** [`app/services/slot_models.py`](../app/services/slot_models.py)

---

### 3. SlotResolver (`app/services/slot_resolver.py`)

**Propósito:** Resuelve slots ejecutando su estrategia de búsqueda.

**Métodos principales:**

```python
class SlotResolver:
    def resolve_slot(slot: Slot, dropbox_base_path: str) -> SlotResult

    # Estrategias soportadas:
    def _resolve_folder_search(...)
    def _resolve_recursive_download(...)
    def _resolve_prioritized_search(...)
    def _resolve_generated(...)
```

**Ubicación:** [`app/services/slot_resolver.py`](../app/services/slot_resolver.py)

---

### 4. SlotBasedOrchestrator (`app/services/slot_orchestrator.py`)

**Propósito:** Orquestador principal que coordina todo el proceso.

**Flujo de ejecución:**

```python
async def process_request(request: PacketRequest) -> PacketResponse:
    1. Obtener token de Dropbox
    2. Resolver path de Dropbox
    3. Para cada slot en manifest:
       - Ejecutar SlotResolver
       - Recopilar resultados
    4. Convertir imágenes a PDF
    5. Generar contenido para slots "generated"
    6. Ensamblar PDF final con PDFAssembler
    7. Subir a Google Drive
    8. Actualizar Google Sheets
    9. Retornar PacketResponse
```

**Ubicación:** [`app/services/slot_orchestrator.py`](../app/services/slot_orchestrator.py)

---

### 5. VAWA Default Manifest (`app/services/vawa_default_manifest.py`)

**Propósito:** Define el manifest estándar para paquetes VAWA.

**Ubicación:** [`app/services/vawa_default_manifest.py`](../app/services/vawa_default_manifest.py)

---

## 📝 Manifest de Slots

### Estructura del Manifest

Un manifest define la estructura del paquete mediante una lista ordenada de slots.

```python
from app.services.slot_models import PacketManifest, Slot, SearchStrategy

manifest = PacketManifest(
    name="VAWA Standard Packet",
    version="1.0.0",
    slots=[
        Slot(
            slot_id=1,
            name="Exhibit A – USCIS Documents",
            required=True,
            cover_page=True,
            search_strategy=SearchStrategy(
                type="folder_search",
                folder_keywords=["USCIS", "Receipts"],
                file_keywords=["Prima", "Transfer", "I-360"],
                mode="multiple"
            )
        ),
        # ... más slots
    ]
)
```

### Estrategias de Búsqueda Soportadas

#### 1. `folder_search`
Busca archivos en una carpeta específica.

```python
SearchStrategy(
    type="folder_search",
    folder_keywords=["USCIS"],           # Buscar carpeta con este nombre
    file_keywords=["Prima", "Transfer"], # Buscar archivos con estos keywords
    mode="multiple"                      # Traer todos los que coincidan
)
```

#### 2. `recursive_download`
Descarga todo el contenido de una carpeta recursivamente.

```python
SearchStrategy(
    type="recursive_download",
    folder_path=["VAWA", "Evidence"],  # Navegar jerarquía
    file_keywords=[""],                # Wildcard: traer todo
    mode="multiple"
)
```

#### 3. `prioritized_search`
Busca con prioridad: intenta keywords en orden hasta encontrar uno.

```python
SearchStrategy(
    type="prioritized_search",
    folder_keywords=["7", "Folder7"],
    file_keywords_priority=[            # Orden de prioridad
        "Filed Copy",
        "FILED_COPY",
        "Ready to print",
        "Signed"
    ],
    mode="single"                       # Detener en el primero
)
```

#### 4. `generated`
Contenido generado por el sistema (ej: reporte de faltantes).

```python
SearchStrategy(
    type="generated",
    generator="missing_report"
)
```

---

## 💻 Ejemplos de Uso

### Ejemplo 1: Usar el Sistema Nuevo (Default)

```python
# Endpoint: POST /api/v1/generate-packet
# Body (JSON):
{
  "client_name": "Juan Perez",
  "dropbox_url": "https://www.dropbox.com/sh/ejemplo...",
  "drive_parent_folder_id": "1QBrlti0mpJ_...",
  "sheet_output_config": {
    "spreadsheet_id": "1UY6aPIkfap...",
    "worksheet_name": "PREENSAMBLADO",
    "folder_link_cell": "E5",
    "missing_files_cell": "F5",
    "pdf_link_cell": "G5"
  }
}
```

**Por defecto usa el nuevo orquestador slot-based.**

---

### Ejemplo 2: Usar el Sistema Legacy

```python
# Endpoint: POST /api/v1/generate-packet?use_legacy=true
# Body: (igual que antes)
```

El parámetro `use_legacy=true` permite usar el orquestador antiguo para compatibilidad.

---

### Ejemplo 3: Crear un Manifest Personalizado

```python
from app.services.slot_models import PacketManifest, Slot, SearchStrategy
from app.services.slot_orchestrator import SlotBasedOrchestrator

# Definir manifest custom
custom_manifest = PacketManifest(
    name="Custom Immigration Packet",
    version="1.0.0",
    slots=[
        Slot(
            slot_id=1,
            name="Cover Letter",
            required=True,
            search_strategy=SearchStrategy(
                type="folder_search",
                folder_keywords=["Cover"],
                file_keywords=["letter"],
                mode="single"
            )
        ),
        Slot(
            slot_id=2,
            name="Evidence",
            required=False,
            search_strategy=SearchStrategy(
                type="recursive_download",
                folder_path=["Evidence"],
                file_keywords=[""],
                mode="multiple"
            )
        )
    ]
)

# Usar en el orquestador
orchestrator = SlotBasedOrchestrator(manifest=custom_manifest)
result = await orchestrator.process_request(request)
```

---

### Ejemplo 4: Manifest desde JSON (Futuro)

```json
{
  "name": "VAWA Standard Packet",
  "version": "1.0.0",
  "slots": [
    {
      "slot_id": 1,
      "name": "Exhibit A – USCIS",
      "required": true,
      "cover_page": true,
      "search_strategy": {
        "type": "folder_search",
        "folder_keywords": ["USCIS"],
        "file_keywords": ["Prima", "Transfer"],
        "mode": "multiple"
      }
    }
  ]
}
```

**Nota:** Actualmente los manifests se definen en Python. La carga desde JSON/YAML es una mejora futura.

---

## 🔄 Migración y Compatibilidad

### Compatibilidad con Sistema Legacy

El endpoint soporta ambos sistemas mediante el parámetro `use_legacy`:

```python
# Nuevo (default)
POST /api/v1/generate-packet
{...}

# Legacy (compatibilidad)
POST /api/v1/generate-packet?use_legacy=true
{...}
```

### Plan de Migración

1. **Fase 1 (Actual):** Ambos sistemas activos, nuevo es default
2. **Fase 2 (1 mes):** Monitorear logs y reportes
3. **Fase 3 (2 meses):** Deprecar sistema legacy
4. **Fase 4 (3 meses):** Eliminar código legacy

### Testing de Migración

```bash
# Test con nuevo sistema
curl -X POST "http://localhost:8000/api/v1/generate-packet" \
  -H "Content-Type: application/json" \
  -d '{"client_name": "Test Client", ...}'

# Test con legacy
curl -X POST "http://localhost:8000/api/v1/generate-packet?use_legacy=true" \
  -H "Content-Type: application/json" \
  -d '{"client_name": "Test Client", ...}'
```

---

## ⚠️ Breaking Changes

### No Breaking Changes en API Pública

- ✅ El endpoint `/api/v1/generate-packet` mantiene la misma firma
- ✅ El request/response model (`PacketRequest`, `PacketResponse`) no cambió
- ✅ El payload JSON es idéntico

### Cambios Internos

- 🔵 Se agregó parámetro opcional `use_legacy` (default: `False`)
- 🔵 Logs incluyen información de qué orquestador se está usando
- 🔵 Los reportes de slots son más detallados

---

## 🚀 TODOs y Mejoras Futuras

### Corto Plazo (1-2 meses)

- [ ] Agregar tests unitarios para `SlotResolver`
- [ ] Agregar tests de integración para `SlotBasedOrchestrator`
- [ ] Documentar cómo crear manifests custom en README
- [ ] Agregar métricas de performance (tiempo por slot)

### Mediano Plazo (3-6 meses)

- [ ] Soporte para cargar manifests desde JSON/YAML
- [ ] Interfaz web para configurar manifests
- [ ] Agregar estrategia de búsqueda `google_drive_search`
- [ ] Implementar cache de resolución de slots
- [ ] Eliminar código legacy (`orchestrator.py`, `pdf_engine.py`)

### Largo Plazo (6+ meses)

- [ ] Cambiar de `pypdf` a `pikepdf` si se requiere mejor performance
- [ ] Agregar OCR para PDFs escaneados (usando `pytesseract` o Google Vision)
- [ ] Implementar sistema de plugins para estrategias custom
- [ ] Dashboard de monitoreo en tiempo real
- [ ] Sistema de versioning de manifests

---

## 📚 Referencias

### Archivos Clave del Refactor

| Archivo | Propósito |
|---------|-----------|
| [`app/services/pdf_assembler.py`](../app/services/pdf_assembler.py) | Backend de operaciones PDF |
| [`app/services/slot_models.py`](../app/services/slot_models.py) | Modelos de datos |
| [`app/services/slot_resolver.py`](../app/services/slot_resolver.py) | Resolución de slots |
| [`app/services/slot_orchestrator.py`](../app/services/slot_orchestrator.py) | Orquestador principal |
| [`app/services/vawa_default_manifest.py`](../app/services/vawa_default_manifest.py) | Manifest VAWA default |
| [`app/api/v1/packet.py`](../app/api/v1/packet.py) | Endpoint modificado |

### Archivos Legacy (A Deprecar)

| Archivo | Estado |
|---------|--------|
| [`app/services/orchestrator.py`](../app/services/orchestrator.py) | ⚠️ Legacy - mantener por 3 meses |
| [`app/services/pdf_engine.py`](../app/services/pdf_engine.py) | ⚠️ Parcial - solo `convert_images_to_pdf_recursive()` |

---

## 🎯 Conclusión

El refactor a un sistema basado en slots proporciona:

- ✅ **Flexibilidad:** Cambiar estructura sin tocar código
- ✅ **Mantenibilidad:** Componentes pequeños y testeables
- ✅ **Extensibilidad:** Agregar nuevos tipos de slots fácilmente
- ✅ **Visibilidad:** Reportes detallados por slot
- ✅ **Compatibilidad:** No rompe API existente

El sistema está listo para producción y permite evolucionar el servicio sin refactors mayores en el futuro.

---

**Autor:** Claude Code (Anthropic)
**Revisión:** Honey Maldonado
**Última actualización:** Noviembre 2025
