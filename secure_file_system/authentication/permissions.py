from rest_framework import permissions

class IsOperationsUser(permissions.BasePermission):
    """
    Permission class to check if the user has the OPERATIONS role.
    """
    def has_permission(self, request, view):
        # Check if the user is authenticated and has the OPERATIONS role
        return bool(request.user and request.user.is_authenticated and 
                   hasattr(request.user, 'role') and 
                   request.user.role == 'OPERATIONS')
