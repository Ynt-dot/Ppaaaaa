import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon, SiteSettings
from cartoons.tests.helpers import PNG_FRAME
from cartoons.views import _extract_cartoon_pk_from_link


class ExtractCartoonPkFromLinkTests(TestCase):
    def test_full_url(self):
        self.assertEqual(
            _extract_cartoon_pk_from_link(
                'https://example.com/cartoon/42/'), 42)

    def test_full_url_no_trailing_slash(self):
        self.assertEqual(
            _extract_cartoon_pk_from_link(
                'https://example.com/cartoon/42'), 42)

    def test_bare_path(self):
        self.assertEqual(_extract_cartoon_pk_from_link('/cartoon/7/'), 7)

    def test_bare_number(self):
        self.assertEqual(_extract_cartoon_pk_from_link('123'), 123)

    def test_garbage_returns_none(self):
        self.assertIsNone(_extract_cartoon_pk_from_link('not a link'))

    def test_empty_returns_none(self):
        self.assertIsNone(_extract_cartoon_pk_from_link(''))
        self.assertIsNone(_extract_cartoon_pk_from_link(None))

    def test_unrelated_url_returns_none(self):
        self.assertIsNone(
            _extract_cartoon_pk_from_link('https://example.com/user/bob/'))


class DefaultAvatarPermissionTests(TestCase):
    """Задать общесайтовый аватар по умолчанию может только
    суперпользователь - это должно соблюдаться, даже если кто-то
    подделает запрос напрямую на URL, а не через скрытую кнопку в
    админке."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'root', 'root@example.com', 'x')
        self.staff = User.objects.create_user(
            'staffer', password='x', is_staff=True)
        self.regular = User.objects.create_user('regular', password='x')
        self.cartoon_author = User.objects.create_user(
            'drawer', password='x')
        self.client.force_login(self.cartoon_author)
        self.client.post(reverse('editor_create'), {
            'title': 'source cartoon',
            'fps': '12',
            'frames': json.dumps([PNG_FRAME]),
            'tags': '[]',
            'description': '',
        })
        self.cartoon = Cartoon.objects.get(author=self.cartoon_author)
        self.client.logout()

    def test_anonymous_redirected_from_crop_page(self):
        resp = self.client.get(
            reverse('admin_default_avatar_crop', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_anonymous_forbidden_from_save_endpoint(self):
        resp = self.client.post(
            reverse('set_default_avatar', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_regular_user_forbidden(self):
        self.client.force_login(self.regular)
        resp = self.client.get(
            reverse('admin_default_avatar_crop', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post(
            reverse('set_default_avatar', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(
            SiteSettings.objects.filter(
                pk=1, default_avatar_gif__gt='').exists())

    def test_staff_but_not_superuser_forbidden(self):
        self.client.force_login(self.staff)
        resp = self.client.get(
            reverse('admin_default_avatar_crop', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post(
            reverse('set_default_avatar', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_staff_but_not_superuser_cannot_reach_admin_page(self):
        self.client.force_login(self.staff)
        resp = self.client.get(
            reverse('admin:cartoons_sitesettings_change', args=[1]))
        self.assertEqual(resp.status_code, 403)

    def test_superuser_can_access_crop_page_for_any_users_cartoon(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(
            reverse('admin_default_avatar_crop', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_superuser_can_set_default_avatar(self):
        self.client.force_login(self.superuser)
        resp = self.client.post(
            reverse('set_default_avatar', args=[self.cartoon.pk]),
            data=json.dumps({
                'left': 0.0, 'top': 0.0, 'right': 1.0, 'bottom': 1.0,
            }),
            content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        site_settings = SiteSettings.objects.get(pk=1)
        self.assertTrue(site_settings.default_avatar_gif)

    def test_superuser_can_reach_admin_page(self):
        self.client.force_login(self.superuser)
        resp = self.client.get(
            reverse('admin:cartoons_sitesettings_changelist'), follow=True)
        self.assertEqual(resp.status_code, 200)


class DefaultAvatarEligibilityTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'root', 'root@example.com', 'x')
        self.author = User.objects.create_user('drawer', password='x')
        self.no_preview_cartoon = Cartoon.objects.create(
            title='no preview', author=self.author)
        self.client.force_login(self.superuser)

    def test_cartoon_without_preview_rejected(self):
        resp = self.client.post(
            reverse('set_default_avatar', args=[self.no_preview_cartoon.pk]))
        self.assertEqual(resp.status_code, 400)

    def test_crop_page_redirects_for_ineligible_cartoon(self):
        resp = self.client.get(
            reverse(
                'admin_default_avatar_crop',
                args=[self.no_preview_cartoon.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_unknown_cartoon_404s(self):
        resp = self.client.get(
            reverse('admin_default_avatar_crop', args=[999999]))
        self.assertEqual(resp.status_code, 404)


class DefaultAvatarFallbackTests(TestCase):
    """После того как задан общесайтовый аватар, пользователи без
    своего личного аватара должны видеть его вместо статичной
    заглушки - но свой собственный аватар пользователя всё равно в
    приоритете."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'root', 'root@example.com', 'x')
        self.author = User.objects.create_user('drawer', password='x')
        self.client.force_login(self.author)
        self.client.post(reverse('editor_create'), {
            'title': 'source cartoon',
            'fps': '12',
            'frames': json.dumps([PNG_FRAME]),
            'tags': '[]',
            'description': '',
        })
        self.cartoon = Cartoon.objects.get(author=self.author)
        self.client.logout()

        self.client.force_login(self.superuser)
        self.client.post(
            reverse('set_default_avatar', args=[self.cartoon.pk]),
            data=json.dumps({
                'left': 0.0, 'top': 0.0, 'right': 1.0, 'bottom': 1.0,
            }),
            content_type='application/json')
        self.client.logout()

    def test_user_without_own_avatar_sees_site_default(self):
        from cartoons.views import _get_user_avatar_url
        site_settings = SiteSettings.objects.get(pk=1)
        self.assertEqual(
            _get_user_avatar_url(self.author),
            site_settings.default_avatar_gif.url)

    def test_user_with_own_avatar_still_sees_their_own(self):
        self.client.force_login(self.author)
        self.client.post(
            reverse('set_as_avatar', args=[self.cartoon.pk]),
            data=json.dumps({
                'left': 0.0, 'top': 0.0, 'right': 1.0, 'bottom': 1.0,
            }),
            content_type='application/json')
        from cartoons.views import _get_user_avatar_url
        self.author.refresh_from_db()
        site_settings = SiteSettings.objects.get(pk=1)
        own_url = _get_user_avatar_url(self.author)
        self.assertNotEqual(own_url, site_settings.default_avatar_gif.url)
