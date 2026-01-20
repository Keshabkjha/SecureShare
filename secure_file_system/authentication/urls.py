from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = 'authentication'

urlpatterns = [
    # User registration and authentication
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Email verification
    path('verify-email/', views.EmailVerificationView.as_view(), name='verify_email'),
    path('resend-verification/', views.ResendVerificationEmailView.as_view(), name='resend_verification'),
    
    # Password management
    path('password/reset/request/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password/reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password/change/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # User profile
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('profile/update/', views.UserProfileView.as_view(), name='update_profile'),
    
    # Token management
    path('logout/', views.LogoutView.as_view(), name='logout'),
]
