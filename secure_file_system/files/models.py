import os
import uuid
from typing import Optional, Type, TypeVar, Any, Dict, Tuple, Union, List
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator
from django.core.files.uploadedfile import UploadedFile
from django.contrib.auth import get_user_model

User = get_user_model()


def user_directory_path(instance: 'File', filename: str) -> str:
    """File will be uploaded to MEDIA_ROOT/user_<id>/<filename>"""
    return f'user_{instance.uploaded_by.id}/{uuid.uuid4().hex}_{filename}'


class File(models.Model):
    """Model to store file information"""
    class FileType(models.TextChoices):
        DOCX = 'DOCX', _('Word Document')
        XLSX = 'XLSX', _('Excel Spreadsheet')
        PPTX = 'PPTX', _('PowerPoint Presentation')
    
    id: 'models.UUIDField' = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file: 'models.FileField[Union[UploadedFile, str]]' = models.FileField(
        _('file'),
        upload_to=user_directory_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['docx', 'xlsx', 'pptx'],
                message=_('Only .docx, .xlsx, and .pptx files are allowed.')
            )
        ]
    )
    original_filename: 'models.CharField' = models.CharField(_('original filename'), max_length=255)
    file_type: 'models.CharField' = models.CharField(
        _('file type'),
        max_length=10,
        choices=FileType.choices
    )
    file_size: 'models.PositiveBigIntegerField' = models.PositiveBigIntegerField(_('file size in bytes'))
    uploaded_by: 'models.ForeignKey[User, models.Model]' = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_files',
        verbose_name=_('uploaded by')
    )
    created_at: 'models.DateTimeField' = models.DateTimeField(_('created at'), auto_now_add=True)
    updated_at: 'models.DateTimeField' = models.DateTimeField(_('updated at'), auto_now=True)
    description: 'models.TextField' = models.TextField(_('description'), blank=True)
    is_public: 'models.BooleanField' = models.BooleanField(_('is public'), default=False)
    
    class Meta:
        verbose_name = _('file')
        verbose_name_plural = _('files')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.original_filename} ({self.get_file_type_display()}) - {self.uploaded_by.email}"
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        # Set the original filename and file type before saving
        if not self.original_filename and self.file:
            self.original_filename = os.path.basename(self.file.name)
        
        # Set file size
        if self.file:
            self.file_size = self.file.size
            
            # Determine file type based on extension
            if hasattr(self.file, 'name') and self.file.name:
                ext = os.path.splitext(self.file.name)[1].lower()
                if ext == '.docx':
                    self.file_type = self.FileType.DOCX
                elif ext == '.xlsx':
                    self.file_type = self.FileType.XLSX
                elif ext == '.pptx':
                    self.file_type = self.FileType.PPTX
        
        super().save(*args, **kwargs)
    
    def get_download_url(self) -> str:
        """Generate a secure download URL for the file"""
        from django.urls import reverse
        from django.utils.http import urlencode
        from django.utils.crypto import get_random_string
        
        # Create a one-time token for this download
        token = get_random_string(length=32)
        
        # Store the token in the cache with a short expiration
        from django.core.cache import cache
        cache_key = f'file_download_{self.id}_{token}'
        cache.set(cache_key, True, timeout=3600)  # 1 hour expiration
        
        # Generate the download URL
        return f"{settings.FRONTEND_URL}/api/files/{self.id}/download/?token={token}"


class FileShareLink(models.Model):
    """Model to manage shared file access links"""
    id: 'models.UUIDField' = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file: 'models.ForeignKey[File, models.Model]' = models.ForeignKey(
        File,
        on_delete=models.CASCADE,
        related_name='share_links',
        verbose_name=_('file')
    )
    token: 'models.UUIDField' = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_by: 'models.ForeignKey[User, models.Model]' = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_share_links',
        verbose_name=_('created by')
    )
    created_at: 'models.DateTimeField' = models.DateTimeField(_('created at'), auto_now_add=True)
    expires_at: 'models.DateTimeField' = models.DateTimeField(_('expires at'), null=True, blank=True)
    is_active: 'models.BooleanField' = models.BooleanField(_('is active'), default=True)
    max_downloads: 'models.PositiveIntegerField' = models.PositiveIntegerField(
        _('maximum downloads'),
        null=True,
        blank=True,
        help_text=_('Maximum number of times this link can be used (leave empty for unlimited)')
    )
    download_count: 'models.PositiveIntegerField' = models.PositiveIntegerField(_('download count'), default=0)
    
    class Meta:
        verbose_name = _('file share link')
        verbose_name_plural = _('file share links')
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"Share link for {self.file.original_filename} by {self.created_by.email}"
    
    def is_expired(self) -> bool:
        """Check if the share link has expired"""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        if self.max_downloads and self.download_count >= self.max_downloads:
            return True
        return not self.is_active
    
    def get_absolute_url(self) -> str:
        """Get the full shareable URL"""
        from django.urls import reverse
        path = reverse('files:shared-file-download', kwargs={'token': self.token})
        return f"{settings.FRONTEND_URL}{path}"
