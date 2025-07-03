import uuid
from datetime import timedelta
from typing import Any, Dict, Optional, Type, TypeVar, cast
from django.utils import timezone
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from django.db.models import Model
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest

from .models import File, FileShareLink
from authentication.models import User as UserModel

# Type variable for generic serializers
T = TypeVar('T', bound=Model)


class FileSerializer(serializers.ModelSerializer[File]):
    """Serializer for file upload and details"""
    file: 'serializers.FileField' = serializers.FileField(
        required=True,
        max_length=255,
        allow_empty_file=False,
        use_url=True
    )
    file_type: 'serializers.CharField' = serializers.CharField(read_only=True)
    file_size: 'serializers.IntegerField' = serializers.IntegerField(read_only=True)
    uploaded_by: 'serializers.PrimaryKeyRelatedField' = serializers.PrimaryKeyRelatedField(
        read_only=True,
        default=serializers.CurrentUserDefault()
    )
    download_url: 'serializers.SerializerMethodField' = serializers.SerializerMethodField()
    file_name: 'serializers.SerializerMethodField' = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            'id', 'file', 'original_filename', 'file_type', 'file_size',
            'uploaded_by', 'created_at', 'description', 'is_public',
            'download_url', 'file_name'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'file_type', 'file_size']

    def get_download_url(self, obj: File) -> Optional[str]:
        """
        Generate a secure download URL for the file
        This will be a one-time use URL that expires
        """
        request = self.context.get('request')
        if request:
            return obj.get_download_url()
        return None
    
    def get_file_name(self, obj: File) -> str:
        """Return the original filename"""
        return obj.original_filename
    
    def validate_file(self, value: UploadedFile) -> UploadedFile:
        """Validate the uploaded file"""
        # Check file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB
        if value.size > max_size:
            raise serializers.ValidationError(
                _('File size cannot exceed 50MB')
            )
        
        # Check file extension
        valid_extensions = ('.docx', '.xlsx', '.pptx')
        if not any(value.name.lower().endswith(ext) for ext in valid_extensions):
            raise serializers.ValidationError(
                _('File type is not supported. Only .docx, .xlsx, and .pptx files are allowed.')
            )
        
        return value
    
    def create(self, validated_data: Dict[str, Any]) -> File:
        """Create a new file instance"""
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['uploaded_by'] = request.user
        
        # Set the original filename
        if 'file' in validated_data and hasattr(validated_data['file'], 'name'):
            validated_data['original_filename'] = validated_data['file'].name
        
        return super().create(validated_data)


class FileShareLinkSerializer(serializers.ModelSerializer[FileShareLink]):
    """Serializer for file share links"""
    file: 'serializers.PrimaryKeyRelatedField' = serializers.PrimaryKeyRelatedField(
        queryset=File.objects.all()
    )
    created_by: 'serializers.PrimaryKeyRelatedField' = serializers.PrimaryKeyRelatedField(
        read_only=True,
        default=serializers.CurrentUserDefault()
    )
    share_url: 'serializers.SerializerMethodField' = serializers.SerializerMethodField()
    file_name: 'serializers.SerializerMethodField' = serializers.SerializerMethodField()
    expires_in: 'serializers.SerializerMethodField' = serializers.SerializerMethodField()

    class Meta:
        model = FileShareLink
        fields = [
            'id', 'file', 'token', 'created_by', 'created_at',
            'expires_at', 'is_active', 'max_downloads', 'download_count',
            'share_url', 'file_name', 'expires_in'
        ]
        read_only_fields = ['id', 'token', 'created_at', 'download_count']

    def get_share_url(self, obj: FileShareLink) -> str:
        """Get the full shareable URL"""
        request = self.context.get('request')
        if request and hasattr(request, 'build_absolute_uri'):
            return request.build_absolute_uri(obj.get_absolute_url())
        return obj.get_absolute_url()
    
    def get_file_name(self, obj: FileShareLink) -> str:
        """Return the original filename of the shared file"""
        return obj.file.original_filename
    
    def get_expires_in(self, obj: FileShareLink) -> Optional[int]:
        """Return the number of days until the link expires"""
        if obj.expires_at:
            delta = obj.expires_at - timezone.now()
            return max(0, delta.days)
        return None
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the file share link"""
        request = self.context.get('request')
        if request and hasattr(request, 'user') and hasattr(request.user, 'is_staff'):
            attrs['created_by'] = request.user
            
            # Check if the user has permission to share the file
            file = attrs.get('file')
            if file and file.uploaded_by != request.user and not request.user.is_staff:
                raise serializers.ValidationError({
                    'file': _('You do not have permission to share this file.')
                })
        
        # Set expiration to 7 days from now if not provided
        if 'expires_at' not in attrs or not attrs['expires_at']:
            attrs['expires_at'] = timezone.now() + timedelta(days=7)
        
        return attrs


class FileShareLinkCreateSerializer(serializers.ModelSerializer[FileShareLink]):
    """Serializer for creating file share links"""
    file_id: 'serializers.UUIDField' = serializers.UUIDField(write_only=True)
    expires_in_days: 'serializers.IntegerField' = serializers.IntegerField(
        min_value=1,
        max_value=30,
        default=7,
        help_text=_('Number of days until the link expires')
    )
    max_downloads: 'serializers.IntegerField' = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True,
        help_text=_('Maximum number of downloads (leave empty for unlimited)')
    )
    share_url: 'serializers.SerializerMethodField' = serializers.SerializerMethodField()

    class Meta:
        model = FileShareLink
        fields = ['file_id', 'expires_in_days', 'max_downloads', 'share_url']
        read_only_fields = ['share_url']

    def get_share_url(self, obj: FileShareLink) -> str:
        """Get the full shareable URL"""
        request = self.context.get('request')
        if request and hasattr(request, 'build_absolute_uri'):
            return request.build_absolute_uri(obj.get_absolute_url())
        return obj.get_absolute_url()

    def validate_file_id(self, value: uuid.UUID) -> uuid.UUID:
        """Validate that the file exists and belongs to the user"""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError(_('Authentication required'))
        
        try:
            file = File.objects.get(id=value)
        except File.DoesNotExist as e:
            raise serializers.ValidationError(_('File not found')) from e
        
        # Check if the user has permission to share the file
        if file.uploaded_by != request.user and not request.user.is_staff:
            raise serializers.ValidationError(
                _('You do not have permission to share this file')
            )
        
        return value

    def create(self, validated_data: Dict[str, Any]) -> FileShareLink:
        """Create a new file share link"""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            raise serializers.ValidationError(_('Authentication required'))
        
        # Get the file
        file_id = validated_data.pop('file_id')
        try:
            file = File.objects.get(id=file_id)
        except File.DoesNotExist as e:
            raise serializers.ValidationError({'file_id': _('File not found')}) from e
        
        # Set expiration date
        expires_in_days = validated_data.pop('expires_in_days', 7)
        expires_at = timezone.now() + timedelta(days=expires_in_days)
        
        # Create the share link
        share_link = FileShareLink.objects.create(
            file=file,
            created_by=request.user,
            expires_at=expires_at,
            max_downloads=validated_data.get('max_downloads')
        )
        
        return share_link
