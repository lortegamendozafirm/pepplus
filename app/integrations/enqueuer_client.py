"""
Cliente HTTP para interactuar con el servicio enqueuer en GCP.
"""
from __future__ import annotations

import httpx
from typing import Any, Optional

from logger import get_logger

logger = get_logger(__name__)


class EnqueuerClient:
    """
    Cliente para encolar jobs de larga duración en el servicio enqueuer.

    El enqueuer se encarga de:
    - Recibir requests desde Apps Script u otros servicios
    - Encolar jobs pesados (>6 minutos)
    - Llamar al microservicio correspondiente de forma asíncrona
    - Responder rápidamente al cliente

    Uso:
        client = EnqueuerClient(service_url="https://enqueuer-....run.app")
        job_id = client.enqueue_job(
            service_name="pdf-packet-service",
            endpoint="/api/v1/packets/process",
            payload={"client_name": "..."}
        )
    """

    def __init__(self, service_url: str, timeout: float = 10.0):
        """
        Args:
            service_url: URL base del servicio enqueuer (ej: https://enqueuer-....run.app)
            timeout: Timeout en segundos para la request HTTP
        """
        if not service_url:
            raise ValueError("service_url cannot be empty")
        self.service_url = service_url.rstrip('/')
        self.timeout = timeout

    def enqueue_job(
        self,
        service_name: str,
        endpoint: str,
        payload: dict[str, Any],
        priority: str = "normal"
    ) -> Optional[str]:
        """
        Encola un job en el enqueuer.

        Args:
            service_name: Nombre del microservicio destino (ej: "pdf-packet-service")
            endpoint: Endpoint a llamar en el microservicio (ej: "/api/v1/packets/process")
            payload: Datos del job a procesar
            priority: Prioridad del job ("low", "normal", "high")

        Returns:
            job_id si exitoso, None en caso de error
        """
        enqueue_payload = {
            "service": service_name,
            "endpoint": endpoint,
            "payload": payload,
            "priority": priority
        }

        try:
            logger.info("Enqueuing job to %s%s via enqueuer", service_name, endpoint)

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.service_url}/api/v1/jobs/enqueue",
                    json=enqueue_payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

            data = response.json()
            job_id = data.get("job_id")

            if job_id:
                logger.info("Successfully enqueued job: %s", job_id)
            else:
                logger.warning("Enqueue response missing job_id: %s", data)

            return job_id

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error enqueuing job: status=%s body=%s",
                e.response.status_code,
                e.response.text
            )
            return None
        except httpx.RequestError as e:
            logger.error("Network error enqueuing job: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error enqueuing job: %s", e)
            return None

    def get_job_status(self, job_id: str) -> Optional[dict]:
        """
        Consulta el status de un job encolado.

        Args:
            job_id: ID del job a consultar

        Returns:
            dict con status del job, None en caso de error
        """
        try:
            logger.debug("Querying job status: %s", job_id)

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.service_url}/api/v1/jobs/{job_id}",
                )
                response.raise_for_status()

            data = response.json()
            logger.debug("Job status for %s: %s", job_id, data.get("status"))
            return data

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error getting job status: status=%s body=%s",
                e.response.status_code,
                e.response.text
            )
            return None
        except httpx.RequestError as e:
            logger.error("Network error getting job status: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error getting job status: %s", e)
            return None
