from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from cartoons.models import Cartoon


@override_settings(SITE_URL='https://example.test')
class OpenGraphTagsTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('og_author', password='x')

    def test_og_tags_present_with_description(self):
        cartoon = Cartoon.objects.create(
            title='My Cartoon', author=self.author,
            description='A fun little animation')
        resp = self.client.get(reverse('detail', args=[cartoon.pk]))
        content = resp.content.decode()
        self.assertIn(
            '<meta property="og:title" content="My Cartoon">', content)
        self.assertIn('A fun little animation', content)
        self.assertIn(
            f'<meta property="og:url" content="https://example.test'
            f'{reverse("detail", args=[cartoon.pk])}">', content)
        self.assertIn(
            'twitter:card" content="summary_large_image"', content)

    def test_og_description_falls_back_when_no_description(self):
        cartoon = Cartoon.objects.create(
            title='No Desc', author=self.author)
        resp = self.client.get(reverse('detail', args=[cartoon.pk]))
        content = resp.content.decode()
        self.assertIn('No Desc', content)
        self.assertIn('og_author', content)

    def test_og_image_points_to_absolute_gif_url_when_preview_exists(self):
        cartoon = Cartoon.objects.create(
            title='With preview', author=self.author)
        cartoon.preview.name = 'cartoons/gifs/fake.gif'
        cartoon.save(update_fields=['preview'])
        resp = self.client.get(reverse('detail', args=[cartoon.pk]))
        content = resp.content.decode()
        self.assertIn(
            'og:image" content="https://example.test/media/'
            'cartoons/gifs/fake.gif"', content)
        self.assertIn('og:image:type" content="image/gif"', content)

    def test_no_og_image_tag_when_no_preview(self):
        cartoon = Cartoon.objects.create(title='No preview',
                                         author=self.author)
        resp = self.client.get(reverse('detail', args=[cartoon.pk]))
        content = resp.content.decode()
        self.assertNotIn('property="og:image"', content)
