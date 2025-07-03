"""
App configuration for the config app.
"""
from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig as BaseAdminConfig


class ConfigConfig(AppConfig):
    """Default app config for the config app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'config'

    def ready(self):
        """
        Method called when the app is ready.
        Import admin modules here to ensure they're loaded after the app registry is populated.
        """
        # Import the admin module to register models
        from . import admin  # noqa


class AdminConfig(BaseAdminConfig):
    """
    Custom admin configuration that uses our custom admin site.
    """
    default_site = 'config.admin_site.CustomAdminSite'
