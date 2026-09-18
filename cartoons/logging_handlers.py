import logging

import requests
from django.conf import settings


class DiscordLogHandler(logging.Handler):
    """Отправляет отформатированные записи лога в Discord-вебхук.

    Отдельно от DISCORD_WEBHOOK_URL, который используется для алертов
    о блокировке axes (cartoons/signals.py) - читает свой собственный
    DISCORD_LOG_WEBHOOK_URL, поэтому логи ошибок могут идти в другой
    канал, чем уведомления о блокировках, или быть отключены
    независимо простым отсутствием этой переменной.

    URL вебхука читается из settings при каждом вызове, а не
    запекается на момент настройки LOGGING, поскольку
    local_settings.py (где он реально задаётся) импортируется уже
    после определения LOGGING.
    """

    def emit(self, record):
        webhook_url = getattr(settings, 'DISCORD_LOG_WEBHOOK_URL', None)
        if not webhook_url:
            return

        try:
            message = self.format(record)
        except Exception:
            return

        if len(message) > 3800:
            message = message[:3800] + '\n... (обрезано)'

        color = 0xff0000 if record.levelno >= logging.ERROR else 0xffaa00
        payload = {
            'embeds': [{
                'title': f'{record.levelname}: {record.name}',
                'description': f'```\n{message}\n```',
                'color': color,
            }],
        }

        try:
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception:
            # Обработчик логирования никогда не должен быть причиной
            # падения запроса - если Discord недоступен, просто
            # отбрасываем запись лога.
            pass
