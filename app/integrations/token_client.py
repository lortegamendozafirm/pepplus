# app/integrations/token_client.py
import requests
from typing import Optional
from app.config import settings
from app.utils.logger import logger

class TokenServiceClient:
    """
    Cliente para comunicarse con el microservicio AccessTokenDropbox.
    """
    
    def __init__(self):
        self.service_url = settings.TOKEN_SERVICE_URL
        self.signature = settings.TOKEN_SERVICE_SIGNATURE
        self.client_name = settings.TOKEN_SERVICE_CLIENT_NAME

    def get_valid_token(self) -> str:
        """
        Solicita un token válido al servicio centralizado.
        Lanza una excepción si falla, ya que sin token no podemos trabajar.
        """
        payload = {
            "signature": self.signature,
            "service": self.client_name
        }
        
        logger.info(f"🔐 Solicitando token a: {self.service_url}")

        try:
            # Timeout de 10s para no colgar el proceso si el otro servicio está lento
            response = requests.post(self.service_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                if token:
                    logger.info("✅ Token de Dropbox obtenido exitosamente.")
                    return token
                else:
                    raise ValueError("La respuesta del servicio de tokens no contiene 'access_token'")
            
            elif response.status_code == 401:
                raise PermissionError(f"Firma rechazada por el servicio de tokens. Verifica TOKEN_SERVICE_SIGNATURE.")
            
            else:
                raise ConnectionError(f"El servicio de tokens respondió con error: {response.status_code} - {response.text}")

        except requests.exceptions.RequestException as e:
            logger.critical(f"🔥 Error de conexión con el servicio de tokens: {e}")
            raise e
        except Exception as e:
            logger.critical(f"🔥 Error inesperado obteniendo token: {e}")
            raise e