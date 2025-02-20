from django.contrib import admin
from .models import *

# Register your models here.
class LeadCallsMcubeAdmin(admin.ModelAdmin):
    list_display = ('callid', 'lead_phone', 'executive', 'call_type', 'call_duration', 'call_status')
    list_filter = ( 'call_type', 'call_status', 'executive',)
    search_fields = ('lead_phone', 'executive', 'call_type', 'call_status',)


admin.site.register(LeadCallsMcube, LeadCallsMcubeAdmin)
