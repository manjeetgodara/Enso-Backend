from django.db import models
from auth.models import Users
from lead.models import Lead

# Create your models here.
class LeadCallsMcube(models.Model):
    CALL_TYPE = [
        ('INCOMING', 'INCOMING'),
        ('OUTGOING', 'OUTGOING'),
    ]
    lead_phone=models.CharField(max_length=13)
    callid=models.CharField(max_length=50)
    executive=models.ForeignKey(Users, on_delete=models.CASCADE)
    lead=models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL)
    call_type=models.CharField(max_length=20, choices=CALL_TYPE)
    call_duration=models.CharField(max_length=20,blank=True, null=True)
    call_status=models.CharField(max_length=20)
    followup_date=models.DateField(blank=True, null=True)
    start_time=models.DateTimeField(blank=True, null=True)
    end_time=models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    request_body = models.JSONField(blank=True,null=True)

    def __str__(self):
        return f"Lead added"