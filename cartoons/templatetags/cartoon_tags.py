import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

register = template.Library()


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
