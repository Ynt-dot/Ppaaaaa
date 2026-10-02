from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon, Comment


class DeleteCartoonPermissionTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('author', password='x')
        self.regular = User.objects.create_user('regular', password='x')
        self.staff = User.objects.create_user(
            'staff', password='x', is_staff=True)
        self.cartoon = Cartoon.objects.create(
            title='t', author=self.author)

    def test_anonymous_forbidden(self):
        resp = self.client.post(
            reverse('delete_cartoon', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(Cartoon.objects.filter(pk=self.cartoon.pk).exists())

    def test_regular_user_forbidden(self):
        self.client.force_login(self.regular)
        resp = self.client.post(
            reverse('delete_cartoon', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Cartoon.objects.filter(pk=self.cartoon.pk).exists())

    def test_author_alone_is_not_enough(self):
        # Авторство не даёт права на удаление - только is_staff.
        self.client.force_login(self.author)
        resp = self.client.post(
            reverse('delete_cartoon', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Cartoon.objects.filter(pk=self.cartoon.pk).exists())

    def test_staff_can_delete(self):
        self.client.force_login(self.staff)
        resp = self.client.post(
            reverse('delete_cartoon', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Cartoon.objects.filter(pk=self.cartoon.pk).exists())


class DeleteCommentPermissionTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('cauthor', password='x')
        self.staff = User.objects.create_user(
            'cstaff', password='x', is_staff=True)
        self.cartoon = Cartoon.objects.create(title='t', author=self.author)
        self.comment = Comment.objects.create(
            cartoon=self.cartoon, author=self.author, text='hi')

    def test_own_comment_not_deletable_by_author(self):
        self.client.force_login(self.author)
        resp = self.client.post(
            reverse('delete_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_staff_can_delete_any_comment(self):
        self.client.force_login(self.staff)
        resp = self.client.post(
            reverse('delete_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())

    def test_delete_cascades_to_all_nested_replies(self):
        reply1 = Comment.objects.create(
            cartoon=self.cartoon, author=self.author,
            parent=self.comment, level=1, text='r1')
        Comment.objects.create(
            cartoon=self.cartoon, author=self.author,
            parent=reply1, level=2, text='r2 (nested)')
        unrelated = Comment.objects.create(
            cartoon=self.cartoon, author=self.author, text='unrelated')

        self.client.force_login(self.staff)
        self.client.post(reverse('delete_comment', args=[self.comment.pk]))

        remaining = set(
            Comment.objects.filter(cartoon=self.cartoon)
            .values_list('pk', flat=True)
        )
        self.assertEqual(remaining, {unrelated.pk})


class CommentDescendantsCountTests(TestCase):
    def setUp(self):
        self.regular = User.objects.create_user('dregular', password='x')
        self.staff = User.objects.create_user(
            'dstaff', password='x', is_staff=True)
        self.cartoon = Cartoon.objects.create(
            title='t', author=self.regular)
        self.root = Comment.objects.create(
            cartoon=self.cartoon, author=self.regular, text='root')

    def test_regular_user_forbidden(self):
        self.client.force_login(self.regular)
        resp = self.client.get(
            reverse('get_comment_descendants_count', args=[self.root.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_counts_all_nested_levels(self):
        r1 = Comment.objects.create(
            cartoon=self.cartoon, author=self.regular,
            parent=self.root, level=1, text='r1')
        Comment.objects.create(
            cartoon=self.cartoon, author=self.regular,
            parent=self.root, level=1, text='r2')
        Comment.objects.create(
            cartoon=self.cartoon, author=self.regular,
            parent=r1, level=2, text='r3 (nested under r1)')

        self.client.force_login(self.staff)
        resp = self.client.get(
            reverse('get_comment_descendants_count', args=[self.root.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['count'], 3)

    def test_leaf_comment_has_zero_descendants(self):
        self.client.force_login(self.staff)
        resp = self.client.get(
            reverse('get_comment_descendants_count', args=[self.root.pk]))
        self.assertEqual(resp.json()['count'], 0)
