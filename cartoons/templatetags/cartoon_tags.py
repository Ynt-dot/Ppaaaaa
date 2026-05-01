from django import template
from django.utils import timezone

register = template.Library()


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
