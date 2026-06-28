import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_btp.settings')

app = Celery('erp_btp')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
