from django.db import migrations


def reencode_tags(apps, schema_editor):
    """Перезаписывает tags у уже существующих мультов, чтобы они
    сохранились через новый кодировщик (UnicodeJSONEncoder,
    ensure_ascii=False) - иначе кириллица в тегах, сохранённых до
    этой миграции, так и останется нечитаемыми \\uXXXX-escape'ами и
    не будет находиться поиском."""
    Cartoon = apps.get_model('cartoons', 'Cartoon')
    for cartoon in Cartoon.objects.exclude(tags=[]).only('id', 'tags'):
        cartoon.save(update_fields=['tags'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons', '0034_alter_cartoon_tags'),
    ]

    operations = [
        migrations.RunPython(reencode_tags, noop_reverse),
    ]
