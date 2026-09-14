import logging
from unittest.mock import patch

from django.test import TestCase, override_settings

from cartoons.logging_handlers import DiscordLogHandler


def _make_record(level=logging.ERROR, msg='boom'):
    return logging.LogRecord(
        name='cartoons.views', level=level, pathname=__file__,
        lineno=1, msg=msg, args=(), exc_info=None,
    )


class DiscordLogHandlerTests(TestCase):
    @override_settings(DISCORD_LOG_WEBHOOK_URL=None)
    @patch('cartoons.logging_handlers.requests.post')
    def test_noop_when_webhook_not_configured(self, mock_post):
        DiscordLogHandler().emit(_make_record())
        mock_post.assert_not_called()

    @override_settings(
        DISCORD_LOG_WEBHOOK_URL='https://discord.com/api/webhooks/x/y')
    @patch('cartoons.logging_handlers.requests.post')
    def test_posts_to_webhook_when_configured(self, mock_post):
        DiscordLogHandler().emit(_make_record(msg='something broke'))
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://discord.com/api/webhooks/x/y')
        self.assertIn('something broke',
                       kwargs['json']['embeds'][0]['description'])

    @override_settings(
        DISCORD_LOG_WEBHOOK_URL='https://discord.com/api/webhooks/x/y')
    @patch('cartoons.logging_handlers.requests.post',
           side_effect=Exception('network down'))
    def test_never_raises_when_discord_unreachable(self, mock_post):
        # A logging handler failing must never break the app.
        try:
            DiscordLogHandler().emit(_make_record())
        except Exception as e:
            self.fail(f'emit() raised unexpectedly: {e}')

    @override_settings(
        DISCORD_LOG_WEBHOOK_URL='https://discord.com/api/webhooks/x/y')
    @patch('cartoons.logging_handlers.requests.post')
    def test_long_message_is_truncated(self, mock_post):
        DiscordLogHandler().emit(_make_record(msg='x' * 5000))
        description = mock_post.call_args.kwargs['json']['embeds'][0][
            'description']
        self.assertLess(len(description), 4000)
