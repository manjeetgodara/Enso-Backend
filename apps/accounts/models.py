from django.db import models
from django.contrib.postgres.fields import ArrayField
from marketing.models import *
from simple_history.models import HistoricalRecords    
from django.utils import timezone
from auth.models import Users 
from lead.models import ChannelPartner, Lead
# Create your models here.
class Payment(models.Model):
    STATUS_CHOICES = [
        ('Approval Pending', 'Approval Pending'),
        ('Reject', 'Reject'),
        ('On Hold', 'On Hold'),
        ('Payment Done', 'Payment Done'),
    ]

    PAYMENT_MODE_CHOICES = [
        ('Cash', 'Cash'),
        ('Paytm', 'Paytm'),
        ('Phone Pe', 'Phone Pe'),
        ('UPI', 'UPI'),
        ('Razorpay', 'Razorpay'),
        ('Bank transfer', 'Bank transfer'),
    ]

    REQUEST_TYPE_CHOICES = [
        ('Immediate', 'Immediate'),
        ('Custom', 'Custom'),
    ]

    PAYMENT_TO_CHOICES = [
        ('Marketing', 'Marketing'),
        ('Sales', 'Sales'),
        ('Refund', 'Refund')
    ]

    INVOICE_OVERVIEW_CHOICES = [
        ('Approved by Account', 'Approved by Account'),
        ('Denied by Account', 'Denied by Account'),
        ('Paid by Account', 'Paid by Account'),
    ]
    PAYMENT_TYPE_CHOICES = [
        ('Standard', 'Standard'),
        ('Direct', 'Direct'),
        ('Refund','Refund')
    ]
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE,null=True,blank=True)
    amount = models.IntegerField(null=True, blank=True)
    transaction_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Approval Pending", null=True, blank=True)
    payment_mode = models.CharField(max_length=35, choices=PAYMENT_MODE_CHOICES, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    paid_date = models.DateField(null=True, blank=True)
    paid_time = models.TimeField(null=True, blank=True)
    payment_to = models.CharField(max_length=55, choices=PAYMENT_TO_CHOICES, null=True, blank=True)
    payment_for = models.CharField(max_length=200, null=True, blank=True)
    denied_reason = models.CharField(max_length=255, null=True, blank=True)
   # attached_documents = models.CharField(max_length=100, null=True, blank=True)
    #attached_documents = ArrayField(models.FileField(upload_to='payment/documents/'), null=True, blank=True)
    # attached_documents = models.FileField(upload_to="payment/documents/", null=True,blank=True)
    # invoice_copy = models.FileField(upload_to="payment/documents/",  null=True,blank=True)
    request_type = models.CharField(max_length=25, choices=REQUEST_TYPE_CHOICES, null=True,blank=True)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, null=True,blank=True)
   # agency_type = models.CharField(max_length=255, null=True, blank=True)
    source_id = models.CharField(max_length=255, null=True, blank=True)
    budget = models.IntegerField(null=True, blank=True)
    amount_available = models.IntegerField(null=True,blank=True)
    campaign_type = models.CharField(max_length=255, null=True, blank=True)
    invoice_overview = models.CharField(max_length=20, choices=INVOICE_OVERVIEW_CHOICES, null=True, blank=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, null=True,blank=True)
   # agency = models.ForeignKey(Agency,on_delete=models.CASCADE,null=True,blank=True)
    agency_type = models.ManyToManyField(AgencyType, related_name="agency_type_payments", blank=True)
    agency_name = models.ManyToManyField(Agency, related_name="agency_payments", blank=True)
    created_on = models.DateTimeField(auto_now_add=True, null=True,blank=True)
    invoice_overview_list = ArrayField(models.JSONField(),default=list,blank=True,null=True) 
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES,default="Standard", null=True, blank=True)
    expense_head = models.CharField(max_length=255, null=True, blank=True)
    customer_name = models.CharField(max_length=100, null=True, blank=True)

    # Sales payment changes
    channel_partner = models.ForeignKey(ChannelPartner, on_delete=models.CASCADE, null=True,blank=True)
    project = models.ForeignKey('inventory.ProjectDetail', on_delete=models.CASCADE, null=True,blank=True)
    apartment_no = models.ForeignKey('inventory.ProjectInventory', on_delete=models.CASCADE, null=True,blank=True)

    history = HistoricalRecords()
    def save(self, *args, **kwargs):
        if self.budget is not None and self.amount is not None:
            self.amount_available = self.budget - self.amount
        else:
            self.amount_available = None
        super(Payment, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.payment_for} - {self.amount} - {self.status} -{self.id} "



# class RefundPaymentOverview(models.Model):
#     STATUS_CHOICES = [
#         ('Approval Pending', 'Approval Pending'),
#         ('Reject', 'Reject'),
#         ('On Hold', 'On Hold'),
#         ('Payment Done', 'Payment Done'),
#     ]


#     INVOICE_OVERVIEW_CHOICES = [
#         ('Approved by Account', 'Approved by Account'),
#         ('Denied by Account', 'Denied by Account'),
#         ('Paid by Account', 'Paid by Account'),
#     ]
    
#     lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
#     amount = models.IntegerField(null=True, blank=True)
#     apartment_no = models.CharField(max_length=50 , null=True,blank=True)
#     project_id = models.IntegerField(null=True,blank=True)
#     denied_reason = models.CharField(max_length=225,null=True,blank=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Approval Pending", null=True, blank=True)
#     invoice_overview = models.CharField(max_length=20, choices=INVOICE_OVERVIEW_CHOICES, null=True, blank=True)
#     invoice_overview_list = ArrayField(models.JSONField(),default=list,blank=True,null=True) 
#     history = HistoricalRecords()

#     def __str__(self):
#         return f"{self.lead}-{self.amount} - {self.status} -{self.id} "


class InvoicePaymentDoc(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, null=True, blank=True)
    invoice_doc = models.FileField(upload_to='payment/documents/', null=True, blank=True) 

    def __str__(self):
        return f"{self.id}-->{self.payment.payment_for}"


class AttachedPaymentDoc(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, null=True, blank=True)
    attached_doc = models.FileField(upload_to='payment/documents/', null=True, blank=True) 

    def __str__(self):
        return f"{self.id}-->{self.payment.payment_for}"

class Notes(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True, related_name='account_notes_created_by')
    notes = models.TextField(null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.id}"

    def save(self, *args, **kwargs):
        if not self.created_on:
            self.created_on = timezone.now().astimezone(timezone.pytz.timezone('Asia/Kolkata'))
            print("timestamp in model: ", self.created_on)
        super().save(*args, **kwargs)

    class Meta:

        indexes = [
            models.Index(fields=['created_on'])
        ]


class CustomerPayment(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('Cash', 'Cash'),
        ('Paytm', 'Paytm'),
        ('Phone Pe', 'Phone Pe'),
        ('UPI', 'UPI'),
        ('Razorpay', 'Razorpay'),
        ('Bank transfer', 'Bank transfer'),
    ]

    PAYMENT_TYPE_CHOICES = [
        ('Refund','Refund'),
        ('Payment','Payment'),
        ('TDS','TDS')
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='customer_payments')
    event_name = models.CharField(max_length=255 , null =True , blank=True)
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    time = models.TimeField(default=timezone.now, null=True, blank=True)
    payment_mode = models.CharField(max_length=35, choices=PAYMENT_MODE_CHOICES)
    transaction_id = models.CharField(max_length=255)
    tds_transaction_id = models.CharField(max_length=255 , unique=True,null=True,blank=True)
    tds_date =  models.DateField(null=True,blank=True)
    tds_time = models.TimeField( null=True, blank=True)
    tds_status = models.CharField(max_length=35, default="Pending")
    tds_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    payment_type = models.CharField(max_length=35, choices=PAYMENT_TYPE_CHOICES , default="Payment")
    created_date = models.DateTimeField(default=timezone.now) 
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.event_name} - {self.amount} - {self.payment_mode}"


