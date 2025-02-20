from datetime import datetime
from django.db import models
from .constants import PERIODS, TRIGGERS, ACTIONS, APPOINTMENT_TYPES


class TodoDefinitionMixin(models.Model):
    due_count = models.IntegerField(null=True, blank=True)
    due_period = models.CharField(max_length=100, null=True, blank=True, choices=PERIODS)
    due_trigger = models.CharField(max_length=100, null=True, blank=True, choices=TRIGGERS)
    due_trigger_obj = models.ForeignKey("self", on_delete = models.SET_DEFAULT, default=None, null = True, blank=True, related_name ='dependent_due')
    due_flag = models.BooleanField(default=False)
    reminder_count = models.IntegerField(null=True, blank=True)
    reminder_period = models.CharField(max_length=100, null=True, blank=True, choices=PERIODS)
    reminder_trigger = models.CharField(max_length=100, null=True, blank=True, choices=TRIGGERS)
    reminder_trigger_obj = models.ForeignKey("self", on_delete = models.SET_DEFAULT, default=None, null = True, blank=True, related_name = 'dependent_reminder')
    reminder_flag = models.BooleanField(default=False)

    class Meta:
        abstract = True


class AutomationDefinitionMixin(models.Model):
    action = models.CharField(max_length=100, null=True, blank=True, choices=ACTIONS)
    send_automatically = models.BooleanField(default=False)

    class Meta:
        abstract = True


class AppointmentDefinitionMixin(models.Model):
    # action = models.CharField(max_length=100, null=True, blank=True, choices=ACTIONS)
    time=models.DateTimeField(null=False,default=datetime.now)
    appointment_with=models.CharField(null=True, blank=True,max_length=100)
    contact_number=models.CharField(null=True,blank=True,max_length=100)
    email=models.CharField(null=True,blank=True,max_length=100)
    appointment_type=models.CharField(null=True,blank=True,max_length=100,choices=APPOINTMENT_TYPES)

    class Meta:
        abstract = True


class TodoDefinitionInstanceMixin(TodoDefinitionMixin):
    is_flagged = models.BooleanField(default=False)
    reminder_sent = models.BooleanField(default=False)
    is_reminder_flagged = models.BooleanField(default=False)

    class Meta:
        abstract = True


class AutomationDefinitionInstanceMixin(AutomationDefinitionMixin):
    is_action_sent = models.BooleanField(default=False)

    class Meta:
        abstract = True

class WorkflowTrackingMixin(models.Model):
    started_at = models.DateTimeField(null=True, blank=True)
    started = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True