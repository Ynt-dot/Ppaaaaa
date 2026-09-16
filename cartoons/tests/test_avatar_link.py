import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon, Comment, UserPreference
from cartoons.tests.helpers import PNG_FRAME
from cartoons.views import _avatar_link_url


class AvatarLinkUrlTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('drawer', password='x')
        self.client.force_login(self.author)
        self.client.post(reverse('editor_create'), {
            'title': 'avatar source',
            'fps': '12',
            'frames': json.dumps([PNG_FRAME]),
            'tags': '[]',
            'description': '',
        })
        self.cartoon = Cartoon.objects.get(author=self.author)

    def test_no_avatar_set_links_to_profile(self):
        from cartoons.views import _profile_url
        self.assertEqual(
            _avatar_link_url(self.author), _profile_url(self.author))

    def test_avatar_set_links_to_that_cartoon(self):
        self.client.post(
            reverse('set_as_avatar', args=[self.cartoon.pk]),
            data=json.dumps({
                'left': 0.0, 'top': 0.0, 'right': 1.0, 'bottom': 1.0,
            }),
            content_type='application/json')
        self.author.refresh_from_db()
        self.assertEqual(
            _avatar_link_url(self.author),
            reverse('detail', args=[self.cartoon.pk]))

    def test_none_user_returns_none(self):
        self.assertIsNone(_avatar_link_url(None))


class AvatarLinkInResponsesTests(TestCase):
    """The four surfaces the user asked about: comments under a
    cartoon, the cartoon's own author block, a profile's comments
    tab, and the big avatar on someone's profile page."""

    def setUp(self):
        self.author = User.objects.create_user('drawer', password='x')
        self.viewer = User.objects.create_user('viewer', password='x')
        UserPreference.objects.create(user=self.author, profile_slug='drawer')
        self.client.force_login(self.author)
        self.client.post(reverse('editor_create'), {
            'title': 'avatar source',
            'fps': '12',
            'frames': json.dumps([PNG_FRAME]),
            'tags': '[]',
            'description': '',
        })
        self.cartoon = Cartoon.objects.get(author=self.author)
        self.client.post(
            reverse('set_as_avatar', args=[self.cartoon.pk]),
            data=json.dumps({
                'left': 0.0, 'top': 0.0, 'right': 1.0, 'bottom': 1.0,
            }),
            content_type='application/json')

        self.target_cartoon = Cartoon.objects.create(
            title='target', author=self.viewer)
        Comment.objects.create(
            cartoon=self.target_cartoon, author=self.author, text='hi')
        self.client.logout()

    def test_comment_avatar_link_points_to_avatar_cartoon(self):
        resp = self.client.get(
            reverse('get_comments', args=[self.target_cartoon.pk]))
        data = resp.json()
        self.assertEqual(
            data['comments'][0]['avatar_link_url'],
            reverse('detail', args=[self.cartoon.pk]))

    def test_cartoon_detail_page_author_avatar_link(self):
        resp = self.client.get(reverse('detail', args=[self.cartoon.pk]))
        self.assertEqual(
            resp.context['author_avatar_link_url'],
            reverse('detail', args=[self.cartoon.pk]))

    def test_profile_comments_tab_avatar_link(self):
        resp = self.client.get(
            reverse('user_profile_comments', args=['drawer']),
            {'type': 'user'})
        data = resp.json()
        self.assertEqual(
            data['comments'][0]['avatar_link_url'],
            reverse('detail', args=[self.cartoon.pk]))

    def test_profile_page_big_avatar_link_for_other_users(self):
        self.client.force_login(self.viewer)
        resp = self.client.get(reverse('user_profile', args=['drawer']))
        self.assertEqual(
            resp.context['avatar_link_url'],
            reverse('detail', args=[self.cartoon.pk]))
