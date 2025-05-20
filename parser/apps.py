from django.apps import AppConfig
from django.db.migrations.executor import MigrationExecutor
from django.db import connections
import os
from django.conf import settings


class ParserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parser'
    verbose_name = 'Парсер стажировок'
    
    def ready(self):
        if not settings.DEBUG or os.environ.get('RUN_SCHEDULER', False):
            # Проверяем, есть ли неприменённые миграции
            connection = connections['default']
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            
            # Если нет неприменённых миграций, запускаем scheduler
            if not plan:
                from .scheduler import start_scheduler
                start_scheduler()
    
    def _setup_scheduler(self):
        """Инициализация планировщика задач"""
        try:
            from django_apscheduler.jobstores import DjangoJobStore
            from apscheduler.schedulers.background import BackgroundScheduler
            
            from .tasks import run_all_parsers, cleanup_old_internships
            
            scheduler = BackgroundScheduler()
            scheduler.add_jobstore(DjangoJobStore(), 'default')
            
            interval_seconds = getattr(settings, 'PARSER_RUN_INTERVAL', 4 * 60 * 60)
            
            scheduler.add_job(
                run_all_parsers,
                'interval',
                seconds=interval_seconds,
                id='run_all_parsers',
                replace_existing=True
            )
            
            scheduler.add_job(
                cleanup_old_internships,
                'cron',
                hour=0,
                minute=0,
                id='cleanup_old_internships',
                replace_existing=True
            )
            
            scheduler.start()
        except ImportError:
            pass
