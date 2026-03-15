from rest_framework.permissions import BasePermission

class IsAgencyAdmin(BasePermission):
    
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and  
            request.user.role == 'agency_admin'
        )