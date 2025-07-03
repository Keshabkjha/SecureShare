import os
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from . import serializers
from files.models import File, FileShareLink
from authentication.models import EmailVerificationToken

User = get_user_model()

class IsOwner(permissions.BasePermission):
    """Custom permission to only allow owners of an object to edit it."""
    def has_object_permission(self, request, view, obj):
        return obj.uploaded_by == request.user

class IsClientUser(permissions.BasePermission):
    """Allows access only to client users."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == User.UserType.CLIENT

class IsOperationsUser(permissions.BasePermission):
    """Allows access only to operations users."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == User.UserType.OPERATIONS

class ClientSignupView(generics.CreateAPIView):
    """View for client user registration"""
    serializer_class = serializers.ClientSignupSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create email verification token
        verification_token = EmailVerificationToken.objects.create(user=user)
        
        # Send verification email
        verification_url = request.build_absolute_uri(
            reverse('verify-email') + f'?token={verification_token.token}'
        )
        
        subject = 'Verify your email address'
        message = render_to_string('emails/verify_email.html', {
            'user': user,
            'verification_url': verification_url,
        })
        
        send_mail(
            subject=subject,
            message='',  # Plain text version (empty since we're using html_message)
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=message,
            fail_silently=False,
        )
        
        return Response(
            {'detail': 'Registration successful. Please check your email to verify your account.'},
            status=status.HTTP_201_CREATED
        )

class VerifyEmailView(generics.GenericAPIView):
    """View for email verification"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return Response(
                {'error': 'Token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            verification = EmailVerificationToken.objects.get(token=token)
            if verification.is_valid():
                user = verification.user
                user.is_verified = True
                user.save()
                verification.delete()
                return Response(
                    {'detail': 'Email verified successfully'},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'error': 'Verification link has expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {'error': 'Invalid verification token'},
                status=status.HTTP_400_BAD_REQUEST
            )

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token obtain view that includes user details in the response"""
    serializer_class = serializers.CustomTokenObtainPairSerializer

class FileViewSet(viewsets.ModelViewSet):
    """ViewSet for managing files"""
    queryset = File.objects.all()
    serializer_class = serializers.FileSerializer
    permission_classes = [IsAuthenticated, IsOperationsUser]
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        """Return only files uploaded by the current user"""
        return self.queryset.filter(uploaded_by=self.request.user)
    
    def perform_create(self, serializer):
        """Set the uploaded_by field to the current user"""
        file_obj = self.request.FILES.get('file')
        if not file_obj:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get file extension and validate
        file_extension = os.path.splitext(file_obj.name)[1].lower()
        if file_extension not in ['.docx', '.xlsx', '.pptx']:
            return Response(
                {'error': 'Only .docx, .xlsx, and .pptx files are allowed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Map file extension to file type
        file_type_map = {
            '.docx': File.FileType.DOCX,
            '.xlsx': File.FileType.XLSX,
            '.pptx': File.FileType.PPTX,
        }
        
        serializer.save(
            uploaded_by=self.request.user,
            original_filename=file_obj.name,
            file_type=file_type_map[file_extension],
            file_size=file_obj.size
        )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def share(self, request, pk=None):
        """Create a shareable link for the file"""
        try:
            file_obj = self.get_queryset().get(pk=pk)
        except File.DoesNotExist:
            return Response(
                {'error': 'File not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create a share link that expires in 7 days
        expires_at = timezone.now() + timedelta(days=7)
        share_link = FileShareLink.objects.create(
            file=file_obj,
            created_by=request.user,
            expires_at=expires_at,
            max_downloads=10  # Allow up to 10 downloads
        )
        
        serializer = serializers.FileShareLinkSerializer(
            share_link,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class FileShareLinkViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for managing file share links"""
    serializer_class = serializers.FileShareLinkSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return only share links created by the current user"""
        return FileShareLink.objects.filter(created_by=self.request.user)
    
    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def download(self, request, token=None):
        """Download a file using a share link"""
        try:
            share_link = FileShareLink.objects.get(token=token, is_active=True)
            
            # Check if the link has expired
            if share_link.is_expired():
                return Response(
                    {'error': 'This link has expired'},
                    status=status.HTTP_410_GONE
                )
            
            # Check download limit
            if (share_link.max_downloads is not None and 
                share_link.download_count >= share_link.max_downloads):
                return Response(
                    {'error': 'Download limit exceeded'},
                    status=status.HTTP_410_GONE
                )
            
            # For authenticated users, check if they have access
            if request.user.is_authenticated and request.user.user_type != User.UserType.CLIENT:
                return Response(
                    {'error': 'Only client users can download files'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Increment download count
            share_link.download_count += 1
            share_link.save()
            
            # Return the file for download
            file_obj = share_link.file.file
            response = Response(file_obj, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{share_link.file.original_filename}"'
            return response
            
        except FileShareLink.DoesNotExist:
            return Response(
                {'error': 'Invalid or expired share link'},
                status=status.HTTP_404_NOT_FOUND
            )

class ClientFileListView(generics.ListAPIView):
    """View for clients to list all available files"""
    serializer_class = serializers.FileSerializer
    permission_classes = [IsAuthenticated, IsClientUser]
    
    def get_queryset(self):
        """Return all files that have active share links"""
        return File.objects.filter(share_links__is_active=True).distinct()
