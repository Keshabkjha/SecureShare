from django.shortcuts import render
from django.http import JsonResponse, Http404, HttpResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.views import exception_handler
from rest_framework.exceptions import (
    ValidationError, PermissionDenied, NotAuthenticated, MethodNotAllowed,
    NotAcceptable, UnsupportedMediaType, Throttled, NotFound
)
from django.conf import settings

@require_GET
def welcome(request):
    """
    Welcome page for the Secure File Sharing System
    """
    context = {
        'site_name': 'SecureShare',
        'current_year': '2025',
        'api_docs_url': '/swagger/',
        'admin_url': '/admin/',
        'register_url': '/api/v1/auth/register/',
    }
    return render(request, 'welcome.html', context)

def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If the exception is handled by DRF, return the response as is
    if response is not None:
        return response
    
    # Handle Django's Http404
    if isinstance(exc, Http404):
        return JsonResponse(
            {'detail': str(exc) if str(exc) else _('Not found.')},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Handle Django's PermissionDenied
    if isinstance(exc, PermissionDenied):
        return JsonResponse(
            {'detail': str(exc) if str(exc) else _('You do not have permission to perform this action.')},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Default case: return 500 with a generic error message
    return JsonResponse(
        {'detail': _('A server error occurred.')},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

def bad_request(request, exception, *args, **kwargs):
    """
    Handler for 400 Bad Request errors.
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.META.get('HTTP_ACCEPT', ''):
        data = {
            'error': _('Bad Request'),
            'message': _('The request could not be processed.')
        }
        return JsonResponse(data, status=status.HTTP_400_BAD_REQUEST)
    return render(request, '400.html', status=400)

def permission_denied(request, exception, *args, **kwargs):
    """
    Handler for 403 Forbidden errors.
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.META.get('HTTP_ACCEPT', ''):
        data = {
            'error': _('Permission Denied'),
            'message': _('You do not have permission to perform this action.')
        }
        return JsonResponse(data, status=status.HTTP_403_FORBIDDEN)
    return render(request, '403.html', status=403)

def page_not_found(request, exception, *args, **kwargs):
    """
    Handler for 404 Not Found errors.
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.META.get('HTTP_ACCEPT', ''):
        data = {
            'error': _('Not Found'),
            'message': _('The requested resource was not found.')
        }
        return JsonResponse(data, status=status.HTTP_404_NOT_FOUND)
    return render(request, '404.html', status=404)

def server_error(request, *args, **kwargs):
    """
    Handler for 500 Server Error.
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.META.get('HTTP_ACCEPT', ''):
        data = {
            'error': _('Server Error'),
            'message': _('An internal server error occurred.')
        }
        return JsonResponse(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return render(request, '500.html', status=500)
