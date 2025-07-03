from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, EmailVerificationToken, PasswordResetToken


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Custom User admin interface."""
    list_display = ('email', 'first_name', 'last_name', 'user_type', 'is_staff', 'is_active', 'is_verified')
    list_filter = ('user_type', 'is_staff', 'is_active', 'is_verified')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions', 'is_verified'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('User Type'), {'fields': ('user_type',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'user_type', 'is_staff', 'is_active'),
        }),
    )
    readonly_fields = ('last_login', 'date_joined')


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    """Email verification token admin interface."""
    list_display = ('user', 'token', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'token')
    readonly_fields = ('created_at', 'user', 'token')
    
    def has_add_permission(self, request):
        return False


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    """Password reset token admin interface."""
    list_display = ('user', 'token', 'created_at', 'is_used')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__email', 'token')
    readonly_fields = ('created_at', 'user', 'token', 'is_used')
    
    def has_add_permission(self, request):
        return False
