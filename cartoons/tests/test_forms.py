from unittest.mock import patch

import requests
from django.contrib.auth.models import User
from django.test import TestCase

from cartoons.forms import CustomUserCreationForm


def _valid_data(**overrides):
    data = {
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password1': 'SuperStrongPass123',
        'password2': 'SuperStrongPass123',
        'agree_to_terms': True,
    }
    data.update(overrides)
    return data


class RegistrationFormTests(TestCase):
    def test_requires_agree_to_terms(self):
        data = _valid_data(agree_to_terms=False)
        form = CustomUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('agree_to_terms', form.errors)

    def test_rejects_duplicate_email(self):
        User.objects.create_user(
            username='existing', email='taken@example.com', password='x')
        data = _valid_data(email='taken@example.com')
        form = CustomUserCreationForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    @patch('cartoons.forms.requests.get',
           side_effect=requests.exceptions.RequestException)
    def test_valid_when_email_api_unreachable(self, mock_get):
        # clean_email() must not hard-fail the whole registration just
        # because the third-party verification API is down.
        form = CustomUserCreationForm(_valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_username_over_15_chars_currently_accepted(self):
        # NOTE: forms.py sets `self.fields['username'].max_length = 15`
        # in __init__, but that only updates the widget's HTML
        # `maxlength` attribute - the validator Django attaches at
        # field-construction time still uses the model's max_length
        # (150), so this does NOT actually enforce the 15-char limit
        # server-side despite the help text promising it. Documenting
        # the current (buggy) behavior here rather than silently
        # asserting the intended one.
        data = _valid_data(username='a' * 16)
        form = CustomUserCreationForm(data)
        self.assertTrue(form.is_valid(), form.errors)
