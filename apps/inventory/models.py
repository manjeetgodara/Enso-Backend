from django.db import models
from datetime import date
from simple_history.models import HistoricalRecords
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.postgres.fields import ArrayField
from django.db.models.signals import pre_save, post_save
from django.utils import timezone
from auth.models import Users
from comms.utils import send_push_notification
from workflow.models import Notifications
from .utils import generate_form_pdf
from django.utils.timezone import now

# class Slab(models.Model):
#     name = models.CharField(max_length=255)
#     start_date = models.DateTimeField(null=True, blank=True)
#     end_date = models.DateTimeField(null=True, blank=True)
#     completed = models.BooleanField(default=False)
#     completed_at = models.DateTimeField(null=True, blank=True)


class PropertyType(models.Model):
    name = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name

class ProjectDetail(models.Model):
    area_choices = [
        ('<1000', 'Less than 1000 acres'),
        ('1000-1500', '1000-1500 acres'),
        ('>1500', 'More than 1500 acres'),
    ]

    project_type_choices = [
        ('Commercial', 'Commercial'),
        ('Personal', 'Personal'),
        ('Mixed', 'Mixed'),
    ]

    # property_type_choices = [
    #     ('Flats', 'Flats'),
    #     ('Bungalows', 'Bungalows'),
    #     ('Villas', 'Villas'),
    # ]

    name = models.CharField(max_length=255)
    description = models.TextField()
    rera_number = models.CharField(max_length=20)
    area = models.CharField(max_length=10, choices=area_choices)
    project_type = models.CharField(max_length=20, choices=project_type_choices)
    properties_type = models.ManyToManyField(PropertyType)
    total_towers = models.IntegerField()
    total_units = models.IntegerField()
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    pincode = models.CharField(max_length=10)
    current_event_order = models.IntegerField(default=3)

    def __str__(self):
        return self.name

class ProjectTower(models.Model):
    project = models.ForeignKey(ProjectDetail, on_delete=models.CASCADE)
    name = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.name} - {self.project}"
        
    class Meta:
        unique_together = ('name', 'project')
# class Tower(models.Model):
#     wing = models.ForeignKey(ProjectWing, on_delete=models.CASCADE)
#     name = models.CharField(max_length=10)

#     def __str__(self):
#         return f"{self.name} - {self.wing}"

class Configuration(models.Model):
    name = models.CharField(max_length=50,unique=True)

    def __str__(self):
        return self.name

class SalesActivity(models.Model):
    history_date = models.DateTimeField(blank=True,null=True)
    history_type = models.CharField(max_length=255,blank=True,null=True)
    history_user = models.CharField(max_length=255,blank=True,null=True)
    sent_to = models.CharField(max_length=255,blank=True,null=True)
    message = models.TextField(blank=True,null=True)
    activity_type = models.CharField(max_length=255,blank=True,null=True)
    lead = models.ForeignKey('lead.Lead', on_delete=models.CASCADE, blank=True, null=True)
    def __str__(self):
        return f"{self.activity_type} - {self.history_user} - {self.history_date}"

class ProjectInventory(models.Model):
    STATUS_CHOICES = [
        ('Yet to book', 'Yet to book'),
        ('Booked', 'Booked'),
        ('EOI', 'EOI'),
        ('Risk', 'Risk'),
        ('Hold Refuge', 'Hold Refuge'),
    ]

    project_inventory_type_choices = [
        ('flat', 'Flat'),
        ('bunglow', 'Bunglow'),
        ('villa', 'Villa'),
        ('commercial', 'Commercial'),
    ]

    # AREA_CHOICES=[
    #     ('<1000 Sqft', '<1000 Sqft'),
    #     ('1000-1500 Sqft', '1000-1500 Sqft'),
    #     ('>1500 Sqft', '<1500 Sqft')
    # ]
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

    tower = models.ForeignKey(ProjectTower,on_delete=models.CASCADE,blank=True,null=True)
    #tower = models.CharField(max_length=20,blank=True,null=True)
    configuration = models.ForeignKey(Configuration,on_delete=models.SET_NULL,blank=True,null=True)
    flat_no = models.CharField(max_length=50, blank=True, null=True)
    apartment_no = models.CharField(max_length=50, blank=True, null=True)
    car_parking = models.CharField(max_length=50, blank=True, null=True, default=0)
    amount_per_car_parking = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    floor_number = models.IntegerField()
    area = models.CharField(max_length=50, choices=AREA_CHOICES, default='<1000 Sqft')
    exact_area = models.IntegerField(blank=True, null=True, default=0)
    no_of_bathrooms = models.IntegerField()
    no_of_bedrooms = models.IntegerField()
    no_of_balcony = models.IntegerField()
    vastu_details = models.TextField(blank=True, null=True)
    pre_deal_amount = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    min_deal_amount_cm = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    min_deal_amount_sh= models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    min_deal_amount_vp = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    token_amount = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    token_percentage = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    # cost_of_flat = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    # other_charges = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='Yet to book')
    # project_inventory_type = models.CharField(max_length=20, choices=project_inventory_type_choices)
    #project = models.ForeignKey(ProjectDetail, on_delete=models.CASCADE, blank=True, null=True)
    project_inventory_type = models.ForeignKey(PropertyType,on_delete=models.SET_NULL, blank=True, null=True)
    lead = models.ForeignKey('lead.Lead', on_delete=models.SET_NULL, blank=True, null=True)
    in_progress = models.BooleanField(default=False)
    booked_on = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=now,null=True,blank=True)

    # Add other flat details as needed
    @property
    def tower_display(self):
        return self.tower.name if self.tower else ''

    @property
    def project_display(self):
        return self.tower.project.name if self.tower else ''

    def __str__(self):
        return f"{self.configuration} - {self.flat_no} in Tower {self.tower.name}, Project {self.tower.project.name}"
    
    def save(self, *args, **kwargs):
        if self.status == 'Booked' and not self.booked_on:
            self.booked_on = timezone.now() 
        if self.flat_no and self.tower and not self.apartment_no:
            self.apartment_no = f"{self.tower.name}{self.flat_no}"
        super(ProjectInventory, self).save(*args, **kwargs)



class BookingForm(models.Model):

    FUNDING_CHOICES = [
        ('loan', 'Banking loan'),
        ('self fund', 'Self Funded'),
    ]

    MARITAL_STATUS= [
        ('Unmarried', 'UNMARRIED'),
        ('Married', 'MARRIED'),
        ('Widowed', 'WIDOWED'),
        ('Divorced', 'DIVORCED'),
    ]

    CORRESPONDANCE_CHOICES = [
        ('Residence', 'Residence'),
        ('Permanent', 'Permanent'),
    ]
    
    # Personal Information
    lead_id = models.ForeignKey('lead.Lead', on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=100)
    pan_no = models.CharField(max_length=20)
    aadhaar_details = models.CharField(max_length=20, blank=True, null=True)
    nationality = models.CharField(max_length=50)
    dob =models.DateField(null=True,blank=True)
    
    # Contact Information
    residence_address = models.TextField()
    residence_phone_no = models.CharField(max_length=15,null=True,blank=True)
    permanent_address = models.TextField()
    permanent_address_telephone_no = models.CharField(max_length=15,null=True,blank=True)
    correspondance_address = models.CharField(max_length=30, choices=CORRESPONDANCE_CHOICES, default='Residence')
    # Professional Details
    company_name = models.CharField(max_length=100,null=True,blank=True)
    designation = models.CharField(max_length=100,null=True,blank=True)
    company_address = models.TextField(null=True,blank=True)
    telephone_no = models.CharField(max_length=15,null=True,blank=True)
    # extension = models.CharField(max_length=10,null=True,blank=True)
    mobile_no = models.CharField(max_length=10,null=True,blank=True)
    fax = models.CharField(max_length=15,null=True,blank=True)
    email_id = models.EmailField(max_length=255,null=True,blank=True)
    personal_email_id = models.EmailField(max_length=255,null=True,blank=True)
    
    # Co-owner 1 Details
    co_owner1_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner1_pan_no = models.CharField(max_length=10,null=True,blank=True)
    co_owner1_nationality = models.CharField(max_length=50,null=True,blank=True)
    relation_with_customer1 = models.CharField(max_length=100,null=True,blank=True)
    
    # Co-owner 1 Professional Details
    co_owner1_company_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner1_designation = models.CharField(max_length=100,null=True,blank=True)
    co_owner1_company_address = models.TextField(null=True,blank=True)
    co_owner1_telephone_no = models.CharField(max_length=10,null=True,blank=True)
    # co_owner1_extension = models.CharField(max_length=10,null=True,blank=True)
    co_owner1_mobile_no = models.CharField(max_length=10,null=True,blank=True)
    co_owner1_fax = models.CharField(max_length=15,null=True,blank=True)
    co_owner1_email_id = models.EmailField(null=True,blank=True)

    # Co-owner 2 Details
    co_owner2_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner2_pan_no = models.CharField(max_length=20,null=True,blank=True)
    co_owner2_nationality = models.CharField(max_length=50,null=True,blank=True)
    relation_with_customer2 = models.CharField(max_length=100,null=True,blank=True)
    
    # Co-owner 2 Professional Details
    co_owner2_company_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner2_designation = models.CharField(max_length=100,null=True,blank=True)
    co_owner2_company_address = models.TextField(null=True,blank=True)
    co_owner2_telephone_no = models.CharField(max_length=10,null=True,blank=True)
    # co_owner2_extension = models.CharField(max_length=10,null=True,blank=True)
    co_owner2_mobile_no = models.CharField(max_length=10,null=True,blank=True)
    co_owner2_fax = models.CharField(max_length=15,null=True,blank=True)
    co_owner2_email_id = models.EmailField(null=True,blank=True)
    
    #Co-owner 3 Details
    co_owner3_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner3_pan_no = models.CharField(max_length=10,null=True,blank=True)
    co_owner3_nationality = models.CharField(max_length=50,null=True,blank=True)
    relation_with_customer3 = models.CharField(max_length=100,null=True,blank=True)
    
    # Co-owner 3 Professional Details
    co_owner3_company_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner3_designation = models.CharField(max_length=100,null=True,blank=True)
    co_owner3_company_address = models.TextField(null=True,blank=True)
    co_owner3_telephone_no = models.CharField(max_length=10,null=True,blank=True)
    # co_owner3_extension = models.CharField(max_length=10,null=True,blank=True)
    co_owner3_mobile_no = models.CharField(max_length=10,null=True,blank=True)
    co_owner3_fax = models.CharField(max_length=15,null=True,blank=True)
    co_owner3_email_id = models.EmailField(null=True,blank=True)
    
    #Co-owner 4 Details
    co_owner4_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner4_pan_no = models.CharField(max_length=10,null=True,blank=True)
    co_owner4_nationality = models.CharField(max_length=50,null=True,blank=True)
    relation_with_customer4 = models.CharField(max_length=100,null=True,blank=True)
    
    # Co-owner 4 Professional Details
    co_owner4_company_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner4_designation = models.CharField(max_length=100,null=True,blank=True)
    co_owner4_company_address = models.TextField(null=True,blank=True)
    co_owner4_telephone_no = models.CharField(max_length=10,null=True,blank=True)
    # co_owner4_extension = models.CharField(max_length=10,null=True,blank=True)
    co_owner4_mobile_no = models.CharField(max_length=10,null=True,blank=True)
    co_owner4_fax = models.CharField(max_length=15,null=True,blank=True)
    co_owner4_email_id = models.EmailField(null=True,blank=True)
    
    #Co-owner 5 Details
    co_owner5_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner5_pan_no = models.CharField(max_length=10,null=True,blank=True)
    co_owner5_nationality = models.CharField(max_length=50,null=True,blank=True)
    relation_with_customer5 = models.CharField(max_length=100,null=True,blank=True)
    
    # Co-owner 5 Professional Details
    co_owner5_company_name = models.CharField(max_length=100,null=True,blank=True)
    co_owner5_designation = models.CharField(max_length=100,null=True,blank=True)
    co_owner5_company_address = models.TextField(null=True,blank=True)
    co_owner5_telephone_no = models.CharField(max_length=10,null=True,blank=True)
    # co_owner5_extension = models.CharField(max_length=10,null=True,blank=True)
    co_owner5_mobile_no = models.CharField(max_length=10,null=True,blank=True)
    co_owner5_fax = models.CharField(max_length=15,null=True,blank=True)
    co_owner5_email_id = models.EmailField(null=True,blank=True)
    
    # Personal Details
    marital_status = models.CharField(max_length=20,choices=MARITAL_STATUS)
    date_of_anniversary = models.DateField(null=True,blank=True)
    family_configuration = models.TextField(null=True,blank=True)

    #guardian_details
    guardian_name = models.CharField(max_length=100,null=True,blank=True) 
    guardian_dob =models.DateField(null=True,blank=True)
    guardian_relationship= models.CharField(max_length=20,null=True)

    #remarks
    remarks = models.CharField(max_length=100,null=True,blank=True)
    
    # Apartment Details
    configuration = models.ForeignKey(Configuration,on_delete=models.SET_NULL,blank=True,null=True)
    tower = models.ForeignKey(ProjectTower, on_delete=models.CASCADE , blank=True, null=True)
    project = models.ForeignKey(ProjectDetail, on_delete=models.CASCADE, blank=True, null=True)
    apartment_no = models.CharField(max_length=50)
    floor = models.IntegerField()
    date_of_booking = models.DateField(default=date.today)
    booking_source = models.CharField(max_length=100)
    sub_source = models.CharField(max_length=100,null=True,blank=True)
    source_of_finance = models.CharField(max_length=10,null=True,blank=True)
    sales_manager_name = models.ForeignKey('myauth.Users', on_delete=models.CASCADE, blank=True, null=True)

    #contact person
    contact_person_name= models.CharField(max_length=100)
    contact_person_number = models.CharField(max_length=10)
    contact_person_email= models.CharField(max_length=100,null=True,blank=True)

    #Referrals
    referral1_name = models.CharField(max_length=100,null=True,blank=True) 
    referral1_phone_number =models.CharField(max_length=10,null=True,blank=True)

    referral2_name = models.CharField(max_length=100,null=True,blank=True) 
    referral2_phone_number =models.CharField(max_length=10,null=True,blank=True)

    referral3_name = models.CharField(max_length=100,null=True,blank=True) 
    referral3_phone_number =models.CharField(max_length=15,null=True,blank=True)

    # Signature fields
    # client_signature = models.ImageField(upload_to='signatures/client/', null=True, blank=True)
    # cm_signature = models.ImageField(upload_to='signatures/cm/', null=True, blank=True)
    # vp_signature = models.ImageField(upload_to='signatures/vp/', null=True, blank=True)
    # co_owner_signature = models.ImageField(upload_to='signatures/co_owner/', null=True, blank=True)
    # co_owner2_signature = models.ImageField(upload_to='signatures/co_owner2/',null=True,blank=True)
    # co_owner3_signature = models.ImageField(upload_to='signatures/co_owner3/',null=True,blank=True)
    # co_owner4_signature = models.ImageField(upload_to='signatures/co_owner4/',null=True,blank=True)
    # co_owner5_signature = models.ImageField(upload_to='signatures/co_owner5/',null=True,blank=True)
    history = HistoricalRecords()
        
    class Meta:
        unique_together = ("lead_id", "configuration", "apartment_no", "floor", "project")

    def validate_co_owners(self):
        co_owner1_fields = [
            'co_owner1_name',
            'co_owner1_pan_no',
            'co_owner1_nationality',
            'relation_with_customer1',
            'co_owner1_company_name',
            'co_owner1_designation',
            'co_owner1_mobile_no',
            'co_owner1_email_id',
        ]
        co_owner2_fields = [
            'co_owner2_name',
            'co_owner2_pan_no',
            'co_owner2_nationality',
            'relation_with_customer2',
            'co_owner2_company_name',
            'co_owner2_designation',
            'co_owner2_mobile_no',
            'co_owner2_email_id',
        ]
        co_owner3_fields = [
            'co_owner3_name',
            'co_owner3_pan_no',
            'co_owner3_nationality',
            'relation_with_customer3',
            'co_owner3_company_name',
            'co_owner3_designation',
            'co_owner3_mobile_no',
            'co_owner3_email_id',
        ]
        co_owner4_fields = [
            'co_owner4_name',
            'co_owner4_pan_no',
            'co_owner4_nationality',
            'relation_with_customer4',
            'co_owner4_company_name',
            'co_owner4_designation',
            'co_owner4_mobile_no',
            'co_owner4_email_id',
        ]
        co_owner5_fields = [
            'co_owner5_name',
            'co_owner5_pan_no',
            'co_owner5_nationality',
            'relation_with_customer5',
            'co_owner5_company_name',
            'co_owner5_designation',
            'co_owner5_mobile_no',
            'co_owner5_email_id',
        ]

        co_owner1_provided = all(getattr(self, field, None) for field in co_owner1_fields)
        co_owner2_provided = all(getattr(self, field, None) for field in co_owner2_fields)
        co_owner3_provided = all(getattr(self, field, None) for field in co_owner3_fields)
        co_owner4_provided = all(getattr(self, field, None) for field in co_owner4_fields)
        co_owner5_provided = all(getattr(self, field, None) for field in co_owner5_fields)
        print(co_owner1_fields)
        print(co_owner2_fields)
        if co_owner1_provided or co_owner2_provided or co_owner3_provided or co_owner4_provided or co_owner5_provided:
            return True
        return False

    def save(self, *args, **kwargs):
        # Check if co_owner fields are provided and valid
        # if self.validate_co_owners():
        super(BookingForm, self).save(*args, **kwargs)
        # else:
        #     # Handle the case when the required fields are missing or invalid
        #     raise Exception("Required co-owner fields are missing or invalid")

    def __str__(self):
        return self.customer_name
    

@receiver(post_save, sender=BookingForm)
def generate_cost_sheet_pdf_on_save(sender, instance, created, **kwargs):

    generate_form_pdf(lead_id=instance.lead_id.id, booking_form_param=True)


# @receiver(post_save, sender=BookingForm)
# def create_property_owner_and_inventory_cost_sheets(sender, instance, created, **kwargs):
#     if created:
#         # Create PropertyOwner
#         property_instance = ProjectInventory.objects.get(apartment_no=instance.apartment_no,tower=instance.tower)
#         print('property_instance:', property_instance)
#         property_instance.lead=instance.lead_id
#         property_instance.save()

#         current_event_order = property_instance.tower.project.current_event_order
#         print('current_event_order:', current_event_order)

#         property_owner, created = PropertyOwner.objects.get_or_create(
#             lead=instance.lead_id,
#             property=property_instance
#         )

#         # Create InventoryCostSheet events based on ProjectCostSheet
#         project_cost_sheets = ProjectCostSheet.objects.filter(project=property_instance.tower.project)

#         for project_cost_sheet in project_cost_sheets:
#             if project_cost_sheet.event_order <= 2 or project_cost_sheet.event_order >= current_event_order:
#                 print('project_cost_sheet:', project_cost_sheet.payment_type)
#                 if project_cost_sheet.payment_type == "Registration Fees":
#                     print('project_cost_sheet:', project_cost_sheet)
#                     InventoryCostSheet.objects.create(
#                         inventory=property_instance,
#                         event_order=project_cost_sheet.event_order,
#                         event=project_cost_sheet.event,
#                         completed=False,
#                         payment_type=project_cost_sheet.payment_type,
#                         payment_in_percentage=project_cost_sheet.payment_in_percentage,
#                         amount=project_cost_sheet.amount
#                     )
#                 else:
#                     InventoryCostSheet.objects.create(
#                         inventory=property_instance,
#                         event_order=project_cost_sheet.event_order,
#                         event=project_cost_sheet.event,
#                         completed=False,
#                         payment_type=project_cost_sheet.payment_type,
#                         payment_in_percentage=project_cost_sheet.payment_in_percentage
#                     )

#         collect_token_event = InventoryCostSheet.objects.filter(inventory__lead__id=instance.lead_id.id, event_order = 0)
#         print('collect_token_event:', collect_token_event)
#         if not collect_token_event:
#             print('here')
#             InventoryCostSheet.objects.create(
#                 inventory=property_instance,
#                 event_order=0,
#                 event="Token amount of initial payment",
#                 completed=False,
#                 payment_type="Token"
#             )

    
class ProjectCostSheet(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ("Installment", "Installment"),
        ("Registration Fees", "Registration Fees"),
        ("Stamp Duty", "Stamp Duty"),
        ("Token", "Token")
    ]

    EVENT_STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Done", "Done")
    ]

    project = models.ForeignKey(ProjectDetail, on_delete=models.CASCADE)
    event_order = models.PositiveIntegerField()
    event = models.CharField(max_length=1000)
    amount = models.IntegerField(blank=True, null=True)
    payment_in_percentage = models.IntegerField(default=0)
    # started = models.BooleanField(default=False)
    # started_at = models.DateTimeField(null=True, blank=True)
    # completed = models.BooleanField(default=False)
    event_status = models.CharField(max_length=50, choices=EVENT_STATUS_CHOICES,default="Pending")
    completed_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    # delayed_reason = models.TextField(null=True, blank=True)
    payment_type = models.CharField(max_length=50, choices=PAYMENT_TYPE_CHOICES,default="Installment")
    delayed_reasons  = ArrayField(models.CharField(max_length=150), default=list, null=True, blank=True) 
    architect_certificate = models.FileField(upload_to='documents/architect_certificates/', null=True, blank=True)
    site_image = models.ImageField(upload_to='documents/site_images/', null=True, blank=True)

    def __str__(self):
        return f"{self.project.name} - Event Order {self.event_order}: {self.event}"
    
    def save(self, *args, **kwargs):
        if self.event_status=='Done':
            project = self.project
            if self.event_order >= 3:
                project.current_event_order = self.event_order
                project.save()
        super(ProjectCostSheet, self).save(*args, **kwargs)
    
@receiver(pre_save, sender=ProjectCostSheet)
def track_field_changes(sender, instance, **kwargs):
    try:
        original_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return  
    print("Orignial instance: ", original_instance.event_status)

    if original_instance.event_status != instance.event_status and instance.event_status == "Done":

        vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
        promoter_users = Users.objects.filter(groups__name="PROMOTER")[:3]
        sitehead_user = Users.objects.filter(groups__name="SITE_HEAD").first()

        title = f"{instance.event} slab has been completed."
        body = f"{instance.event} slab has been completed."
        data = {'notification_type': 'event_slab'}

        if vp_user:
            fcm_token_vp = vp_user.fcm_token
            Notifications.objects.create(notification_id=f"Event-{instance.event_order}-{vp_user.id}", user_id=vp_user,created=timezone.now(), notification_message=body, notification_url='')
            send_push_notification(fcm_token_vp, title, body, data)

        for promoter_user in promoter_users:
            if promoter_user:
                fcm_token_promoter = promoter_user.fcm_token
                Notifications.objects.create(notification_id=f"Event-{instance.event_order}-{promoter_user.id}", user_id=promoter_user,created=timezone.now(),  notification_message=body, notification_url='')
                send_push_notification(fcm_token_promoter, title, body, data)

        if sitehead_user:
            fcm_token_vp = vp_user.fcm_token
            Notifications.objects.create(notification_id=f"Event-{instance.event_order}-{vp_user.id}", user_id=vp_user,created=timezone.now(), notification_message=body, notification_url='')
            send_push_notification(fcm_token_vp, title, body, data)
        
    if original_instance.delayed_reasons != instance.delayed_reasons and instance.event_status == "Pending":

        vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
        promoter_users = Users.objects.filter(groups__name="PROMOTER")[:3]
        sitehead_user = Users.objects.filter(groups__name="SITE_HEAD").first()

        title = f"{instance.event} slab has been Delayed."
        body = f"{instance.event} slab has been Delayed."
        data = {'notification_type': 'event_slab'}

        if vp_user:
            fcm_token_vp = vp_user.fcm_token
            Notifications.objects.create(notification_id=f"Event-{instance.event_order}-{vp_user.id}", user_id=vp_user,created=timezone.now(), notification_message=body, notification_url='')
            send_push_notification(fcm_token_vp, title, body, data)

        for promoter_user in promoter_users:
            if promoter_user:
                fcm_token_promoter = promoter_user.fcm_token
                Notifications.objects.create(notification_id=f"Event-{instance.event_order}-{promoter_user.id}", user_id=promoter_user,created=timezone.now(),  notification_message=body, notification_url='')
                send_push_notification(fcm_token_promoter, title, body, data)

        if sitehead_user:
            fcm_token_vp = vp_user.fcm_token
            Notifications.objects.create(notification_id=f"Event-{instance.event_order}-{vp_user.id}", user_id=vp_user,created=timezone.now(), notification_message=body, notification_url='')
            send_push_notification(fcm_token_vp, title, body, data)
        print("Event status changed to Delayed. Additional operations can be performed here.")

pre_save.connect(track_field_changes, sender=ProjectCostSheet)

@receiver(post_save, sender=ProjectCostSheet)
def projectcostsheet_post_save_handler(sender, instance, created, **kwargs):

    if created:
        print(f'ProjectCostSheet instance {instance.id} has been created!')
    else:
        print(f'ProjectCostSheet instance {instance.id} has been updated!')

post_save.connect(projectcostsheet_post_save_handler, sender=ProjectCostSheet)

class InventoryCostSheet(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ("Installment", "Installment"),
        ("Registration Fees", "Registration Fees"),
        ("Stamp Duty", "Stamp Duty"),
        ("Token", "Token")
    ]
    inventory = models.ForeignKey(ProjectInventory, on_delete=models.CASCADE)
    event_order = models.PositiveIntegerField()
    event = models.CharField(max_length=1000)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    payment_in_percentage = models.DecimalField(max_digits=50,default=0, decimal_places=2)
    amount = models.DecimalField(max_digits=50,blank=True, null=True, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=50,default=0, decimal_places=2)
    gst = models.DecimalField(max_digits=50,blank=True, null=True, decimal_places=2)
    tds = models.DecimalField(max_digits=50,blank=True, default=0, decimal_places=2)
    total_amount = models.DecimalField(max_digits=50, decimal_places=2,blank=True, null=True)
    # transaction_id = models.CharField(max_length=500,null=True,blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    paid = models.BooleanField(default=False)
    paid_date = models.DateTimeField(null=True, blank=True)
    tds_paid = models.BooleanField(default=False)
    tds_paid_date = models.DateTimeField(null=True, blank=True)
    pay_via_cheque = models.BooleanField(default=False)
    payment_type = models.CharField(max_length=50, choices=PAYMENT_TYPE_CHOICES,default="Installment")
    lead = models.ForeignKey('lead.Lead', on_delete=models.SET_NULL, blank=True, null=True)
    is_changed = models.BooleanField(default=False)
    history = HistoricalRecords()

    # @property
    # def tds(self):
    #     return self.amount * 0.01

    @property
    def remaining_amount(self):
        if self.event == "Token amount of initial payment":
            return 0
        
        if self.total_amount is not None and self.amount_paid is not None:
            return self.total_amount - self.amount_paid
        return None
    
    @property
    def payment_status(self):
        if self.event == "Token amount of initial payment":
            return "Paid"
           
        if self.paid:
            if self.remaining_amount is not None and self.remaining_amount > 0:
                return "Partially Paid"
            else:
                return "Paid"
        else:
            return "Pending"

    def __str__(self):
        return f"{self.inventory.tower.project.name} - {self.inventory.apartment_no} - Event Order {self.event_order}: {self.event}"
    
# @receiver(post_save, sender=InventoryCostSheet)
# def generate_cost_sheet_pdf_on_save(sender, instance, created, **kwargs):

#     generate_form_pdf(lead_id=instance.lead.id, cost_sheet_param=True)

# @receiver(pre_save, sender=InventoryCostSheet)
# def handle_inventory_cost_sheet_pre_save(sender, instance, **kwargs):
#     # Check if the instance is being created or updated
#     if instance.pk:
#         try:
#             # Fetch the current state from the database
#             existing_instance = sender.objects.get(pk=instance.pk)
#             print('existing_instance:', existing_instance)
#         except sender.DoesNotExist:
#             existing_instance = None

#         if existing_instance:
#             # Compare the 'name' field to check if there are changes
#             if instance.payment_in_percentage != existing_instance.payment_in_percentage:
#                 print("here")
#                 # Generate the PDF only if the 'payment_in_percentage' field has changed
#                 generate_form_pdf(lead_id=instance.lead.id, cost_sheet_param=True)

class PropertyOwner(models.Model):
    BOOKING_STATUS = (
        ('initiated', 'initiated'),
        ('active', 'active'),
        ('cancel', 'cancel'),
    )
    
    property = models.ForeignKey(ProjectInventory, on_delete=models.CASCADE, related_name='brik_detail')
    # owner = models.ForeignKey(User, related_name='property_owner', on_delete=models.CASCADE)
    lead = models.ForeignKey('lead.Lead', related_name='property_owner', on_delete=models.CASCADE)
    deal_amount = models.DecimalField(decimal_places=2, max_digits=20,default=0) #agreement_value
    total_value = models.DecimalField(decimal_places=2, max_digits=20,default=0) #agreement_value
    refund_amount = models.DecimalField(decimal_places=2, max_digits=20,default=0)
    refund_status = models.BooleanField(default=False)
    cost_of_flat = models.IntegerField(blank=True, null=True)
    other_charges = models.IntegerField(blank=True, null=True)
    ownership_number = models.CharField(max_length=100, blank=True, null=True)
    property_buy_date = models.DateTimeField(blank=True, null=True)
    cost_sheet_pdf = models.FileField(upload_to='cost_sheet/', blank=True, null=True)
    booking_form_pdf = models.FileField(upload_to='booking_form/', blank=True, null=True)
    cost_sheet_deny_reason = models.CharField(max_length=255, null=True, blank=True)
    booking_status = models.CharField(max_length=50, choices=BOOKING_STATUS, default="initiated")
    booking_cancelled_at = models.DateTimeField(null=True, blank=True)
    history = HistoricalRecords() 
    #key_transfer = models.BooleanField(default=False)
    def __str__(self):
        return "%s - %s" % (f"{self.lead.first_name} {self.lead.last_name}", self.property.apartment_no)

    class Meta:
        unique_together = ('property', 'lead')

class PaymentNotifications(models.Model):
    NOTIFICATION_TYPE = (
        ('payment_reminder', 'payment_reminder'),
        ('payment_received', 'payment_received'),
    )
    payment = models.ForeignKey(InventoryCostSheet, related_name="payment_notification", blank=True, on_delete=models.CASCADE, null=True)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE, default="payment_reminder")
    payment_amount = models.FloatField(max_length=50, blank=True, null=True)
    read = models.BooleanField(default=False)
    email = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return "%s - %s" % (self.payment, self.read)

    class Meta:
        ordering = ('read','-created')

    @property
    def inventory(self):
        return self.payment.inventory

    @property
    def due_date(self):
        return self.payment.due_date

    @property
    def installment_paid(self):
        return self.payment.paid

    @property
    def owner(self):
        return self.payment.inventory.lead

    @property
    def notification_message(self):
        content = {'message':''}
        if self.notification_type == 'payment_reminder':
            # content = email_services.get_email_content('installment_notification',installment_amount = self.instalment_amount,due_date =self.due_date,brik_name = self.brik_name)
            pass
        elif self.notification_type == 'payment_received':
            # content = email_services.get_email_content('payment_received_notification',payment_amount = self.payment_amount,brik_name = self.brik_name)
            pass
        return content['message']

    @property
    def notification_title(self):
        title = ''
        if self.notification_type == 'payment_reminder':
            title = 'Payment Reminder'
        elif self.notification_type == 'payment_received':
            title = 'Payment Received'
        return title