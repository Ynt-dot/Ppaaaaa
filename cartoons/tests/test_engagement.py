import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon, CartoonLike, Comment, Favorite


class AnonymousEngagementRejectedTests(TestCase):
    """Likes, favorites and comments are authenticated-only actions -
    there is no legitimate anonymous path to any of them."""

    def setUp(self):
        self.author = User.objects.create_user('eauthor', password='x')
        self.cartoon = Cartoon.objects.create(title='t', author=self.author)

    def test_anonymous_cannot_like_cartoon(self):
        resp = self.client.post(
            reverse('toggle_cartoon_like', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(CartoonLike.objects.count(), 0)

    def test_anonymous_cannot_favorite(self):
        resp = self.client.post(
            reverse('toggle_favorite', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_anonymous_cannot_comment(self):
        resp = self.client.post(
            reverse('add_comment', args=[self.cartoon.pk]),
            data=json.dumps({'text': 'hi'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Comment.objects.count(), 0)

    def test_anonymous_cannot_like_comment(self):
        comment = Comment.objects.create(
            cartoon=self.cartoon, author=self.author, text='hi')
        resp = self.client.post(
            reverse('toggle_comment_like', args=[comment.pk]))
        self.assertEqual(resp.status_code, 401)


class AuthenticatedEngagementWorksTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('eauthor2', password='x')
        self.user = User.objects.create_user('eliker', password='x')
        self.cartoon = Cartoon.objects.create(title='t', author=self.author)
        self.client.force_login(self.user)

    def test_toggle_like_creates_and_removes(self):
        resp = self.client.post(
            reverse('toggle_cartoon_like', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['liked'])
        self.assertEqual(CartoonLike.objects.count(), 1)

        resp = self.client.post(
            reverse('toggle_cartoon_like', args=[self.cartoon.pk]))
        self.assertFalse(resp.json()['liked'])
        self.assertEqual(CartoonLike.objects.count(), 0)

    def test_can_comment(self):
        resp = self.client.post(
            reverse('add_comment', args=[self.cartoon.pk]),
            data=json.dumps({'text': 'nice cartoon'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(Comment.objects.first().author, self.user)

    def test_can_favorite(self):
        resp = self.client.post(
            reverse('toggle_favorite', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['favorited'])
        self.assertEqual(Favorite.objects.count(), 1)
