from django.contrib import admin
from .models import CancelBookingReason, Notes, SiteVisit

class NotesAdmin(admin.ModelAdmin):
   list_display = ('id', 'lead', 'created_on', 'created_by', 'notes', 'history')

class SiteVisitAdmin(admin.ModelAdmin):
  list_display = ('id', 'lead', 'visit_date', 'property', 'timeslot', 'closing_manager','sourcing_manager')

admin.site.register(Notes,NotesAdmin)
admin.site.register(SiteVisit,SiteVisitAdmin)
admin.site.register(CancelBookingReason)


