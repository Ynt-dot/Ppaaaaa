from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons', '0012_userpreference_avatar'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartoon',
            name='author_last_seen_comments',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
