from django.urls import path
from . import views
from .views import CancelReasonCreateView, GetSourcingManager, SiteVisitDetailsbyId, SiteVisitUpdateView, GetClosingManager, CalendarViewList, SiteVisitMetaAPIView, AvailableTimeslotsView, GetMISDashboardDetailsView

urlpatterns = [
    path('notes/', views.NotesListCreateView.as_view(), name='notes-list-create'),
    path('notes/lead/<int:lead_id>/', views.NotesListView.as_view(), name='notes-list'),
    path('notes/<int:id>/', views.UpdateOrDeleteNoteView.as_view(), name='update-or-delete-note'),
    path('schedule-site-visit/', views.SiteVisitBookingView.as_view(), name='schedule-site-visit'),
    path('site-visit/<int:pk>/', SiteVisitUpdateView.as_view(), name='site-visit-update'),
    path('calendar-view/', CalendarViewList.as_view(), name='calendar-view-list'),
    path('site-visit/available/', GetClosingManager.as_view(), name='get-closing-manager'),
    path('site-visit/sourcing-manager-available/',GetSourcingManager.as_view(),name='get-sourcing-manager'),
    path('site-visit/lead/<int:pk>/',SiteVisitDetailsbyId.as_view(), name='get-site-visit-id'),
    path('get-site-visit-metadata/',SiteVisitMetaAPIView.as_view(), name='get-site-visit-metadata'),
    path('available-timeslots/<int:lead_id>/<str:visit_date>/',AvailableTimeslotsView.as_view(), name='available-timeslots'),
    path('mis-dashboard/', GetMISDashboardDetailsView.as_view(), name='get-mis-dashboard-details')  ,  
    path('cancel-reasons/', CancelReasonCreateView.as_view(), name='cancel-reason-create'),
]


