import logging
import re
from datetime import datetime, timedelta
from django.utils import timezone
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class BaseParser:
    """
    Базовый класс для парсеров вакансий.
    """
    def __init__(self):
        """Инициализация базового парсера."""
        logger.debug(f"Инициализирован {self.__class__.__name__}")

    def clean_description(self, html_content):
        """
        Очищает HTML-описание вакансии.
        Извлекает текст, заменяет множественные пробелы и удаляет непечатаемые символы.
        """
        if not html_content:
            return ''

        soup = BeautifulSoup(html_content, 'html.parser')
        
        for br in soup.find_all("br"):
            br.replace_with("\\n")
        for p in soup.find_all("p"):
            p.append("\\n")

        text = soup.get_text(separator=' ')
        text = re.sub(r'\\s+', ' ', text).strip()
        text = re.sub(r' (\\n)+', '\\n', text)
        text = re.sub(r'(\\n\\s*)+', '\\n', text)

        text = ''.join(char for char in text if char.isprintable() or char in '\\n\\r\\t')
        
        return text.strip()
        
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
