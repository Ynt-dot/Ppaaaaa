import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons', '0015_userpreference_rec_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='parent',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='replies',
                to='cartoons.comment',
            ),
        ),
        migrations.AddField(
            model_name='comment',
            name='level',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
