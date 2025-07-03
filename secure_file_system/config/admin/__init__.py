from django.contrib import admin
from .admin import SecureFileSystemAdminSite

# Create an instance of the custom admin site
admin_site = SecureFileSystemAdminSite(name='secure_file_system_admin')

# Make it available as default_site for Django's default admin
default_site = admin_site
