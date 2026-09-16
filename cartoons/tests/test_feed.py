from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cartoons.models import Cartoon, CartoonLike, CartoonView


class IndexSortTests(TestCase):
    """Regression tests for the Subquery-based like/view counting in
    index() - previously two Count() annotations joined to different
    related tables in the same query caused a cartesian-product
    fan-out that got dramatically slower as likes/views accumulated
    (see get_recommendations() below for the same issue, benchmarked
    at ~7s/query with 300 cartoons x 60 likes x 60 views vs ~30ms
    after the fix). These tests only check correctness, not speed -
    timing assertions are unreliable in CI."""

    def setUp(self):
        self.author = User.objects.create_user('feed_author', password='x')
        self.liker1 = User.objects.create_user('feed_liker1', password='x')
        self.liker2 = User.objects.create_user('feed_liker2', password='x')

        self.old_liked = Cartoon.objects.create(
            title='old but liked', author=self.author)
        self.new_unliked = Cartoon.objects.create(
            title='new unliked', author=self.author)

        CartoonLike.objects.create(cartoon=self.old_liked, user=self.liker1)
        CartoonLike.objects.create(cartoon=self.old_liked, user=self.liker2)

        CartoonView.objects.create(
            cartoon=self.old_liked, user=self.liker1)
        CartoonView.objects.create(
            cartoon=self.old_liked, user=self.liker2)
        CartoonView.objects.create(
            cartoon=self.new_unliked, user=self.liker1)

    def test_popular_sort_orders_by_like_count(self):
        resp = self.client.get(reverse('index'), {'sort': 'popular'})
        titles = [c.title for c in resp.context['cartoons']]
        self.assertEqual(
            titles.index('old but liked'), 0,
            'more-liked cartoon should sort first')

    def test_unique_views_count_is_correct(self):
        resp = self.client.get(reverse('index'), {'sort': 'popular'})
        by_title = {c.title: c for c in resp.context['cartoons']}
        self.assertEqual(by_title['old but liked'].unique_views_count, 2)
        self.assertEqual(by_title['new unliked'].unique_views_count, 1)

    def test_trending_excludes_old_likes(self):
        old_liked_cartoon2 = Cartoon.objects.create(
            title='old like only', author=self.author)
        old_like = CartoonLike.objects.create(
            cartoon=old_liked_cartoon2, user=self.liker1)
        old_like.created_at = timezone.now() - timedelta(days=30)
        old_like.save(update_fields=['created_at'])

        resp = self.client.get(reverse('index'), {'sort': 'trending'})
        by_title = {c.title: c for c in resp.context['cartoons']}
        # 'old but liked' has 2 recent likes (created just now),
        # 'old like only' has a like from 30 days ago - trending
        # (7-day window) should not count it.
        self.assertEqual(by_title['old but liked'].recent_likes, 2)
        self.assertEqual(by_title['old like only'].recent_likes, 0)


class RecommendationsTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('rec_author', password='x')
        self.liker = User.objects.create_user('rec_liker', password='x')
        self.current = Cartoon.objects.create(
            title='current', author=self.author)
        self.popular = Cartoon.objects.create(
            title='popular one', author=self.author)
        self.plain = Cartoon.objects.create(
            title='plain one', author=self.author)
        CartoonLike.objects.create(cartoon=self.popular, user=self.liker)
        CartoonView.objects.create(cartoon=self.popular, user=self.liker)
        CartoonView.objects.create(cartoon=self.popular, user=self.author)

    def test_excludes_current_cartoon(self):
        resp = self.client.get(
            reverse('get_recommendations', args=[self.current.pk]),
            {'sort': 'popular'})
        self.assertEqual(resp.status_code, 200)
        html = resp.json()['html']
        self.assertNotIn('current', html)
        self.assertIn('popular one', html)

    def test_popular_ranks_liked_cartoon_first(self):
        resp = self.client.get(
            reverse('get_recommendations', args=[self.current.pk]),
            {'sort': 'popular'})
        html = resp.json()['html']
        self.assertLess(html.index('popular one'), html.index('plain one'))

    def test_author_filter_only_shows_same_author_cartoons(self):
        other_author = User.objects.create_user('rec_other', password='x')
        Cartoon.objects.create(title='by someone else', author=other_author)

        resp = self.client.get(
            reverse('get_recommendations', args=[self.current.pk]),
            {'sort': 'new', 'filter': 'author'})
        html = resp.json()['html']
        self.assertNotIn('by someone else', html)
        self.assertIn('popular one', html)

    def test_no_has_next_when_ten_or_fewer_results(self):
        resp = self.client.get(
            reverse('get_recommendations', args=[self.current.pk]),
            {'sort': 'new'})
        data = resp.json()
        self.assertFalse(data['has_next'])
        self.assertFalse(data['empty'])

    def test_pagination_across_pages(self):
        for i in range(15):
            Cartoon.objects.create(title=f'extra {i}', author=self.author)
        # 15 extra + popular + plain = 17 candidates total

        resp1 = self.client.get(
            reverse('get_recommendations', args=[self.current.pk]),
            {'sort': 'new', 'page': 1})
        data1 = resp1.json()
        self.assertTrue(data1['has_next'])
        self.assertEqual(data1['html'].count('<a href="/cartoon/'), 10)

        resp2 = self.client.get(
            reverse('get_recommendations', args=[self.current.pk]),
            {'sort': 'new', 'page': 2})
        data2 = resp2.json()
        self.assertFalse(data2['has_next'])
        self.assertEqual(data2['html'].count('<a href="/cartoon/'), 7)

    def test_pagination_no_duplicate_or_missing_items(self):
        titles = [f'extra {i}' for i in range(15)]
        for t in titles:
            Cartoon.objects.create(title=t, author=self.author)

        seen = []
        for page in (1, 2):
            resp = self.client.get(
                reverse('get_recommendations', args=[self.current.pk]),
                {'sort': 'new', 'page': page})
            seen.append(resp.json()['html'])

        combined = ''.join(seen)
        for t in titles + ['popular one', 'plain one']:
            self.assertEqual(
                combined.count(f'title="{t}"'), 1,
                f'{t!r} should appear exactly once across both pages')
