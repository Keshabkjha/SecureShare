from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register(r'files', views.FileViewSet, basename='file')
router.register(r'share-links', views.FileShareLinkViewSet, basename='share-link')

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', views.ClientSignupView.as_view(), name='client-register'),
    path('auth/verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('auth/token/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # File endpoints
    path('client/files/', views.ClientFileListView.as_view(), name='client-file-list'),
    
    # Include router URLs
    path('', include(router.urls)),
]
