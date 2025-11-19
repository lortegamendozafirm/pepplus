# VAWA Packet Assembler Service

🤖📄 Microservicio de automatización robótica (RPA) basado en **FastAPI** y **Google Cloud Run**.  
Su función es ensamblar expedientes legales complejos para solicitudes de visa **VAWA**, extrayendo evidencia desde **Dropbox**, procesándola y entregando un PDF final en **Google Drive**.

Este servicio está diseñado para ser consumido por **Google Apps Script** u otros clientes HTTP.

---

## 🚀 Características principales

- **Arquitectura de Microservicios**  
  Se integra con un servicio externo (`AccessTokenDropbox`) para obtener tokens de Dropbox siempre válidos.

- **Búsqueda Inteligente ("Fuzzy Search")**  
  Encuentra carpetas y archivos incluso si los nombres varían ligeramente  
  (ej: `Filed Copy` vs `FILE-COPY`).

- **Conversión Automática**  
  Detecta imágenes (`.jpg`, `.png`, etc.) y las convierte a **PDF** automáticamente.

- **Ensamblaje Estructurado**  
  Genera un PDF maestro con portadas y separadores (Exhibits) siguiendo reglas de negocio legales estrictas.

- **Reporte de Fallos**  
  Genera un reporte PDF interno si faltan documentos obligatorios y actualiza el estado en **Google Sheets**.

- **Google Cloud Native**  
  Optimizado para **Cloud Run** con logging estructurado y manejo de secretos.

---

## 🛠️ Arquitectura del proyecto

```plaintext
preensamblado-service/
├── app/
│   ├── api/v1/packet.py       # Endpoint principal
│   ├── integrations/          # Clientes (Dropbox, Google, TokenService)
│   ├── services/              # Lógica de negocio (Orquestador, PDF Engine)
│   ├── utils/                 # Logger y helpers
│   ├── config.py              # Configuración global (Pydantic)
│   └── main.py                # Inicialización de FastAPI
├── Dockerfile                 # Configuración para Cloud Run
├── requirements.txt           # Dependencias
└── .env                       # Variables de entorno (local)
````

---

## 📋 Prerrequisitos

* **Python 3.10+** instalado.
* **Google Cloud SDK (`gcloud`)** instalado y configurado.
* **Cuenta de servicio de Google (JSON)** con permisos para:

  * Google Drive API
  * Google Sheets API
* **Servicio de Tokens desplegado** (`AccessTokenDropbox`):

  * URL pública del servicio
  * Firma/secret compartido

---

## ⚙️ Configuración (variables de entorno)

El servicio se configura mediante variables de entorno (o un archivo `.env` en local).

| Variable                    | Descripción                            | Ejemplo                           |
| --------------------------- | -------------------------------------- | --------------------------------- |
| `APP_NAME`                  | Nombre del servicio                    | `VAWA Assembler`                  |
| `LOG_LEVEL`                 | Nivel de detalle de logs               | `INFO` o `DEBUG`                  |
| `GOOGLE_CREDENTIALS_FILE`   | Ruta al JSON de credenciales de Google | `credentials.json`                |
| `TOKEN_SERVICE_URL`         | URL del microservicio de tokens        | `https://...run.app/api/v1/token` |
| `TOKEN_SERVICE_SIGNATURE`   | Firma (secret) compartida              | `tu-api-secret-key`               |
| `TOKEN_SERVICE_CLIENT_NAME` | Nombre lógico de este cliente          | `vawa_assembler`                  |

---

## 💻 Instalación y ejecución local

### 1. Clonar y preparar entorno

```bash
# Clonar repositorio (si aplica)
git clone <repo-url>
cd preensamblado-service

# Crear entorno virtual
python -m venv venv
source venv/bin/activate      # Mac/Linux
# venv\Scripts\activate       # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar credenciales

1. Coloca tu archivo `credentials.json` (Service Account de Google) en la **raíz del proyecto**.
2. Crea un archivo `.env` en la raíz con las variables mencionadas en la sección anterior.

### 3. Ejecutar servidor

```bash
uvicorn app.main:app --reload
```

El servicio estará disponible en:

* Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## ☁️ Despliegue en Google Cloud Run

### 1. Construir y subir imagen

```bash
export PROJECT_ID="tu-proyecto-gcp"
export IMAGE_NAME="vawa-assembler"

gcloud builds submit --tag gcr.io/$PROJECT_ID/$IMAGE_NAME
```

### 2. Desplegar servicio

```bash
gcloud run deploy $IMAGE_NAME \
  --image gcr.io/$PROJECT_ID/$IMAGE_NAME \
  --platform managed \
  --region us-central1 \
  --memory 1Gi \
  --timeout 300s \
  --set-env-vars "TOKEN_SERVICE_URL=https://tusservicio.run.app/api/v1/token,TOKEN_SERVICE_SIGNATURE=tu_secreto,TOKEN_SERVICE_CLIENT_NAME=vawa_client" \
  --service-account "tu-service-account@tu-proyecto.iam.gserviceaccount.com"
```

**Nota:** Asegúrate de aumentar el `--timeout` (ej. `300s` o `600s`) ya que el procesamiento de PDFs pesados puede tardar más que el valor por defecto (60s).

---

## 🔗 Uso de la API

### Endpoint principal

* **Método:** `POST`
* **Path:** `/api/v1/generate-packet`
* **Uso típico:** llamado desde **Google Apps Script** u otros servicios.

### Headers

```http
Content-Type: application/json
```

### Body (JSON request)

```json
{
  "client_name": "Juan Perez",
  "dropbox_url": "https://www.dropbox.com/sh/Ejemplo...",
  "drive_parent_folder_id": "1QBrlti0mpJ_XFWif2...",
  "sheet_output_config": {
    "spreadsheet_id": "1UY6aPIkfap...",
    "worksheet_name": "PREENSAMBLADO",
    "folder_link_cell": "E5",
    "missing_files_cell": "F5",
    "pdf_link_cell": "G5"
  }
}
```

📝 **Nota:** No es necesario enviar `dropbox_token`.
El servicio lo obtiene automáticamente del microservicio `AccessTokenDropbox`.

### Respuesta exitosa (`200 OK`)

```json
{
  "status": "success",
  "message": "Paquete generado correctamente.",
  "drive_folder_link": "https://drive.google.com/...",
  "final_pdf_link": "https://drive.google.com/...",
  "missing_files": []
}
```

---

## 🧩 Lógica de negocio (Exhibits)

El orquestador sigue estrictamente el siguiente flujo de ensamblaje:

1. **Validación inicial**

   * Verifica que existan las carpetas: `USCIS`, `VAWA` y `7` (Folder 7).
   * Si falta alguna carpeta crítica, detiene el proceso y genera reporte.

2. **Exhibit 1 – USCIS**

   * Busca documentos como:

     * Prima Facie
     * Transfer Notices
     * Otros avisos relevantes de USCIS

3. **Exhibit 2 – Faltantes**

   * Genera un resumen (hoja/listado) con lo que **no se encontró**.
   * Este listado se incluye en el paquete y/o se escribe en Google Sheets.

4. **Exhibit 3 – Evidence**

   * Descarga recursivamente todo el contenido de la carpeta `VAWA/Evidence`.
   * Convierte imágenes a PDF y las ensambla en el orden definido.

5. **Exhibit 4 – Filed Copy**

   * Busca el documento maestro (ej. filed packet) en la carpeta `7`.

---

## 📞 Soporte y troubleshooting

* Para problemas con **tokens de Dropbox**:

  * Revisa los logs del servicio `AccessTokenDropbox`.

* Para problemas de ensamblaje de paquetes:

  * Revisa **Cloud Logging** filtrando por el nombre del servicio (ej. `vawa_service` o el `APP_NAME` configurado).
