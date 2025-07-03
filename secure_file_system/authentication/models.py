import uuid
from typing import Optional, Dict, Any, Type, TypeVar, Union, List, cast
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import QuerySet


class UserManager(BaseUserManager):
    """Custom user model manager where email is the unique identifier"""
    
    def create_user(self, email: str, password: Optional[str] = None, **extra_fields: Any) -> 'User':
        """Create and save a user with the given email and password."""
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)  # type: ignore[call-arg]
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: Optional[str] = None, **extra_fields: Any) -> 'User':
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model that uses email as the unique identifier"""
    class UserType(models.TextChoices):
        CLIENT = 'CLIENT', _('Client')
        OPERATIONS = 'OPERATIONS', _('Operations')
    
    id: 'models.UUIDField' = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email: 'models.EmailField' = models.EmailField(_('email address'), unique=True)
    first_name: 'models.CharField' = models.CharField(_('first name'), max_length=30, blank=True)
    last_name: 'models.CharField' = models.CharField(_('last name'), max_length=30, blank=True)
    user_type: 'models.CharField' = models.CharField(
        _('user type'),
        max_length=20,
        choices=UserType.choices,
        default=UserType.CLIENT
    )
    is_verified: 'models.BooleanField' = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_('Designates whether the user has verified their email address.')
    )
    is_staff: 'models.BooleanField' = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_active: 'models.BooleanField' = models.BooleanField(
        _('active'),
        default=True,
        help_text=(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    is_verified: 'models.BooleanField' = models.BooleanField(
        _('verified'),
        default=False,
        help_text=_('Designates whether this user has verified their email.'),
    )
    date_joined: 'models.DateTimeField' = models.DateTimeField(_('date joined'), default=timezone.now)
    last_login: 'models.DateTimeField' = models.DateTimeField(_('last login'), auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self) -> str:
        return self.email
    
    def get_full_name(self) -> str:
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()
    
    def get_short_name(self) -> str:
        """Return the short name for the user."""
        return self.first_name or ''
    
    def email_user(self, subject: str, message: str, from_email: Optional[str] = None, **kwargs: Any) -> int:
        """Send an email to this user."""
        return send_mail(subject, message, from_email, [self.email], **kwargs)


class EmailVerificationToken(models.Model):
    """Model to store email verification tokens"""
    user: 'models.OneToOneField[User, models.Model]' = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='email_verification_token'
    )
    token: 'models.UUIDField' = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at: 'models.DateTimeField' = models.DateTimeField(auto_now_add=True)
    
    def __str__(self) -> str:
        return f"Verification token for {self.user.email}"
    
    def is_valid(self) -> bool:
        """Check if the token is still valid (24 hours)"""
        expiration_time = timezone.timedelta(hours=24)
        return (timezone.now() - self.created_at) < expiration_time


class PasswordResetToken(models.Model):
    """Model to store password reset tokens"""
    user: 'models.ForeignKey[User, models.Model]' = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens'
    )
    token: 'models.UUIDField' = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at: 'models.DateTimeField' = models.DateTimeField(auto_now_add=True)
    is_used: 'models.BooleanField' = models.BooleanField(default=False)
    
    def __str__(self) -> str:
        return f"Password reset token for {self.user.email}"
    
    def is_valid(self) -> bool:
        """Check if the token is still valid (1 hour) and not used"""
        if self.is_used:
            return False
        expiration_time = timezone.timedelta(hours=1)
        return (timezone.now() - self.created_at) < expiration_time
