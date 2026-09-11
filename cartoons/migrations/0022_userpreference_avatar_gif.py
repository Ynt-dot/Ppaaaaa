from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons', '0021_userpreference_avatar_xy'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreference',
            name='avatar_gif',
            field=models.ImageField(blank=True, null=True, upload_to='avatars/'),
        ),
        migrations.RemoveField(
            model_name='userpreference',
            name='avatar_x',
        ),
        migrations.RemoveField(
            model_name='userpreference',
            name='avatar_y',
        ),
    ]
