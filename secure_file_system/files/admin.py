from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import File, FileShareLink


def format_file_size(size):
    """Convert file size to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    """Admin interface for File model."""
    list_display = ('original_filename', 'file_type', 'uploader_email', 'file_size', 'description_short', 'created_at')
    list_filter = ('file_type', 'created_at', 'updated_at')
    search_fields = ('original_filename', 'description', 'uploader__email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'file_size_formatted', 'download_link')
    fieldsets = (
        (None, {
            'fields': ('id', 'uploader', 'file_type', 'file', 'file_size_formatted', 'download_link')
        }),
        ('Details', {
            'fields': ('original_filename', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uploader')
    
    def uploader_email(self, obj):
        return obj.uploader.email
    uploader_email.short_description = 'Uploaded By'
    uploader_email.admin_order_field = 'uploader__email'
    
    def file_size(self, obj):
        return format_file_size(obj.file.size)
    file_size.short_description = 'Size'
    file_size.admin_order_field = 'file__size'
    
    def file_size_formatted(self, obj):
        return format_file_size(obj.file.size)
    file_size_formatted.short_description = 'File Size'
    
    def description_short(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else obj.description
    description_short.short_description = 'Description'
    
    def download_link(self, obj):
        if obj.id:
            url = reverse('admin:files_file_download', args=[obj.id])
            return mark_safe(f'<a href="{url}">Download</a>')
        return "-"
    download_link.short_description = 'Download'
    
    def has_add_permission(self, request):
        # Only allow adding files through the API
        return False


@admin.register(FileShareLink)
class FileShareLinkAdmin(admin.ModelAdmin):
    """Admin interface for FileShareLink model."""
    list_display = ('token', 'file_name', 'created_by_email', 'expires_at', 'is_active', 'download_count', 'max_downloads')
    list_filter = ('is_active', 'created_at', 'expires_at')
    search_fields = ('token', 'file__original_filename', 'created_by__email')
    readonly_fields = ('token', 'created_at', 'download_count', 'download_link')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('file', 'created_by')
    
    def file_name(self, obj):
        return obj.file.original_filename
    file_name.short_description = 'File'
    file_name.admin_order_field = 'file__original_filename'
    
    def created_by_email(self, obj):
        return obj.created_by.email
    created_by_email.short_description = 'Created By'
    created_by_email.admin_order_field = 'created_by__email'
    
    def download_link(self, obj):
        if obj.id and obj.is_active:
            url = reverse('files:public_file_download', kwargs={'pk': obj.id})
            full_url = f"{settings.SITE_URL}{url}" if hasattr(settings, 'SITE_URL') else f"[SITE_URL not set]{url}"
            return mark_safe(f'<a href="{url}" target="_blank">{full_url}</a>')
        return "-"
    download_link.short_description = 'Share Link'
    
    def has_add_permission(self, request):
        # Only allow adding share links through the API
        return False
