import logging
from django.utils import timezone
from .models import Internship

logger = logging.getLogger('parser')

def run_all_parsers():
    """Заглушка функции запуска всех парсеров"""
    logger.info("Функция запуска всех парсеров отключена")
    return False

def run_hh_api_parser():
    """Заглушка функции запуска парсера HeadHunter через API"""
    logger.info("Функция парсера HeadHunter API отключена")
    return False

def cleanup_old_internships():
    """Заглушка функции перемещения устаревших стажировок в архив"""
    logger.info("Функция архивации устаревших стажировок отключена")
    return 0 