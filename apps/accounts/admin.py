from django.contrib import admin
from .models  import *
# Register your models here.

class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'amount', 'payment_to', 'status', 'paid_date','lead')

    fieldsets = (
        ('Basic Information', {
            'fields': ( 'amount', 'transaction_id', 'status', 'customer_name', 'payment_mode', 'due_date', 'paid_date','paid_time','payment_to','payment_for', 'budget','amount_available','denied_reason','request_type','campaign','agency_type','source_id','campaign_type','payment_type','expense_head','channel_partner', 'agency_name','project','apartment_no', 'invoice_overview_list', 'lead')
        }),
    )

class CustomerPaymentAdmin(admin.ModelAdmin):
    list_display = ('lead','event_name','amount','transaction_id','payment_type','date','time')
admin.site.register(Payment, PaymentAdmin)
admin.site.register(AttachedPaymentDoc)
admin.site.register(InvoicePaymentDoc)
admin.site.register(CustomerPayment,CustomerPaymentAdmin)


