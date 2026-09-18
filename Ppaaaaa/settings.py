"""
Настройки Django для проекта Ppaaaaa.

Сгенерировано 'django-admin startproject' с Django 4.2.28.

Подробнее об этом файле см.
https://docs.djangoproject.com/en/4.2/topics/settings/

Полный список настроек и их значений см.
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from pathlib import Path
import os
from django.contrib.messages import constants as messages

# Пути внутри проекта строятся так: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Настройки для быстрого старта разработки - не годятся для продакшена
# См. https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# ПРЕДУПРЕЖДЕНИЕ БЕЗОПАСНОСТИ: секретный ключ в продакшене должен
# храниться в секрете!
SECRET_KEY = \
    'django-insecure-6iwoaenbt0so)+@j2zlpo-rmlh1upnzq9tu0nhe-%)r#8)_dnc'

ALLOWED_HOSTS = []


# Определение приложения

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cartoons',
    'bootstrap4',
    'axes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
]

# Безопасное значение по умолчанию, если local_settings.py его не переопределит
DEBUG = False

ROOT_URLCONF = 'Ppaaaaa.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'libraries': {
                'cartoon_tags': 'cartoons.templatetags.cartoon_tags',
            },
        },
    },
]

WSGI_APPLICATION = 'Ppaaaaa.wsgi.application'


# База данных
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Валидация пароля
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME':
        'django.contrib.auth.password_validation.UserAttributeSimilarityValida\
tor',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME':
        'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Интернационализация
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'ru'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Статические файлы (CSS, JavaScript, изображения)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# Тип поля первичного ключа по умолчанию
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

LOGIN_REDIRECT_URL = 'index'  # имя маршрута главной страницы
LOGOUT_REDIRECT_URL = 'index'  # опционально, после выхода тоже на главную

# Настройки почты для разработки (письма выводятся в консоль)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@mycartoon.com'

SITE_URL = 'http://127.0.0.1:8000'  # для разработки

MESSAGE_TAGS = {
    messages.ERROR: 'danger',
    messages.SUCCESS: 'success',
}

STATIC_ROOT = os.path.join(BASE_DIR, 'static')

INTERNAL_IPS = [
    '127.0.0.1',
]

# Логирование
LOGS_DIR = BASE_DIR / 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'django.log',
            'encoding': 'utf-8',
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
        },
        # Требует DISCORD_LOG_WEBHOOK_URL в local_settings.py, иначе
        # молча ничего не отправляет (см. cartoons/logging_handlers.py)
        'discord': {
            'class': 'cartoons.logging_handlers.DiscordLogHandler',
            'level': 'ERROR',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'WARNING',
    },
    'loggers': {
        # Необработанные исключения и 5xx-ошибки во view
        'django.request': {
            'handlers': ['console', 'file', 'discord'],
            'level': 'ERROR',
            'propagate': False,
        },
        # Все logger.warning()/logger.error() из cartoons/*.py
        'cartoons': {
            'handlers': ['console', 'file', 'discord'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Настройки django-axes
AXES_FAILURE_LIMIT = 5               # количество неудачных попыток
AXES_COOLOFF_TIME = 1                # блокировка на 1 час (в часах)
AXES_LOCK_OUT_BY_COMBINATION_USER_IP = True   # блокировать по паре (username,
# IP)
AXES_ENABLE_ADMIN = True             # отображать логи в админке
AXES_RESET_ON_SUCCESS = True         # сброс счётчика после успешного входа
AXES_LOCKOUT_TEMPLATE = 'registration/locked_out.html'  # шаблон для
# заблокированных

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',  # должен быть первым для
    # отслеживания попыток
    'django.contrib.auth.backends.ModelBackend',
]

try:
    from .local_settings import * # type: ignore # noqa
except ImportError:
    pass

# django-debug-toolbar - только для локальной разработки, на проде
# не устанавливается вообще (см. requirements-prod.txt)
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
