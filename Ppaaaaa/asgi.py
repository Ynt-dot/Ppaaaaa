"""
Конфигурация ASGI для проекта Ppaaaaa.

Экспортирует ASGI-приложение как переменную модуля ``application``.

Подробнее об этом файле см.
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Ppaaaaa.settings')

application = get_asgi_application()
