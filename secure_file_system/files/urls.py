from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'files'

# Create a router for ViewSets
router = DefaultRouter()
router.register(r'share', views.FileShareLinkViewSet, basename='fileshare')

urlpatterns = [
    # File operations
    path('', views.FileListView.as_view(), name='file_list'),
    path('upload/', views.FileUploadView.as_view(), name='file_upload'),
    path('<uuid:id>/', views.FileDetailView.as_view(), name='file_detail'),
    path('<uuid:id>/get-download-link/', views.FileDownloadView.as_view(), name='get_download_link'),
    path('<uuid:id>/download/', views.SecureFileDownloadView.as_view(), name='secure_file_download'),
    path('<uuid:id>/share/', views.FileShareLinkViewSet.as_view({'post': 'create'}), name='file_share'),
    
    # Search
    path('search/', views.FileSearchView.as_view(), name='file_search'),
    
    # Include router URLs
    path('', include(router.urls)),
    
    # Public download link (no authentication required)
    path('share/<uuid:pk>/download/', 
         views.FileShareLinkViewSet.as_view({'get': 'download'}), 
         name='public_file_download'),
]
