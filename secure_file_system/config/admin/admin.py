from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _


class SecureFileSystemAdminSite(AdminSite):
    site_header = _("Secure File System Admin")
    site_title = _("Secure File System Site Admin")
    index_title = _("Welcome to Secure File System Admin")

# Note: We don't create the admin_site instance here anymore
# It's now created in __init__.py to avoid circular imports
