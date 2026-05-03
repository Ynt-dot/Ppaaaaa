from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count


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
    description = models.TextField(blank=True, verbose_name="Описание")
    tags = models.JSONField(default=list, blank=True, verbose_name="Теги")
    views_count = models.PositiveIntegerField(default=0, verbose_name="Просмотры")
    author_last_seen_comments = models.DateTimeField(null=True, blank=True)

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
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cartoon', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_cartoon_user_like'
            ),
            models.UniqueConstraint(
                fields=['cartoon', 'session_key'],
                condition=models.Q(session_key__gt=''),
                name='unique_cartoon_session_like'
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Комментарий к «{self.cartoon}»"

    def display_author(self):
        if self.author:
            return self.author.username
        return self.author_name or 'Аноним'


class CommentLike(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE,
                                related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['comment', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_comment_user_like'
            ),
            models.UniqueConstraint(
                fields=['comment', 'session_key'],
                condition=models.Q(session_key__gt=''),
                name='unique_comment_session_like'
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
    rec_sort = models.CharField(max_length=20, default='trending')
    rec_author_filter = models.BooleanField(default=False)
    index_sort = models.CharField(max_length=20, default='trending')


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


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='favorites')
    cartoon = models.ForeignKey(Cartoon, on_delete=models.CASCADE,
                                related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('user', 'cartoon')]
        ordering = ['-created_at']
