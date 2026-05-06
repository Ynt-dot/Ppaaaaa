from django.db import migrations, models
from django.db.models import Count, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce


def populate_likes_count(apps, schema_editor):
    Comment = apps.get_model('cartoons', 'Comment')
    CommentLike = apps.get_model('cartoons', 'CommentLike')
    likes_subquery = Subquery(
        CommentLike.objects.filter(comment_id=OuterRef('pk'))
        .values('comment_id')
        .annotate(cnt=Count('id'))
        .values('cnt'),
        output_field=IntegerField()
    )
    Comment.objects.update(likes_count=Coalesce(likes_subquery, 0))


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons', '0022_userpreference_avatar_gif'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='likes_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(populate_likes_count, migrations.RunPython.noop),
    ]
