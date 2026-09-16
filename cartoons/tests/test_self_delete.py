import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon, Comment, CommentLike


class DeleteOwnCartoonTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            'own_cartoon_owner', password='x')
        self.stranger = User.objects.create_user(
            'own_cartoon_stranger', password='x')
        self.cartoon = Cartoon.objects.create(title='mine', author=self.owner)

    def test_anonymous_forbidden(self):
        resp = self.client.post(
            reverse('delete_own_cartoon', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(Cartoon.objects.filter(pk=self.cartoon.pk).exists())

    def test_other_user_forbidden(self):
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('delete_own_cartoon', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Cartoon.objects.filter(pk=self.cartoon.pk).exists())

    def test_owner_can_delete(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            reverse('delete_own_cartoon', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.assertFalse(Cartoon.objects.filter(pk=self.cartoon.pk).exists())

    def test_anonymous_cartoon_has_no_owner_to_delete_it(self):
        anon_cartoon = Cartoon.objects.create(title='anon', author=None)
        self.client.force_login(self.owner)
        resp = self.client.post(
            reverse('delete_own_cartoon', args=[anon_cartoon.pk]))
        self.assertEqual(resp.status_code, 403)


class DeleteOwnCommentTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            'own_comment_author', password='x')
        self.stranger = User.objects.create_user(
            'own_comment_stranger', password='x')
        self.cartoon = Cartoon.objects.create(title='t', author=self.author)
        self.comment = Comment.objects.create(
            cartoon=self.cartoon, author=self.author, text='hello world')

    def test_anonymous_forbidden(self):
        resp = self.client.post(
            reverse('delete_own_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 401)

    def test_other_user_forbidden(self):
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('delete_own_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 403)
        self.comment.refresh_from_db()
        self.assertFalse(self.comment.is_deleted)

    def test_owner_can_soft_delete(self):
        self.client.force_login(self.author)
        resp = self.client.post(
            reverse('delete_own_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 200)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_deleted)
        self.assertEqual(self.comment.text, '')
        # the row itself must still exist - not a hard delete
        self.assertTrue(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_replies_survive_deletion(self):
        reply = Comment.objects.create(
            cartoon=self.cartoon, author=self.stranger,
            parent=self.comment, level=1, text='a reply')
        self.client.force_login(self.author)
        self.client.post(
            reverse('delete_own_comment', args=[self.comment.pk]))
        self.assertTrue(Comment.objects.filter(pk=reply.pk).exists())

    def test_cannot_delete_twice(self):
        self.client.force_login(self.author)
        self.client.post(
            reverse('delete_own_comment', args=[self.comment.pk]))
        resp = self.client.post(
            reverse('delete_own_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 400)

    def test_cannot_edit_after_deletion(self):
        self.comment.is_deleted = True
        self.comment.save(update_fields=['is_deleted'])
        self.client.force_login(self.author)
        resp = self.client.post(
            reverse('edit_comment', args=[self.comment.pk]),
            data=json.dumps({'text': 'nope'}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_can_still_like_deleted_comment(self):
        self.comment.is_deleted = True
        self.comment.text = ''
        self.comment.save(update_fields=['is_deleted', 'text'])
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('toggle_comment_like', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(CommentLike.objects.filter(
            comment=self.comment, user=self.stranger).exists())

    def test_can_still_pin_deleted_comment(self):
        self.comment.is_deleted = True
        self.comment.text = ''
        self.comment.save(update_fields=['is_deleted', 'text'])
        self.client.force_login(self.author)  # cartoon author
        resp = self.client.post(
            reverse('pin_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 200)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_pinned)

    def test_can_still_reply_to_deleted_comment(self):
        self.comment.is_deleted = True
        self.comment.text = ''
        self.comment.save(update_fields=['is_deleted', 'text'])
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('add_comment', args=[self.cartoon.pk]),
            data=json.dumps(
                {'text': 'reply to deleted', 'parent_id': self.comment.pk}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Comment.objects.filter(
            parent=self.comment, text='reply to deleted').exists())

    def test_serialized_output_hides_author_and_text(self):
        self.comment.is_deleted = True
        self.comment.text = ''
        self.comment.save(update_fields=['is_deleted', 'text'])
        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        data = resp.json()['comments'][0]
        self.assertTrue(data['is_deleted'])
        self.assertEqual(data['author'], '')
        self.assertIsNone(data['author_url'])
        self.assertFalse(data['is_own'])
        self.assertNotIn('hello world', data['text'])

    def test_deleted_comment_excluded_from_profile_comment_list(self):
        self.comment.is_deleted = True
        self.comment.text = ''
        self.comment.save(update_fields=['is_deleted', 'text'])
        resp = self.client.get(
            reverse('user_profile_comments', args=[self.author.username]))
        ids = [c['id'] for c in resp.json()['comments']]
        self.assertNotIn(self.comment.pk, ids)
