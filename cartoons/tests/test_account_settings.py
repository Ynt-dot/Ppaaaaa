import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon, Comment, UserBlock, UserPreference


class BlockUserTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')
        self.staff = User.objects.create_user(
            'staffer', password='x', is_staff=True)
        UserPreference.objects.create(user=self.alice, profile_slug='alice')
        UserPreference.objects.create(user=self.bob, profile_slug='bob')
        UserPreference.objects.create(
            user=self.staff, profile_slug='staffer')

    def test_login_required(self):
        resp = self.client.post(reverse('toggle_block_user', args=['bob']))
        self.assertEqual(resp.status_code, 401)

    def test_block_then_unblock_toggles(self):
        self.client.force_login(self.alice)
        resp = self.client.post(reverse('toggle_block_user', args=['bob']))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['blocked'])
        self.assertTrue(
            UserBlock.objects.filter(
                blocker=self.alice, blocked=self.bob).exists())

        resp = self.client.post(reverse('toggle_block_user', args=['bob']))
        self.assertFalse(resp.json()['blocked'])
        self.assertFalse(
            UserBlock.objects.filter(
                blocker=self.alice, blocked=self.bob).exists())

    def test_cannot_block_self(self):
        self.client.force_login(self.alice)
        resp = self.client.post(reverse('toggle_block_user', args=['alice']))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(UserBlock.objects.exists())

    def test_cannot_block_staff(self):
        self.client.force_login(self.alice)
        resp = self.client.post(
            reverse('toggle_block_user', args=['staffer']))
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(UserBlock.objects.exists())

    def test_blocking_bob_does_not_affect_other_users_blocklists(self):
        # Поддельный/дублирующий запрос не может выдать блокировку
        # за действие другого пользователя - актёр всегда request.user.
        self.client.force_login(self.alice)
        self.client.post(reverse('toggle_block_user', args=['bob']))
        self.assertFalse(
            UserBlock.objects.filter(
                blocker=self.bob, blocked=self.alice).exists())


class BlocklistAddTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')
        UserPreference.objects.create(
            user=self.bob, profile_slug='bobby-link')
        self.client.force_login(self.alice)

    def _post(self, identifier):
        return self.client.post(
            reverse('blocklist_add'),
            data=json.dumps({'identifier': identifier}),
            content_type='application/json')

    def test_add_by_username(self):
        resp = self._post('bob')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            UserBlock.objects.filter(
                blocker=self.alice, blocked=self.bob).exists())

    def test_add_by_profile_slug(self):
        resp = self._post('bobby-link')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            UserBlock.objects.filter(
                blocker=self.alice, blocked=self.bob).exists())

    def test_add_by_pasted_url(self):
        resp = self._post('https://example.com/user/bobby-link/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            UserBlock.objects.filter(
                blocker=self.alice, blocked=self.bob).exists())

    def test_unknown_identifier_404(self):
        resp = self._post('nobody-here')
        self.assertEqual(resp.status_code, 404)

    def test_login_required(self):
        self.client.logout()
        resp = self._post('bob')
        self.assertEqual(resp.status_code, 401)


class CommentBlockEnforcementTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('author', password='x')
        self.stranger = User.objects.create_user('stranger', password='x')
        self.cartoon = Cartoon.objects.create(
            title='c', author=self.author)

    def test_blocked_user_cannot_comment_on_blockers_cartoon(self):
        UserBlock.objects.create(
            blocker=self.author, blocked=self.stranger)
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('add_comment', args=[self.cartoon.pk]),
            data=json.dumps({'text': 'hi'}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Comment.objects.count(), 0)

    def test_unblocked_user_can_still_comment(self):
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('add_comment', args=[self.cartoon.pk]),
            data=json.dumps({'text': 'hi'}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 201)

    def test_being_blocked_by_someone_else_does_not_block_you_here(self):
        third = User.objects.create_user('third', password='x')
        UserBlock.objects.create(blocker=third, blocked=self.stranger)
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('add_comment', args=[self.cartoon.pk]),
            data=json.dumps({'text': 'hi'}),
            content_type='application/json')
        self.assertEqual(resp.status_code, 201)


class CartoonAuthorModerationTests(TestCase):
    """Автор мульта может мягко удалять комментарии под своими же
    мультами (обычное удаление), но никто другой не может подделать
    это действие."""

    def setUp(self):
        self.author = User.objects.create_user('author', password='x')
        self.commenter = User.objects.create_user('commenter', password='x')
        self.stranger = User.objects.create_user('stranger', password='x')
        self.cartoon = Cartoon.objects.create(
            title='c', author=self.author)
        self.comment = Comment.objects.create(
            cartoon=self.cartoon, author=self.commenter, text='hello')

    def test_cartoon_author_can_delete_comment_on_own_cartoon(self):
        self.client.force_login(self.author)
        resp = self.client.post(
            reverse('delete_own_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 200)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_deleted)

    def test_comment_author_can_still_delete_own_comment(self):
        self.client.force_login(self.commenter)
        resp = self.client.post(
            reverse('delete_own_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_unrelated_stranger_cannot_delete_comment(self):
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('delete_own_comment', args=[self.comment.pk]))
        self.assertEqual(resp.status_code, 403)
        self.comment.refresh_from_db()
        self.assertFalse(self.comment.is_deleted)


class CartoonPinTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='x')
        self.stranger = User.objects.create_user('stranger', password='x')
        self.cartoon = Cartoon.objects.create(
            title='c', author=self.owner)

    def test_owner_can_toggle_pin(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            reverse('toggle_cartoon_pin', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['pinned'])
        self.cartoon.refresh_from_db()
        self.assertTrue(self.cartoon.is_pinned)

        resp = self.client.post(
            reverse('toggle_cartoon_pin', args=[self.cartoon.pk]))
        self.assertFalse(resp.json()['pinned'])

    def test_stranger_cannot_pin_someone_elses_cartoon(self):
        self.client.force_login(self.stranger)
        resp = self.client.post(
            reverse('toggle_cartoon_pin', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 403)
        self.cartoon.refresh_from_db()
        self.assertFalse(self.cartoon.is_pinned)

    def test_login_required(self):
        resp = self.client.post(
            reverse('toggle_cartoon_pin', args=[self.cartoon.pk]))
        self.assertEqual(resp.status_code, 401)


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('pw_user', password='oldpass123')
        self.other = User.objects.create_user('other', password='otherpass1')
        self.client.force_login(self.user)

    def test_correct_old_password_changes_it(self):
        resp = self.client.post(reverse('change_password'), {
            'old_password': 'oldpass123',
            'new_password1': 'BrandNewPass9!',
            'new_password2': 'BrandNewPass9!',
        })
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNewPass9!'))

    def test_wrong_old_password_rejected(self):
        resp = self.client.post(reverse('change_password'), {
            'old_password': 'totally-wrong',
            'new_password1': 'BrandNewPass9!',
            'new_password2': 'BrandNewPass9!',
        })
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpass123'))

    def test_login_required(self):
        self.client.logout()
        resp = self.client.post(reverse('change_password'), {
            'old_password': 'oldpass123',
            'new_password1': 'BrandNewPass9!',
            'new_password2': 'BrandNewPass9!',
        })
        self.assertEqual(resp.status_code, 302)
        self.other.refresh_from_db()
        self.assertTrue(self.other.check_password('otherpass1'))


class UsernameSlugChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('original', password='x')
        self.pref = UserPreference.objects.create(
            user=self.user, profile_slug='original')
        self.other = User.objects.create_user('taken', password='x')
        UserPreference.objects.create(
            user=self.other, profile_slug='taken-link')
        self.client.force_login(self.user)

    def test_change_username_leaves_slug_untouched(self):
        self.client.post(reverse('update_username'), {
            'username': 'renamed', 'slug': 'original',
        })
        self.user.refresh_from_db()
        self.pref.refresh_from_db()
        self.assertEqual(self.user.username, 'renamed')
        self.assertEqual(self.pref.profile_slug, 'original')

    def test_change_slug_only_leaves_username_untouched(self):
        self.client.post(reverse('update_username'), {
            'username': 'original', 'slug': 'new-link',
        })
        self.user.refresh_from_db()
        self.pref.refresh_from_db()
        self.assertEqual(self.user.username, 'original')
        self.assertEqual(self.pref.profile_slug, 'new-link')

    def test_duplicate_username_rejected(self):
        self.client.post(reverse('update_username'), {
            'username': 'taken', 'slug': 'original',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'original')

    def test_duplicate_slug_rejected(self):
        self.client.post(reverse('update_username'), {
            'username': 'original', 'slug': 'taken-link',
        })
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.profile_slug, 'original')

    def test_login_required(self):
        self.client.logout()
        resp = self.client.post(reverse('update_username'), {
            'username': 'hijacked', 'slug': 'hijacked',
        })
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'original')


class DescriptionUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('bio_user', password='x')
        self.pref = UserPreference.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_saves_description(self):
        self.client.post(
            reverse('update_description'), {'description': 'Hello there'})
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.description, 'Hello there')

    def test_over_1000_chars_rejected(self):
        self.client.post(
            reverse('update_description'), {'description': 'x' * 1001})
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.description, '')

    def test_login_required(self):
        self.client.logout()
        resp = self.client.post(
            reverse('update_description'), {'description': 'nope'})
        self.assertEqual(resp.status_code, 302)
        self.pref.refresh_from_db()
        self.assertEqual(self.pref.description, '')


class TrollFlagCommentVisibilityTests(TestCase):
    def setUp(self):
        self.cartoon_author = User.objects.create_user('owner', password='x')
        self.troll = User.objects.create_user('troll', password='x')
        UserPreference.objects.create(user=self.troll, is_troll=True)
        self.viewer = User.objects.create_user('viewer', password='x')
        self.cartoon = Cartoon.objects.create(
            title='c', author=self.cartoon_author)
        Comment.objects.create(
            cartoon=self.cartoon, author=self.troll, text='troll text')

    def test_any_viewer_sees_block_label_for_troll(self):
        self.client.force_login(self.viewer)
        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        data = resp.json()
        self.assertTrue(data['comments'][0]['show_block_label'])

    def test_non_author_does_not_see_block_label_for_regular_user(self):
        normal = User.objects.create_user('normal', password='x')
        Comment.objects.create(
            cartoon=self.cartoon, author=normal, text='normal text')
        self.client.force_login(self.viewer)
        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        data = resp.json()
        normal_comment = next(
            c for c in data['comments'] if c['text'] == 'normal text')
        self.assertFalse(normal_comment['show_block_label'])

    def test_staff_never_shows_block_label(self):
        staff = User.objects.create_user(
            'staffer', password='x', is_staff=True)
        Comment.objects.create(
            cartoon=self.cartoon, author=staff, text='staff text')
        self.client.force_login(self.cartoon_author)
        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        data = resp.json()
        staff_comment = next(
            c for c in data['comments'] if c['text'] == 'staff text')
        self.assertFalse(staff_comment['show_block_label'])


class BlockUrlConsistentAcrossCommentsTests(TestCase):
    """Фронтенд обновляет все надписи "заблокировать" для автора на
    странице разом после одного действия блокировки, сопоставляя по
    block_url (см. handleBlockUser в detail.html) - это работает,
    только если у каждого комментария этого автора одинаковый
    block_url, что и закрепляет этот тест."""

    def setUp(self):
        self.cartoon_author = User.objects.create_user('owner', password='x')
        self.commenter = User.objects.create_user('chatty', password='x')
        self.cartoon = Cartoon.objects.create(
            title='c', author=self.cartoon_author)
        Comment.objects.create(
            cartoon=self.cartoon, author=self.commenter, text='first')
        Comment.objects.create(
            cartoon=self.cartoon, author=self.commenter, text='second')
        self.client.force_login(self.cartoon_author)

    def test_block_url_identical_for_same_authors_comments(self):
        resp = self.client.get(
            reverse('get_comments', args=[self.cartoon.pk]))
        comments = resp.json()['comments']
        urls = {c['block_url'] for c in comments}
        self.assertEqual(len(comments), 2)
        self.assertEqual(len(urls), 1)
        self.assertIsNotNone(next(iter(urls)))
