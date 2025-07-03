"""
Custom admin site configuration for the Secure File System.
"""
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.utils.translation import gettext_lazy as _
import logging

# Import your models
try:
    from authentication.models import User
except ImportError:
    User = None
    
try:
    from files.models import File, SharedFile, DownloadLog
except ImportError:
    File = None
    SharedFile = None
    DownloadLog = None

logger = logging.getLogger(__name__)

class CustomAdminSite(admin.AdminSite):
    """
    Custom admin site with enhanced functionality and styling.
    """
    site_header = _('Secure File System Admin')
    site_title = _('Secure File System Admin Portal')
    index_title = _('Dashboard')
    
    def get_app_list(self, request, app_label=None):
        """
        Return a sorted list of all the installed apps that have been
        registered in this site.
        """
        app_dict = self._build_app_dict(request)
        
        # Sort the apps alphabetically.
        app_list = sorted(app_dict.values(), key=lambda x: x['name'].lower())
        
        # Sort the models alphabetically within each app.
        for app in app_list:
            app['models'].sort(key=lambda x: x['name'].lower())
            
        return app_list
    
    def index(self, request, extra_context=None):
        """
        Override the default admin index page to include custom statistics.
        """
        # Initialize statistics dictionary
        stats = {}
        recent_activity = []
        
        try:
            # User statistics
            if User is not None:
                stats['user_count'] = User.objects.count()
                stats['new_users_this_week'] = User.objects.filter(
                    date_joined__gte=timezone.now() - timezone.timedelta(days=7)
                ).count()
                
                # Add recent user registrations to activity
                recent_users = User.objects.order_by('-date_joined').select_related('profile')[:5]
                for user in recent_users:
                    recent_activity.append({
                        'message': f'New user registered: {user.email}',
                        'time': user.date_joined,
                        'icon': 'fa-user-plus',
                        'url': reverse('admin:authentication_user_change', args=[user.id])
                    })
            else:
                stats['user_count'] = 0
                stats['new_users_this_week'] = 0
            
            # File statistics
            if File is not None:
                stats['file_count'] = File.objects.count()
                
                # Calculate total storage used
                total_size = File.objects.aggregate(
                    total_size=Sum('size')
                )['total_size'] or 0
                stats['total_file_size_mb'] = round(total_size / (1024 * 1024), 2)  # Convert to MB
                
                # Add recent uploads to activity
                recent_uploads = File.objects.order_by('-uploaded_at').select_related('uploaded_by')[:5]
                for file in recent_uploads:
                    recent_activity.append({
                        'message': f'New file uploaded: {file.original_filename}',
                        'time': file.uploaded_at,
                        'icon': 'fa-file-upload',
                        'url': reverse('admin:files_file_change', args=[file.id])
                    })
            else:
                stats['file_count'] = 0
                stats['total_file_size_mb'] = 0
            
            # Download statistics
            if DownloadLog is not None:
                stats['download_count'] = DownloadLog.objects.count()
                stats['downloads_this_week'] = DownloadLog.objects.filter(
                    downloaded_at__gte=timezone.now() - timezone.timedelta(days=7)
                ).count()
                
                # Add recent downloads to activity
                recent_downloads = DownloadLog.objects.select_related('file', 'user') \
                                                   .order_by('-downloaded_at')[:5]
                for dl in recent_downloads:
                    recent_activity.append({
                        'message': f'File downloaded: {dl.file.original_filename if dl.file else "Unknown file"}',
                        'time': dl.downloaded_at,
                        'icon': 'fa-download',
                        'url': reverse('admin:files_downloadlog_change', args=[dl.id]) if dl.id else '#'
                    })
            else:
                stats['download_count'] = 0
                stats['downloads_this_week'] = 0
                
        except Exception as e:
            logger.error(f'Error generating admin dashboard: {str(e)}', exc_info=True)
            # Set default values in case of error
            stats.update({
                'user_count': 0,
                'new_users_this_week': 0,
                'file_count': 0,
                'total_file_size_mb': 0,
                'download_count': 0,
                'downloads_this_week': 0
            })
        
        # Sort activities by time and limit to 10 most recent
        recent_activity.sort(key=lambda x: x['time'], reverse=True)
        recent_activity = recent_activity[:10]
        
        # Add the statistics and activity to the context
        extra_context = extra_context or {}
        extra_context.update({
            'user_count': stats.get('user_count', 0),
            'file_count': stats.get('file_count', 0),
            'download_count': stats.get('download_count', 0),
            'storage_used': stats.get('total_file_size_mb', 0),
            'recent_activity': recent_activity,
            'new_users_this_week': stats.get('new_users_this_week', 0),
            'downloads_this_week': stats.get('downloads_this_week', 0),
            'stats': stats,
            'site_header': self.site_header,
            'site_title': self.site_title,
            'site_url': self.site_url,
        })
        
        return super().index(request, extra_context)

# Create an instance of the custom admin site
admin_site = CustomAdminSite()
