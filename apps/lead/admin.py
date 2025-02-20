from django.contrib import admin
from lead.models import *
#from .models import BookingForm, CollectToken, Inventory, Project
from simple_history.admin import SimpleHistoryAdmin

class LeadAdmin(admin.ModelAdmin):
   list_display = ('id','first_name', 'last_name', 'primary_phone_no', 'primary_email' ,'followers','source', 'current_stage','creation_stage','history')

class LeadRequirementAdmin(admin.ModelAdmin):
   list_display = ('purpose', 'funding', 'configuration','history')

class SourceAdmin(admin.ModelAdmin):
   list_display = ('id','source_id','name')

class UpdatesAdmin(admin.ModelAdmin):
   list_display = ('lead','welcome_call_status','welcome_email_status','demand_letter_status')

class DocumentSectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'document_id')

    def document_id(self, obj):
        return obj.id
    document_id.short_description = 'Document ID'

class ChannelPartnerAdmin(admin.ModelAdmin):
   list_display = ('id', 'full_name', 'firm')   

class NotificationCountAdmin(admin.ModelAdmin):
   list_display = ('lead','count')
   search_fields = ('lead__id',)

# class BookingFormAdmin(admin.ModelAdmin):
#     list_display = ('customer_name', 'pan_no', 'nationality', 'apartment_type', 'tower', 'date_of_booking')
#     list_filter = ('apartment_type', 'tower', 'date_of_booking')
#     search_fields = ('customer_name__first_name', 'customer_name__last_name')

# class CollectTokenAdmin(admin.ModelAdmin):
#     list_display = ('name', 'occupation', 'configuration', 'area', 'project', 'tower')
#     list_filter = ('occupation', 'configuration', 'area', 'project', 'tower')
#     search_fields = ('name',)


# class InventoryAdmin(admin.ModelAdmin):
#     list_display = ('project', 'wings', 'towers', 'configuration', 'apartment_no', 'floor_number', 'status')
#     list_filter = ('project', 'configuration', 'status')
#     search_fields = ('apartment_no',)


# class ProjectAdmin(admin.ModelAdmin):
#     list_display = ('name',)
#     search_fields = ('name',)
# admin.site.register(BookingForm, BookingFormAdmin)
# admin.site.register(CollectToken, CollectTokenAdmin)

# admin.site.register(Inventory, InventoryAdmin)
# admin.site.register(Project, ProjectAdmin)
admin.site.register(LeadRequirements,LeadRequirementAdmin)
# admin.site.register(Lead, SimpleHistoryAdmin)
admin.site.register(Lead, LeadAdmin)
admin.site.register(Source,SourceAdmin)
admin.site.register(Updates,UpdatesAdmin)
admin.site.register(DocumentSection,DocumentSectionAdmin)
admin.site.register(PostSalesDocumentSection)
admin.site.register(PostSalesDocumentType)
admin.site.register(Meeting)
admin.site.register(ChannelPartner, ChannelPartnerAdmin)
admin.site.register(ExportFile)
admin.site.register(BrokerageCategory)
admin.site.register(BrokerageDeal)
admin.site.register(ChannelPartnerBrokerage)
admin.site.register(NotificationCount , NotificationCountAdmin)
