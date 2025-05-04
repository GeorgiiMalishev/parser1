import logging
import re

logger = logging.getLogger(__name__)

class BaseParser:
    """
    Базовый класс для парсеров вакансий.
    """
    def __init__(self):
        """Инициализация базового парсера."""
        logger.debug(f"Инициализирован {self.__class__.__name__}")

    def clean_description(self, text):
        return re.sub(r'<[^>]+>', '', text) if text else ''
