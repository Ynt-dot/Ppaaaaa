from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import EmailVerificationToken


class ResendVerificationEmailTests(TestCase):
    """Regression test: resend_verification() used to call
    send_verification_email() twice in a row (leftover from an
    abandoned edit, never cleaned up), so every "resend" click sent
    the user two identical emails."""

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
