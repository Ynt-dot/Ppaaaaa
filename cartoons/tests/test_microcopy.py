from django.test import TestCase
from django.urls import reverse

from cartoons.models import Cartoon


class HalloweenMicrocopyTests(TestCase):
    def test_404_page(self):
        resp = self.client.get('/no-such-page-at-all/')
        self.assertEqual(resp.status_code, 404)
        self.assertContains(
            resp, 'Эта страница ушла на кладбище', status_code=404)

    def test_missing_cartoon_uses_404_page(self):
        resp = self.client.get(reverse('detail', args=[999999]))
        self.assertContains(
            resp, 'Эта страница ушла на кладбище', status_code=404)

    def test_comments_heading(self):
        cartoon = Cartoon.objects.create(title='c')
        resp = self.client.get(reverse('detail', args=[cartoon.pk]))
        self.assertContains(resp, 'Шёпот из склепа')

    def test_publish_button(self):
        resp = self.client.get(reverse('editor_create'))
        self.assertContains(resp, 'Выпустить в ночь')
