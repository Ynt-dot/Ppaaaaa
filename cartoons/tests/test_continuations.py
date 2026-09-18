import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon
from cartoons.tests.helpers import PNG_FRAME


class ContinueButtonVisibilityTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('orig_author', password='x')
        self.cartoon = Cartoon.objects.create(
            title='original', author=self.author)

    def test_continue_link_shown_to_anonymous(self):
        resp = self.client.get(reverse('detail', args=[self.cartoon.pk]))
        expected = (
            reverse('editor_create') + '?continue=' + str(self.cartoon.pk))
        self.assertContains(resp, expected)

    def test_continue_link_shown_to_other_logged_in_user(self):
        stranger = User.objects.create_user('stranger', password='x')
        self.client.force_login(stranger)
        resp = self.client.get(reverse('detail', args=[self.cartoon.pk]))
        expected = (
            reverse('editor_create') + '?continue=' + str(self.cartoon.pk))
        self.assertContains(resp, expected)


class ContinueEditorPrefillTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('orig_author2', password='x')
        self.cartoon = Cartoon.objects.create(
            title='original', author=self.author,
            frames_data=[PNG_FRAME, PNG_FRAME])

    def test_get_with_continue_prefills_frames(self):
        resp = self.client.get(
            reverse('editor_create'), {'continue': self.cartoon.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['continuation_of'], self.cartoon.pk)
        self.assertIn(PNG_FRAME, resp.context['frames_json'])

    def test_anonymous_can_open_continue_editor(self):
        resp = self.client.get(
            reverse('editor_create'), {'continue': self.cartoon.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertIn(PNG_FRAME, resp.context['frames_json'])

    def test_missing_source_falls_back_to_blank_editor(self):
        resp = self.client.get(
            reverse('editor_create'), {'continue': 999999})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('continuation_of', resp.context)

    def test_garbage_continue_param_does_not_crash(self):
        resp = self.client.get(
            reverse('editor_create'), {'continue': 'not-a-number'})
        self.assertEqual(resp.status_code, 200)

    def test_source_without_frames_ignored(self):
        empty = Cartoon.objects.create(title='empty', author=self.author)
        resp = self.client.get(
            reverse('editor_create'), {'continue': empty.pk})
        self.assertNotIn('continuation_of', resp.context)


class ContinuationCreationTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('orig_author3', password='x')
        self.original = Cartoon.objects.create(
            title='original', author=self.author,
            frames_data=[PNG_FRAME])

    def _post(self, user=None, **overrides):
        data = {
            'title': 'a continuation',
            'fps': '12',
            'frames': json.dumps([PNG_FRAME, PNG_FRAME]),
            'tags': '[]',
            'description': '',
            'continuation_of': str(self.original.pk),
        }
        data.update(overrides)
        if user:
            self.client.force_login(user)
        return self.client.post(reverse('editor_create'), data)

    def test_creates_cartoon_linked_to_original(self):
        drawer = User.objects.create_user('drawer2', password='x')
        self._post(user=drawer)
        continuation = Cartoon.objects.get(title='a continuation')
        self.assertEqual(continuation.continuation_of_id, self.original.pk)
        self.assertEqual(continuation.author, drawer)

    def test_anonymous_continuation_has_no_author(self):
        self._post(user=None)
        continuation = Cartoon.objects.get(title='a continuation')
        self.assertIsNone(continuation.author)
        self.assertEqual(continuation.continuation_of_id, self.original.pk)

    def test_can_continue_someone_elses_cartoon(self):
        stranger = User.objects.create_user('stranger2', password='x')
        self._post(user=stranger)
        continuation = Cartoon.objects.get(title='a continuation')
        self.assertEqual(continuation.author, stranger)
        self.assertNotEqual(continuation.author, self.author)

    def test_garbage_continuation_of_ignored(self):
        self._post(continuation_of='not-a-number')
        continuation = Cartoon.objects.get(title='a continuation')
        self.assertIsNone(continuation.continuation_of_id)

    def test_nonexistent_continuation_of_ignored(self):
        self._post(continuation_of='999999')
        continuation = Cartoon.objects.get(title='a continuation')
        self.assertIsNone(continuation.continuation_of_id)

    def test_editing_own_cartoon_cannot_set_continuation_of_retroactively(
            self):
        drawer = User.objects.create_user('drawer3', password='x')
        self.client.force_login(drawer)
        own = Cartoon.objects.create(
            title='own cartoon', author=drawer, frames_data=[PNG_FRAME])
        self.client.post(reverse('editor_edit', args=[own.pk]), {
            'title': 'own cartoon renamed',
            'fps': '12',
            'frames': json.dumps([PNG_FRAME]),
            'tags': '[]',
            'description': '',
            'continuation_of': str(self.original.pk),
        })
        own.refresh_from_db()
        self.assertIsNone(own.continuation_of_id)


class ContinuationPreviewFramesTests(TestCase):
    """Превью обычного мульта строится по первым 50 кадрам, превью
    продолжения - по последним 50 (то новое, что дорисовали)."""

    def setUp(self):
        self.author = User.objects.create_user('orig_author4', password='x')
        self.original = Cartoon.objects.create(
            title='original', author=self.author, frames_data=[PNG_FRAME])

    @patch('cartoons.views.create_gif_from_frames')
    def test_normal_cartoon_uses_first_50_via_max_frames(self, mock_gif):
        mock_gif.return_value = ContentFile(b'gif-bytes')
        many_frames = [PNG_FRAME] * 60
        self.client.post(reverse('editor_create'), {
            'title': 'plain cartoon',
            'fps': '12',
            'frames': json.dumps(many_frames),
            'tags': '[]',
            'description': '',
        })
        args, kwargs = mock_gif.call_args
        self.assertEqual(args[0], many_frames)
        self.assertEqual(kwargs.get('max_frames'), 50)

    @patch('cartoons.views.create_gif_from_frames')
    def test_continuation_uses_last_50_frames(self, mock_gif):
        mock_gif.return_value = ContentFile(b'gif-bytes')
        many_frames = [PNG_FRAME] * 60
        self.client.post(reverse('editor_create'), {
            'title': 'a continuation',
            'fps': '12',
            'frames': json.dumps(many_frames),
            'tags': '[]',
            'description': '',
            'continuation_of': str(self.original.pk),
        })
        args, kwargs = mock_gif.call_args
        self.assertEqual(args[0], many_frames[-50:])
        self.assertNotIn('max_frames', kwargs)


class DetailPageOriginalAndContinuationsTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('orig_author5', password='x')
        self.original = Cartoon.objects.create(
            title='the original', author=self.author)

    def test_no_original_block_for_non_continuation(self):
        resp = self.client.get(reverse('detail', args=[self.original.pk]))
        self.assertIsNone(resp.context['continuation_original'])
        self.assertNotContains(resp, 'Оригинал')

    def test_no_continuations_block_when_none_exist(self):
        resp = self.client.get(reverse('detail', args=[self.original.pk]))
        self.assertEqual(list(resp.context['continuations_list']), [])
        self.assertNotContains(resp, 'Продолжения')

    def test_original_block_shown_on_continuation_page(self):
        drawer = User.objects.create_user('drawer4', password='x')
        continuation = Cartoon.objects.create(
            title='the continuation', author=drawer,
            continuation_of=self.original)
        resp = self.client.get(reverse('detail', args=[continuation.pk]))
        self.assertEqual(
            resp.context['continuation_original'], self.original)
        self.assertContains(resp, 'Оригинал')
        self.assertContains(resp, 'the original')

    def test_continuations_block_lists_named_continuations(self):
        drawer = User.objects.create_user('drawer5', password='x')
        Cartoon.objects.create(
            title='named continuation', author=drawer,
            continuation_of=self.original)
        resp = self.client.get(reverse('detail', args=[self.original.pk]))
        titles = [c.title for c in resp.context['continuations_list']]
        self.assertIn('named continuation', titles)
        self.assertContains(resp, 'Продолжения')
        self.assertContains(resp, 'named continuation')

    def test_anonymous_continuations_excluded_from_list(self):
        Cartoon.objects.create(
            title='anon continuation', author=None,
            continuation_of=self.original)
        resp = self.client.get(reverse('detail', args=[self.original.pk]))
        titles = [c.title for c in resp.context['continuations_list']]
        self.assertNotIn('anon continuation', titles)
        self.assertNotContains(resp, 'anon continuation')

    def test_second_level_continuation_original_is_first_level(self):
        drawer1 = User.objects.create_user('drawer6', password='x')
        drawer2 = User.objects.create_user('drawer7', password='x')
        level1 = Cartoon.objects.create(
            title='level one', author=drawer1,
            continuation_of=self.original)
        level2 = Cartoon.objects.create(
            title='level two', author=drawer2, continuation_of=level1)
        resp = self.client.get(reverse('detail', args=[level2.pk]))
        self.assertEqual(resp.context['continuation_original'], level1)
        self.assertContains(resp, 'level one')
        self.assertNotContains(resp, 'the original')

    def test_deleting_original_keeps_continuation(self):
        drawer = User.objects.create_user('drawer8', password='x')
        continuation = Cartoon.objects.create(
            title='survives deletion', author=drawer,
            continuation_of=self.original)
        self.original.delete()
        continuation.refresh_from_db()
        self.assertIsNone(continuation.continuation_of_id)
        self.assertTrue(
            Cartoon.objects.filter(pk=continuation.pk).exists())
