from django.db import models
from simple_history.models import HistoricalRecords
from core.models import Organization
from auth.models import Users
from django.contrib.postgres.fields import ArrayField
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from datetime import date
from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
from django.utils import timezone
#from django.contrib.gis.db import models
class Source(models.Model):
    source_id = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    #description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.source_id} - {self.name} "


class BrokerageCategory(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name    

class ChannelPartner(models.Model):
    #REQUIRED_FIELDS = []
    CP_STATUS = [
        ('New','New'),
        ('Interested', 'Interested'),
        ('Not Interested', 'Not Interested'),
        ('Might be Interested', 'Might be Interested')
    ]
    CATEGORY = [
        ('1', '1'),
        ('2', '2'),
        ('3', '3')
    ] 
    TYPE_OF_CP = [
        ('ICP', 'ICP'),
        ('RETAIL', 'RETAIL')
    ] 

    full_name=models.CharField(max_length=100,blank=True, null=True) 
    #last_name=models.CharField(max_length=100)
    primary_phone_no=models.CharField(max_length=10,blank=True,unique=True,null=True)
    secondary_phone_no=models.CharField(max_length=10,blank=True, null=True)
    primary_email=models.EmailField(max_length=255,blank=True, null=True)
    secondary_email=models.EmailField(max_length=255,blank=True)
    firm=models.CharField(max_length=100,blank=True,unique=True, null=True)
    pan_no = models.CharField(max_length=20,blank=True, null=True)
    # aadhaar_details = models.CharField(max_length=20,blank=True, null=True)
    gstin_number = models.CharField(max_length=15, null=True, blank=True)
    location=models.CharField(max_length=255,blank=True, null=True)
    address= models.CharField(max_length=255, blank=True, null=True)
    pin_code= models.CharField(max_length=6, blank=True, null=True)
    created_on = models.DateTimeField(auto_now_add=True)
    rera_id = models.CharField(max_length=25,blank=True, null=True)
    channel_partner_status=models.CharField(max_length=30,choices=CP_STATUS,default='New')
    category=models.CharField(max_length=5,choices=CATEGORY,blank=True, null=True)
    type_of_cp=models.CharField(max_length=20,choices=TYPE_OF_CP,blank=True, null=True)
    bank_name =  models.CharField(max_length=100,blank=True, null=True)
    bank_account_number = models.CharField(max_length=40,blank=True, null=True)
    bank_account_holder_name = models.CharField(max_length=80,blank=True, null=True)
    ifsc_code =  models.CharField(max_length=80,blank=True, null=True)
    brokerage_category = models.ForeignKey(BrokerageCategory,related_name = "brokerage_category_cp",on_delete = models.CASCADE,null=True,blank=True)
   # brokerage_percentage = models.DecimalField(max_digits=5, decimal_places=2 , default = 0)
    creator = models.ForeignKey(Users, default=None, related_name="cp_creator", on_delete=models.CASCADE, null=True,blank=True)
    gst_certificate = models.FileField(upload_to='channel_partner_certificates/',blank=True, null=True)
    pan_card = models.FileField(upload_to='channel_partner_certificates/',blank=True, null=True)
    rera_certificate = models.FileField(upload_to='channel_partner_certificates/',blank=True, null=True)
    business_card = models.FileField(upload_to='channel_partner_certificates/',blank=True, null=True)
    brokerage_updated = models.BooleanField(default=False)
    #creator = models.ForeignKey(Users, default=None, related_name="lead_creator", on_delete=models.CASCADE, null=True,blank=True)
    history = HistoricalRecords()

    # def __str__(self):
    #     return self.full_name

    def __str__(self):

        if self.full_name:
            return f"{self.full_name} ({self.firm})"
        else:
            return self.firm

    
    class Meta:
        indexes = [
            models.Index(fields=['primary_phone_no']),
            models.Index(fields=['primary_email']),
        ]
        unique_together = ("firm", "primary_phone_no")
    


class BrokerageDeal(models.Model):
    category = models.ForeignKey(BrokerageCategory, on_delete=models.CASCADE, related_name='deals')
    deal_range = models.CharField(max_length=20,default="1-3") 
    percentage = models.DecimalField(max_digits=5, decimal_places=2)

    def __str__(self):
        return f"{self.category.name} --> {self.deal_range}: {self.percentage}%"


class ChannelPartnerBrokerage(models.Model):
    channel_partner = models.ForeignKey(ChannelPartner, on_delete=models.CASCADE, related_name='brokerage_cp')
    brokerage_category = models.ForeignKey(BrokerageCategory, on_delete=models.CASCADE, related_name='brokerages')
    brokerage_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id} - {self.channel_partner} - {self.brokerage_category}: {self.brokerage_percentage}%"

    class Meta:
        indexes = [
            models.Index(fields=['channel_partner', 'brokerage_category']),
        ]


class Meeting(models.Model):
    channel_partner = models.ForeignKey(ChannelPartner,related_name="meetings", on_delete=models.CASCADE)
    # date = models.DateField(auto_now_add=True)  
    date = models.DateField()
    duration = models.DurationField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)  
    location = models.CharField(max_length=150,blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    sourcing_manager = models.ForeignKey(Users, related_name='sourcing_manager', on_delete=models.CASCADE,null=True, blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"Meeting with {self.channel_partner.full_name} on {self.date}"

class LeadRequirements(models.Model):
    PURPOSE_CHOICES = [
        ('Investment', 'Investment'),
        ('Self', 'Self'),
    ]
    """
    PROJECT_CHOICES = [
        ('P1', 'P1'),
        ('P2', 'P2'),
        ('P3','P3'),
        ('P4','P4')
    ]"""
    FUNDING_CHOICES = [
        ('Loan', 'Loan'),
        ('Self funded', 'Self funded'),
        ('Both','Both'),
    ]
    CONFIGURATION_CHOICES=[
        ('1BHK', '1BHK'),
        ('1.5BHK', '1.5BHK'),
        ('2BHK', '2BHK'),
        ('3BHK', '3BHK'),
        ('4BHK', '4BHK'),
    ]
  
    AREA_CHOICES=[
        ('<400 Sqft', '<400 Sqft'),
        ('400 - 500 Sqft', '400 - 500 Sqft'),
        ('>500 Sqft', '>500 Sqft'),
        ('<600 Sqft', '<600 Sqft'), 
        ('600 - 700 Sqft', '600 - 700 Sqft'),
        ('>700 Sqft', '>700 Sqft'),      
        ('<1000 Sqft', '<1000 Sqft'),
        ('1000 - 1300 Sqft', '1000 - 1300 Sqft'),
        ('>1300 Sqft', '>1300 Sqft'),
        ('1000 - 1500 Sqft', '1000 - 1500 Sqft'),
        ('>1500 Sqft', '>1500 Sqft'),
    ]
    purpose=models.CharField(max_length=10,choices=PURPOSE_CHOICES, blank=True, null=True)
    budget_min = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    budget_max = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    funding=models.CharField(max_length=20,choices=FUNDING_CHOICES, blank=True, null=True)
    area = models.CharField(max_length= 20, choices=AREA_CHOICES, blank=True, null=True)
    configuration=models.CharField(max_length=10,choices=CONFIGURATION_CHOICES, blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"ID: {self.id}"  
class Lead(models.Model):
    REQUIRED_FIELDS = ["name"]
    LEAD_STATUS=[
        ('New','New'),
        ('Hot','Hot'),
        ('Warm','Warm'),
        ('Cold','Cold'),
        ('Lost','Lost')
    ]
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Others', 'Others'),
    ]
    FAMILY_CHOICES = [
        ('1-2', '1-2'),
        ('3-4', '3-4'),
        ('More than 4', 'More than 4'),
    ]
    OCCUPATION_CHOICES = [
        ('Business', 'Business'),
        ('Service', 'Service'),
        ('Police or Army', 'Police or Army'),
    ]
    AGE_CHOICES = (
        ('25 - 30', '25 - 30'),
        ('31 - 35', '31 - 35'),
        ('36 - 40', '36 - 40'),
        ('41 - 45', '41 - 45'),
        ('46 - 50', '46 - 50'),
        ('51 - 55', '51 - 55'),
        ('56 - 60', '56 - 60'),
        ('>60', '>60'),
    )
    INCOME_CHOICES = (
        ('Upto 12 Lacs', 'Upto 12 Lacs'),
        ('12 - 18 Lacs', '12 - 18 Lacs'),
        ('18 - 25 Lacs', '18 - 25 Lacs'),
        ('25 - 30 Lacs', '25 - 30 Lacs'),
        ('> 30 Lacs', '> 30 Lacs'),
    )
    # LOST_REASON_CHOICES = (
    #     ('Not Interested' , 'Not Interested'),
    #     ('Budget Issue', 'Budget Issue'),
    #     ('Did Not Like the Property Options', 'Did Not Like the Property Options'),
    #     ('Mind Changed' , 'Mind Changed')
    # )
    first_name=models.CharField(max_length=100) # By default, blank=False and null=False
    last_name=models.CharField(max_length=100)
    primary_phone_no=models.CharField(max_length=10)
    secondary_phone_no=models.CharField(max_length=10,blank=True, null=True)
    primary_email=models.EmailField(max_length=255,blank=True, null=True)
    secondary_email=models.EmailField(max_length=255,null=True,blank=True)
    age = models.CharField(max_length=15, choices=AGE_CHOICES,null=True,blank=True)
    gender=models.CharField(max_length=15,choices=GENDER_CHOICES,null=True)
    lead_status=models.CharField(max_length=4,choices=LEAD_STATUS,default='New')
    # nationality = models.CharField(max_length=20,null=True,blank=True)
    address=models.CharField(max_length=255,blank=True, null=True)
    city=models.CharField(max_length=255,blank=True, null=True)
    state=models.CharField(max_length=255,blank=True, null=True)
    pincode=models.CharField(max_length=255,blank=True, null=True)
    office_location = models.CharField(max_length=100,null=True,blank=True)
    office_pincode = models.CharField(max_length=100,null=True,blank=True)
    annual_income = models.CharField(max_length=20, choices=INCOME_CHOICES,null=True,blank=True)
    occupation=models.CharField(max_length=255,choices= OCCUPATION_CHOICES, blank=True, null=True)
    #source=models.CharField(max_length=25,blank=True, null=True)
    source = models.ForeignKey(Source, on_delete=models.SET_NULL, null=True, blank=True)
    no_of_family=models.CharField(max_length=20,choices=FAMILY_CHOICES,blank=True, null=True) 
    created_on = models.DateTimeField(auto_now_add=True)
    creator = models.ForeignKey(Users, default=None, related_name="lead_creator", on_delete=models.CASCADE, null=True,blank=True)
    created_by = models.CharField(max_length=255,blank=True, null=True)
    converted_on = models.DateField(blank=True, null=True)
    followers = ArrayField(models.IntegerField(), default=list, blank=True)
    lead_requirement = models.OneToOneField(LeadRequirements, on_delete=models.CASCADE,null=True)
    is_important = models.BooleanField(default=False)
    #default_organinzation = Organization.objects.get_or_create(name='Enso')[0]
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, default=1, null=True)
    remarks =models.CharField(max_length=255,blank=True, null=True)
    lost_reason = models.CharField(max_length= 150, blank= True, null= True)
    creation_stage = models.CharField(max_length=255, null = True , blank=True, default="PreSales")
    # lost_reason_choices = models.CharField(max_length=150, choices=LOST_REASON_CHOICES, blank=True, null=True, verbose_name="Lost Reason Choice")
    channel_partner = models.ForeignKey(ChannelPartner, on_delete=models.SET_NULL, null=True, blank=True)
    #booking_form_signatures
    sh_signature = models.ImageField(upload_to='signatures/sh/', null=True, blank=True)
    co_owner1_signature = models.ImageField(upload_to='signatures/owner/',null=True,blank=True)
    co_owner2_signature = models.ImageField(upload_to='signatures/owner2/',null=True,blank=True)
    co_owner3_signature = models.ImageField(upload_to='signatures/owner3/',null=True,blank=True)
    co_owner4_signature = models.ImageField(upload_to='signatures/owner4/',null=True,blank=True)
    co_owner5_signature = models.ImageField(upload_to='signatures/owner5/',null=True,blank=True)
    customer_signature = models.ImageField(upload_to='signaures/customer/',null=True,blank=True)
    #signatures for the cost sheet
    client_signature = models.ImageField(upload_to='signatures/client/', null=True, blank=True)
    cm_signature = models.ImageField(upload_to='signatures/cm/', null=True, blank=True)
    vp_signature = models.ImageField(upload_to='signatures/vp/', null=True, blank=True)
    cost_sheet_co_owner_signature = models.ImageField(upload_to='signatures/co_owner/', null=True, blank=True)
    cost_sheet_co_owner2_signature = models.ImageField(upload_to='signatures/co_owner2/',null=True,blank=True)
    cost_sheet_co_owner3_signature = models.ImageField(upload_to='signatures/co_owner3/',null=True,blank=True)
    cost_sheet_co_owner4_signature = models.ImageField(upload_to='signatures/co_owner4/',null=True,blank=True)
    cost_sheet_co_owner5_signature = models.ImageField(upload_to='signatures/co_owner5/',null=True,blank=True)
    history = HistoricalRecords()

    class Meta:
        indexes = [
            models.Index(fields=['primary_phone_no']),
            models.Index(fields=['primary_email']),
        ]

    def current_stage(self):
        from workflow.models import Workflow
        lead_workflow =  Workflow.objects.filter(lead=self).first()
        if lead_workflow:
            current_stage = lead_workflow.stages.get(order=lead_workflow.current_stage)
            return current_stage.name
        return None
        
    def __str__(self):
        return F"{self.first_name} - ID: {self.id}"
    
    def get_channel_partner_choices(self):
        choices = [(None, 'None')]
        channel_partners = ChannelPartner.objects.all()
        choices += [(cp.id, cp.name) for cp in channel_partners]
        return choices

class Updates(models.Model):
    CHOICES = [
        ('Done', 'Done'),
        ('Not Done', 'Not Done')
    ]
    EMAIL_CHOICES = [
        ('Sent', 'Sent'),
        ('Not Sent', 'Not Sent')
    ]  
    lead = models.OneToOneField('lead.Lead', on_delete=models.CASCADE)
    welcome_call_status = models.CharField(max_length=50,choices=CHOICES, default='Not Done')
    welcome_email_status = models.CharField(max_length=50,choices=EMAIL_CHOICES, default='Not Sent')
    demand_letter_status = models.CharField(max_length=50,choices=EMAIL_CHOICES, default='Not Sent')
    snagging_email_status = models.CharField(max_length=50,choices=EMAIL_CHOICES, default='Not Sent')
    possession_due_email_status = models.CharField(max_length=50,choices=EMAIL_CHOICES, default='Not Sent')
    slab = models.ForeignKey('inventory.ProjectCostSheet',on_delete=models.SET_NULL,blank=True,null=True)
    history = HistoricalRecords()
    def __str__(self):
        return f" Welcome Section"
    
def upload_to_directory(instance, filename):
    lead_id = instance.lead_id if instance.lead_id else "unknown"
    return f'uploads/lead_{lead_id}/{filename}'


class MyS3Storage(S3Boto3Storage):
    location = settings.AWS_STORAGE_BUCKET_NAME  


   
class DocumentSection(models.Model):
    lead = models.ForeignKey('lead.Lead', on_delete=models.CASCADE)
    upload_docs = models.FileField(upload_to=upload_to_directory, blank=True, null=True, verbose_name='Upload Docs')
    #upload_docs = models.FileField(storage=MyS3Storage(), upload_to=upload_to_directory, blank=True, null=True, verbose_name='Upload Docs')
    doc_name = models.CharField(max_length=500,blank=True, null=True)
    doc_tag = models.CharField(max_length=100,blank=True, null=True)
    slug = models.CharField(max_length=100,blank=True, null=True)
    
    def __str__(self):
        return f"Document #{self.id} for Lead: {self.lead.first_name if self.lead else 'Unknown Lead'}"

class PostSalesDocumentType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    is_mandatory = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class PostSalesDocumentSection(models.Model):
    lead = models.ForeignKey('lead.Lead', on_delete=models.CASCADE)
    document_type = models.ForeignKey(PostSalesDocumentType, on_delete=models.CASCADE)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Post Sales Document #{self.id}, containing {self.document_type.name} - {self.file.name} for Lead: {self.lead.first_name if self.lead else 'Unknown Lead'}"


@receiver(pre_save, sender=Source)
def source_pre_save_handler(sender, instance, **kwargs):
    pass
    #print(f'Source instance {instance.id} about to be saved!')

@receiver(post_save, sender=Source)
def source_post_save_handler(sender, instance, created, **kwargs):
    if created:
        print(f'Source instance {instance.id} has been created!')
    else:
        print(f'Source instance {instance.id} has been updated!')


@receiver(pre_save, sender=ChannelPartner)
def channelpartner_pre_save_handler(sender, instance, **kwargs):
    pass
    #print(f'ChannelPartner instance {instance.id} about to be saved!')

@receiver(post_save, sender=ChannelPartner)
def channelpartner_post_save_handler(sender, instance, created, **kwargs):
    if created:
        print(f'ChannelPartner instance {instance.id} has been created!')
    else:
        print(f'ChannelPartner instance {instance.id} has been updated!')

@receiver(pre_save, sender=LeadRequirements)
def leadrequirements_pre_save_handler(sender, instance, **kwargs):
    pass
    #print(f'LeadRequirements instance {instance.id} about to be saved!')

@receiver(post_save, sender=LeadRequirements)
def leadrequirements_post_save_handler(sender, instance, created, **kwargs):
    if created:
        print(f'LeadRequirements instance {instance.id} has been created!')
    else:
        print(f'LeadRequirements instance {instance.id} has been updated!')

@receiver(pre_save, sender=Lead)
def lead_pre_save_handler(sender, instance, **kwargs):
    pass
    #print(f'Lead instance {instance.id} about to be saved!')

@receiver(post_save, sender=Lead)
def lead_post_save_handler(sender, instance, created, **kwargs):
    if created:
        print(f'Lead instance {instance.id} has been created!')
    else:
        print(f'Lead instance {instance.id} has been updated!')


@receiver(pre_save, sender=Updates)
def updates_pre_save_handler(sender, instance, **kwargs):
    pass
    #print(f'Updates instance {instance.id} about to be saved!')

@receiver(post_save, sender=Updates)
def updates_post_save_handler(sender, instance, created, **kwargs):
    if created:
        print(f'Updates instance {instance.id} has been created!')
    else:
        print(f'Updates instance {instance.id} has been updated!')


@receiver(pre_save, sender=DocumentSection)
def documentsection_pre_save_handler(sender, instance, **kwargs):
    pass
    #print(f'DocumentSection instance {instance.id} about to be saved!')


@receiver(post_save, sender=DocumentSection)
def documentsection_post_save_handler(sender, instance, created, **kwargs):

    if created:
        print(f'DocumentSection instance {instance.id} has been created!')
    else:
        print(f'DocumentSection instance {instance.id} has been updated!')


class ExportFile(models.Model):
    file = models.FileField(upload_to='exports/')
    created_at = models.DateTimeField(auto_now_add=True)


class NotificationCount(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    # user = models.ForeignKey(Users, on_delete=models.CASCADE)
    count = models.PositiveIntegerField(default=0)
    last_notified = models.DateTimeField(default=timezone.now)

    


# class BookingForm(models.Model):

#     FUNDING_CHOICES = [
#         ('loan', 'Banking loan'),
#         ('self fund', 'Self Funded'),
#     ]

#     MARITAL_STATUS= [
#         ('MARRIED', 'MARRIED'),
#         ('UNMARRIED', 'UNMARRIED'),
#     ]

#     CONFIGURATION_CHOICES = [
#         ('1BHK', '1BHK'),
#         ('1.5BHK', '1.5BHK'),
#         ('2BHK', '2BHK'),
#         ('3BHK', '3BHK'),
#         ('4BHK', '4BHK'),
#     ]
#     CORRESPONDANCE_CHOICES = [
#         ('Residence', 'Residence'),
#         ('Permanent', 'Permanent'),
#     ]
#     TOWER_CHOICES = [
#         ('Tower A', 'Tower A'),
#         ('Tower B', 'Tower B'),
#         ('Tower C', 'Tower C'),
#         ('Other', 'Other'),
#     ]
#     # Personal Information
#     lead_id = models.ForeignKey('lead.Lead', on_delete=models.CASCADE)
#     customer_name = models.CharField(max_length=100)
#     pan_no = models.CharField(max_length=20)
#     nationality = models.CharField(max_length=50)
    
#     # Contact Information
#     residence_address = models.TextField()
#     residence_phone_no = models.CharField(max_length=15)
#     permanent_address = models.TextField()
#     permanent_address_telephone_no = models.CharField(max_length=15)
#     correspondance_address = models.CharField(max_length=100, choices=CORRESPONDANCE_CHOICES, default='Residence')
#     # Professional Details
#     company_name = models.CharField(max_length=100)
#     designation = models.CharField(max_length=100)
#     company_address = models.TextField(null=True,blank=True)
#     telephone_no = models.CharField(max_length=15,null=True,blank=True)
#     extension = models.CharField(max_length=10,null=True,blank=True)
#     mobile_no = models.CharField(max_length=10)
#     fax = models.CharField(max_length=15,null=True,blank=True)
#     email_id = models.EmailField(max_length=255)
    
#     # Co-owner 1 Details
#     co_owner1_name = models.CharField(max_length=100,null=True,blank=True)
#     co_owner1_pan_no = models.CharField(max_length=10,null=True,blank=True)
#     co_owner1_nationality = models.CharField(max_length=50,null=True,blank=True)
#     relation_with_customer1 = models.CharField(max_length=100,null=True,blank=True)
    
#     # Co-owner 1 Professional Details
#     co_owner1_company_name = models.CharField(max_length=100,null=True,blank=True)
#     co_owner1_designation = models.CharField(max_length=100,null=True,blank=True)
#     co_owner1_company_address = models.TextField(null=True,blank=True)
#     co_owner1_telephone_no = models.CharField(max_length=10,null=True,blank=True)
#     co_owner1_extension = models.CharField(max_length=10,null=True,blank=True)
#     co_owner1_mobile_no = models.CharField(max_length=10,null=True,blank=True)
#     co_owner1_fax = models.CharField(max_length=15,null=True,blank=True)
#     co_owner1_email_id = models.EmailField(null=True,blank=True)

#     # Co-owner 2 Details
#     co_owner2_name = models.CharField(max_length=100,null=True,blank=True)
#     co_owner2_pan_no = models.CharField(max_length=20,null=True,blank=True)
#     co_owner2_nationality = models.CharField(max_length=50,null=True,blank=True)
#     relation_with_customer2 = models.CharField(max_length=100,null=True,blank=True)
    
#     # Co-owner 2 Professional Details
#     co_owner2_company_name = models.CharField(max_length=100,null=True,blank=True)
#     co_owner2_designation = models.CharField(max_length=100,null=True,blank=True)
#     co_owner2_company_address = models.TextField(null=True,blank=True)
#     co_owner2_telephone_no = models.CharField(max_length=10,null=True,blank=True)
#     co_owner2_extension = models.CharField(max_length=10,null=True,blank=True)
#     co_owner2_mobile_no = models.CharField(max_length=10,null=True,blank=True)
#     co_owner2_fax = models.CharField(max_length=15,null=True,blank=True)
#     co_owner2_email_id = models.EmailField(null=True,blank=True)
    
#     # Personal Details
#     marital_status = models.CharField(max_length=20,choices=MARITAL_STATUS)
#     date_of_anniversary = models.DateField(null=True,blank=True)
#     family_configuration = models.TextField()
    
#     # Apartment Details
#     apartment_type =  models.CharField(max_length=10, choices=CONFIGURATION_CHOICES, default='1BHK')
#     tower = models.CharField(max_length=20, choices=TOWER_CHOICES, default='Tower A')
#     project = models.ForeignKey('Project', on_delete=models.CASCADE)
#     apartment_no = models.CharField(max_length=20)
#     floor = models.IntegerField()
#     date_of_booking = models.DateField(default=date.today)
#     booking_source = models.CharField(max_length=100)
#     sub_source = models.CharField(max_length=100)
#     source_of_finance = models.CharField(max_length=10,choices=FUNDING_CHOICES, default='loan')
#     sales_manager_name = models.ForeignKey('myauth.Users', on_delete=models.CASCADE)

#     #contact person
#     contact_person_name= models.CharField(max_length=100)
#     contact_person_number = models.CharField(max_length=10)
#     signatature = models.CharField(max_length=100,null=True,blank=True)
#     history = HistoricalRecords()
        
#     class Meta:
#         unique_together = ("lead_id", "apartment_type", "tower", "apartment_no", "floor", "project")

#     def validate_co_owners(self):
#         co_owner1_fields = [
#             'co_owner1_name',
#             'co_owner1_pan_no',
#             'co_owner1_nationality',
#             'relation_with_customer1',
#             'co_owner1_company_name',
#             'co_owner1_designation',
#             'co_owner1_mobile_no',
#             'co_owner1_email_id',
#         ]
#         co_owner2_fields = [
#             'co_owner2_name',
#             'co_owner2_pan_no',
#             'co_owner2_nationality',
#             'relation_with_customer2',
#             'co_owner2_company_name',
#             'co_owner2_designation',
#             'co_owner2_mobile_no',
#             'co_owner2_email_id',
#         ]

#         co_owner1_provided = all(getattr(self, field, None) for field in co_owner1_fields)
#         co_owner2_provided = all(getattr(self, field, None) for field in co_owner2_fields)
#         print(co_owner1_fields)
#         print(co_owner2_fields)
#         if co_owner1_provided or co_owner2_provided:
#             return True
#         return False

#     def save(self, *args, **kwargs):
#         # Check if co_owner fields are provided and valid
#         # if self.validate_co_owners():
#         super(BookingForm, self).save(*args, **kwargs)
#         # else:
#         #     # Handle the case when the required fields are missing or invalid
#         #     raise Exception("Required co-owner fields are missing or invalid")

#     def __str__(self):
#         return self.customer_name
    
# @receiver(pre_save, sender=BookingForm)
# def booking_form_pre_save_handler(sender, instance, **kwargs):
#     pass


# @receiver(post_save, sender=BookingForm)
# def booking_form_post_save_handler(sender, instance, created, **kwargs):
#     if created:
#         print(f'BookingForm instance {instance.id} has been created!')
#     else:
#         print(f'BookingForm instance {instance.id} has been updated!')




# class Project(models.Model):
#     name = models.CharField(max_length=100)

#     def __str__(self):
#         return self.name

# @receiver(pre_save, sender=Project)
# def project_pre_save_handler(sender, instance, **kwargs):
#     pass

# @receiver(post_save, sender=Project)
# def project_post_save_handler(sender, instance, created, **kwargs):

#     if created:
#         print(f'Project instance {instance.id} has been created!')
#     else:
#         print(f'Project instance {instance.id} has been updated!')




# class CollectToken(models.Model):
#     OCCUPATION_CHOICES = [
#         ('Employed', 'Employed'),
#         ('Self-Employed', 'Self-Employed'),
#         ('Business Owner', 'Business Owner'),
#         ('Other', 'Other'),
#     ]

#     TOWER_CHOICES = [
#         ('Tower A', 'Tower A'),
#         ('Tower B', 'Tower B'),
#         ('Tower C', 'Tower C'),
#         ('Other', 'Other'),
#     ]

#     AREA_CHOICES = [
#         ('<1000 sqft', '<1000 sqft'),
#         ('1000-1500 sqft', '1000-1500 sqft'),
#         ('>1500 sqft', '>1500 sqft'),
#     ]

#     CONFIGURATION_CHOICES = [
#         ('1BHK', '1BHK'),
#         ('1.5BHK', '1.5BHK'),
#         ('2BHK', '2BHK'),
#         ('3BHK', '3BHK'),
#         ('4BHK', '4BHK'),
#     ]

#     name = models.CharField(max_length=100)
#     occupation = models.CharField(max_length=20, choices=OCCUPATION_CHOICES)
#     configuration = models.CharField(max_length=10, choices=CONFIGURATION_CHOICES)
#     area = models.CharField(max_length=15, choices=AREA_CHOICES)
#     project = models.ForeignKey('Project', on_delete=models.CASCADE)
#     apartment_no = models.CharField(max_length=20)
#     tower = models.CharField(max_length=20, choices=TOWER_CHOICES)
#     pre_deal_amount = models.DecimalField(max_digits=10, decimal_places=2)
#     deal_amount = models.DecimalField(max_digits=10, decimal_places=2)
#     percentage_of_token_amount = models.DecimalField(max_digits=5, decimal_places=2)
#     token_amount = models.DecimalField(max_digits=10, decimal_places=2)
#     payment_link = models.URLField(max_length=200)
#     lead_id = models.ForeignKey('lead.Lead', on_delete=models.CASCADE)
#     history = HistoricalRecords()

#     class Meta:
#         unique_together = ("lead_id", "configuration" , "tower", "apartment_no", "project")

#     def __str__(self):
#         return self.name

#     def save(self, *args, **kwargs):

#         try:
#             booking_form = BookingForm.objects.get(customer_name=self.name)

#             self.occupation = booking_form.designation 
#             self.configuration = booking_form.apartment_type
#             self.tower = booking_form.tower


#         except BookingForm.DoesNotExist:
#             pass  
#         super(CollectToken, self).save(*args, **kwargs)


# @receiver(pre_save, sender=CollectToken)
# def collect_token_pre_save_handler(sender, instance, **kwargs):
#     pass


# @receiver(post_save, sender=CollectToken)
# def collect_token_post_save_handler(sender, instance, created, **kwargs):
  
#     if created:
#         print(f'CollectToken instance {instance.id} has been created!')
#     else:
#         print(f'CollectToken instance {instance.id} has been updated!')



# def upload_to_directory(instance, filename):
#     lead_id = instance.lead_id if instance.lead_id else "unknown"
#     return f'uploads/lead_{lead_id}/{filename}'

# class Inventory(models.Model):
#     STATUS_CHOICES = [
#         ('Yet to book', 'Yet to book'),
#         ('Booked', 'Booked'),
#         ('EOI', 'EOI'),
#         ('Risk', 'Risk'),
#         ('Hold Refuge', 'Hold Refuge'),
#     ]

#     project = models.ForeignKey('Project', on_delete=models.CASCADE)
#     wings = models.CharField(max_length=50, blank=True, null=True)
#     towers = models.CharField(max_length=50, blank=True, null=True)
#     configuration = models.CharField(max_length=10)
#     apartment_no = models.CharField(max_length=20)
#     floor_number = models.IntegerField()
#     pre_deal_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
#     min_deal_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
#     deal_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Yet to book')
#     lead = models.ForeignKey('lead.Lead', on_delete=models.CASCADE, blank=True, null=True)
#     history = HistoricalRecords()

#     class Meta:
#         unique_together = ( "project", "configuration" , "towers", "apartment_no")

#     def __str__(self):
#         return f"{self.project} - Apt {self.apartment_no}"

#     def save(self, *args, **kwargs):
#         # Check if the Project already exists or create a new one
#         project, created = Project.objects.get_or_create(name=self.project)
#         super(Inventory, self).save(*args, **kwargs)


# @receiver(pre_save, sender=Inventory)
# def inventory_pre_save_handler(sender, instance, **kwargs):
#     pass


# @receiver(post_save, sender=Inventory)
# def inventory_post_save_handler(sender, instance, created, **kwargs):

#     if created:
#         print(f'Inventory instance {instance.id} has been created!')
#     else:
#         print(f'Inventory instance {instance.id} has been updated!')

# pre_save.connect(booking_form_pre_save_handler, sender=BookingForm)
# post_save.connect(booking_form_post_save_handler, sender=BookingForm)
# pre_save.connect(project_pre_save_handler, sender=Project)
# post_save.connect(project_post_save_handler, sender=Project)
# pre_save.connect(collect_token_pre_save_handler, sender=CollectToken)
# post_save.connect(collect_token_post_save_handler, sender=CollectToken)
# pre_save.connect(inventory_pre_save_handler, sender=Inventory)
# post_save.connect(inventory_post_save_handler, sender=Inventory)

pre_save.connect(source_pre_save_handler, sender=Source)
post_save.connect(source_post_save_handler, sender=Source)
pre_save.connect(channelpartner_pre_save_handler, sender=ChannelPartner)
post_save.connect(channelpartner_post_save_handler, sender=ChannelPartner)
pre_save.connect(leadrequirements_pre_save_handler, sender=LeadRequirements)
post_save.connect(leadrequirements_post_save_handler, sender=LeadRequirements)
# pre_save.connect(lead_pre_save_handler, sender=Lead)
post_save.connect(lead_post_save_handler, sender=Lead)
pre_save.connect(updates_pre_save_handler, sender=Updates)
post_save.connect(updates_post_save_handler, sender=Updates)
pre_save.connect(documentsection_pre_save_handler, sender=DocumentSection)
post_save.connect(documentsection_post_save_handler, sender=DocumentSection)