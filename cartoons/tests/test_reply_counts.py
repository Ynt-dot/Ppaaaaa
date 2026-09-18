from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cartoons.models import Cartoon, Comment


class RepliesCountAllLevelsTests(TestCase):
    """replies_count должен включать вложенные ответы на любой
    глубине, а не только прямых детей."""

    def setUp(self):
        self.author = User.objects.create_user('rc_author', password='x')
        self.cartoon = Cartoon.objects.create(title='t', author=self.author)
        self.root = Comment.objects.create(
            cartoon=self.cartoon, author=self.author, text='root')
        self.reply1 = Comment.objects.create(
            cartoon=self.cartoon, author=self.author,
            parent=self.root, level=1, text='reply1')
        Comment.objects.create(
            cartoon=self.cartoon, author=self.author,
            parent=self.reply1, level=2, text='reply2 (nested)')

    def test_get_comments_counts_all_descendant_levels(self):
        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        data = resp.json()['comments'][0]
        self.assertEqual(data['replies_count'], 2)

    def test_get_thread_root_counts_all_descendant_levels(self):
        resp = self.client.get(
            reverse('get_thread', args=[self.reply1.pk]))
        self.assertEqual(resp.json()['root']['replies_count'], 1)


class UnreadRepliesBadgeTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            'unread_author', password='x')
        self.stranger = User.objects.create_user(
            'unread_stranger', password='x')
        self.cartoon = Cartoon.objects.create(
            title='t', author=self.author,
            author_last_seen_comments=timezone.now() - timedelta(hours=1))
        self.root = Comment.objects.create(
            cartoon=self.cartoon, author=self.stranger, text='root')

    def _add_reply(self, minutes_ago, parent=None):
        # created_at имеет auto_now_add=True, поэтому игнорирует
        # любое значение, переданное в create() - его нужно
        # переопределить отдельным save() после того, как строка
        # уже существует.
        reply = Comment.objects.create(
            cartoon=self.cartoon, author=self.stranger,
            parent=parent or self.root,
            level=(parent.level + 1) if parent else 1, text='reply')
        reply.created_at = timezone.now() - timedelta(minutes=minutes_ago)
        reply.save(update_fields=['created_at'])
        return reply

    def test_owner_sees_new_replies_count(self):
        self._add_reply(minutes_ago=30)  # после cutoff (1ч назад) -> новый
        self._add_reply(minutes_ago=90)  # до cutoff -> не новый

        self.client.force_login(self.author)
        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        data = resp.json()['comments'][0]
        self.assertEqual(data['replies_count'], 2)
        self.assertEqual(data['new_replies_count'], 1)

    def test_non_owner_never_sees_new_replies_count(self):
        self._add_reply(minutes_ago=30)

        self.client.force_login(self.stranger)
        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        data = resp.json()['comments'][0]
        self.assertEqual(data['new_replies_count'], 0)

    def test_anonymous_never_sees_new_replies_count(self):
        self._add_reply(minutes_ago=30)

        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        data = resp.json()['comments'][0]
        self.assertEqual(data['new_replies_count'], 0)

    def test_new_replies_counted_at_any_nested_depth(self):
        reply = self._add_reply(minutes_ago=30)
        self._add_reply(minutes_ago=10, parent=reply)

        self.client.force_login(self.author)
        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        data = resp.json()['comments'][0]
        self.assertEqual(data['replies_count'], 2)
        self.assertEqual(data['new_replies_count'], 2)


class SeenTimestampResetTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            'seen_author', password='x')
        self.stranger = User.objects.create_user(
            'seen_stranger', password='x')
        self.old_cutoff = timezone.now() - timedelta(days=1)
        self.cartoon = Cartoon.objects.create(
            title='t', author=self.author,
            author_last_seen_comments=self.old_cutoff)

    def test_visiting_detail_page_does_not_reset_timestamp(self):
        self.client.force_login(self.author)
        self.client.get(reverse('detail', args=[self.cartoon.pk]))
        self.cartoon.refresh_from_db()
        self.assertEqual(
            self.cartoon.author_last_seen_comments, self.old_cutoff)

    def test_mark_comments_seen_resets_timestamp(self):
        self.client.force_login(self.author)
        resp = self.client.post(
            reverse('mark_comments_seen', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 200)
        self.cartoon.refresh_from_db()
        self.assertGreater(
            self.cartoon.author_last_seen_comments, self.old_cutoff)

    def test_mark_comments_seen_forbidden_for_non_owner(self):
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('mark_comments_seen', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)
        self.cartoon.refresh_from_db()
        self.assertEqual(
            self.cartoon.author_last_seen_comments, self.old_cutoff)

    def test_mark_comments_seen_requires_login(self):
        resp = self.client.post(
            reverse('mark_comments_seen', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 401)

    def test_personal_page_badge_still_accurate_after_visiting_detail(self):
        # Посещение страницы своего же мульта не должно молча
        # помечать комментарии прочитанными (раньше это происходило
        # сразу на GET) - бейдж "новых комментариев" на личной
        # странице, посчитанный по тому же полю
        # author_last_seen_comments, должен по-прежнему считать этот
        # ответ, пока реально не сработает mark_comments_seen.
        Comment.objects.create(
            cartoon=self.cartoon, author=self.stranger, text='new one',
            created_at=timezone.now() - timedelta(hours=1))

        self.client.force_login(self.author)
        self.client.get(reverse('detail', args=[self.cartoon.pk]))

        resp = self.client.get(
            reverse('user_profile', args=[self.author.username]))
        cartoons = list(resp.context['cartoons'])
        self.assertEqual(cartoons[0].new_comments_count, 1)
