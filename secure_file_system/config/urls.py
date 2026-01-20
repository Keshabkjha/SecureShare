"""
URL configuration for Secure File System API.

This module defines the URL patterns for the Secure File Sharing System,
including API endpoints, admin interface, and documentation.
"""
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework import permissions
from rest_framework_simplejwt.views import TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.schemas import get_schema_view as get_schema

# Import custom admin site
from config.admin import admin_site as secure_file_system_admin
from config.views import welcome

# Import API URLs
from api.urls import urlpatterns as api_urls

# API Schema and Documentation
api_info = openapi.Info(
    title="Secure File Sharing System API",
    default_version='v1',
    description="""
    # Secure File Sharing System API
    
    This API enables secure file sharing between Operations and Client users with role-based access control.
    
    ## Key Features:
    - JWT Authentication
    - Role-based access control (Operations/Client)
    - Secure file upload/download
    - Email verification
    - File sharing with expiring links
    
    ## Authentication
    Use JWT authentication by including the token in the Authorization header:
    ```
    Authorization: Bearer <token>
    ```
    """,
    terms_of_service="https://www.yourapp.com/terms/",
    contact=openapi.Contact(
        name="API Support",
        email="support@securefileshare.com",
        url="https://www.securefileshare.com/support"
    ),
    license=openapi.License(
        name="Proprietary",
        url="https://www.securefileshare.com/license"
    ),
)

schema_view = get_schema_view(
    api_info,
    public=True,
    permission_classes=(permissions.AllowAny,),
    authentication_classes=()
)

# URL Patterns
urlpatterns = [
    # Admin site
    path('admin/', secure_file_system_admin.urls, name='admin'),
    
    # Welcome page
    path('', welcome, name='welcome'),
    
    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/schema/', schema_view.without_ui(cache_timeout=0), name='openapi-schema'),
    
    # API Version 1
    path('api/v1/', include(api_urls)),
    
    # JWT Token Refresh
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Health check endpoint
    path('health/', include('health_check.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers
handler400 = 'config.views.bad_request'
handler403 = 'config.views.permission_denied'
handler404 = 'config.views.page_not_found'
handler500 = 'config.views.server_error'
