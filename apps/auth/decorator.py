from functools import wraps
from .utils import ResponseHandler

def role_check(required_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(self, request, *args, **kwargs):
            user_role = self.request.user.role if hasattr(request.user, 'role') else None
            allowed_roles = ['SUPER ADMIN', 'ADMIN', 'MANAGER', 'EXECUTIVE']
            
            if user_role in allowed_roles and user_role in required_roles:
                return view_func(self, request, *args, **kwargs)
            else:               
                return ResponseHandler(True,"Access Denied.","",403)
        return _wrapped_view
    return decorator