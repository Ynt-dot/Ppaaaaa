import base64
import json
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from cartoons.models import Cartoon, normalize_frame_backgrounds
from cartoons.utils import create_gif_from_frames

BLACK = '#000000'
WHITE = '#ffffff'


def _transparent_frame():
    # PNG_FRAME из helpers - непрозрачный чёрный пиксель, на нём фон не
    # проверить; здесь нужен по-настоящему прозрачный кадр.
    buf = BytesIO()
    Image.new('RGBA', (1, 1), (0, 0, 0, 0)).save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


FRAME = _transparent_frame()


def _gif_pixels(content_file):
    """Цвет пикселя (0, 0) каждого кадра GIF."""
    content_file.seek(0)
    pixels = []
    with Image.open(BytesIO(content_file.read())) as gif:
        for i in range(getattr(gif, 'n_frames', 1)):
            gif.seek(i)
            pixels.append(gif.convert('RGB').getpixel((0, 0)))
    return pixels


class NormalizeFrameBackgroundsTests(TestCase):
    def test_pads_missing_with_white(self):
        self.assertEqual(
            normalize_frame_backgrounds([BLACK], 3), [BLACK, WHITE, WHITE])

    def test_replaces_unknown_and_trims(self):
        self.assertEqual(
            normalize_frame_backgrounds(['#123456', BLACK, BLACK], 2),
            [WHITE, BLACK])

    def test_non_list_means_all_white(self):
        self.assertEqual(
            normalize_frame_backgrounds('junk', 2), [WHITE, WHITE])

    def test_old_cartoon_without_backgrounds_is_white(self):
        cartoon = Cartoon(frames_data=[FRAME, FRAME])
        self.assertEqual(cartoon.frame_backgrounds_full(), [WHITE, WHITE])


class GifBackgroundTests(TestCase):
    """Кадры прозрачные - фон каждого кадра GIF задаёт его подложка."""

    def test_default_background_is_white(self):
        gif = create_gif_from_frames([FRAME], fps=10)
        self.assertEqual(_gif_pixels(gif), [(255, 255, 255)])

    def test_per_frame_backgrounds(self):
        gif = create_gif_from_frames(
            [FRAME, FRAME], fps=10, backgrounds=[BLACK, WHITE])
        self.assertEqual(_gif_pixels(gif), [(0, 0, 0), (255, 255, 255)])


class EditorBackgroundSaveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('bg_author', password='x')
        self.client.force_login(self.user)

    def _post(self, url, frames=1, **extra):
        data = {
            'title': 'bg cartoon',
            'fps': '10',
            'frames': json.dumps([FRAME] * frames),
            'tags': '[]',
            'description': '',
        }
        data.update(extra)
        return self.client.post(url, data)

    def test_saves_per_frame_backgrounds_and_gif(self):
        self._post(reverse('editor_create'), frames=2,
                   frame_backgrounds=json.dumps([BLACK, WHITE]))
        cartoon = Cartoon.objects.get(title='bg cartoon')
        self.assertEqual(cartoon.frame_backgrounds, [BLACK, WHITE])
        self.assertEqual(
            _gif_pixels(cartoon.preview), [(0, 0, 0), (255, 255, 255)])

    def test_missing_backgrounds_fall_back_to_white(self):
        self._post(reverse('editor_create'), frames=2)
        cartoon = Cartoon.objects.get(title='bg cartoon')
        self.assertEqual(cartoon.frame_backgrounds, [WHITE, WHITE])

    def test_garbage_backgrounds_fall_back_to_white(self):
        self._post(reverse('editor_create'), frame_backgrounds='not json')
        cartoon = Cartoon.objects.get(title='bg cartoon')
        self.assertEqual(cartoon.frame_backgrounds, [WHITE])

    def test_edit_without_field_keeps_backgrounds(self):
        cartoon = Cartoon.objects.create(
            title='old', author=self.user, frames_data=[FRAME],
            frame_backgrounds=[BLACK])
        self._post(reverse('editor_edit', args=[cartoon.pk]))
        cartoon.refresh_from_db()
        self.assertEqual(cartoon.frame_backgrounds, [BLACK])

    def test_edit_can_change_single_frame(self):
        cartoon = Cartoon.objects.create(
            title='old', author=self.user, frames_data=[FRAME, FRAME],
            frame_backgrounds=[WHITE, WHITE])
        self._post(reverse('editor_edit', args=[cartoon.pk]), frames=2,
                   frame_backgrounds=json.dumps([WHITE, BLACK]))
        cartoon.refresh_from_db()
        self.assertEqual(cartoon.frame_backgrounds, [WHITE, BLACK])


class EditorInitialBackgroundTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('bg_author2', password='x')

    def test_new_cartoon_starts_black_with_white_ink(self):
        resp = self.client.get(reverse('editor_create'))
        self.assertEqual(resp.context['frame_backgrounds'], [BLACK])
        self.assertEqual(resp.context['initial_ink'], WHITE)
        self.assertContains(
            resp, 'class="color-btn ink-color active" data-color="#ffffff"')

    def test_edit_starts_with_own_backgrounds(self):
        cartoon = Cartoon.objects.create(
            title='mixed', author=self.user, frames_data=[FRAME, FRAME],
            frame_backgrounds=[WHITE, BLACK])
        self.client.force_login(self.user)
        resp = self.client.get(reverse('editor_edit', args=[cartoon.pk]))
        self.assertEqual(resp.context['frame_backgrounds'], [WHITE, BLACK])
        self.assertEqual(resp.context['initial_ink'], BLACK)

    def test_continuation_inherits_original_backgrounds(self):
        original = Cartoon.objects.create(
            title='old white original', author=self.user,
            frames_data=[FRAME, FRAME])
        resp = self.client.get(
            reverse('editor_create'), {'continue': original.pk})
        self.assertEqual(resp.context['frame_backgrounds'], [WHITE, WHITE])


class PlayerBackgroundTests(TestCase):
    def test_player_gets_frame_backgrounds(self):
        cartoon = Cartoon.objects.create(
            title='mixed', frames_data=[FRAME, FRAME],
            frame_backgrounds=[BLACK, WHITE])
        resp = self.client.get(reverse('detail', args=[cartoon.pk]))
        self.assertContains(
            resp,
            '<script id="frame-backgrounds-data" type="application/json">'
            '["#000000", "#ffffff"]</script>')


class ShrinkFrameTests(TestCase):
    def test_fast_path_keeps_light_edges(self):
        # белая полоса до x=2502: блок 2500-2504 при уменьшении в 5 раз
        # закрыт на 2/5 - край должен остаться белым, полупрозрачным, а
        # не серым (если усреднять цвет без учёта альфы - тёмный ободок)
        from cartoons.utils import _shrink_frame
        img = Image.new('RGBA', (3000, 2000), (0, 0, 0, 0))
        img.paste((255, 255, 255, 255), (0, 0, 2502, 2000))
        small = _shrink_frame(img, (600, 400))
        self.assertEqual(small.size, (600, 400))
        r, g, b, a = small.getpixel((500, 10))
        self.assertGreater(min(r, g, b), 245)
        self.assertTrue(90 <= a <= 115, a)

    def test_other_sizes_still_resized(self):
        from cartoons.utils import _shrink_frame
        img = Image.new('RGBA', (1234, 567), (255, 0, 0, 255))
        self.assertEqual(_shrink_frame(img, (600, 400)).size, (600, 400))
