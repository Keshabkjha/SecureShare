import uuid
from typing import Any, Dict, Optional, Type, TypeVar, cast
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer  # type: ignore[import-untyped]
from rest_framework_simplejwt.tokens import RefreshToken  # type: ignore[import-untyped]
from .models import EmailVerificationToken, PasswordResetToken, User as UserModel

User = get_user_model()

# Type variable for generic serializers
T = TypeVar('T', bound=serializers.Serializer)


class UserRegistrationSerializer(serializers.ModelSerializer[UserModel]):
    """Serializer for user registration"""
    password: 'serializers.CharField' = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        min_length=8,
        max_length=128,
        error_messages={
            'min_length': _('Password must be at least 8 characters long.'),
            'max_length': _('Password cannot be longer than 128 characters.'),
        }
    )
    confirm_password: 'serializers.CharField' = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )
    user_type: 'serializers.ChoiceField' = serializers.ChoiceField(
        choices=UserModel.UserType.choices,
        default=UserModel.UserType.CLIENT
    )

    class Meta:
        model = UserModel
        fields = ('email', 'first_name', 'last_name', 'password', 'confirm_password', 'user_type')
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False},
            'last_name': {'required': True, 'allow_blank': False},
        }

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if attrs['password'] != attrs.pop('confirm_password'):
            raise serializers.ValidationError({"password": _("Password fields didn't match.")})
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> UserModel:
        # Remove confirm_password as it's not a model field
        validated_data.pop('confirm_password', None)
        user = UserModel.objects.create_user(**validated_data)
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):  # type: ignore[misc,valid-type]
    """Custom token serializer to include additional user data in the response"""
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        data = super().validate(attrs)
        refresh = self.get_token(self.user)
        
        # Add custom claims
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        data['user'] = {
            'id': str(self.user.id),  # Convert UUID to string
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'user_type': self.user.user_type,
            'is_verified': self.user.is_verified,
        }
        return data


class UserSerializer(serializers.ModelSerializer[UserModel]):
    """Serializer for user details"""
    class Meta:
        model = UserModel
        fields = ('id', 'email', 'first_name', 'last_name', 'user_type', 'is_verified', 'date_joined')
        read_only_fields = ('id', 'email', 'user_type', 'is_verified', 'date_joined')


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification"""
    token: 'serializers.UUIDField' = serializers.UUIDField()
    verification_token: Optional[EmailVerificationToken] = None

    def validate_token(self, value: uuid.UUID) -> uuid.UUID:
        try:
            self.verification_token = EmailVerificationToken.objects.get(token=value)
            if not self.verification_token.is_valid():
                raise serializers.ValidationError(_("Verification link has expired."))
            return value
        except EmailVerificationToken.DoesNotExist as e:
            raise serializers.ValidationError(_("Invalid verification token.")) from e


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for requesting a password reset"""
    email: 'serializers.EmailField' = serializers.EmailField()
    user: Optional[UserModel] = None

    def validate_email(self, value: str) -> str:
        try:
            self.user = UserModel.objects.get(email=value, is_active=True)
        except UserModel.DoesNotExist as e:
            raise serializers.ValidationError(_("No active account found with this email address.")) from e
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset"""
    token: 'serializers.UUIDField' = serializers.UUIDField()
    new_password: 'serializers.CharField' = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        min_length=8,
        max_length=128,
    )
    confirm_password: 'serializers.CharField' = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"new_password": _("Password fields didn't match.")})
        
        try:
            self.reset_token = PasswordResetToken.objects.get(
                token=attrs['token'],
                is_used=False
            )
            if not self.reset_token.is_valid():
                raise serializers.ValidationError({"token": _("Password reset link has expired.")})
            return attrs
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError({"token": _("Invalid password reset token.")})


class RefreshTokenSerializer(serializers.Serializer):
    """Serializer for refreshing access token"""
    refresh: 'serializers.CharField' = serializers.CharField()

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            refresh = RefreshToken(attrs['refresh'])
            attrs['refresh'] = refresh
            return attrs
        except Exception as e:
            raise serializers.ValidationError({"refresh": str(e)}) from e


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    old_password: 'serializers.CharField' = serializers.CharField(required=True, write_only=True)
    new_password: 'serializers.CharField' = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
        max_length=128,
        style={'input_type': 'password'}
    )
    confirm_password: 'serializers.CharField' = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_old_password(self, value: str) -> str:
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Old password is not correct"))
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"new_password": _("Password fields didn't match.")})
        return attrs
