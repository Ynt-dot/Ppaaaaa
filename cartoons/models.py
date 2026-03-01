from django.db import models
from django.contrib.auth.models import User


class Cartoon(models.Model):
    title = models.CharField(max_length=200, verbose_name="Название")
    author = models.ForeignKey(User, on_delete=models.CASCADE,
                               related_name='cartoons')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    preview = models.ImageField(upload_to='cartoons/gifs/')
    # сюда сохраним GIF
    frames_data = models.JSONField(default=dict, blank=True)
    # метаданные кадров
    fps = models.PositiveSmallIntegerField(default=12)

    class Meta:
        ordering = ['-created_at']  # сортировка по новизне

    def __str__(self):
        return self.title
