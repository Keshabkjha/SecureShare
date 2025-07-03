import os
import logging
from celery import Celery
from django.conf import settings

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# Configure task routing
app.conf.task_routes = {
    'files.tasks.*': {'queue': 'files'},
    'authentication.tasks.*': {'queue': 'auth'},
    'celery.*': {'queue': 'celery'},
}

# Task execution settings
app.conf.task_acks_late = True
app.conf.task_reject_on_worker_lost = True
app.conf.worker_prefetch_multiplier = 1
app.conf.worker_max_tasks_per_child = 100

# Error handling
app.conf.task_acks_on_failure_or_timeout = False
app.conf.task_reject_on_worker_lost = True

# Timezone
app.conf.timezone = 'UTC'
app.conf.enable_utc = True

# Beat settings for scheduled tasks
app.conf.beat_schedule = {
    'cleanup-expired-share-links': {
        'task': 'files.tasks.cleanup_expired_share_links',
        'schedule': 86400.0,  # Run daily
    },
    'send-email-notifications': {
        'task': 'authentication.tasks.send_daily_stats',
        'schedule': 86400.0,  # Run daily
    },
}

# Error email notifications
ADMINS = getattr(settings, 'ADMINS', [])
if ADMINS:
    app.conf.worker_send_task_events = True
    app.conf.worker_prefetch_multiplier = 1
    
    from celery.signals import task_failure
    from django.core.mail import mail_admins
    
    @task_failure.connect
    def celery_task_failure_email(**kwargs):
        """Send task failure emails to admins."""
        subject = f"[Django][{app.main}] Error: {kwargs['exception']}"
        message = f"""
        Task {kwargs['sender'].name} with id {kwargs['task_id']} raised exception:
        {kwargs['exception']!r}
        
        Task was called with args: {kwargs['args']} kwargs: {kwargs['kwargs']}.
        The contents of the full traceback was:
        {kwargs['traceback']}
        """
        mail_admins(subject, message, fail_silently=True)

# Optional: Add custom task logging
from celery.signals import after_setup_logger, after_setup_task_logger

@after_setup_logger.connect
def setup_logger(logger, *args, **kwargs):
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

@after_setup_task_logger.connect
def setup_task_logger(logger, *args, **kwargs):
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)
