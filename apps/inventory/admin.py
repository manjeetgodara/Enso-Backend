from django.contrib import admin
from .models import *

class ProjectInventoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'apartment_no', 'configuration', 'flat_no', 'floor_number', 'area', 'no_of_bathrooms', 'no_of_bedrooms', 'no_of_balcony', 'pre_deal_amount', 'min_deal_amount_cm', 'min_deal_amount_sh', 'min_deal_amount_vp', 'status', 'project_inventory_type', 'tower_display', 'project_display','lead','in_progress',)

    list_filter = ('configuration', 'status', 'project_inventory_type')
    search_fields = ('flat_no', 'tower__project__name', 'tower__name', 'tower__name')

    fieldsets = (
        ('Basic Information', {
            'fields': ('configuration', 'flat_no', 'tower', 'apartment_no', 'floor_number', 'area', 'no_of_bathrooms', 'no_of_bedrooms', 'no_of_balcony', 'status', 'project_inventory_type','lead','car_parking', 'amount_per_car_parking')
        }),
        ('Deal Information', {
            'fields': ('pre_deal_amount', 'min_deal_amount_cm', 'min_deal_amount_sh', 'min_deal_amount_vp'),
            # 'classes': ('collapse',),
        }),
        # ('Location Information', {
        #     'fields': ('wing',),
        # }),
        ('Vastu Details', {
            'fields': ('vastu_details',),
            # 'classes': ('collapse',),
        }),
        ('In Progress', {
            'fields' : ('in_progress',),
        }),
    )

    # readonly_fields = ('id',)
    # raw_id_fields = ('wing', 'configuration')

    def tower_display(self, obj):
        return obj.tower.name if obj.tower else ''

    def project_display(self, obj):
        return obj.tower.project.name if obj.tower and obj.tower.project else ''

    tower_display.short_description = 'Tower'
    project_display.short_description = 'Project'


class ProjectDetailAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'rera_number', 'area', 'project_type', 'total_towers', 'pincode', 'address', 'city', 'current_event_order')

class ProjectTowerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'project')

class ConfigurationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

class PropertyTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

# class TowerAdmin(admin.ModelAdmin):
#     list_display = ('id', 'name', 'wing')
    
class BookingFormAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'pan_no', 'aadhaar_details', 'nationality', 'configuration', 'tower', 'date_of_booking')
    list_filter = ('configuration', 'tower', 'date_of_booking')
    search_fields = ('customer_name__first_name', 'customer_name__last_name')

class ProjectCostSheetAdmin(admin.ModelAdmin):
    list_display = ('id', 'project', 'event_order', 'event', 'event_status','due_date')
    list_filter = ('project', 'completed_at')
    search_fields = ('event',)
    ordering = ('project', 'event_order')

class InventoryCostSheetAdmin(admin.ModelAdmin):
    list_display = ('id', 'inventory_display', 'event_order', 'event', 'completed', 'completed_at', 'due_date' , 'payment_in_percentage', 'amount', 'gst', 'tds', 'total_amount', 'paid', 'paid_date', 'lead',)

    list_filter = ('inventory__tower__project', 'inventory__tower', 'inventory', 'completed', 'paid')
    search_fields = ('inventory__apartment_no', 'inventory__tower__project__name', 'inventory__tower__name', 'event')

    fieldsets = (
        ('Basic Information', {
            'fields': ('inventory', 'lead','event_order', 'event', 'due_date' , 'completed', 'completed_at'),
        }),
        ('Payment Information', {
            'fields': ('payment_in_percentage', 'amount', 'gst', 'total_amount', 'paid', 'paid_date'),
        }),
    )

    readonly_fields = ('id', 'inventory_display')

    def inventory_display(self, obj):
        return f"{obj.inventory.tower.project.name} - {obj.inventory.apartment_no} - Event Order {obj.event_order}"

    inventory_display.short_description = 'Inventory'

class PropertyOwnerAdmin(admin.ModelAdmin):
    list_display = ('id', 'lead', 'property', 'deal_amount', 'cost_of_flat', 'other_charges','ownership_number', 'refund_amount' , 'refund_status', 'booking_status' , 'booking_cancelled_at', 'property_buy_date')
    list_filter = ('lead', 'property', 'property__configuration', 'property__status')
    search_fields = ('lead__primary_email', 'property__apartment_no')

    fieldsets = (
        ('Basic Information', {
            'fields': ('lead', 'property', 'deal_amount', 'cost_of_flat', 'other_charges', 'ownership_number', 'property_buy_date','cost_sheet_pdf','booking_form_pdf', 'booking_status')
        }),
    )

    readonly_fields = ('id',)

class PaymentNotificationsAdmin(admin.ModelAdmin):
    list_display = ['payment','read','email','created']
    search_fields = ['payment']

class SalesActivityAdmin(admin.ModelAdmin):
    list_display = ['id']
    
admin.site.register(PropertyOwner, PropertyOwnerAdmin)

admin.site.register(InventoryCostSheet, InventoryCostSheetAdmin)
admin.site.register(ProjectCostSheet, ProjectCostSheetAdmin)
admin.site.register(ProjectDetail, ProjectDetailAdmin)
admin.site.register(ProjectTower, ProjectTowerAdmin)
# admin.site.register(Tower, TowerAdmin)
admin.site.register(ProjectInventory, ProjectInventoryAdmin)
admin.site.register(Configuration, ConfigurationAdmin)
admin.site.register(PropertyType, PropertyTypeAdmin)
admin.site.register(BookingForm, BookingFormAdmin)
admin.site.register(PaymentNotifications, PaymentNotificationsAdmin)
admin.site.register(SalesActivity,SalesActivityAdmin)
