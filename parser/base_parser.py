import logging
import re
from datetime import datetime, timedelta
from django.utils import timezone

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
        
    def should_update_internship(self, existing_internship):
        """
        Проверяет, нужно ли обновлять информацию о стажировке.
        
        Args:
            existing_internship: Существующая стажировка из БД
            
        Returns:
            bool: True, если стажировку нужно обновить (прошло более 7 дней с момента последнего обновления)
        """
        if not existing_internship:
            return True
            
        seven_days_ago = timezone.now() - timedelta(days=7)
        return existing_internship.updated_at <= seven_days_ago
