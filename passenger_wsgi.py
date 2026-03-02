import sys
import os
from django.core.wsgi import get_wsgi_application

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(__file__))

# Указываем файл настроек (замените Ppaaaaa на имя вашего проекта)
os.environ['DJANGO_SETTINGS_MODULE'] = 'Ppaaaaa.settings'


application = get_wsgi_application()
