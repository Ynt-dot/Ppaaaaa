import os

from django import template
from django.contrib.staticfiles import finders
from django.db.models import Count
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from cartoons.models import Cartoon

register = template.Library()


def balanced_row_sizes(count, per_row=4):
    """Размеры рядов сетки: полные ряды по per_row, но без одинокого
    хвоста - остаток 1 превращается в 3+2, остаток 2 - в 3+3 (для
    per_row=4: 5 -> [3, 2], 6 -> [3, 3], 9 -> [4, 3, 2])."""
    if count <= per_row:
        return [count] if count else []
    full, rest = divmod(count, per_row)
    if rest in (1, 2):
        return [per_row] * (full - 1) + [per_row - 1, rest + 1]
    return [per_row] * full + ([rest] if rest else [])


@register.simple_tag(takes_context=True)
def cartoons(context, *pks):
    """{% cartoons 12 34 56 %} - сетка карточек выбранных мультов, как в
    поиске, в указанном порядке. Для страниц конкурсов (их HTML
    рендерится как шаблон, см. views.contest). Несуществующие номера
    молча пропускаются - удалённый мульт не ломает страницу."""
    ids = []
    for pk in pks:
        try:
            ids.append(int(pk))
        except (TypeError, ValueError):
            continue
    found = {
        c.pk: c for c in Cartoon.objects.filter(pk__in=ids)
        .select_related('author', 'author__preference')
        .annotate(unique_views_count=Count('unique_views', distinct=True))
    }
    items = [found[i] for i in ids if i in found]
    # Перенос строки (на широком экране) после каждого ряда, кроме
    # последнего - иначе неполные ряды из balanced_row_sizes слиплись бы.
    breaks, end = set(), 0
    for size in balanced_row_sizes(len(items))[:-1]:
        end += size
        breaks.add(end - 1)
    return mark_safe(render_to_string(
        'cartoons/_cartoon_grid.html',
        {'cartoons': [(c, i in breaks) for i, c in enumerate(items)]},
        request=context.get('request')))


@register.simple_tag
def static_v(path):
    """{% static %} с версией ?v=<mtime файла>. У нашей статики нет хэшей
    в именах, и браузер мог держать старый JS при новом шаблоне - с
    версией адрес меняется при каждом изменении файла."""
    url = static(path)
    full_path = finders.find(path)
    if not full_path:
        return url
    return f'{url}?v={int(os.path.getmtime(full_path))}'


# Тег хэллоуинского ивента и его частые варианты написания; сравниваем
# без регистра и без ведущей решётки.
HALLOWEEN_TAGS = {'хэллоуин', 'хеллоуин', 'halloween'}


@register.filter
def is_halloween_event(cartoon):
    """Мульт участвует в ивенте #хэллоуин - для подсветки карточки."""
    tags = getattr(cartoon, 'tags', None)
    if not isinstance(tags, list):
        return False
    return any(isinstance(t, str) and t.strip().lstrip('#').lower()
               in HALLOWEEN_TAGS for t in tags)


@register.filter
def display_name(user):
    if not user:
        return ''
    pref = getattr(user, 'preference', None)
    if pref and pref.display_name:
        return pref.display_name
    return user.username


@register.filter
def profile_url(user):
    if not user:
        return ''
    return reverse('user_profile', args=[user.username])


@register.filter
def time_ago(dt):
    if not dt:
        return ''
    now = timezone.now()
    diff = int((now - dt).total_seconds())
    if diff < 60:
        return 'только что'
    if diff < 3600:
        return f'{diff // 60}м назад'
    if diff < 86400:
        return f'{diff // 3600}ч назад'
    if diff < 604800:
        return f'{diff // 86400}д назад'
    if diff < 2592000:
        return f'{diff // 604800}н назад'
    if diff < 31536000:
        return f'{diff // 2592000}мес назад'
    return f'{diff // 31536000}г назад'
