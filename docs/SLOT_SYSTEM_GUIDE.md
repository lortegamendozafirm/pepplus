# Guía Rápida: Sistema de Slots

**Guía práctica para usar el nuevo sistema de ensamblado basado en slots**

---

## 🎯 ¿Qué es el Sistema de Slots?

El sistema de slots permite definir la estructura de un paquete PDF mediante una **configuración declarativa** llamada "manifest".

### Concepto Clave: Slot

Un **slot** es una posición en el documento final que puede contener:
- Uno o más archivos PDF
- Una portada generada automáticamente
- Contenido generado (ej: reportes)

---

## 🚀 Inicio Rápido

### Usar el Sistema Default (VAWA)

```python
# El sistema nuevo es el default, no necesitas hacer nada especial
from app.services.slot_orchestrator import SlotBasedOrchestrator

orchestrator = SlotBasedOrchestrator()
result = await orchestrator.process_request(request)
```

El manifest default incluye 4 slots:
1. **Exhibit A:** USCIS Documents
2. **Exhibit B:** Missing Documents Report
3. **Exhibit C:** VAWA Evidence
4. **Exhibit D:** Filed Copy

---

## 📝 Crear un Manifest Personalizado

### Paso 1: Definir los Slots

```python
from app.services.slot_models import PacketManifest, Slot, SearchStrategy

my_manifest = PacketManifest(
    name="My Custom Packet",
    version="1.0.0",
    description="Packet personalizado para mi caso de uso",
    slots=[
        # Slot 1: Cover Letter
        Slot(
            slot_id=1,
            name="Cover Letter",
            required=True,
            cover_page=False,  # No agregar portada para este slot
            search_strategy=SearchStrategy(
                type="folder_search",
                folder_keywords=["Cover", "Letter"],
                file_keywords=["cover_letter", "letter"],
                mode="single"  # Solo buscar un archivo
            )
        ),

        # Slot 2: Supporting Documents
        Slot(
            slot_id=2,
            name="Supporting Documents",
            required=False,
            cover_page=True,
            search_strategy=SearchStrategy(
                type="recursive_download",
                folder_path=["Documents", "Supporting"],
                file_keywords=[""],  # Wildcard: traer todo
                mode="multiple"
            )
        )
    ]
)
```

### Paso 2: Usar el Manifest

```python
from app.services.slot_orchestrator import SlotBasedOrchestrator

orchestrator = SlotBasedOrchestrator(manifest=my_manifest)
result = await orchestrator.process_request(request)
```

---

## 🔍 Estrategias de Búsqueda

### 1. folder_search

Busca archivos en una carpeta específica usando keywords.

```python
SearchStrategy(
    type="folder_search",
    folder_keywords=["USCIS"],           # Buscar carpeta con este nombre
    file_keywords=["Prima", "Transfer"], # Archivos que contengan estos keywords
    mode="multiple"                      # "single" o "multiple"
)
```

**Cuándo usar:** Cuando necesitas archivos específicos de una carpeta conocida.

---

### 2. recursive_download

Descarga TODO el contenido de una carpeta recursivamente.

```python
SearchStrategy(
    type="recursive_download",
    folder_path=["VAWA", "Evidence"],  # Jerarquía de carpetas
    file_keywords=[""],                # "" = traer todo
    mode="multiple"
)
```

**Cuándo usar:** Cuando necesitas TODO el contenido de una carpeta (ej: evidencias).

---

### 3. prioritized_search

Busca archivos con prioridad: intenta keywords en orden.

```python
SearchStrategy(
    type="prioritized_search",
    folder_keywords=["7"],
    file_keywords_priority=[        # Orden de prioridad
        "Filed Copy",
        "Ready to print",
        "Signed"
    ],
    mode="single"                   # Detiene en el primero que encuentre
)
```

**Cuándo usar:** Cuando hay múltiples nombres posibles y quieres priorizar uno.

---

### 4. generated

Contenido generado por el sistema.

```python
SearchStrategy(
    type="generated",
    generator="missing_report"      # Generador a usar
)
```

**Cuándo usar:** Para contenido que se genera dinámicamente (ej: reportes).

---

## 🎨 Personalizar Portadas

```python
Slot(
    slot_id=1,
    name="My Section",
    cover_page=True,                # Agregar portada
    cover_title="Custom Title",     # Título personalizado (opcional)
    search_strategy=...
)
```

Si no especificas `cover_title`, usa el campo `name` del slot.

---

## 🧪 Testing

### Test Básico

```python
from app.services.vawa_default_manifest import get_vawa_default_manifest

manifest = get_vawa_default_manifest()
print(f"Manifest: {manifest.name}")
print(f"Total slots: {len(manifest.slots)}")

for slot in manifest.get_ordered_slots():
    print(f"  Slot {slot.slot_id}: {slot.name} (required={slot.required})")
```

### Test con Mock Data

```python
import pytest
from app.services.slot_resolver import SlotResolver
from unittest.mock import Mock

def test_slot_resolver():
    # Mock Dropbox client
    mock_dbx = Mock()
    resolver = SlotResolver(mock_dbx, "/tmp/test")

    slot = Slot(
        slot_id=1,
        name="Test Slot",
        required=True,
        search_strategy=SearchStrategy(
            type="folder_search",
            folder_keywords=["Test"],
            file_keywords=["test"],
            mode="single"
        )
    )

    result = resolver.resolve_slot(slot, "/test/base/path")
    assert result.slot_id == 1
```

---

## 📊 Analizar Resultados

### SlotResult

Cada slot retorna un `SlotResult`:

```python
class SlotResult(BaseModel):
    slot_id: int
    name: str
    files_found: List[str]                          # Archivos encontrados
    status: Literal["success", "partial", "missing"]
    error_message: Optional[str]
    required: bool

    @property
    def is_complete(self) -> bool:
        # True si el slot se resolvió correctamente
        ...

    @property
    def has_files(self) -> bool:
        # True si se encontraron archivos
        ...
```

### AssemblyReport

El proceso completo genera un `AssemblyReport`:

```python
class AssemblyReport(BaseModel):
    success: bool
    total_slots: int
    completed_slots: int
    missing_required_slots: List[str]
    slot_results: List[SlotResult]
    final_pdf_path: Optional[str]

    def get_missing_items(self) -> List[str]:
        # Lista de items faltantes
        ...
```

---

## 🔧 Ejemplos Avanzados

### Ejemplo 1: Manifest con Slots Opcionales

```python
manifest = PacketManifest(
    name="Flexible Packet",
    version="1.0.0",
    slots=[
        Slot(
            slot_id=1,
            name="Required Document",
            required=True,  # Si falta, el proceso reporta error
            search_strategy=...
        ),
        Slot(
            slot_id=2,
            name="Optional Document",
            required=False,  # Puede faltar sin problema
            search_strategy=...
        )
    ]
)
```

---

### Ejemplo 2: Agregar Metadata Custom

```python
SearchStrategy(
    type="folder_search",
    folder_keywords=["USCIS"],
    file_keywords=["Prima"],
    mode="single",
    metadata={
        "source": "dropbox",
        "priority": "high",
        "category": "legal_docs"
    }
)
```

El campo `metadata` es un dict libre que puedes usar para almacenar info custom.

---

### Ejemplo 3: Combinar Múltiples Estrategias

```python
slots = [
    # Slot 1: Archivo específico (priorizado)
    Slot(
        slot_id=1,
        name="Cover Letter",
        search_strategy=SearchStrategy(
            type="prioritized_search",
            folder_keywords=["Cover"],
            file_keywords_priority=["cover_letter", "letter"],
            mode="single"
        )
    ),

    # Slot 2: Todo un folder (recursivo)
    Slot(
        slot_id=2,
        name="All Evidence",
        search_strategy=SearchStrategy(
            type="recursive_download",
            folder_path=["Evidence"],
            file_keywords=[""],
            mode="multiple"
        )
    ),

    # Slot 3: Contenido generado
    Slot(
        slot_id=3,
        name="Summary Report",
        search_strategy=SearchStrategy(
            type="generated",
            generator="missing_report"
        )
    )
]
```

---

## 🐛 Troubleshooting

### Problema: Slot no encuentra archivos

**Síntoma:**
```
SlotResult(status="missing", error_message="No se encontraron archivos...")
```

**Solución:**
1. Verifica que `folder_keywords` y `file_keywords` sean correctos
2. Revisa los logs: el sistema imprime qué carpetas busca
3. Usa keywords más generales (ej: `["USCIS", "UCIS"]`)

---

### Problema: Orden incorrecto de documentos

**Síntoma:** Los exhibits aparecen en orden diferente al esperado

**Solución:**
Los slots se ordenan por `slot_id`. Asegúrate de que:
```python
slots = [
    Slot(slot_id=1, ...),  # Aparece primero
    Slot(slot_id=2, ...),  # Aparece segundo
    Slot(slot_id=3, ...),  # Aparece tercero
]
```

---

### Problema: PDF corrupto o error al unir

**Síntoma:**
```
❌ PDF Corrupto omitido: file.pdf - Error: ...
```

**Solución:**
1. El sistema omite PDFs corruptos automáticamente
2. Revisa si las imágenes se convirtieron correctamente
3. Verifica que todos los archivos en Dropbox sean válidos

---

## 📚 Recursos Adicionales

- [REFACTOR_PDF_ASSEMBLER.md](./REFACTOR_PDF_ASSEMBLER.md) - Documentación completa del refactor
- [README.md](../README.md) - Documentación general del servicio
- [app/services/vawa_default_manifest.py](../app/services/vawa_default_manifest.py) - Ejemplo de manifest default

---

## 💡 Tips y Best Practices

### 1. Usa keywords flexibles

```python
# ❌ Muy específico
folder_keywords=["USCIS Documents 2024"]

# ✅ Flexible
folder_keywords=["USCIS", "UCIS", "Receipts"]
```

---

### 2. Marca slots opcionales cuando corresponda

```python
# Si el slot PUEDE faltar sin romper el proceso
Slot(
    slot_id=3,
    name="Optional Evidence",
    required=False,  # ✅
    ...
)
```

---

### 3. Usa mode="single" para archivos únicos

```python
# Para "Filed Copy" solo necesitas UNO
SearchStrategy(
    type="prioritized_search",
    mode="single",  # ✅ Detiene en el primero
    ...
)
```

---

### 4. Aprovecha el logging

El sistema loguea cada paso:
```
🔍 Resolviendo Slot 1: Exhibit A – USCIS Documents
✅ Carpeta encontrada: USCIS
⬇️ Descargando: Prima_Facie.pdf
✅ Slot 1 resuelto: 3 archivo(s)
```

---

## 🎓 Preguntas Frecuentes

### ¿Puedo cambiar el orden de los exhibits?

Sí, solo cambia los `slot_id`:

```python
slots = [
    Slot(slot_id=1, name="Evidence"),    # Ahora aparece primero
    Slot(slot_id=2, name="Cover Letter") # Ahora aparece segundo
]
```

---

### ¿Puedo agregar un nuevo exhibit?

Sí, agrega un nuevo Slot:

```python
slots = [
    # ... slots existentes
    Slot(
        slot_id=5,  # Nuevo ID
        name="Exhibit E – New Section",
        required=False,
        search_strategy=...
    )
]
```

---

### ¿Puedo usar este sistema para otros tipos de documentos?

¡Sí! Crea tu propio manifest:

```python
from app.services.slot_orchestrator import SlotBasedOrchestrator

my_manifest = PacketManifest(
    name="My Document Type",
    slots=[...]
)

orchestrator = SlotBasedOrchestrator(manifest=my_manifest)
```

---

### ¿El sistema legacy seguirá funcionando?

Sí, por 3 meses. Usa `use_legacy=true` en el endpoint:

```python
POST /api/v1/generate-packet?use_legacy=true
```

---

## ✅ Checklist para Crear un Manifest

- [ ] Definir todos los slots necesarios
- [ ] Asignar `slot_id` en el orden correcto
- [ ] Especificar si cada slot es `required` o no
- [ ] Elegir la estrategia de búsqueda adecuada
- [ ] Definir keywords flexibles
- [ ] Decidir si incluir `cover_page`
- [ ] Testear con datos reales
- [ ] Documentar el propósito del manifest

---

**¿Necesitas ayuda?** Consulta la documentación completa en [`REFACTOR_PDF_ASSEMBLER.md`](./REFACTOR_PDF_ASSEMBLER.md)
