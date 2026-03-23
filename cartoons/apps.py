from django.apps import AppConfig


class CartoonsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cartoons'

    def ready(self):
        import cartoons.signals # noqa
