import logging

import requests
from django.conf import settings


class DiscordLogHandler(logging.Handler):
    """Sends formatted log records to a Discord webhook.

    Separate from the DISCORD_WEBHOOK_URL used for axes lockout alerts
    (cartoons/signals.py) - reads its own DISCORD_LOG_WEBHOOK_URL, so
    error logs can go to a different channel than lockout notices, or
    be disabled independently by simply not setting it.

    The webhook URL is read from settings on every call rather than
    baked in at LOGGING-config time, since local_settings.py (where
    it's actually set) is imported after LOGGING is defined.
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
            # A logging handler must never be the reason a request
            # fails - if Discord is unreachable, just drop the log.
            pass
