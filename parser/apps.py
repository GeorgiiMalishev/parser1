from django.apps import AppConfig


class ParserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parser'
    verbose_name = 'Парсер стажировок'
    
    def ready(self):
        """Настройка планировщика заданий при загрузке приложения"""
        import os
        if os.environ.get('RUN_MAIN', None) != 'true':
            return
            
        self._setup_scheduler()
    
    def _setup_scheduler(self):
        """Инициализация планировщика задач"""
        try:
            from django_apscheduler.jobstores import DjangoJobStore
            from apscheduler.schedulers.background import BackgroundScheduler
            from django.conf import settings
            
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
