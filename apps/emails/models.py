from django.db import models
from simple_history.models import HistoricalRecords
# Create your models here.

class Email(models.Model):
    name = models.EmailField(max_length=255, unique=True, blank= False)
    subject = models.CharField(max_length=100, blank= True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True) 
    attached_file = models.FileField(upload_to='email_attachments/', blank=True, null=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.subject
    
class EmailTemplate(models.Model):
    subject = models.CharField(max_length= 255)
    message = models.TextField()
    history = HistoricalRecords()
    class Meta:
        unique_together = ('subject' , 'message')

    def __str__(self):
        return self.subject