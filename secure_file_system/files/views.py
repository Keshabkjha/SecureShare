import logging
import os
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone
from django.http import FileResponse, Http404
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status, generics, permissions, viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.pagination import PageNumberPagination

from .tasks import send_file_upload_notification

from .models import File, FileShareLink
from .serializers import (
    FileSerializer, 
    FileShareLinkSerializer,
    FileShareLinkCreateSerializer
)
from authentication.models import User
from authentication.permissions import IsOperationsUser

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """Custom pagination class for consistent pagination across API endpoints."""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class FileUploadView(generics.CreateAPIView):
    """
    API endpoint for uploading files.
    Only authenticated users with OPERATIONS role can upload files.
    """
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    permission_classes = [permissions.IsAuthenticated, IsOperationsUser]
    serializer_class = FileSerializer

    def perform_create(self, serializer):
        # Add the uploader to the file
        file_obj = self.request.FILES.get('file')
        
        if not file_obj:
            raise ValidationError({'file': _('No file was provided.')})
        
        # Validate file size
        max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 50 * 1024 * 1024)  # 50MB default
        if file_obj.size > max_size:
            raise ValidationError({
                'file': _('File size exceeds the maximum allowed size of %(max_size)sMB') % 
                {'max_size': max_size // (1024 * 1024)}
            })
        
        # Save the file with the uploader
        file_instance = serializer.save(
            uploader=self.request.user,
            file_size=file_obj.size,
            original_filename=file_obj.name,
            file_type=os.path.splitext(file_obj.name)[1][1:].upper() or 'UNKNOWN'
        )
        
        # Send notification to all admin users
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_emails = User.objects.filter(
            is_staff=True
        ).values_list('email', flat=True)
        
        if admin_emails:
            send_file_upload_notification.delay(
                file_instance.id,
                list(admin_emails)
            )
        
        logger.info(f"File '{file_obj.name}' uploaded by {self.request.user.email}")


class FileDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint to view, update or delete a file.
    Only the uploader or admin can update/delete the file.
    """
    queryset = File.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        return FileSerializer
    
    def get_queryset(self):
        # Regular users can only see their own files
        if self.request.user.user_type != 'OPERATIONS':
            return File.objects.filter(uploader=self.request.user)
        return File.objects.all()
    
    def perform_destroy(self, instance):
        # Only allow deletion by uploader or admin
        if instance.uploader != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied(_("You don't have permission to delete this file."))
        
        # Delete the actual file from storage
        if instance.file:
            if os.path.isfile(instance.file.path):
                os.remove(instance.file.path)
        
        # Delete the database record
        instance.delete()
        logger.info(f"File '{instance.original_filename}' deleted by {self.request.user.email}")


class FileListView(generics.ListAPIView):
    """
    API endpoint to list all files.
    Regular users only see their own files, while operations users see all files.
    """
    serializer_class = FileSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['created_at', 'file_size', 'original_filename']
    search_fields = ['original_filename', 'description', 'file_type']
    
    def get_queryset(self):
        queryset = File.objects.all()
        
        # Filter by uploader if not an operations user
        if self.request.user.user_type != 'OPERATIONS':
            queryset = queryset.filter(uploader=self.request.user)
        
        # Filter by file type if provided
        file_type = self.request.query_params.get('file_type')
        if file_type:
            queryset = queryset.filter(file_type__iexact=file_type.upper())
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
            
        return queryset.order_by('-created_at')


class FileDownloadView(generics.RetrieveAPIView):
    """
    API endpoint to generate a secure download link for a file.
    Only the uploader, admin, or someone with a valid share link can get the download link.
    """
    queryset = File.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'id'

    def get_object(self):
        file_id = self.kwargs.get('id')
        file_obj = get_object_or_404(File, id=file_id)
        
        # Check if user has permission to access the file
        if not (self.request.user.is_staff or file_obj.uploader == self.request.user):
            raise PermissionDenied(_('You do not have permission to access this file'))
            
        return file_obj

    def get(self, request, *args, **kwargs):
        file_obj = self.get_object()
        
        # Create a secure download token
        share_link = FileShareLink.objects.create(
            file=file_obj,
            created_by=request.user,
            expires_at=timezone.now() + timedelta(hours=24)  # Link expires in 24 hours
        )
        
        # Build the download URL
        download_url = f"{settings.BASE_URL}/api/files/{file_obj.id}/download/?token={share_link.token}"
        
        # Return the response in the required format
        return Response({
            "download-link": download_url,
            "message": "success"
        }, status=status.HTTP_200_OK)


class SecureFileDownloadView(generics.RetrieveAPIView):
    """
    Secure endpoint to download a file using a token.
    This is the actual download endpoint that gets called with the secure token.
    """
    permission_classes = [permissions.AllowAny]  # Will handle permissions manually
    
    def get(self, request, *args, **kwargs):
        file_id = self.kwargs.get('id')
        token = self.request.query_params.get('token')
        
        if not token:
            raise PermissionDenied(_('Download token is required'))
        
        # Get the file and verify the token
        try:
            file_obj = File.objects.get(id=file_id)
            share_link = FileShareLink.objects.get(
                token=token,
                file=file_obj,
                is_active=True,
                expires_at__gt=timezone.now()
            )
            
            # Check download limit if set
            if share_link.max_downloads and share_link.download_count >= share_link.max_downloads:
                raise PermissionDenied(_('Download limit reached for this link'))
            
            # Increment download count
            share_link.download_count += 1
            share_link.save()
            
            # Get the file path
            file_path = file_obj.file.path
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found at path: {file_path}")
                raise Http404(_('File not found'))
            
            # Open the file for reading in binary mode
            try:
                file = open(file_path, 'rb')
                response = FileResponse(file)
                
                # Set content type based on file extension
                filename = file_obj.original_filename
                content_type = 'application/octet-stream'
                
                if filename.endswith('.docx'):
                    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                elif filename.endswith('.xlsx'):
                    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                elif filename.endswith('.pptx'):
                    content_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                
                # Set response headers
                response['Content-Type'] = content_type
                response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
                response['Content-Length'] = file_obj.file_size
                
                return response
                
            except Exception as e:
                logger.error(f"Error serving file {file_path}: {str(e)}")
                raise Http404(_('Error serving file'))
                
        except (File.DoesNotExist, FileShareLink.DoesNotExist):
            raise PermissionDenied(_('Invalid or expired download link'))(
                {'error': _('Error downloading file.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FileShareLinkViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing file share links.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return FileShareLinkCreateSerializer
        return FileShareLinkSerializer
    
    def get_queryset(self):
        # Users can only see their own share links
        return FileShareLink.objects.filter(created_by=self.request.user)
    
    def perform_create(self, serializer):
        # Set the creator of the share link
        file = serializer.validated_data['file']
        
        # Check if user has permission to share this file
        if file.uploader != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied(_("You don't have permission to share this file."))
        
        # Set expiration date if not provided (default 7 days)
        expires_at = serializer.validated_data.get('expires_at')
        if not expires_at:
            expires_at = timezone.now() + timedelta(days=7)
            
        # Create the share link
        share_link = serializer.save(
            created_by=self.request.user,
            expires_at=expires_at
        )
        
        logger.info(f"Share link created for file '{file.original_filename}' by {self.request.user.email}")
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a share link"""
        share_link = self.get_object()
        share_link.is_active = False
        share_link.save()
        
        logger.info(f"Share link {share_link.token} deactivated by {request.user.email}")
        return Response({'status': 'Share link deactivated'})
    
    @action(detail=True, methods=['post'])
    def extend(self, request, pk=None):
        """Extend a share link's expiration"""
        share_link = self.get_object()
        days = int(request.data.get('days', 7))  # Default 7 days extension
        
        share_link.expires_at += timedelta(days=days)
        share_link.save()
        
        logger.info(f"Share link {share_link.token} extended by {days} days by {request.user.email}")
        return Response({
            'status': f'Share link extended by {days} days',
            'new_expiration': share_link.expires_at
        })


class FileSearchView(generics.ListAPIView):
    """
    API endpoint to search for files by name or description.
    """
    serializer_class = FileSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = File.objects.all()
        
        # Apply user-based filtering
        if self.request.user.user_type != 'OPERATIONS':
            queryset = queryset.filter(uploader=self.request.user)
        
        # Get search query
        query = self.request.query_params.get('q', '').strip()
        if not query:
            return queryset.none()
        
        # Search in filename and description
        queryset = queryset.filter(
            Q(original_filename__icontains=query) |
            Q(description__icontains=query)
        )
        
        # Filter by file type if provided
        file_type = self.request.query_params.get('type')
        if file_type:
            queryset = queryset.filter(file_type__iexact=file_type.upper())
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Order by relevance (exact matches first, then partial matches)
        queryset = queryset.order_by(
            '-created_at',
            'original_filename'
        )
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get paginated results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # If not using pagination
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)