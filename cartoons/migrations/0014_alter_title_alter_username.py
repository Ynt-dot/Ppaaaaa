from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons', '0013_cartoon_author_last_seen_comments'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cartoon',
            name='title',
            field=models.CharField(max_length=15, verbose_name='Название'),
        ),
    ]
