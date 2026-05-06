from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons', '0023_comment_likes_count'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(fields=['author', '-likes_count', '-created_at'], name='comment_author_popular_idx'),
        ),
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(fields=['cartoon', '-likes_count', '-created_at'], name='comment_cartoon_popular_idx'),
        ),
    ]
