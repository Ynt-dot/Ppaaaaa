from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from datetime import timedelta


class Cartoon(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название")
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
