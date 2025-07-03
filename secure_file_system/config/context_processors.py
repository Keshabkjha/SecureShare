"""
Context processors for the config app.
"""
from django.conf import settings

def site_info(request):
    """
    Add site-wide context variables.
    """
    return {
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'Secure File System'),
        'SITE_URL': getattr(settings, 'SITE_URL', '/'),
        'VERSION': getattr(settings, 'VERSION', '1.0.0'),
        'ENVIRONMENT': getattr(settings, 'ENVIRONMENT', 'development'),
        'DEBUG': settings.DEBUG,
    }
