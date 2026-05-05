from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons', '0020_userpreference_index_sort'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreference',
            name='avatar_x',
            field=models.FloatField(default=50.0),
        ),
        migrations.AddField(
            model_name='userpreference',
            name='avatar_y',
            field=models.FloatField(default=50.0),
        ),
    ]
