from .utils import restrict_access_file_format
from auth.utils import ResponseHandler
from rest_framework import status
from functools import wraps

def check_group_access(required_groups):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self,request,*args, **kwargs):
            print(self.request)
            #print(self.request.user.first_name)
            user_groups = self.request.user.groups.values_list('name', flat=True)
            print('user_groups:', user_groups)
            if any(group in required_groups for group in user_groups):
                print("It exists")
                return view_func(self, request, *args, **kwargs)
            else:
                error = True
                message = 'Access denied.'
                body = None
                return ResponseHandler(error,message,body,status.HTTP_403_FORBIDDEN)
        return _wrapped_view
    return decorator

def restrict_access(view_func):
    @wraps(view_func)
    def _wrapped_view(self, request, *args, **kwargs):
        file_format = request.GET.get('fileformat')
        if not restrict_access_file_format(self.request.user, file_format):
            error = True
            message = 'Access denied.'
            body = None
            return ResponseHandler(error,message,body,status.HTTP_403_FORBIDDEN)
        return view_func(self, request, *args, **kwargs)
    return _wrapped_view


from django.contrib.auth.models import Group
def group_access(view_func):
    @wraps(view_func)
    def _wrapped_view(self,request,*args, **kwargs):
        print(self.request)
        #print(self.request.user.first_name)
        if self.request.user.groups.filter(name='Manager').exists():
            print("It exists")
            return view_func(self, request, *args, **kwargs)
        else:
            error = True
            message = 'Access denied.'
            body = None
            return ResponseHandler(error,message,body,status.HTTP_403_FORBIDDEN)
    return _wrapped_view


def bulk_group_access(view_func):
    @wraps(view_func)
    def _wrapped_view(self,request,*args, **kwargs):
        print(self.request)
        #print(self.request.user.first_name)
        if self.request.user.groups.filter(name='ADMIN').exists() or self.request.user.groups.filter(name='PROMOTER').exists() or self.request.user.groups.filter(name='VICE_PRESIDENT').exists():
            print("It exists")
            return view_func(self, request, *args, **kwargs)
        else:
            error = True
            message = 'Access denied.'
            body = None
            return ResponseHandler(error,message,body,status.HTTP_403_FORBIDDEN)
    return _wrapped_view
#manager_required = user_passes_test(is_manager, login_url='login')

def check_group_access(required_groups):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self,request,*args, **kwargs):
            print(self.request)
            #print(self.request.user.first_name)
            user_groups = self.request.user.groups.values_list('name', flat=True)
            print('user_groups:', user_groups)
            if any(group in required_groups for group in user_groups):
                print("It exists")
                return view_func(self, request, *args, **kwargs)
            else:
                error = True
                message = 'Access denied.'
                body = None
                return ResponseHandler(error,message,body,status.HTTP_403_FORBIDDEN)
        return _wrapped_view
    return decorator

def check_access(required_groups=None, required_permissions=None):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self,request, *args, **kwargs):
            if required_groups:

                if not any(request.user.groups.filter(name=group).exists() for group in required_groups):
                    return ResponseHandler(True,"You do not have permission to access this view.",None,status.HTTP_403_FORBIDDEN)
                
            # user_permissions = request.user.user_permissions.all()

            # # Print the permissions
            # print(f"User: {request.user.name}")
            # print("Permissions:")
            # for permission in user_permissions:
            #     print(f"- {permission.codename} ({permission.content_type.app_label}.{permission.codename})")
            # print(required_permissions,request.user)
            # if required_permissions:

            #     if not all(request.user.has_perm(permission) for permission in required_permissions):
            #         return ResponseHandler(True,"You do not have permission to access this view.",None,status.HTTP_403_FORBIDDEN)
            #     else:
            #         print("He has access")
            if required_permissions:
                user_has_required_permissions = all(
                    request.user.has_perm(permission) or
                    any(group.permissions.filter(codename=permission).exists() for group in request.user.groups.all())
                    for permission in required_permissions
                )
                if not user_has_required_permissions:
                    return ResponseHandler(True, "You do not have permission to access this view.", None, status.HTTP_403_FORBIDDEN)
            return view_func(self,request, *args, **kwargs)

        return _wrapped_view

    return decorator