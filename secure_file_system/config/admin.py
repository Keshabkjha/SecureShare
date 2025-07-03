"""
Django admin configuration for the Secure File System.
"""
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin
from django.conf import settings
import logging

# Import our custom admin site
from .admin_site import admin_site

logger = logging.getLogger(__name__)

# Register the default admin models with our custom admin site
try:
    admin_site.register(Group, GroupAdmin)
except Exception as e:
    logger.error(f'Error registering Group model: {str(e)}')

# Import and register other admin classes
try:
    from authentication.admin import UserAdmin
    from authentication.models import User
    admin_site.register(User, UserAdmin)
except ImportError as e:
    logger.warning(f'Could not import authentication admin: {str(e)}')

try:
    from files.admin import FileAdmin, SharedFileAdmin
    from files.models import File, SharedFile
    
    admin_site.register(File, FileAdmin)
    admin_site.register(SharedFile, SharedFileAdmin)
except ImportError as e:
    logger.warning(f'Could not import files admin: {str(e)}')

# Override the default admin site
admin.site = admin_site
