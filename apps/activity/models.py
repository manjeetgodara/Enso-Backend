from django.db import models
#from .models import Users
from lead.models import Lead
from simple_history.models import HistoricalRecords
from django.utils import timezone
from auth.models import Users 
from django.db.models.signals import post_save,pre_save
from django.dispatch import receiver
from django.contrib.postgres.fields import ArrayField
from django.utils.timezone import now
class Notes(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True)
    notes = models.TextField()
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.lead} - {self.id}"

    def save(self, *args, **kwargs):
        if not self.created_on:
            self.created_on = timezone.now().astimezone(timezone.pytz.timezone('Asia/Kolkata'))
            print("timestamp in model: ", self.created_on)
        super().save(*args, **kwargs)

    class Meta:

        indexes = [
            models.Index(fields=['created_on'])
        ]


@receiver(pre_save, sender=Notes)
def notes_pre_save_handler(sender, instance, **kwargs):
    pass
    #print(f'Notes instance {instance.id} about to be saved!')

@receiver(post_save, sender=Notes)
def notes_post_save_handler(sender, instance, **kwargs):
    print(f'Notes instance {instance.id} saved!')

pre_save.connect(notes_pre_save_handler, sender=Notes)
post_save.connect(notes_post_save_handler, sender=Notes)


class SiteVisit(models.Model):
 
    TIMESLOT_CHOICES = [
        ('10:00 AM to 10:30 AM', '10:00 AM to 10:30 AM'),
        ('10:30 AM to 11:00 AM', '10:30 AM to 11:00 AM'),
        ('11:00 AM to 11:30 AM', '11:00 AM to 11:30 AM'),
        ('11:30 AM to 12:00 PM', '11:30 AM to 12:00 PM'),
        ('12:00 PM to 12:30 PM', '12:00 PM to 12:30 PM'),
        ('12:30 PM to 01:00 PM', '12:30 PM to 01:00 PM'),
        ('01:00 PM to 01:30 PM', '01:00 PM to 01:30 PM'),
        ('01:30 PM to 02:00 PM', '01:30 PM to 02:00 PM'),
        ('02:00 PM to 02:30 PM', '02:00 PM to 02:30 PM'),
        ('02:30 PM to 03:00 PM', '02:30 PM to 03:00 PM'),
        ('03:00 PM to 03:30 PM', '03:00 PM to 03:30 PM'),
        ('03:30 PM to 04:00 PM', '03:30 PM to 04:00 PM'),
        ('04:00 PM to 04:30 PM', '04:00 PM to 04:30 PM'),
        ('04:30 PM to 05:00 PM', '04:30 PM to 05:00 PM'),
        ('05:00 PM to 05:30 PM', '05:00 PM to 05:30 PM'),
        ('05:30 PM to 06:00 PM', '05:30 PM to 06:00 PM'),
        ('06:00 PM to 06:30 PM', '06:00 PM to 06:30 PM'),
        ('06:30 PM to 07:00 PM', '06:30 PM to 07:00 PM'),
        ('07:00 PM to 07:30 PM', '07:00 PM to 07:30 PM'),
        ('07:30 PM to 08:00 PM', '07:30 PM to 08:00 PM'),
        ('08:00 PM to 08:30 PM', '08:00 PM to 08:30 PM'),
        ('08:30 PM to 09:00 PM', '08:30 PM to 09:00 PM'),
    ]

    SITEVISIT_CHOICES = [
        ("Site Visit Done", "Site Visit Done"),
        ("Missed", "Missed"),
        ("Scheduled", "Scheduled"),
    ]
    SITEVISIT_TYPES_CHOICES = [
        ("Regular", "Regular"),
        ("Snagging", "Snagging")
    ]
    SNAGGING_CHOICES = [
        ("Snagging clear", "Snagging clear"),
        ("Defects Spotted", "Defects Spotted")
    ]
    visit_date = models.DateField()
    property = models.CharField(max_length=100,null=True,blank=True)
    timeslot = models.CharField(max_length=50, choices=TIMESLOT_CHOICES,null=True,blank=True)
    closing_manager = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True)
    sourcing_manager = models.ForeignKey(Users, on_delete=models.SET_NULL, null=True, blank=True, related_name='sourcing_manager_site_visits')
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    site_visit_status = models.CharField(max_length=50, choices=SITEVISIT_CHOICES,default="Scheduled")
    site_visit_type = models.CharField(max_length=50, choices=SITEVISIT_TYPES_CHOICES,default="Regular")
    constructor =models.CharField(max_length=60,null=True,blank=True )
    snagging_status = models.CharField(max_length = 25, choices=SNAGGING_CHOICES,null=True,blank=True)
    #snagging_issues = models.CharField(max_length=60,null=True,blank=True)
    snagging_issues  = ArrayField(models.CharField(max_length=150), default=list, blank=True) 
    created_at = models.DateTimeField(default=now,null=True,blank=True)
    history = HistoricalRecords()
        
    def __str__(self):
        return f"{self.visit_date} - {self.property} - {self.lead}"
    
    class Meta:
        indexes = [
            models.Index(fields=['visit_date'])
        ]


@receiver(pre_save, sender=SiteVisit)
def sitevisit_pre_save_handler(sender, instance, **kwargs):
    pass
    #print(f'SiteVisit instance {instance.id} about to be saved!')

@receiver(post_save, sender=SiteVisit)
def sitevisit_post_save_handler(sender, instance, created, **kwargs):

    if created:
        print(f'SiteVisit instance {instance.id} has been created!')
    else:
        print(f'SiteVisit instance {instance.id} has been updated!')


pre_save.connect(sitevisit_pre_save_handler, sender=SiteVisit)
post_save.connect(sitevisit_post_save_handler, sender=SiteVisit)



class CancelBookingReason(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='cancel_reasons')
    reason = models.TextField()
    create_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cancel Reason for Lead {self.lead.id}"

# class RescheduledDate(models.Model):
#     site_visit = models.ForeignKey(SiteVisit, on_delete=models.CASCADE)
#     new_date = models.DateField()
#     history = HistoricalRecords()
#     def __str__(self):
#         return f"Rescheduled: {self.new_date}"

