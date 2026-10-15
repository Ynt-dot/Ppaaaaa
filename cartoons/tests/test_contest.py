import json
import os
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from cartoons.models import Cartoon, Comment
from cartoons.templatetags.cartoon_tags import balanced_row_sizes


class ContestTestCase(TestCase):
    """Страницы конкурсов читают data/contests/<имя>.html из BASE_DIR -
    подменяем его на временную папку, чтобы не трогать настоящую data/."""

    # настоящий корень проекта - до подмены BASE_DIR (для .example)
    REPO_DIR = settings.BASE_DIR

    def setUp(self):
        self.base_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.base_dir, 'data', 'contests'))
        override = override_settings(BASE_DIR=self.base_dir)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, self.base_dir)

    def write_contest(self, slug, html):
        path = os.path.join(self.base_dir, 'data', 'contests', slug + '.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)


class ContestPageTests(ContestTestCase):
    def test_missing_contest_is_404(self):
        resp = self.client.get(reverse('contest', args=['nope']))
        self.assertEqual(resp.status_code, 404)

    def test_renders_html_and_title(self):
        self.write_contest(
            'halloween', '<h1>Жуткий <b>конкурс</b></h1><p>Текст</p>')
        resp = self.client.get(reverse('contest', args=['halloween']))
        self.assertContains(resp, '<p>Текст</p>', html=False)
        self.assertContains(resp, '<title>Жуткий конкурс</title>')

    def test_cartoons_tag_renders_cards_in_order(self):
        first = Cartoon.objects.create(title='первый мульт')
        second = Cartoon.objects.create(title='второй мульт')
        self.write_contest(
            'halloween',
            '{%% cartoons %d 999999 %d %%}' % (second.pk, first.pk))
        html = self.client.get(
            reverse('contest', args=['halloween'])).content.decode()
        self.assertIn('второй мульт', html)
        self.assertIn('первый мульт', html)
        self.assertLess(html.index('второй мульт'), html.index('первый мульт'))

    def test_django_comments_not_rendered(self):
        self.write_contest('halloween', '{# секрет #}<p>видно</p>')
        resp = self.client.get(reverse('contest', args=['halloween']))
        self.assertContains(resp, 'видно')
        self.assertNotContains(resp, 'секрет')

    def test_has_comments_block(self):
        self.write_contest('halloween', '<p>x</p>')
        resp = self.client.get(reverse('contest', args=['halloween']))
        self.assertContains(resp, 'id="comments-list"')
        self.assertContains(
            resp, reverse('get_page_comments', args=['halloween']))


class ContestCommentsTests(ContestTestCase):
    def setUp(self):
        super().setUp()
        self.write_contest('halloween', '<p>x</p>')
        self.user = User.objects.create_user('commenter', password='x')

    def _add(self, slug='halloween', **body):
        return self.client.post(
            reverse('add_page_comment', args=[slug]),
            json.dumps({'text': 'бу', **body}),
            content_type='application/json')

    def test_add_and_list_page_comment(self):
        self.client.force_login(self.user)
        self.assertEqual(self._add().status_code, 201)
        comment = Comment.objects.get()
        self.assertIsNone(comment.cartoon)
        self.assertEqual(comment.page, 'halloween')
        data = self.client.get(
            reverse('get_page_comments', args=['halloween'])).json()
        self.assertEqual([c['text'] for c in data['comments']], ['бу'])

    def test_cannot_comment_missing_contest(self):
        self.client.force_login(self.user)
        self.assertEqual(self._add(slug='nope').status_code, 404)
        self.assertFalse(Comment.objects.exists())

    def test_anonymous_cannot_comment(self):
        self.assertEqual(self._add().status_code, 403)

    def test_reply_parent_must_be_on_same_page(self):
        cartoon = Cartoon.objects.create(title='m')
        foreign = Comment.objects.create(
            cartoon=cartoon, author=self.user, text='чужой')
        self.client.force_login(self.user)
        self.assertEqual(self._add(parent_id=foreign.pk).status_code, 404)

    def test_reply_on_page(self):
        root = Comment.objects.create(
            page='halloween', author=self.user, text='корень')
        self.client.force_login(self.user)
        self.assertEqual(self._add(parent_id=root.pk).status_code, 201)
        resp = self.client.get(reverse('get_replies', args=[root.pk]))
        self.assertEqual(resp.json()['comments'][0]['text'], 'бу')

    def test_page_comments_do_not_leak_into_cartoon(self):
        cartoon = Cartoon.objects.create(title='m')
        Comment.objects.create(page='halloween', author=self.user, text='бу')
        data = self.client.get(
            reverse('get_comments', args=[cartoon.pk])).json()
        self.assertEqual(data['total'], 0)

    def test_only_staff_can_pin_page_comment(self):
        comment = Comment.objects.create(
            page='halloween', author=self.user, text='бу')
        url = reverse('pin_comment', args=[comment.pk])
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(url).status_code, 403)
        admin = User.objects.create_user('adm', password='x', is_staff=True)
        self.client.force_login(admin)
        self.assertEqual(self.client.post(url).json(), {'pinned': True})

    def test_profile_lists_page_comment_with_contest_link(self):
        Comment.objects.create(page='halloween', author=self.user, text='бу')
        data = self.client.get(
            reverse('user_profile_comments', args=[self.user.username])).json()
        self.assertEqual(
            data['comments'][0]['cartoon_url'],
            reverse('contest', args=['halloween']))


class TemplateCommentLeakTests(ContestTestCase):
    """Многострочный {# #} Django выводит как текст - следим, чтобы
    служебные пояснения не попадали на страницы."""

    def test_example_contest_renders_cleanly(self):
        example = os.path.join(
            self.REPO_DIR, 'data', 'contests', 'halloween.html.example')
        with open(example, encoding='utf-8') as f:
            self.write_contest('halloween', f.read())
        resp = self.client.get(reverse('contest', args=['halloween']))
        self.assertContains(resp, 'Конкурс хэллоуинских мультов')
        self.assertNotContains(resp, 'Образец страницы конкурса')
        self.assertNotContains(resp, '{#')

    def test_cartoon_page_has_no_raw_template_comments(self):
        cartoon = Cartoon.objects.create(title='m')
        resp = self.client.get(reverse('detail', args=[cartoon.pk]))
        self.assertNotContains(resp, '{#')


class BalancedRowsTests(ContestTestCase):
    def test_row_sizes(self):
        self.assertEqual(
            {n: balanced_row_sizes(n) for n in (0, 1, 3, 4, 5, 6, 7, 9, 10)},
            {0: [], 1: [1], 3: [3], 4: [4], 5: [3, 2], 6: [3, 3],
             7: [4, 3], 9: [4, 3, 2], 10: [4, 3, 3]})

    def test_grid_has_row_break_after_each_row_but_last(self):
        pks = [Cartoon.objects.create(title='m%d' % i).pk for i in range(5)]
        self.write_contest(
            'halloween', '{% cartoons ' + ' '.join(map(str, pks)) + ' %}')
        html = self.client.get(
            reverse('contest', args=['halloween'])).content.decode()
        # 5 мультов -> ряды 3 + 2 -> один перенос, после третьего мульта
        self.assertEqual(html.count('w-100 d-none d-md-block'), 1)
        self.assertLess(html.index('m2'), html.index('w-100 d-none'))
        self.assertLess(html.index('w-100 d-none'), html.index('m3'))
