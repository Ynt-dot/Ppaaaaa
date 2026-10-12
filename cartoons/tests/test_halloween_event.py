from django.template.loader import render_to_string
from django.test import TestCase

from cartoons.models import Cartoon
from cartoons.templatetags.cartoon_tags import is_halloween_event


class HalloweenEventTagTests(TestCase):
    def test_matches_tag_variants(self):
        for tag in ('хэллоуин', '#Хэллоуин', ' хеллоуин ', 'Halloween'):
            with self.subTest(tag=tag):
                self.assertTrue(
                    is_halloween_event(Cartoon(tags=['котики', tag])))

    def test_ignores_other_tags(self):
        self.assertFalse(is_halloween_event(Cartoon(tags=['хэллоуин2026'])))
        self.assertFalse(is_halloween_event(Cartoon(tags=[])))

    def test_survives_garbage_tags(self):
        self.assertFalse(is_halloween_event(Cartoon(tags={'a': 1})))
        self.assertFalse(is_halloween_event(Cartoon(tags=[None, 5])))


class HalloweenEventCardTests(TestCase):
    def _render(self, tags, **extra):
        cartoon = Cartoon.objects.create(title='card', tags=tags)
        return render_to_string(
            'cartoons/cartoon_card.html', {'cartoon': cartoon, **extra})

    def test_event_card_highlighted(self):
        html = self._render(['хэллоуин'])
        self.assertIn('hw-event-card', html)
        self.assertIn('hw-event-badge', html)

    def test_regular_card_not_highlighted(self):
        html = self._render(['котики'])
        self.assertNotIn('hw-event-card', html)
        self.assertNotIn('hw-event-badge', html)

    def test_compact_card_gets_mark(self):
        html = self._render(['хэллоуин'], compact=True)
        self.assertIn('hw-event-mark', html)
