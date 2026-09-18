from django.db import models
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
import uuid
from django.utils import timezone
from datetime import timedelta


class UnicodeJSONEncoder(DjangoJSONEncoder):
    """Как обычный DjangoJSONEncoder, но не экранирует не-ASCII
    символы в \\uXXXX - иначе кириллица в JSON-полях (например,
    Cartoon.tags) хранится нечитаемыми escape-последовательностями и
    её невозможно найти обычным LIKE/icontains по сырому тексту поля
    (см. поиск - views.search())."""
    def __init__(self, *args, **kwargs):
        kwargs['ensure_ascii'] = False
        super().__init__(*args, **kwargs)


class Cartoon(models.Model):
    title = models.CharField(max_length=100, verbose_name="Название")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                               blank=True, related_name='cartoons')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    preview = models.ImageField(upload_to='cartoons/gifs/')
    # сюда сохраним GIF
    frames_data = models.JSONField(default=dict, blank=True)
    # метаданные кадров
    fps = models.PositiveSmallIntegerField(default=12)
    description = models.TextField(
        max_length=1000, blank=True, verbose_name="Описание")
    tags = models.JSONField(
        default=list, blank=True, encoder=UnicodeJSONEncoder,
        verbose_name="Теги")
    views_count = models.PositiveIntegerField(
        default=0, verbose_name="Просмотры")
    author_last_seen_comments = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(
        default=False, verbose_name="Закреплён на странице автора")
    # Оригинал для этого мульта - если он сам является продолжением.
    # SET_NULL, а не CASCADE: удаление оригинала не должно утаскивать
    # за собой все продолжения.
    continuation_of = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='continuations', verbose_name="Оригинал")

    class Meta:
        ordering = ['-created_at']  # сортировка по новизне

    def __str__(self):
        return self.title


class EmailVerificationToken(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='verification_token'
        )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # новое поле
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def is_valid(self):
        return timezone.now() <= self.expires_at

    def __str__(self):
        return f"Token for {self.user.username}"


class CartoonLike(models.Model):
    cartoon = models.ForeignKey(Cartoon, on_delete=models.CASCADE,
                                related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cartoon', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_cartoon_user_like'
            ),
        ]


class Comment(models.Model):
    cartoon = models.ForeignKey(Cartoon, on_delete=models.CASCADE,
                                related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE,
                               null=True, blank=True, related_name='replies')
    level = models.PositiveSmallIntegerField(default=0)
    author = models.ForeignKey(User, on_delete=models.SET_NULL,
                               null=True, blank=True)
    author_name = models.CharField(max_length=50, blank=True)
    text = models.TextField(max_length=2000)
    is_edited = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    likes_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['author', '-likes_count', '-created_at'],
                name='comment_author_popular_idx'),
            models.Index(
                fields=['cartoon', '-likes_count', '-created_at'],
                name='comment_cartoon_popular_idx'),
        ]

    def __str__(self):
        return f"Комментарий к «{self.cartoon}»"

    def display_author(self):
        if self.author:
            pref = getattr(self.author, 'preference', None)
            if pref and pref.display_name:
                return pref.display_name
            return self.author.username
        return self.author_name or 'Аноним'


class CommentLike(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE,
                                related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['comment', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_comment_user_like'
            ),
        ]


class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                related_name='preference')
    comment_sort = models.CharField(
        max_length=10,
        default='popular',
        choices=[('popular', 'По популярности'), ('newest', 'По новизне')]
    )
    avatar = models.ForeignKey(
        'Cartoon', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='used_as_avatar'
    )
    avatar_gif = models.ImageField(upload_to='avatars/', null=True, blank=True)
    rec_sort = models.CharField(max_length=20, default='trending')
    rec_author_filter = models.BooleanField(default=False)
    index_sort = models.CharField(max_length=20, default='trending')
    # Отображаемое имя - показывается вместо C-key (User.username)
    # везде, где виден пользователь (комментарии, страница профиля и
    # т.д.). Не задано - показывается C-key. В отличие от C-key, не
    # ограничено требованиями к нику - только длиной.
    display_name = models.CharField(
        max_length=15, blank=True, default='', verbose_name="Отображаемое имя")
    description = models.TextField(
        max_length=1000, blank=True, default='', verbose_name="О себе")
    # Ставится только вручную в админке - не через какой-либо
    # пользовательский запрос.
    is_troll = models.BooleanField(
        default=False, verbose_name="Тролль",
        help_text="Комментарии показываются с кнопкой \"заблокировать\" "
                  "всем, а не только автору мульта.")


class UserBlock(models.Model):
    blocker = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='blocked_users')
    blocked = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='blocked_by_users')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('blocker', 'blocked')]


class UserNote(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='authored_notes')
    about = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='notes_about')
    text = models.TextField(max_length=256, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('author', 'about')]


class CartoonView(models.Model):
    cartoon = models.ForeignKey(Cartoon, on_delete=models.CASCADE,
                                related_name='unique_views')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='viewed_cartoons')

    class Meta:
        unique_together = [('cartoon', 'user')]


class SiteSettings(models.Model):
    """Синглтон (всегда pk=1) с общесайтовыми настройками, которые
    задаёт админ - пока только аватар по умолчанию для пользователей,
    которые не выбрали свой."""
    default_avatar_gif = models.ImageField(
        upload_to='avatars/', null=True, blank=True,
        verbose_name="Аватар по умолчанию")

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return "Настройки сайта"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class AccountAccessLog(models.Model):
    """Одна строка на пару (пользователь, IP), с которой он заходил
    на сайт - помогает админу увидеть все IP конкретного аккаунта и,
    наоборот, все аккаунты, заходившие с конкретного IP (мультиаккаунты,
    обход бана). device_id - id из cookie-файла (см. middleware.py),
    user_agent - строка браузера, обе сохраняются "как есть", без
    попытки собрать из них надёжный отпечаток устройства."""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='access_logs')
    ip_address = models.GenericIPAddressField(verbose_name="IP-адрес")
    device_id = models.CharField(max_length=36, blank=True, default='')
    user_agent = models.CharField(max_length=255, blank=True, default='')
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    visit_count = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [('user', 'ip_address')]
        verbose_name = "Запись о входе"
        verbose_name_plural = "Записи о входах (IP/устройства)"

    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"


class BannedIdentifier(models.Model):
    """IP-адрес или device_id (см. AccountAccessLog), забаненный
    вручную в админке - блокирует доступ к сайту с этого
    идентификатора (см. middleware.py), независимо от того, под
    каким аккаунтом или вообще без входа пытаются зайти."""
    KIND_IP = 'ip'
    KIND_DEVICE = 'device'
    KIND_CHOICES = [
        (KIND_IP, 'IP-адрес'),
        (KIND_DEVICE, 'Device ID (cookie)'),
    ]
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    value = models.CharField(max_length=100, verbose_name="Значение")
    reason = models.CharField(
        max_length=255, blank=True, verbose_name="Причина")
    banned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)
    banned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('kind', 'value')]
        verbose_name = "Бан по IP/устройству"
        verbose_name_plural = "Баны по IP/устройствам"

    def __str__(self):
        return f"{self.get_kind_display()}: {self.value}"


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='favorites')
    cartoon = models.ForeignKey(Cartoon, on_delete=models.CASCADE,
                                related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'cartoon')]
        ordering = ['-created_at']
