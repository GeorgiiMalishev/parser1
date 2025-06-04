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
            connection = connections['default']
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())

            if not plan:
                from .scheduler import start_scheduler
                start_scheduler()
