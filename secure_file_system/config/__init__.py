from .admin import admin_site

# This will make our custom admin site the default
# when 'django.contrib.admin' is in INSTALLED_APPS
# and 'django.contrib.admin.apps.SimpleAdminConfig' is not in INSTALLED_APPS

default_app_config = 'config.apps.AdminConfig'