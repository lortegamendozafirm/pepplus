# PDF Packet Service

Microservicio en Python 3.11 + FastAPI para ensamblar un PDF final a partir de múltiples PDFs obtenidos de Dropbox, con reporte de progreso en Google Sheets y desplegable en Google Cloud Run.

## 📋 Características

- ✅ **Ensamblado de PDFs**: Combina múltiples PDFs en orden usando `pypdf`
- ✅ **Sistema de Slots**: Manifest flexible para definir qué documentos incluir
- ✅ **Resolución inteligente**: Mapea archivos de Dropbox a slots usando folder hints y patrones
- ✅ **Integración Dropbox**: Descarga automática desde carpetas compartidas
- ✅ **Reporte en Google Sheets**: Actualizaciones de progreso en tiempo real
- ✅ **Arquitectura por capas**: Domain, Services, Integrations, API
- ✅ **Enqueuer integration**: Soporte para jobs de larga duración

## 🏗️ Arquitectura

```
app/
├── domain/          # Modelos puros y reglas de negocio
│   ├── slot.py           # Definición de Slot y SlotMeta
│   ├── manifest.py       # Manifest con validación y máscaras
│   ├── packet.py         # Packet, SheetOutputConfig, SheetPosition
│   └── slot_resolution.py # SlotResolver con lógica de mapeo
├── services/        # Orquestación y lógica de aplicación
│   ├── packet_service.py    # Servicio principal
│   └── progress_reporter.py # Reporte de progreso
├── integrations/    # Integraciones externas
│   ├── dropbox_handler.py      # Operaciones de Dropbox API
│   ├── dropbox_client.py       # Cliente de alto nivel
│   ├── dropbox_token_client.py # Cliente de tokens
│   ├── sheets_client.py        # Cliente de Google Sheets API v4
│   └── enqueuer_client.py      # Cliente del servicio enqueuer
├── pdf/             # Capa de ensamblado de PDFs
│   └── pdf_assembler.py # merge_pdfs_in_order()
├── api/             # FastAPI routers y schemas
│   ├── routes.py    # Endpoints /enqueue y /process
│   └── schemas.py   # Pydantic models
├── config/          # Configuración
│   └── settings.py  # Settings con pydantic-settings
└── logger.py        # Logging configurado
```

### 1) Vista general (flujo funcional)

```mermaid
sequenceDiagram
    autonumber
    participant U as Cliente (Apps Script/Thunder)
    participant API as FastAPI (Cloud Run)
    participant ENQ as Servicio Enqueuer
    participant CFG as config/settings.py
    participant PKT as services/packet_service.py
    participant DBX as Dropbox API
    participant TOK as Token Service
    participant RES as domain/slot_resolution.py
    participant PDF as pdf/pdf_assembler.py
    participant SHT as Google Sheets API
    participant GCS as Cloud Storage (futuro)

    Note over U,API: POST /api/v1/packets/enqueue
    U->>API: {client_name, dropbox_url, manifest, sheet_config}

    Note over API,CFG: 1) Validación y configuración
    API->>CFG: Cargar settings (temp_dir, credentials, enqueuer_url)
    CFG-->>API: Settings válidos

    Note over API,PKT: 2) Construcción del dominio
    API->>API: build_domain_packet() (routes.py)
    API->>PKT: enqueue_packet(packet)

    Note over PKT,ENQ: 3) Encolado asíncrono
    PKT->>ENQ: POST /enqueue {service_name, endpoint, payload}
    ENQ-->>PKT: job_id
    PKT-->>API: job_id
    API-->>U: 202 Accepted {status: "enqueued", job_id}

    Note over ENQ,API: 4) Procesamiento asíncrono (llamado por enqueuer)
    ENQ->>API: POST /api/v1/packets/process {packet}
    API->>PKT: process_packet(packet)

    Note over PKT,SHT: 5) Reporte inicial (10%)
    PKT->>SHT: write_status("10% - Resolviendo archivos")

    Note over PKT,TOK: 6) Obtener token de Dropbox
    PKT->>DBX: resolve_shared_link(dropbox_url)
    DBX->>TOK: Solicitar access token
    TOK-->>DBX: Access token válido
    DBX-->>PKT: folder_path interno

    Note over PKT,DBX: 7) Listar archivos en carpeta
    PKT->>DBX: list_folder(folder_path, recursive=True)
    DBX-->>PKT: files_index (lista de paths)

    Note over PKT,RES: 8) Resolución de slots
    PKT->>RES: resolve(manifest.slots, files_index)
    RES->>RES: Filtrar por folder_hint, filename_patterns
    RES-->>PKT: SlotResolution[] (matched_paths)

    alt Faltan slots requeridos
        PKT->>SHT: write_status("ERROR - Faltan slots requeridos")
        PKT-->>API: {status: "error", missing_required: [...]}
        API-->>ENQ: 200 OK (error response)
    else Todos los slots OK
        Note over PKT,SHT: 9) Reporte descarga (40%)
        PKT->>SHT: write_status("40% - Descargando archivos")

        Note over PKT,DBX: 10) Descarga de PDFs
        loop Para cada slot resuelto
            PKT->>DBX: download_file(candidate_path, temp_dir)
            DBX-->>PKT: local_path
        end

        Note over PKT,SHT: 11) Reporte ensamblado (70%)
        PKT->>SHT: write_status("70% - Ensamblando PDF")

        Note over PKT,PDF: 12) Ensamblado de PDFs
        PKT->>PDF: merge_pdfs_in_order(local_paths[], output_path)
        PDF-->>PKT: output_path (temp file)

        Note over PKT,SHT: 13) Reporte final (100%)
        PKT->>SHT: write_status("100% - Completado")
        PKT->>SHT: write_output_url(output_path)

        Note over PKT,GCS: 14) (Futuro) Subir a Cloud Storage
        PKT->>GCS: upload_file(output_path)
        GCS-->>PKT: public_url

        PKT-->>API: {status: "ok", output_path, mask}
        API-->>ENQ: 200 OK
    end
```

### 2) Vista técnica (módulos y dependencias)

```mermaid
graph LR
  %% --- Capas internas ---
  subgraph API["Capa API"]
    M[[app/main.py]]
    RT[[app/api/routes.py]]
    SCH[[app/api/schemas.py]]
  end

  subgraph SVC["Servicios"]
    PKT[[app/services/packet_service.py]]
    PRG[[app/services/progress_reporter.py]]
  end

  subgraph DOM["Dominio"]
    SL[[app/domain/slot.py]]
    MAN[[app/domain/manifest.py]]
    PAC[[app/domain/packet.py]]
    RES[[app/domain/slot_resolution.py]]
  end

  subgraph INT["Integraciones"]
    DBXC[[app/integrations/dropbox_client.py]]
    DBXH[[app/integrations/dropbox_handler.py]]
    DBXT[[app/integrations/dropbox_token_client.py]]
    SHC[[app/integrations/sheets_client.py]]
    ENQ[[app/integrations/enqueuer_client.py]]
  end

  subgraph PDF_["PDF"]
    ASM[[app/pdf/pdf_assembler.py]]
  end

  subgraph CORE["Core"]
    CFG[[app/config/settings.py]]
    LOG[[app/logger.py]]
  end

  %% Relaciones internas
  M --> RT
  RT --> SCH
  RT --> PKT
  RT --> ENQ
  RT --> DBXC
  RT --> SHC
  RT --> CFG

  PKT --> RES
  PKT --> MAN
  PKT --> PAC
  PKT --> DBXC
  PKT --> SHC
  PKT --> ENQ
  PKT --> PRG
  PKT --> ASM

  PRG --> SHC

  MAN --> SL
  PAC --> MAN
  RES --> SL

  DBXC --> DBXH
  DBXC --> DBXT
  DBXH --> DBXT

  %% Core dependencies
  RT --> LOG
  PKT --> LOG
  DBXC --> LOG
  DBXH --> LOG
  SHC --> LOG
  ENQ --> LOG
  PRG --> LOG

  M --> CFG
  PKT --> CFG
  DBXH --> CFG
  SHC --> CFG

  %% --- Servicios externos ---
  subgraph EXT["Servicios Externos"]
    CR[[Cloud Run]]
    SA[[Service Account]]
    DBX_API[(Dropbox API)]
    TOK_SVC[(Token Service)]
    SHT_API[(Google Sheets API)]
    ENQ_SVC[(Enqueuer Service)]
    GCS[(Cloud Storage - futuro)]
  end

  %% Conexiones externas
  M -. despliegue .-> CR
  CR -. usa .-> SA

  DBXH --> DBX_API
  DBXT --> TOK_SVC
  SHC --> SHT_API
  ENQ --> ENQ_SVC

  SA -. credenciales .- SHC
  SA -. scopes .- SHT_API
  TOK_SVC -. access_token .- DBX_API

  %% Estilos
  classDef api fill:#e3f2fd,stroke:#1e88e5,color:#0d47a1
  classDef svc fill:#e8f5e9,stroke:#43a047,color:#1b5e20
  classDef dom fill:#fff8e1,stroke:#f9a825,color:#f57f17
  classDef int fill:#ede7f6,stroke:#5e35b1,color:#311b92
  classDef pdf fill:#f1f8e9,stroke:#7cb342,color:#33691e
  classDef core fill:#f3e5f5,stroke:#8e24aa,color:#4a148c
  classDef ext fill:#eceff1,stroke:#607d8b,color:#37474f

  class M,RT,SCH api
  class PKT,PRG svc
  class SL,MAN,PAC,RES dom
  class DBXC,DBXH,DBXT,SHC,ENQ int
  class ASM pdf
  class CFG,LOG core
  class CR,SA,DBX_API,TOK_SVC,SHT_API,ENQ_SVC,GCS ext
```

## 🚀 Endpoints

### `POST /api/v1/packets/enqueue`

Encola un paquete para procesamiento asíncrono (respuesta inmediata).

**Request:**
```json
{
  "client_name": "Jane Doe",
  "dropbox_url": "https://www.dropbox.com/scl/fo/...",
  "sheet_output_config": {
    "spreadsheet_id": "1abc...",
    "sheet_name": "VAWA"
  },
  "sheet_position": {
    "row": 12,
    "col_output": 5,
    "col_status": 6
  },
  "manifest": [
    {
      "slot": 1,
      "name": "Exhibit A – Cover",
      "required": true,
      "folder_hint": "EXHIBIT 1",
      "filename_patterns": ["cover*.pdf", "petition.pdf"],
      "tags": ["important"]
    }
  ]
}
```

**Response (202 Accepted):**
```json
{
  "status": "enqueued",
  "message": "Job enqueued successfully for client Jane Doe",
  "job_id": "job-abc123"
}
```

### `POST /api/v1/packets/process`

Procesa un paquete de forma síncrona (usado por el enqueuer).

**Response (200 OK):**
```json
{
  "status": "completed",
  "message": "Processed packet for Jane Doe. Output: /tmp/packet_Jane_Doe.pdf",
  "job_id": null
}
```

## ⚙️ Configuración

### Variables de entorno (.env)

```bash
# Service name
PACKET_APP_NAME=pdf-packet-service

# Dropbox integration
PACKET_DROPBOX_TOKEN_SERVICE_URL=https://accesstokendropbox-xxx.run.app/api/v1/token
PACKET_DROPBOX_SERVICE_SIGNATURE=930xY0dJ0pD

# Google Sheets integration
PACKET_GOOGLE_CREDENTIALS_PATH=/path/to/service-account.json

# GCP configuration
PACKET_GCP_PROJECT_ID=my-project-id

# Storage
PACKET_TEMP_DIR=/tmp

# Enqueuer integration (opcional)
PACKET_ENQUEUER_SERVICE_URL=https://enqueuer-xxx.run.app
```

### Service Account de Google

1. Crear service account en GCP Console
2. Habilitar Google Sheets API
3. Descargar JSON de credenciales
4. Compartir las Sheets con el email del service account

## 📦 Instalación

### Local

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# Ejecutar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Abrir documentación interactiva
# http://localhost:8000/docs
```

### Docker

```bash
# Build
docker build -t pdf-packet-service .

# Run
docker run --env-file .env -p 8000:8000 pdf-packet-service
```

## ☁️ Despliegue en Cloud Run

### Con gcloud CLI

```bash
# Configurar proyecto
export PROJECT_ID=my-project-id
gcloud config set project $PROJECT_ID

# Build imagen
gcloud builds submit --tag gcr.io/$PROJECT_ID/pdf-packet-service

# Deploy a Cloud Run
gcloud run deploy pdf-packet-service \
  --image gcr.io/$PROJECT_ID/pdf-packet-service \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --timeout 3600 \
  --memory 2Gi \
  --set-env-vars PACKET_DROPBOX_TOKEN_SERVICE_URL=https://... \
  --set-env-vars PACKET_DROPBOX_SERVICE_SIGNATURE=930xY0dJ0pD \
  --set-env-vars PACKET_GOOGLE_CREDENTIALS_PATH=/secrets/credentials.json

# IMPORTANTE: Montar secret con service account credentials
gcloud run services update pdf-packet-service \
  --update-secrets /secrets/credentials.json=google-credentials:latest
```

## 🔧 Sistema de Slots

### ¿Qué es un Slot?

Un **slot** representa un documento esperado en el PDF final:

```python
{
  "slot": 1,              # Posición en el PDF (1, 2, 3, ...)
  "name": "Cover Page",   # Nombre descriptivo
  "required": true,       # ¿Es obligatorio?
  "folder_hint": "EXHIBIT 1",  # Carpeta donde buscar
  "filename_patterns": ["cover*.pdf", "petition.pdf"],  # Patrones
  "tags": ["important"]   # Etiquetas libres
}
```

### Lógica de Resolución

El `SlotResolver` mapea slots a archivos reales:

1. **Filtro por carpeta**: Si `folder_hint` está presente, busca en carpetas que contengan ese texto
2. **Filtro por patrones**: Si `filename_patterns` está presente, aplica wildcards o regex
3. **Filtro por extensión**: Solo archivos `.pdf`
4. **Selección**: Toma el primer candidato encontrado

**Ejemplo:**

```
Dropbox structure:
  /EXHIBIT 1/
    cover.pdf         ← Match!
    petition.pdf
  /EXHIBIT 2/
    abuse_doc.pdf

Slot:
  slot=1, folder_hint="EXHIBIT 1", patterns=["cover*.pdf"]

Resolution:
  ✅ Match: /EXHIBIT 1/cover.pdf
```

### Patrones soportados

- **Literal**: `"petition.pdf"` → busca "petition" en el nombre
- **Wildcard**: `"petition*.pdf"` → petition_v1.pdf, petition_final.pdf
- **Regex**: `"regex:petition_[0-9]+\\.pdf"` → petition_1.pdf, petition_2.pdf

## 🔄 Flujo de Integración con Enqueuer

```
┌─────────────┐      ┌─────────────┐      ┌──────────────────┐
│ Apps Script │ ───> │  Enqueuer   │ ───> │  PDF Packet Svc  │
└─────────────┘      └─────────────┘      └──────────────────┘
       │                    │                       │
       │ POST /enqueue      │ POST /process         │
       │                    │                       │
       └──── job_id ────────┘                       │
                                                     │
                           ┌─────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐      ┌────────────────┐
                    │   Dropbox    │◄─────┤ Google Sheets  │
                    │ (Descargas)  │      │  (Progreso)    │
                    └──────────────┘      └────────────────┘
```

### Ejemplo de progreso reportado

Durante `process_packet()`, el servicio actualiza la celda de status:

```
10% - Resolviendo archivos
40% - Descargando archivos
70% - Ensamblando PDF
100% - Completado
```

## 📝 Ejemplo de Manifest VAWA

```json
{
  "manifest": [
    {
      "slot": 1,
      "name": "Exhibit A – Cover",
      "required": true,
      "folder_hint": "EXHIBIT 1",
      "filename_patterns": ["cover.pdf"]
    },
    {
      "slot": 2,
      "name": "Exhibit A – Petition",
      "required": true,
      "folder_hint": "EXHIBIT 1",
      "filename_patterns": ["petition*.pdf"]
    },
    {
      "slot": 3,
      "name": "Exhibit B – Evidence",
      "required": false,
      "folder_hint": "EXHIBIT 2"
    },
    {
      "slot": 4,
      "name": "Exhibit C – Police Report",
      "required": true,
      "folder_hint": "EXHIBIT 3",
      "filename_patterns": ["police*.pdf", "rap_sheet.pdf"]
    },
    {
      "slot": 5,
      "name": "Exhibit D – GMC Records",
      "required": true,
      "folder_hint": "EXHIBIT 4/GMC"
    }
  ]
}
```

## 🐛 Troubleshooting

### Error: "DropboxHandler not available"
- Verificar que `PACKET_DROPBOX_TOKEN_SERVICE_URL` esté configurado
- Verificar que el servicio `accesstokendropbox` esté corriendo
- Verificar la firma `PACKET_DROPBOX_SERVICE_SIGNATURE`

### Error: "SheetsClient service not initialized"
- Verificar que `PACKET_GOOGLE_CREDENTIALS_PATH` apunte al JSON válido
- Verificar que el service account tenga permisos en la Sheet
- Habilitar Google Sheets API en GCP Console

### Error: "Failed to resolve Dropbox shared link"
- Verificar que la URL sea un link compartido válido (`/scl/fo/...`)
- Para cuentas de equipo, asegurar que el token tenga acceso al namespace correcto

### PDFs corruptos
- El servicio usa `pypdf` con `strict=False` para PDFs problemáticos
- Si persiste, considerar migrar a `pikepdf` (requiere cambios en `pdf_assembler.py`)

## 📚 Estado del proyecto

### ✅ Completado

- Arquitectura por capas limpia
- Integración completa con Dropbox (handler + token service)
- SlotResolver funcional con folder hints y patrones
- Google Sheets client con API v4
- ProgressReporter integrado en el flujo
- Cliente HTTP para servicio enqueuer
- Manejo robusto de errores en endpoints
- Documentación completa

### 🚧 Próximos pasos

- [ ] Subir PDF final a Google Cloud Storage o Google Drive
- [ ] Implementar retry logic para descargas fallidas
- [ ] Agregar telemetría (Cloud Logging, Cloud Trace)
- [ ] Tests unitarios y de integración
- [ ] Documentación de manifiestos por tipo de caso (VAWA, asylum, etc.)
- [ ] Soporte para otros proveedores de storage (Google Drive, AWS S3)

## 📄 Licencia

Este proyecto es privado y de uso interno.
