from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon, Comment, UserPreference


class SearchMatchingTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('search_author', password='x')

    def _search(self, query):
        return self.client.get(reverse('search'), {'q': query})

    def test_empty_query_shows_no_results_and_no_crash(self):
        Cartoon.objects.create(title='something', author=self.author)
        resp = self._search('')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['cartoons']), 0)

    def test_matches_title(self):
        Cartoon.objects.create(title='Прыгающий кот', author=self.author)
        Cartoon.objects.create(title='Что-то другое', author=self.author)
        resp = self._search('прыгающий')
        titles = [c.title for c in resp.context['cartoons']]
        self.assertEqual(titles, ['Прыгающий кот'])

    def test_matches_description(self):
        Cartoon.objects.create(
            title='c1', author=self.author,
            description='мульт про весёлого хомяка')
        resp = self._search('хомяка')
        self.assertEqual(len(resp.context['cartoons']), 1)

    def test_matches_tags(self):
        Cartoon.objects.create(
            title='c1', author=self.author, tags=['смешной', 'котик'])
        resp = self._search('котик')
        self.assertEqual(len(resp.context['cartoons']), 1)

    def test_matches_author_username(self):
        Cartoon.objects.create(title='c1', author=self.author)
        resp = self._search('search_author')
        self.assertEqual(len(resp.context['cartoons']), 1)

    def test_matches_author_display_name(self):
        UserPreference.objects.create(
            user=self.author, display_name='Смешное Имя')
        Cartoon.objects.create(title='c1', author=self.author)
        resp = self._search('смешное имя')
        self.assertEqual(len(resp.context['cartoons']), 1)

    def test_matches_comment_text(self):
        cartoon = Cartoon.objects.create(title='c1', author=self.author)
        Comment.objects.create(
            cartoon=cartoon, author=self.author,
            text='обожаю этого единорога')
        resp = self._search('единорога')
        self.assertEqual(len(resp.context['cartoons']), 1)

    def test_deleted_comment_text_not_matched(self):
        cartoon = Cartoon.objects.create(title='c1', author=self.author)
        Comment.objects.create(
            cartoon=cartoon, author=self.author,
            text='невидимый текст', is_deleted=True)
        resp = self._search('невидимый')
        self.assertEqual(len(resp.context['cartoons']), 0)

    def test_no_duplicate_rows_from_multiple_matching_comments(self):
        cartoon = Cartoon.objects.create(title='c1', author=self.author)
        Comment.objects.create(
            cartoon=cartoon, author=self.author, text='драконы драконы')
        Comment.objects.create(
            cartoon=cartoon, author=self.author, text='ещё про драконов')
        resp = self._search('дракон')
        self.assertEqual(len(resp.context['cartoons']), 1)

    def test_no_results_message_shown(self):
        resp = self._search('нечтотакогонигденет')
        self.assertContains(resp, 'Ничего не найдено')

    def test_title_match_ranked_above_other_matches(self):
        matches_elsewhere = Cartoon.objects.create(
            title='безымянный', author=self.author,
            description='здесь есть слово жираф')
        matches_title = Cartoon.objects.create(
            title='жираф гуляет', author=self.author)
        resp = self._search('жираф')
        results = list(resp.context['cartoons'])
        self.assertEqual(results[0], matches_title)
        self.assertEqual(results[1], matches_elsewhere)

    def test_unicode_and_special_characters_do_not_crash(self):
        resp = self._search('100% "странный" запрос % _ \\')
        self.assertEqual(resp.status_code, 200)


class SearchPaginationTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('search_author2', password='x')
        for i in range(20):
            Cartoon.objects.create(
                title=f'страница мульт {i}', author=self.author)

    def test_sixteen_per_page(self):
        resp = self.client.get(
            reverse('search'), {'q': 'страница'})
        self.assertEqual(len(resp.context['cartoons']), 16)
        self.assertTrue(resp.context['cartoons'].has_next())

    def test_second_page_has_remainder(self):
        resp = self.client.get(
            reverse('search'), {'q': 'страница', 'page': 2})
        self.assertEqual(len(resp.context['cartoons']), 4)
        self.assertFalse(resp.context['cartoons'].has_next())


class SearchBarRenderTests(TestCase):
    def test_search_form_present_on_every_page(self):
        resp = self.client.get(reverse('index'))
        self.assertContains(resp, 'action="' + reverse('search') + '"')

    def test_query_value_prefilled_on_search_page(self):
        resp = self.client.get(reverse('search'), {'q': 'мой запрос'})
        self.assertContains(resp, 'value="мой запрос"')
