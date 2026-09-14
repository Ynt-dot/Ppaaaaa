import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon
from cartoons.views import _clean_tags
from cartoons.tests.helpers import PNG_FRAME


class CleanTagsTests(TestCase):
    def test_rejects_non_list(self):
        self.assertEqual(_clean_tags('not a list'), [])
        self.assertEqual(_clean_tags({'a': 1}), [])
        self.assertEqual(_clean_tags(None), [])

    def test_drops_non_string_items(self):
        self.assertEqual(_clean_tags([1, 2, 'ok']), ['ok'])

    def test_truncates_long_tags_to_30_chars(self):
        long_tag = 'x' * 100
        result = _clean_tags([long_tag])
        self.assertEqual(len(result[0]), 30)

    def test_caps_at_20_tags(self):
        tags = [str(i) for i in range(50)]
        self.assertEqual(len(_clean_tags(tags)), 20)

    def test_strips_and_drops_empty_tags(self):
        self.assertEqual(_clean_tags(['  ', '', ' hi '], ), ['hi'])

    def test_script_breakout_payload_survives_as_plain_text(self):
        payload = '</script><script>alert(1)</script>'
        result = _clean_tags([payload])
        # It's kept as a string (truncated to 30 chars) - the actual
        # XSS defense is json_script escaping it at render time, not
        # stripping it here.
        self.assertEqual(result, [payload[:30]])


class AnonymousCartoonEditPermissionTests(TestCase):
    """Regression test for the IDOR that let anyone edit/overwrite an
    anonymously-created cartoon, which combined with unvalidated tags
    used to allow stored XSS."""

    def setUp(self):
        self.owner = User.objects.create_user('owner', password='x')
        self.stranger = User.objects.create_user('stranger', password='x')
        self.anon_cartoon = Cartoon.objects.create(title='anon', author=None)
        self.owned_cartoon = Cartoon.objects.create(
            title='owned', author=self.owner)

    def test_anonymous_visitor_cannot_open_editor_for_anonymous_cartoon(self):
        resp = self.client.get(
            reverse('editor_edit', args=[self.anon_cartoon.pk]))
        self.assertRedirects(resp, reverse('index'))

    def test_other_logged_in_user_cannot_open_editor_for_anonymous_cartoon(
            self):
        self.client.force_login(self.stranger)
        resp = self.client.get(
            reverse('editor_edit', args=[self.anon_cartoon.pk]))
        self.assertRedirects(resp, reverse('index'))

    def test_stranger_cannot_open_editor_for_someone_elses_cartoon(self):
        self.client.force_login(self.stranger)
        resp = self.client.get(
            reverse('editor_edit', args=[self.owned_cartoon.pk]))
        self.assertRedirects(resp, reverse('index'))

    def test_owner_can_open_own_editor(self):
        self.client.force_login(self.owner)
        resp = self.client.get(
            reverse('editor_edit', args=[self.owned_cartoon.pk]))
        self.assertEqual(resp.status_code, 200)


class EditorTagsAndDescriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('drawer', password='x')
        self.client.force_login(self.user)

    def _post_editor(self, **overrides):
        data = {
            'title': 'My cartoon',
            'fps': '12',
            'frames': json.dumps([PNG_FRAME]),
            'tags': '[]',
            'description': '',
        }
        data.update(overrides)
        return self.client.post(reverse('editor_create'), data)

    def test_description_truncated_to_1000_chars(self):
        resp = self._post_editor(description='a' * 5000)
        self.assertEqual(resp.status_code, 302)
        cartoon = Cartoon.objects.get(author=self.user)
        self.assertEqual(len(cartoon.description), 1000)

    def test_malformed_tags_saved_as_empty_list(self):
        resp = self._post_editor(tags=json.dumps({'not': 'a list'}))
        self.assertEqual(resp.status_code, 302)
        cartoon = Cartoon.objects.get(author=self.user)
        self.assertEqual(cartoon.tags, [])

    def test_valid_tags_are_kept(self):
        resp = self._post_editor(tags=json.dumps(['funny', 'test']))
        self.assertEqual(resp.status_code, 302)
        cartoon = Cartoon.objects.get(author=self.user)
        self.assertEqual(cartoon.tags, ['funny', 'test'])


class AvatarCropClampTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('avatarer', password='x')
        self.client.force_login(self.user)
        self.client.post(reverse('editor_create'), {
            'title': 'avatar source',
            'fps': '12',
            'frames': json.dumps([PNG_FRAME]),
            'tags': '[]',
            'description': '',
        })
        self.cartoon = Cartoon.objects.get(author=self.user)

    def test_malformed_crop_values_do_not_crash(self):
        resp = self.client.post(
            reverse('set_as_avatar', args=[self.cartoon.pk]),
            data=json.dumps({
                'left': 'not-a-number', 'top': None,
                'right': 'abc', 'bottom': [],
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    def test_valid_crop_values_still_work(self):
        resp = self.client.post(
            reverse('set_as_avatar', args=[self.cartoon.pk]),
            data=json.dumps({
                'left': 0.1, 'top': 0.1, 'right': 0.9, 'bottom': 0.9,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
