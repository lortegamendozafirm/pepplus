# Checklist de Migración al Sistema de Slots

**Guía paso a paso para migrar del sistema legacy al nuevo sistema slot-based**

---

## 📋 Pre-Migración

### 1. Verificar Entorno

- [ ] Servidor de desarrollo configurado
- [ ] Acceso a logs (Cloud Logging o local)
- [ ] Credenciales de Google/Dropbox funcionando
- [ ] Base de datos de prueba lista (si aplica)

### 2. Revisar Documentación

- [ ] Leer [`REFACTOR_PDF_ASSEMBLER.md`](./REFACTOR_PDF_ASSEMBLER.md)
- [ ] Revisar [`SLOT_SYSTEM_GUIDE.md`](./SLOT_SYSTEM_GUIDE.md)
- [ ] Entender diferencias entre legacy y slot-based

---

## 🧪 Testing en Desarrollo

### 3. Tests Locales

#### Test 1: Sistema Nuevo (Default)

```bash
curl -X POST "http://localhost:8000/api/v1/generate-packet" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Test Client",
    "dropbox_url": "https://www.dropbox.com/...",
    "drive_parent_folder_id": "1QBrlti0mpJ_..."
  }'
```

**Resultado esperado:**
- ✅ Status 200
- ✅ Logs muestran: "Usando orquestador SLOT-BASED"
- ✅ PDF generado correctamente
- ✅ Estructura de slots en orden

---

#### Test 2: Sistema Legacy

```bash
curl -X POST "http://localhost:8000/api/v1/generate-packet?use_legacy=true" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Test Client",
    "dropbox_url": "https://www.dropbox.com/...",
    "drive_parent_folder_id": "1QBrlti0mpJ_..."
  }'
```

**Resultado esperado:**
- ✅ Status 200
- ✅ Logs muestran: "Usando orquestador LEGACY"
- ✅ PDF generado correctamente
- ✅ Mismo resultado que sistema nuevo

---

#### Test 3: Comparar Salidas

- [ ] Descargar PDF generado por nuevo sistema
- [ ] Descargar PDF generado por legacy
- [ ] Comparar:
  - [ ] Orden de exhibits
  - [ ] Contenido de cada exhibit
  - [ ] Portadas
  - [ ] Reporte de faltantes

**Checklist de Comparación:**
```
✓ Exhibit A (USCIS) - mismo contenido
✓ Exhibit B (Faltantes) - mismo reporte
✓ Exhibit C (Evidence) - mismo orden
✓ Exhibit D (Filed Copy) - mismo archivo
```

---

### 4. Tests de Edge Cases

#### Test 4: Carpeta sin USCIS

```json
{
  "client_name": "Missing USCIS Test",
  "dropbox_url": "URL_SIN_CARPETA_USCIS"
}
```

**Resultado esperado:**
- ✅ Sistema reporta error claro
- ✅ Slot 1 marcado como "missing"
- ✅ Google Sheet actualizado con faltantes

---

#### Test 5: Todo Faltante

```json
{
  "client_name": "Empty Folder Test",
  "dropbox_url": "URL_CARPETA_VACIA"
}
```

**Resultado esperado:**
- ✅ Error claro de validación
- ✅ Reporte con TODOS los slots faltantes
- ✅ No se genera PDF final

---

#### Test 6: Imágenes Mezcladas

```json
{
  "client_name": "Images Test",
  "dropbox_url": "URL_CON_JPG_Y_PDF"
}
```

**Resultado esperado:**
- ✅ Imágenes convertidas a PDF
- ✅ PDF final incluye ambos tipos
- ✅ Logs muestran: "🖼️ Convirtiendo imágenes..."

---

## 🚀 Despliegue Staging

### 5. Deploy a Staging

```bash
# Build imagen
gcloud builds submit --tag gcr.io/$PROJECT_ID/vawa-assembler:slot-v2

# Deploy a staging
gcloud run deploy vawa-assembler-staging \
  --image gcr.io/$PROJECT_ID/vawa-assembler:slot-v2 \
  --platform managed \
  --region us-central1 \
  --memory 1Gi \
  --timeout 300s \
  --set-env-vars "..."
```

- [ ] Deploy exitoso
- [ ] Health check pasa (`GET /`)
- [ ] Logs accesibles en Cloud Logging

---

### 6. Tests en Staging

#### Test Real con Cliente de Prueba

```bash
curl -X POST "https://vawa-assembler-staging-XXX.run.app/api/v1/generate-packet" \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```

**Checklist:**
- [ ] Cliente procesado correctamente
- [ ] Drive folder creado
- [ ] PDF subido a Drive
- [ ] Google Sheet actualizado
- [ ] No errores en logs

---

### 7. Monitoreo de Performance

Revisar métricas en Cloud Logging:

```
🚀 [RUN ID: abc123] Iniciando proceso SLOT-BASED para: Test Client
🔍 Resolviendo Slot 1: Exhibit A
✅ Slot 1 resuelto: 3 archivo(s)
...
✅ Proceso completado. Slots exitosos: 4/4
```

**Checklist:**
- [ ] Tiempo de respuesta < 2 minutos
- [ ] No memory errors
- [ ] Todos los slots resueltos
- [ ] PDF final generado

---

## 🎯 Despliegue Producción

### 8. Comunicación

- [ ] Notificar al equipo del cambio
- [ ] Enviar email a stakeholders
- [ ] Documentar en Wiki/Confluence

**Template de Email:**

```
Asunto: Actualización del Sistema de Ensamblado VAWA

Hola equipo,

Hemos implementado una mejora importante en el sistema de ensamblado
de paquetes VAWA. El nuevo sistema basado en "slots" es:

✅ Más flexible y configurable
✅ Más fácil de extender
✅ Mejor manejo de errores

El sistema legacy sigue disponible por compatibilidad usando el
parámetro ?use_legacy=true.

Documentación: [link]
Preguntas: [contacto]

Saludos,
[Tu nombre]
```

---

### 9. Feature Flag (Opcional)

Si usas feature flags:

```python
# app/config.py
USE_SLOT_BASED_ORCHESTRATOR = os.getenv("USE_SLOT_SYSTEM", "true").lower() == "true"

# app/api/v1/packet.py
if settings.USE_SLOT_BASED_ORCHESTRATOR and not use_legacy:
    orchestrator = SlotBasedOrchestrator()
else:
    orchestrator = PacketOrchestrator()
```

---

### 10. Deploy a Producción

```bash
# Tag como stable
gcloud container images add-tag \
  gcr.io/$PROJECT_ID/vawa-assembler:slot-v2 \
  gcr.io/$PROJECT_ID/vawa-assembler:stable

# Deploy a producción
gcloud run deploy vawa-assembler-prod \
  --image gcr.io/$PROJECT_ID/vawa-assembler:stable \
  --platform managed \
  --region us-central1
```

- [ ] Deploy exitoso
- [ ] Health check verde
- [ ] No alertas de error

---

## 📊 Post-Migración

### 11. Monitoreo (Primera Semana)

**Revisar diariamente:**

```bash
# Cloud Logging query
resource.type="cloud_run_revision"
resource.labels.service_name="vawa-assembler-prod"
textPayload=~"SLOT-BASED"
severity >= "WARNING"
```

**Checklist Diario:**
- [ ] No errores críticos
- [ ] Tasa de éxito > 95%
- [ ] Tiempo de respuesta estable
- [ ] No quejas de usuarios

---

### 12. Análisis de Logs

Buscar patrones:

```bash
# Contar uso de legacy vs slot-based
grep "Usando orquestador LEGACY" logs.txt | wc -l
grep "Usando orquestador SLOT-BASED" logs.txt | wc -l
```

**Objetivo:** > 95% usando slot-based

---

### 13. Feedback del Equipo

- [ ] Encuesta a usuarios internos
- [ ] Review de tickets de soporte
- [ ] Reunión de retrospectiva

**Preguntas:**
1. ¿Notaron alguna diferencia?
2. ¿Hubo problemas con clientes específicos?
3. ¿Los reportes de faltantes son más claros?

---

## 🔧 Rollback Plan

### Si algo sale mal:

#### Rollback Inmediato (< 5 min)

```bash
# Volver a imagen anterior
gcloud run deploy vawa-assembler-prod \
  --image gcr.io/$PROJECT_ID/vawa-assembler:legacy-stable
```

---

#### Rollback con Feature Flag (< 1 min)

```bash
# Cambiar variable de entorno
gcloud run services update vawa-assembler-prod \
  --set-env-vars "USE_SLOT_SYSTEM=false"
```

---

#### Forzar Legacy en Endpoint (0 min)

Los clientes pueden forzar legacy:

```bash
POST /api/v1/generate-packet?use_legacy=true
```

---

## ✅ Criterios de Éxito

La migración es exitosa si:

- ✅ Tasa de éxito > 95% (igual o mejor que legacy)
- ✅ Tiempo de respuesta < 2x del legacy
- ✅ Cero quejas de usuarios
- ✅ Reportes de faltantes más claros
- ✅ Logs sin errores críticos
- ✅ Equipo satisfecho con el cambio

---

## 📅 Timeline Sugerido

| Fase | Duración | Actividades |
|------|----------|-------------|
| **Fase 1: Testing** | 1 semana | Tests locales y comparación |
| **Fase 2: Staging** | 1 semana | Deploy y tests en staging |
| **Fase 3: Producción** | 1 día | Deploy a producción |
| **Fase 4: Monitoreo** | 1 mes | Monitoreo activo |
| **Fase 5: Deprecación Legacy** | 2 meses | Comunicar deprecación |
| **Fase 6: Limpieza** | 1 semana | Eliminar código legacy |

**Total:** ~4 meses para migración completa y limpieza

---

## 🆘 Contactos

**Desarrolladores:**
- Honey Maldonado - [email]

**Soporte:**
- [Canal de Slack]
- [Email de soporte]

**Documentación:**
- [REFACTOR_PDF_ASSEMBLER.md](./REFACTOR_PDF_ASSEMBLER.md)
- [SLOT_SYSTEM_GUIDE.md](./SLOT_SYSTEM_GUIDE.md)

---

## 📝 Log de Migración

**Fecha:** _____________
**Responsable:** _____________

### Checklist Final

- [ ] Todos los tests pasaron
- [ ] Deploy a producción exitoso
- [ ] Monitoreo configurado
- [ ] Equipo notificado
- [ ] Documentación actualizada
- [ ] Rollback plan listo
- [ ] Contactos documentados

**Notas adicionales:**
_______________________________________
_______________________________________
_______________________________________

---

**✅ Migración completada exitosamente**

_Firma:_ _______________ _Fecha:_ _______________
