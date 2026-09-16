from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class LogoutTests(TestCase):
    """Django's built-in LogoutView only accepts POST as of Django 5.x
    (GET support, deprecated since 4.1, was removed) - the template
    must submit a form, not a plain <a href> link."""

    def setUp(self):
        self.user = User.objects.create_user('logout_user', password='x')

    def test_post_logs_out_and_redirects(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('logout'))
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('logout'))
        self.assertEqual(resp.status_code, 405)

    def test_logout_link_in_nav_is_a_post_form_not_a_get_link(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse('index'))
        content = resp.content.decode()
        logout_url = reverse('logout')
        self.assertIn(f'action="{logout_url}"', content)
        self.assertNotIn(f'href="{logout_url}"', content)
