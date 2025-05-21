from django.apps import AppConfig


class AlaBackendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Ala_BackEnd'

    def ready(self):
        import Ala_BackEnd.signals
