"""SQLite по умолчанию регистронезависимо сравнивает через LIKE
только ASCII-символы - кириллица в разном регистре ("Привет" и
"привет") не считается совпадением, в отличие от MySQL с обычными
utf8-коллациями (там регистронезависимость работает и для кириллицы
из коробки). Раз сайт русскоязычный, а `icontains()` (в том числе
поиск, см. views.search()) в SQLite транслируется именно в LIKE - на
dev-окружении это означает, что поиск/фильтры по кириллице в другом
регистре просто не находят результат.

Чиним, переопределяя встроенную функцию LIKE в SQLite на реализацию
через Python re.IGNORECASE - он корректно регистронезависим для
любого Unicode. Только для SQLite (dev/тесты); в MySQL (продакшн)
трогать нечего.
"""
import re

from django.db.backends.signals import connection_created


def _like_pattern_to_regex(pattern, escape_char):
    """SQL LIKE: % - любая последовательность, _ - один любой символ,
    экранируются через escape_char (у Django всегда '\\')."""
    out = []
    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if escape_char and ch == escape_char and i + 1 < n:
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        if ch == '%':
            out.append('.*')
        elif ch == '_':
            out.append('.')
        else:
            out.append(re.escape(ch))
        i += 1
    return '(?s)\\A' + ''.join(out) + '\\Z'


def _like(pattern, value, escape_char='\\'):
    if pattern is None or value is None:
        return None
    regex = _like_pattern_to_regex(pattern, escape_char)
    return 1 if re.match(regex, value, re.IGNORECASE) else 0


def _like2(pattern, value):
    return _like(pattern, value, '\\')


def _like3(pattern, value, escape_char):
    return _like(pattern, value, escape_char)


def _register_unicode_like(sender, connection, **kwargs):
    if connection.vendor != 'sqlite':
        return
    raw = connection.connection
    raw.create_function('LIKE', 2, _like2)
    raw.create_function('LIKE', 3, _like3)


connection_created.connect(_register_unicode_like)
