import logging
import os

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger. Initializes basicConfig once.
    """
    if not logging.getLogger().handlers:
        logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)
    return logger
