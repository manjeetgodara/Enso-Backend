from django.urls import path
from .views import *

urlpatterns = [
    path('lead-calls/', McubeCreateAPIView.as_view(), name='lead_calls_create'),
    path('get-calls-list/', get_calls_list, name='all_calls_list'),
    path('lead-calls/<int:lead_phone>/', ActivityView.as_view(), name='lead_calls_activity'),
    path('lead-calls/<int:pk>/', MCubeRetrieveUpdateAPIView.as_view(), name='lead_calls_retrieve_update'),
    path('make-outbound-call/', make_outbound_call, name='make-outbound-call'),
]