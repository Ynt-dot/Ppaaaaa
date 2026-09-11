from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons', '0014_alter_title_alter_username'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreference',
            name='rec_sort',
            field=models.CharField(default='trending_week', max_length=20),
        ),
        migrations.AddField(
            model_name='userpreference',
            name='rec_author_filter',
            field=models.BooleanField(default=False),
        ),
    ]
