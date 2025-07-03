from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from files.models import File, FileShareLink

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """Serializer for the user object"""
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    
    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'first_name', 'last_name', 'user_type')
        read_only_fields = ('id',)
        extra_kwargs = {
            'user_type': {'read_only': True}
        }

    def create(self, validated_data):
        """Create and return a user with encrypted password"""
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class ClientSignupSerializer(serializers.ModelSerializer):
    """Serializer for client signup"""
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    
    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name')
        extra_kwargs = {
            'email': {'required': True},
            'password': {'required': True, 'write_only': True},
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def create(self, validated_data):
        """Create and return a client user with encrypted password"""
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            user_type=User.UserType.CLIENT
        )
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom token serializer to include user details in the response"""
    def validate(self, attrs):
        data = super().validate(attrs)
        refresh = self.get_token(self.user)
        
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'user_type': self.user.user_type,
            'is_verified': self.user.is_verified
        }
        return data


class FileSerializer(serializers.ModelSerializer):
    """Serializer for the File model"""
    file = serializers.FileField(write_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = File
        fields = ('id', 'original_filename', 'file_type', 'file_size', 'uploaded_at', 'file', 'file_url')
        read_only_fields = ('id', 'original_filename', 'file_type', 'file_size', 'uploaded_at', 'file_url')

    def get_file_url(self, obj):
        """Get the absolute URL for the file"""
        request = self.context.get('request')
        if obj.file and hasattr(obj.file, 'url'):
            return request.build_absolute_uri(obj.file.url)
        return None


class FileShareLinkSerializer(serializers.ModelSerializer):
    """Serializer for file share links"""
    file = FileSerializer(read_only=True)
    download_url = serializers.SerializerMethodField()
    
    class Meta:
        model = FileShareLink
        fields = ('id', 'file', 'token', 'created_at', 'expires_at', 'is_active', 
                 'max_downloads', 'download_count', 'download_url')
        read_only_fields = ('id', 'token', 'created_at', 'download_count', 'download_url')

    def get_download_url(self, obj):
        """Generate the download URL for the share link"""
        request = self.context.get('request')
        return request.build_absolute_uri(f'/api/files/share/{obj.token}/download/')


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification"""
    token = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    token = serializers.CharField()
    new_password = serializers.CharField(style={'input_type': 'password'})
