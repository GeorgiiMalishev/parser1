
import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from django.conf import settings
from .tasks import parse_all_internships
from .models import SearchQuery

logger = logging.getLogger('parser')

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

    scheduler.add_job(
        parse_all_internships,
        'interval',
        hours=settings.PARSER_RUN_INTERVAL // 3600,
        id='parse_all_internships',
        replace_existing=True
    )

    scheduler.add_job(
        update_saved_search_queries,
        'interval',
        hours=24,
        id='update_saved_search_queries',
        replace_existing=True
    )

    scheduler.start()
    logger.info("Планировщик задач запущен")

def update_saved_search_queries():
    logger.info("Начинаю обновление стажировок по сохраненным запросам")

    search_queries = SearchQuery.objects.all()

    if not search_queries.exists():
        logger.info("Нет сохраненных запросов для обновления")
        return

    for query in search_queries:
        logger.info(f"Обновляю стажировки для запроса: город={query.city}, ключевые слова={query.keywords}")

        parse_all_internships(
            city=query.city,
            keywords=query.keywords,
            max_pages=query.max_pages
        )

    logger.info("Обновление стажировок по сохраненным запросам завершено")