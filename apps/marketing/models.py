from django.db import models

# Create your models here.
from django.core.validators import MinValueValidator
from django.contrib.postgres.fields import ArrayField
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from simple_history.models import HistoricalRecords    
import random
# from auth.models import Users
import os
import uuid
from django.db import models
from django.utils import timezone


def upload_to_path(instance, filename):
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')  
    filename = f"{timestamp}_{filename}"
    return f'vendor/certificates/{filename}'

def upload_agency_path(instance, filename):
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')  
    filename = f"{timestamp}_{filename}"
    return f'agency/certificates/{filename}'

class Vendor(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    brand_name = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    gstin_number = models.CharField(max_length=15, null=True, blank=True)
    reraid = models.CharField(max_length=20, null=True, blank=True)
    pan_details = models.CharField(max_length=20, null=True, blank=True)
    aadhaar_number = models.CharField(max_length=12, null=True, blank=True)
    phone_number = models.CharField(max_length=10, null=True, blank=True)
    telephone_number = models.CharField(max_length=15, null=True, blank=True)
    gst_certificate = models.FileField(upload_to=upload_to_path, null=True, blank=True)
    rera_certificate = models.FileField(upload_to=upload_to_path, null=True, blank=True)
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    account_holder_name = models.CharField(max_length=255, null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)
    ifsc_code = models.CharField(max_length=15, null=True, blank=True)
    history = HistoricalRecords()
    scope_of_work = models.FileField(upload_to=upload_to_path, null=True, blank=True)


    def __str__(self):
        return f"{self.name} - id: {self.id}" if self.name and self.id  else "Vendor"

    class Meta:
        verbose_name_plural = "Vendors"

class AgencyType(models.Model):
    AGENCY_TYPES = [
        ("Creative", "Creative"),
        ("Digital", "Digital"),
        ("Production", "Production"),
        ("PR", "PR"),
        ("Printing", "Printing"),
        ("Event", "Event"),
        ("Other", "Other")
    ]
    name = models.CharField(max_length=20, choices=AGENCY_TYPES, unique=True, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Agency Types"

class AgencyRemark(models.Model): 
    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    created_by = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.remark

    class Meta:
        verbose_name_plural = "Agency Remarks"        
class Agency(models.Model):
    AGENCY_TYPES = [
        ("Creative", "Creative"),
        ("Digital", "Digital"),
        ("Production", "Production"),
        ("PR", "PR"),
        ("Printing", "Printing"),
        ("Event", "Event"),
        ("Other", "Other")
    ]
    agency_number = models.CharField(max_length=4, unique=True, editable=False)
    agency_name = models.CharField(max_length= 255, unique=True, null=True, blank=True)
    agency_type = models.ManyToManyField(AgencyType, related_name="agencies", null=True, blank=True)
    vendors_full_name = models.CharField(max_length= 255, null=True, blank=True)
    brand_name = models.CharField(max_length= 255, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    gstin_number = models.CharField(max_length=15, null=True, blank=True)
    pan_details = models.CharField(max_length=20, null=True, blank=True)
    aadhaar_details = models.CharField(max_length=12, null=True, blank=True)
    phone_number = models.CharField(max_length=10, null=True, blank=True)
    gst_certificate = models.FileField(upload_to=upload_agency_path, null=True, blank=True)
    pan_card = models.FileField(upload_to=upload_agency_path, null=True, blank=True)
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    account_holder_name = models.CharField(max_length=255, null=True, blank=True)
    account_number = models.CharField(max_length=20, null=True, blank=True)
    ifsc_code = models.CharField(max_length=15, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    remarks = models.ManyToManyField(AgencyRemark, null=True, blank=True)

    def __str__(self):
        return f"{self.agency_name} - id: {self.id}" if self.agency_name and self.id  else "Agency"

    def save(self, *args, **kwargs):
        if not self.agency_number:
            self.agency_number = self.generate_unique_agency_number()
        super().save(*args, **kwargs)

    def generate_unique_agency_number(self):
        while True:
            agency_number = str(random.randint(1000, 9999))
            if not Agency.objects.filter(agency_number=agency_number).exists():
                return agency_number    

    class Meta:
        verbose_name_plural = "Agencies"

class CampaignDocument(models.Model):
    campaign = models.ForeignKey('Campaign', related_name='documents', on_delete=models.CASCADE)
    document = models.FileField(upload_to='marketing_documents/')
class Campaign(models.Model):
    AGENCY_TYPES = [
        ("Creative", "Creative"),
        ("Digital", "Digital"),
        ("Production", "Production"),
        ("PR", "PR"),
        ("Printing", "Printing"),
        ("Event", "Event"),
        ("Other", "Other")
    ]
    sourceid = models.CharField(max_length=4, unique=True, editable=False)
    campaign_name = models.CharField(max_length= 100)
    agency_type = models.ManyToManyField(AgencyType, null=True, blank=True)
    agency_name = models.ManyToManyField(Agency, null=True, blank=True)
    budget = models.IntegerField(default=0)
    spend = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField()
    end_date = models.DateField(null= True, blank= True)
    team_members = ArrayField(models.IntegerField(), default=list, blank=True)
    virtual_number=models.CharField(max_length=13, null=True,blank=True)
    history = HistoricalRecords()
    

    def save(self, *args, **kwargs):
        # Check if the instance is being created for the first time
        if self.pk is None:
            # Generate a random unique 4-digit number for sourceid
            while True:
                new_sourceid = str(random.randint(1000, 9999))
                if not Campaign.objects.filter(sourceid=new_sourceid).exists():
                    break
            self.sourceid = new_sourceid

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.campaign_name} - {self.sourceid} - id: {self.id}"
    
@receiver(pre_save, sender=Campaign)
def campaign_pre_save_handler(sender, instance, **kwargs):
    pass

@receiver(post_save, sender=Campaign)
def campaign_post_save_handler(sender, instance, created, **kwargs):

    if created:
        print(f'Campaign instance {instance.id} has been created!')
    else:
        print(f'Campaign instance {instance.id} has been updated!')


class Folder(models.Model):
    name = models.CharField(max_length=255)
    icon = models.ImageField(upload_to='folder_icons/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()
    #created_by = models.ForeignKey(Users, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} - id: {self.id}"
    
@receiver(pre_save, sender=Folder)
def folder_pre_save_handler(sender, instance, **kwargs):
    pass

@receiver(post_save, sender=Folder)
def folder_post_save_handler(sender, instance, created, **kwargs):

    if created:
        print(f'Folder instance {instance.id} has been created!')
    else:
        print(f'Folder instance {instance.id} has been updated!')


def upload_to_directory(instance, filename):
    folder_id = instance.folder.id if instance.folder else "unknown"
    return f'uploads/{folder_id}/{filename}'

class Document(models.Model):
    file = models.FileField(upload_to=upload_to_directory)
    content_type = models.CharField(max_length= 255, null= True, blank= True)
    folder = models.ForeignKey(Folder, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.file.name } - id: {self.id}"

@receiver(pre_save, sender=Document)
def document_pre_save_handler(sender, instance, **kwargs):
    pass


@receiver(post_save, sender=Document)
def document_post_save_handler(sender, instance, created, **kwargs):

    if created:
        print(f'Document instance {instance.id} has been created!')
    else:
        print(f'Document instance {instance.id} has been updated!')


pre_save.connect(campaign_pre_save_handler, sender=Campaign)
post_save.connect(campaign_post_save_handler, sender=Campaign)



class CampaignSpecificBudget(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='specific_budgets')
    expense_head = models.CharField(max_length=100, null =True , blank = True)
    amount = models.IntegerField(default=0)
    paid_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
   

    def __str__(self):
        return f"{self.id} - {self.expense_head}  on {self.paid_date}"
    
class ExportFile(models.Model):
    file = models.FileField(upload_to='exports/')
    created_at = models.DateTimeField(auto_now_add=True)    

# class Payment(models.Model):
#     PAYMENT_STATUS_CHOICES = [
#         ("Pending", "Pending"),
#         ("Done", "Done"),
#         ("Delayed", "Delayed"),
#     ]

#     campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="payments")
#     amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(0)])
#     due_date = models.DateField(null=True, blank=True)  # Due date for recurring payments
#     paid_on = models.DateField(null=True, blank=True)  # Date when payment is done, applicable for both types
#     recurring = models.BooleanField(default=False)
#     status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="Pending")

#     def __str__(self):
#         return f"Payment for Campaign {self.campaign.campaign_name} - Amount: {self.amount} - Due Date: {self.due_date} - Paid On: {self.paid_on}"




