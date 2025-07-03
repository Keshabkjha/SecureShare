import logging
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _
from rest_framework import status, generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
# type: ignore
from rest_framework_simplejwt.views import TokenObtainPairView
# type: ignore
from rest_framework_simplejwt.tokens import RefreshToken
# type: ignore
from rest_framework_simplejwt.exceptions import TokenError
from .models import User, EmailVerificationToken, PasswordResetToken
from .tasks import send_verification_email_task
from .serializers import (
    UserRegistrationSerializer, CustomTokenObtainPairSerializer,
    UserSerializer, EmailVerificationSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    ChangePasswordSerializer, RefreshTokenSerializer
)
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ResendVerificationEmailView(APIView):
    """
    API endpoint to resend the verification email.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        if not email:
            return Response(
                {'error': _('Email is required')},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
            
            # Delete any existing verification tokens
            EmailVerificationToken.objects.filter(user=user).delete()
            
            # Create a new verification token
            verification_token = EmailVerificationToken.objects.create(user=user)
            
            # Send verification email
            verification_url = f"{settings.FRONTEND_URL}/verify-email/{verification_token.token}/"
            send_mail(
                _('Verify your email address'),
                _('Please click the following link to verify your email: {}').format(verification_url),
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            return Response(
                {'message': _('Verification email has been resent. Please check your email.')},
                status=status.HTTP_200_OK
            )
            
        except User.DoesNotExist:
            return Response(
                {'error': _('No user found with this email address.')},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error resending verification email: {str(e)}")
            return Response(
                {'error': _('An error occurred while resending the verification email.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserRegistrationView(generics.CreateAPIView):
    """
    API endpoint that allows users to register a new account.
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate email verification token
        verification_token = EmailVerificationToken.objects.create(user=user)
        
        # Send verification email asynchronously using Celery
        verification_url = f"{settings.FRONTEND_URL}/verify-email/{verification_token.token}/"
        send_verification_email_task.delay(user.email, verification_url)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                'message': _('User registered successfully. Please check your email to verify your account.')
            },
            status=status.HTTP_201_CREATED,
            headers=headers
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom token obtain view that extends the default TokenObtainPairView
    to include additional user data in the response.
    """
    serializer_class = CustomTokenObtainPairSerializer


class EmailVerificationView(APIView):
    """
    API endpoint to verify a user's email address using a verification token.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        verification_token = serializer.validated_data['verification_token']
        user = verification_token.user
        
        if user.is_verified:
            return Response(
                {'message': _('Email is already verified.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark user as verified and delete the token
        user.is_verified = True
        user.save()
        verification_token.delete()
        
        return Response(
            {'message': _('Email verified successfully.')},
            status=status.HTTP_200_OK
        )


class PasswordResetRequestView(APIView):
    """
    API endpoint to request a password reset email.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        
        # Create or get existing reset token
        reset_token, created = PasswordResetToken.objects.get_or_create(
            user=user,
            defaults={'token': PasswordResetToken.generate_token()}
        )
        
        if not created and reset_token.is_valid():
            # If a valid token already exists, don't create a new one
            return Response(
                {'message': _('A password reset link has already been sent to your email.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Send password reset email (in production, this would be a Celery task)
        try:
            reset_url = f"{settings.FRONTEND_URL}/reset-password/{reset_token.token}/"
            send_mail(
                _('Password Reset Request'),
                _('Please click the following link to reset your password: {}').format(reset_url),
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            return Response(
                {'message': _('Failed to send password reset email. Please try again later.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response(
            {'message': _('Password reset link has been sent to your email.')},
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(APIView):
    """
    API endpoint to confirm a password reset using a token.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        reset_token = serializer.validated_data['reset_token']
        user = reset_token.user
        
        # Update user's password
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Mark token as used
        reset_token.is_used = True
        reset_token.save()
        
        return Response(
            {'message': _('Password has been reset successfully.')},
            status=status.HTTP_200_OK
        )


class ChangePasswordView(APIView):
    """
    API endpoint to change a user's password.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        # Update user's password
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        
        return Response(
            {'message': _('Password updated successfully.')},
            status=status.HTTP_200_OK
        )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint to retrieve or update the authenticated user's profile.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class LogoutView(APIView):
    """
    API endpoint to log out a user by blacklisting their refresh token.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'error': _('Refresh token is required.')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {'message': _('Successfully logged out.')},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {'error': _('Invalid token.')},
                status=status.HTTP_400_BAD_REQUEST
            )


class RefreshTokenView(APIView):
    """
    API endpoint to refresh an access token using a refresh token.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        try:
            serializer = RefreshTokenSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            refresh_token = serializer.validated_data['refresh']
            
            # Create a new access token from the refresh token
            token = RefreshToken(refresh_token)
            access = str(token.access_token)
            
            # Rotate the refresh token (optional but recommended)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=token['user_id'])
            refresh = str(RefreshToken.for_user(user))
            
            # Blacklist the old refresh token
            token.blacklist()
            
            # Calculate token expiration time
            access_expires = int((timezone.now() + settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']).timestamp())
            
            return Response({
                'access': access,
                'refresh': refresh,
                'access_expires': access_expires
            })
            
        except TokenError as e:
            return Response(
                {'error': _('Invalid or expired refresh token.')},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except User.DoesNotExist:
            return Response(
                {'error': _('User not found.')},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return Response(
                {'error': _('Could not refresh token.')},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
