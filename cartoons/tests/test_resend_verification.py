from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import EmailVerificationToken


class ResendVerificationEmailTests(TestCase):
    """Регрессионный тест: resend_verification() раньше вызывала
    send_verification_email() дважды подряд (осталось от
    незавершённой правки, которую забыли вычистить), из-за чего
    каждый клик "отправить повторно" слал пользователю два
    одинаковых письма."""

    def setUp(self):
        self.user = User.objects.create_user(
            'pending', password='x', is_active=False)
        session = self.client.session
        session['pending_user_id'] = self.user.id
        session.save()

    @patch('cartoons.views.send_verification_email')
    def test_sends_exactly_one_email(self, mock_send):
        resp = self.client.post(reverse('resend_verification'))
        self.assertRedirects(resp, reverse('verification_sent'))
        mock_send.assert_called_once_with(self.user)

    @patch('cartoons.views.send_verification_email')
    def test_cooldown_still_blocks_rapid_resends(self, mock_send):
        EmailVerificationToken.objects.create(user=self.user)
        resp = self.client.post(reverse('resend_verification'))
        self.assertRedirects(resp, reverse('verification_sent'))
        mock_send.assert_not_called()
