from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon, CartoonLike, Favorite, UserPreference


class PinnedBorderScopeTests(TestCase):
    """Закреплённый мульт должен получать чёрную рамку только на
    вкладке "Альбом" профиля своего автора - не на заглавной, не на
    чужих вкладках "Понравившееся"/"Избранное". Регрессионный тест:
    раньше рамка зависела только от cartoon.is_pinned, без учёта
    того, где рендерилась карточка."""

    def setUp(self):
        self.author = User.objects.create_user('pinner', password='x')
        UserPreference.objects.create(user=self.author, profile_slug='pinner')
        self.cartoon = Cartoon.objects.create(
            title='pinned one', author=self.author, is_pinned=True)

    # Важно: глобальный скрипт переключения закрепа в base.html всегда
    # содержит буквальную JS-строку 'cartoon-pinned' (в одинарных
    # кавычках), независимо от того, закреплена ли какая-то карточка
    # на странице - поэтому ищем именно HTML-атрибут class (в двойных
    # кавычках), а не голую подстроку через assertContains/
    # assertNotContains.
    @staticmethod
    def _has_pinned_class_in_html(resp):
        return 'cartoon-pinned"' in resp.content.decode()

    def test_border_shown_on_own_album_tab(self):
        resp = self.client.get(
            reverse('user_profile', args=['pinner']), {'tab': 'album'})
        self.assertTrue(self._has_pinned_class_in_html(resp))

    def test_border_not_shown_on_index_page(self):
        resp = self.client.get(reverse('index'))
        self.assertFalse(self._has_pinned_class_in_html(resp))

    def test_border_not_shown_on_someone_elses_liked_tab(self):
        viewer = User.objects.create_user('viewer', password='x')
        UserPreference.objects.create(user=viewer, profile_slug='viewer')
        CartoonLike.objects.create(cartoon=self.cartoon, user=viewer)
        resp = self.client.get(
            reverse('user_profile', args=['viewer']), {'tab': 'liked'})
        self.assertFalse(self._has_pinned_class_in_html(resp))

    def test_border_not_shown_on_someone_elses_favorites_tab(self):
        viewer = User.objects.create_user('favoriter', password='x')
        UserPreference.objects.create(
            user=viewer, profile_slug='favoriter')
        Favorite.objects.create(cartoon=self.cartoon, user=viewer)
        resp = self.client.get(
            reverse('user_profile', args=['favoriter']),
            {'tab': 'favorites'})
        self.assertFalse(self._has_pinned_class_in_html(resp))

    def test_pin_button_still_only_for_owner_on_own_album(self):
        self.client.force_login(self.author)
        resp = self.client.get(
            reverse('user_profile', args=['pinner']), {'tab': 'album'})
        self.assertContains(resp, 'cartoon-pin-toggle')
