from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'files', views.FileViewSet, basename='file')
router.register(r'share-links', views.FileShareLinkViewSet, basename='share-link')

urlpatterns = [
    # Authentication endpoints
    path('auth/register/', views.ClientSignupView.as_view(), name='client-register'),
    path('auth/verify-email/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('auth/token/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/', include('rest_framework_simplejwt.urls')),  # For token refresh
    
    # File endpoints
    path('client/files/', views.ClientFileListView.as_view(), name='client-file-list'),
    
    # Include router URLs
    path('', include(router.urls)),
]
