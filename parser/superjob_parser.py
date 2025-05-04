import logging
from .base_parser import BaseParser

logger = logging.getLogger(__name__)

class SuperJobParser(BaseParser):
    """
    Заглушка для класса работы с API SuperJob.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.warning(f"{self.__class__.__name__} не реализован.")

    def create_internship(self, internship_data, website):
        logger.warning(f"Метод create_internship в {self.__class__.__name__} не реализован.")
        return None, False

def fetch_superjob_internships(*args, **kwargs):
    """
    Заглушка для функции получения стажировок с SuperJob.
    """
    logger.warning("Функция fetch_superjob_internships не реализована.")
    return []