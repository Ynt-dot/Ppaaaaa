from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class Command(BaseCommand):
    help = 'Удаляет неактивированных пользователей (is_active=False), зарегист\
рированных более 24 часов назад'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=24)
        # Находим пользователей, которые неактивны и созданы раньше cutoff
        users_to_delete = User.objects.filter(is_active=False,
                                              date_joined__lt=cutoff)
        count = users_to_delete.count()
        if count > 0:
            users_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f'Удалено {count} неактивиров\
анных аккаунтов.'))
        else:
            self.stdout.write(self.style.SUCCESS('Нет аккаунтов для удаления.'
                                                 ))
