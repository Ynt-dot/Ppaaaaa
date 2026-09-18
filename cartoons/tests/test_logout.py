from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class LogoutTests(TestCase):
    """Встроенный LogoutView в Django принимает только POST начиная с
    Django 5.x (поддержку GET, устаревшую с 4.1, убрали) - шаблон
    должен отправлять форму, а не обычную ссылку <a href>."""

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
