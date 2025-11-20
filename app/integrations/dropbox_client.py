from __future__ import annotations

from typing import Iterable, Optional

from config.settings import Settings
from integrations.dropbox_handler import DropboxHandler
from integrations.dropbox_token_client import DropboxTokenClient
from logger import get_logger

logger = get_logger(__name__)


class DropboxClient:
    """
    Cliente de alto nivel para Dropbox que maneja autenticación automática
    y operaciones comunes de archivos/carpetas.

    Obtiene tokens automáticamente desde el servicio accesstokendropbox
    e inicializa el DropboxHandler.
    """

    def __init__(
        self,
        handler: Optional[DropboxHandler] = None,
        token_client: Optional[DropboxTokenClient] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """
        Args:
            handler: DropboxHandler ya inicializado (para testing/DI)
            token_client: Cliente de tokens (para testing/DI)
            settings: Settings de la app (para obtener URLs de servicios)
        """
        self.settings = settings or Settings()
        self._handler = handler
        self._token_client = token_client

        # Lazy initialization: solo inicializar handler cuando se necesite
        if self._handler is None and self.settings.dropbox_token_service_url:
            self._initialize_handler()

    def _initialize_handler(self) -> None:
        """Inicializa el handler obteniendo un token fresco del servicio."""
        try:
            if self._token_client is None:
                self._token_client = DropboxTokenClient(
                    service_url=self.settings.dropbox_token_service_url
                )

            # Obtener token usando signature de settings
            token_response = self._token_client.get_token(
                signature=self.settings.dropbox_service_signature,
                service=self.settings.app_name,
            )

            if token_response and token_response.access_token:
                self._handler = DropboxHandler(access_token=token_response.access_token)
                logger.info("DropboxHandler initialized successfully")
            else:
                logger.error("Failed to obtain Dropbox token, handler not initialized")

        except Exception as e:
            logger.error("Error initializing DropboxHandler: %s", e)
            self._handler = None

    @property
    def handler(self) -> Optional[DropboxHandler]:
        """Lazy getter para el handler."""
        if self._handler is None:
            self._initialize_handler()
        return self._handler

    def resolve_shared_link(self, shared_link: str) -> Optional[str]:
        """
        Resuelve un link compartido de Dropbox a su ruta interna.

        Args:
            shared_link: URL del link compartido

        Returns:
            Ruta interna (path_lower) o None si falla
        """
        if not self.handler:
            logger.warning("DropboxHandler not available, cannot resolve link")
            return None
        return self.handler.get_folder_path_from_shared_link(shared_link)

    def list_folder(self, folder_path: str, recursive: bool = False) -> Iterable:
        """
        Lista archivos y carpetas en una ruta de Dropbox.

        Args:
            folder_path: Ruta de la carpeta en Dropbox
            recursive: Si es True, lista recursivamente

        Returns:
            Lista de entries (FileMetadata/FolderMetadata)
        """
        if not self.handler:
            logger.warning("DropboxHandler not available, cannot list folder")
            return []
        return self.handler.list_folder_contents(folder_path, recursive=recursive)

    def download_file(self, remote_path: str, local_folder: str) -> Optional[str]:
        """
        Descarga un archivo de Dropbox.

        Args:
            remote_path: Ruta del archivo en Dropbox
            local_folder: Carpeta local de destino

        Returns:
            Ruta local del archivo descargado o None si falla
        """
        if not self.handler:
            logger.warning("DropboxHandler not available, cannot download file")
            return None
        return self.handler.download_file(remote_path, local_folder)
