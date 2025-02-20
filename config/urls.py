"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


admin.site.site_header = "ESTO Administration"
admin.site.index_title = "ESTO Admin Site"
admin.site.site_title = "ESTO Admin Login"

schema_view = get_schema_view(
    openapi.Info(
        title="ESTO API",
        default_version='v1',
        description="ESTO API Documentation",
        terms_of_service="NA",
        contact=openapi.Contact(email="contact@yourapp.com"),
        license=openapi.License(name="Your License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("auth.urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/leads/", include("lead.urls")),
    path("api/leads/activity/", include("activity.urls")),
    path("api/workflow/", include("workflow.urls")),
    path("api/core/", include("core.urls")),
    path("api/email/", include("emails.urls")),
    path("api/mcube/", include("mcube.urls")),
    path("api/marketing/", include("marketing.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/communications/", include("comms.urls")),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
