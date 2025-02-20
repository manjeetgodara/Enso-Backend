from django.db import models
from django.db.models import PROTECT
from django.utils.translation import gettext_lazy as _
from django_multitenant.fields import TenantForeignKey
from accounts.models import *
from river.config import app_config
from river.models import BaseModel, State
from river.models.managers.workflowmetada import WorkflowManager
# from workflow.models import WorkflowDefinition
from workflow.constants import WORKFLOW_TYPES
from lead.models import Lead
from auth.models import Users
from core.models import Organization
# from workflow.models import Task

class WorkflowDefinition(models.Model):
    name = models.CharField(max_length=200)
    workflow_type = models.CharField(max_length=100, choices=WORKFLOW_TYPES)
    creator = models.ForeignKey(Users, on_delete=models.PROTECT)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    def __str__(self):
        return "%s - %s" %(self.name, self.creator)
    
    
class Workflow(BaseModel):
    class Meta:
        app_label = 'river'
        verbose_name = _("Workflow")
        verbose_name_plural = _("Workflows")
        # unique_together = [("content_type", "field_name")]

    objects = WorkflowManager()

    content_type = models.ForeignKey(app_config.CONTENT_TYPE_CLASS, verbose_name=_('Content Type'), on_delete=PROTECT)
    # content_type = models.ForeignKey('workflow.Task', verbose_name=_('Content Type'), on_delete=PROTECT, related_name='workflow_content_types')
    field_name = models.CharField(_("Field Name"), max_length=200)
    initial_state = models.ForeignKey(State, verbose_name=_("Initial State"), related_name='workflow_this_set_as_initial_state', on_delete=PROTECT)

    current_stage = models.IntegerField(default=0)  # The order of the current running stage
    current_task = models.IntegerField(default=0)  # The order value of the current running task
    name = models.CharField(max_length=200)
    workflow_type = models.CharField(max_length=100, choices=WORKFLOW_TYPES)
    lead = models.ForeignKey(Lead, related_name="workflow", on_delete=models.CASCADE,null=True,blank=True)
    payment = models.ForeignKey(Payment,related_name="payment_workflow", on_delete=models.CASCADE,null=True,blank=True) 
    definition = models.ForeignKey(WorkflowDefinition, related_name="created_objects", on_delete=models.SET_NULL, null = True)
    assigned_to = models.ForeignKey(Users, related_name="assigned_workflows", on_delete=models.CASCADE,null=True,blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, default=None, null=True)

    started_at = models.DateTimeField(null=True, blank=True)
    started = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    def natural_key(self):
        return self.content_type, self.field_name

    def __str__(self):
        return "%s.%s" % (self.content_type.model, self.field_name)
