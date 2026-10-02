from django.db import migrations


def backfill_profile_slug(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserPreference = apps.get_model('cartoons', 'UserPreference')

    taken = set(
        UserPreference.objects.exclude(profile_slug=None)
        .values_list('profile_slug', flat=True)
    )

    for user in User.objects.all():
        pref, _ = UserPreference.objects.get_or_create(user=user)
        if pref.profile_slug:
            continue
        slug = user.username
        suffix = 1
        while slug in taken:
            suffix += 1
            slug = f'{user.username}{suffix}'
        pref.profile_slug = slug
        pref.save(update_fields=['profile_slug'])
        taken.add(slug)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cartoons',
         '0028_cartoon_is_pinned_userpreference_description_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_profile_slug, noop_reverse),
    ]
