from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf.urls import url
from .views import TaskViewSet,SubmitApproval,ApprovalListView, RequestApproval, NotificationsView, NotificationsRetrieveUpdateDestroyView


router = DefaultRouter()
router.register(r'task', TaskViewSet, basename='task')

urlpatterns = [
    path('', include(router.urls)),
    path('request_approval/', RequestApproval.as_view(), name='approval-list'),
    path('get_approvals/', ApprovalListView.as_view(), name='approval-list'),
    path('submit_approval/', SubmitApproval.as_view(), name='submit_approval'),
    path('notifications/', NotificationsView.as_view(), name='notifications'),
    path('notifications/<int:pk>/', NotificationsRetrieveUpdateDestroyView.as_view(), name='notifications'),
]
