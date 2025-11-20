"""
Cliente para obtener tokens de acceso desde el servicio accesstokendropbox en GCP.
"""
from __future__ import annotations

import httpx
from datetime import datetime
from typing import Optional

from logger import get_logger

logger = get_logger(__name__)


class DropboxTokenResponse:
    """Representa la respuesta del servicio de tokens."""

    def __init__(self, access_token: str, expires_at: str, token_type: str, refreshed: bool):
        self.access_token = access_token
        self.expires_at = expires_at
        self.token_type = token_type
        self.refreshed = refreshed

    def is_valid(self) -> bool:
        """Verifica si el token aún es válido basándose en expires_at."""
        try:
            expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(expiry.tzinfo) < expiry
        except Exception as e:
            logger.warning("Error parsing token expiry: %s", e)
            return False


class DropboxTokenClient:
    """
    Cliente HTTP para obtener tokens de acceso desde el servicio accesstokendropbox.

    Uso:
        client = DropboxTokenClient(service_url="https://accesstokendropbox-....run.app/api/v1/token")
        token_response = client.get_token(signature="930xY0dJ0pD", service="pdf-packet-service")
        if token_response:
            access_token = token_response.access_token
    """

    def __init__(self, service_url: str, timeout: float = 10.0):
        """
        Args:
            service_url: URL completa del endpoint de tokens (ej: https://.../api/v1/token)
            timeout: Timeout en segundos para la request HTTP
        """
        if not service_url:
            raise ValueError("service_url cannot be empty")
        self.service_url = service_url
        self.timeout = timeout

    def get_token(self, signature: str, service: str) -> Optional[DropboxTokenResponse]:
        """
        Obtiene un token de acceso desde el servicio.

        Args:
            signature: Firma de autenticación (ej: "930xY0dJ0pD")
            service: Nombre del servicio solicitante (ej: "pdf-packet-service")

        Returns:
            DropboxTokenResponse si exitoso, None en caso de error
        """
        payload = {"signature": signature, "service": service}

        try:
            logger.info("Requesting Dropbox token from %s for service=%s", self.service_url, service)

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.service_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

            data = response.json()
            token_response = DropboxTokenResponse(
                access_token=data["access_token"],
                expires_at=data["expires_at"],
                token_type=data.get("token_type", "bearer"),
                refreshed=data.get("refreshed", False),
            )

            if token_response.is_valid():
                logger.info("Successfully obtained valid Dropbox token (refreshed=%s)", token_response.refreshed)
            else:
                logger.warning("Obtained token may be expired or invalid")

            return token_response

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error obtaining Dropbox token: status=%s body=%s", e.response.status_code, e.response.text)
            return None
        except httpx.RequestError as e:
            logger.error("Network error obtaining Dropbox token: %s", e)
            return None
        except KeyError as e:
            logger.error("Missing expected field in token response: %s", e)
            return None
        except Exception as e:
            logger.error("Unexpected error obtaining Dropbox token: %s", e)
            return None
