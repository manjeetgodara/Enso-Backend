from django.db import models
from comms.utils import send_push_notification
from lead.models import Lead
from auth.models import Users
from .constants import WORKFLOW_TYPES, TASK_TYPES
from datetime import datetime
from .mixins import WorkflowTrackingMixin, AppointmentDefinitionMixin, AutomationDefinitionMixin, TodoDefinitionMixin, TodoDefinitionInstanceMixin, AutomationDefinitionInstanceMixin
from core.models import Organization
from django.dispatch import receiver
from django.db.models.signals import post_save,pre_save
from river.models import Workflow, WorkflowDefinition
from river.models.fields.state import StateField
from river.config import app_config
from simple_history.models import HistoricalRecords
from django.shortcuts import get_object_or_404
from river.models import State
from django.db.models import Max
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField


# class WorkflowDefinition(models.Model):
#     name = models.CharField(max_length=200)
#     workflow_type = models.CharField(max_length=100, choices=WORKFLOW_TYPES)
#     creator = models.ForeignKey(Users, on_delete=models.PROTECT)
#     organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

#     def __str__(self):
#         return "%s - %s" %(self.name, self.creator)

# class Workflow(WorkflowTrackingMixin):
#     current_stage = models.IntegerField(default=0)  # The order of the current running stage
#     current_task = models.IntegerField(default=0)  # The order value of the current running task
#     name = models.CharField(max_length=200)
#     workflow_type = models.CharField(max_length=100, choices=WORKFLOW_TYPES)
#     lead = models.ForeignKey(Lead, related_name="workflow", on_delete=models.CASCADE)
#     definition = models.ForeignKey(WorkflowDefinition, related_name="created_objects", on_delete=models.SET_NULL, null = True)
#     assigned_to = models.ForeignKey(Users, related_name="assigned_workflows", on_delete=models.CASCADE,null=True,blank=True)
#     organization = models.ForeignKey(Organization, on_delete=models.CASCADE, default=None, null=True)

#     def __str__(self):
#         return "%s - %s" %(self.name, self.lead)
    
from river.models import State
class StageDefinition(models.Model):
    name = models.CharField(max_length=200)
    order = models.IntegerField()
    workflow = models.ForeignKey(WorkflowDefinition, related_name="stages", on_delete=models.CASCADE)

    def __str__(self):
        return "%s - %s" %(self.name, self.workflow)   

class Stage(WorkflowTrackingMixin):
    name = models.CharField(max_length=200)
    order = models.IntegerField()
    current_task = models.IntegerField(default=0)
    workflow = models.ForeignKey(Workflow, related_name="stages", on_delete=models.CASCADE)
    definition = models.ForeignKey(StageDefinition, on_delete=models.SET_NULL,null=True)
    assigned_to = models.ForeignKey(Users, related_name="assigned_stage", on_delete=models.CASCADE,null=True,blank=True)

    def __str__(self):
        return "%s - %s" %(self.name, self.workflow)

    @property
    def is_complete(self):
        if not self.started:
            return False
        
        if self.tasks.filter(completed=False).exists():
            return False

        if self.completed != True and not self.tasks.filter(completed=False).exists():
            self.completed = True
            self.completed_at = timezone.now()
            self.save()
        
        return True

class TaskDefinition(TodoDefinitionMixin, AutomationDefinitionMixin,AppointmentDefinitionMixin):
    name = models.CharField(max_length=200)
    order = models.IntegerField()
    task_type = models.CharField(max_length=100, choices=TASK_TYPES)
    # Email linking here
    # email_template = models.ForeignKey(EmailTemplate, null=True, blank=True, on_delete=models.PROTECT)
    stage = models.ForeignKey(StageDefinition, related_name="tasks", on_delete=models.CASCADE)
    workflow = models.ForeignKey(WorkflowDefinition, related_name="flattened_tasks", on_delete=models.CASCADE)
    permissions = models.ManyToManyField(app_config.PERMISSION_CLASS, verbose_name=('Permissions'), blank=True)
    groups = models.ManyToManyField(app_config.GROUP_CLASS, verbose_name=('Groups'), blank=True)
    users = models.ManyToManyField("myauth.users",verbose_name=('Users'), blank=True)
    minimum_approvals_required = models.IntegerField(default=-1)
    # notification_meta =  models.ManyToManyField("workflow.NotificationMeta",verbose_name=('Notification Meta'), blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.stage.name} - Order({self.order})"
    

class NotificationMetaDefinition(models.Model):
    task = models.ForeignKey(TaskDefinition, related_name="task_definition_id", on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    time_interval = models.IntegerField(default=24, help_text="Time interval in hours for triggering the notification")
    groups = models.ManyToManyField(app_config.GROUP_CLASS, verbose_name=('Groups'), blank=True)
    users = models.ManyToManyField("myauth.users",verbose_name=('Users'), blank=True)

class Task(
    WorkflowTrackingMixin,
    TodoDefinitionInstanceMixin,
    AutomationDefinitionInstanceMixin,
    AppointmentDefinitionMixin,
):
    name = models.CharField(max_length=200)
    order = models.IntegerField()
    task_type = models.CharField(max_length=100, choices=TASK_TYPES)
    # email_template = models.ForeignKey(EmailTemplate, null=True, blank=True, on_delete=models.CASCADE)
    stage = models.ForeignKey(Stage, related_name="tasks", on_delete=models.CASCADE)
    # workflow = models.ForeignKey(Workflow, related_name="flattened_tasks", on_delete=models.CASCADE)
    workflow = models.ForeignKey(Workflow, related_name="tasks", on_delete=models.CASCADE, db_column='workflow_id')
    details=models.TextField(null=True,blank=True)
    # notification_recipients = ArrayField(models.IntegerField(), default=list, blank=True)
    permissions = models.ManyToManyField(app_config.PERMISSION_CLASS, verbose_name=('Permissions'), blank=True)
    groups = models.ManyToManyField(app_config.GROUP_CLASS, verbose_name=('Groups'), blank=True)
    users = models.ManyToManyField("myauth.users",verbose_name=('Users'), blank=True)
    minimum_approvals_required = models.IntegerField(default=-1)
    status = StateField()
    # notification_meta =  models.ManyToManyField("workflow.NotificationMeta",verbose_name=('Notification Meta'), blank=True, null=True)
    current_notification_meta = models.ForeignKey("workflow.NotificationMeta", related_name="current_notification_meta_id", on_delete=models.CASCADE, null=True, blank=True)

    history = HistoricalRecords(cascade_delete_history=True)

class NotificationMeta(models.Model):
    task = models.ForeignKey(Task, related_name="task_id", on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200, blank=True, null=True)
    time_interval = models.IntegerField(default=24, help_text="Time interval in hours for triggering the notification")
    groups = models.ManyToManyField(app_config.GROUP_CLASS, verbose_name=('Groups'), blank=True)
    users = models.ManyToManyField("myauth.users",verbose_name=('Users'), blank=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "NotificationMeta"

    def __str__(self):
        return f"{self.name} - Notify after {self.time_interval}hrs"


class Notifications(models.Model):
    NOTIFICATION_TYPE = (
        ('task_reminder', 'task_reminder'),
        ('converted', 'converted'),
        ('payment_reminder', 'payment_reminder'),
        ('payment_received', 'payment_received'),
    )
    notification_id = models.CharField(max_length=255)
    user_id = models.ForeignKey(Users, related_name="user_id", on_delete=models.CASCADE, null=False, blank=False)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE, default="task_reminder")
    notification_url = models.CharField(max_length=255, null=True, blank=True, default=None)
    notification_message = models.TextField(null=True, blank=True)
    read = models.BooleanField(default=False)
    email = models.BooleanField(default=False)
    created = models.DateTimeField(blank=True,null=True)
    

    class Meta:
        verbose_name_plural = "Notifications"

    @property
    def notification_title(self):
        title = ''
        if self.notification_type == 'payment_reminder':
            title = 'Payment Reminder'
        elif self.notification_type == 'payment_received':
            title = 'Payment Received'
        elif self.notification_type == 'task_reminder':
            title = 'Task Reminder'
        elif self.notification_type == 'converted':
            title = 'Converted'
        return title
    
    # @property
    # def notification_message(self):
    #     message = ""
    #     if self.notification_type == 'booking_confirmed':
    #         message = f"Your booking for brik {self.brik_name} is confirmed"
    #     if self.notification_type == 'contact_detail_request_pending':
    #         message = f'{self.sender_owner.first_name} send you request for contact details.'
    #     if self.notification_type == 'contact_detail_request_accept':
    #         message = f'{self.sender_owner.first_name} accepted your request for contact details.'
    #     return message


def sendNotificationLocal(instance):
    if not Notifications.objects.filter(notification_id=f"lead-{instance.id}").exists():
        print("Adding New Notification")
        Notifications.objects.create(notification_id=f"lead-{instance.id}", broker_id=instance.creator, notification_type='sales_done')

    #TODO - send email notification
    
    # notificationObj = Notifications.objects.get(notification_id = f"lead-{instance.id}", email=False)
    # try:
    #     subject = f"About {notificationObj.notification_type}"
    #     leadId = (notificationObj.notification_id).split("-")[1]
    #     broker_name = (notificationObj.broker_id.name).split(" ")[0]
    #     leadObj = Lead.objects.get(id=leadId)
    #     redirLink = email_services.create_redirect_url(f"/lead/{leadObj.id}")

    #     keyValueDict = {}
    #     for key in email_template_lead_sales_done.replace_list:
    #         keyValueDict[key] = ""

    #     keyValueDict["{user-name}"] = broker_name
    #     keyValueDict["{email-message}"] = f"Your lead for client {leadObj.client.name}, marked sales done."
    #     keyValueDict["{redirect-link}"] = redirLink

    #     email_body = email_services.set_email_body(keyValueDict,email_template_lead_sales_done.email_conf)
    #     to_email =notificationObj.broker_id.email
    #     email_services.send_email(subject=subject,message=email_body,to_email=to_email)
    #     print(f"send mail to {to_email}")
    #     notificationObj.email = True
    #     notificationObj.save()
    # except Exception as ex:
    #     print(str(ex))
    #     pass                    
        
@receiver(post_save, sender=Organization)
def create_workflow_defination(sender, instance, created, *args, **kwargs):
    if created:
        user= Users.objects.first()
        wd=WorkflowDefinition.objects.create(name="Sales Template", organization=instance, creator=user, workflow_type='sales')
        sd = StageDefinition.objects.create(name='PreSales', order=0, workflow=wd)
        sd1 = StageDefinition.objects.create(name='Sales', order=1, workflow=wd)
        sd2 = StageDefinition.objects.create(name='PostSales', order=2, workflow=wd)


@receiver(post_save, sender=Task)
def task_update_handler(sender, instance, created, *args, **kwargs):
    print('task_update_handler triggered', instance.status)
    if created:
        return

    if instance.status=='Accept':
        from .tasks import process_task
        process_task.delay(instance.id)

    if instance.completed and not instance.name =='Follow Up':
        from .tasks import process_task_update
        process_task_update.delay(instance.id)

    if instance.completed and instance.workflow.workflow_type == 'accounts':
        from .tasks import process_task_update
        process_task_update.delay(instance.id)

# @receiver(pre_save,sender=Lead)
def update_action_journey(sender, instance, *args, **kwargs):
    if instance._state.adding:
        return

    previous = sender.objects.get(id=instance.id)
    
    print(instance.lead_status, previous.lead_status)
    #TODO - Sales done
    if instance.lead_status == 'Sales Done' and previous.lead_status != 'Sales Done':
        sendNotificationLocal(instance)
    
    state = get_object_or_404(State, label='Accept')
    # if previous.last_call_status != instance.last_call_status:
    #     data=   {
    #                 "stage":instance.workflow.get().stages.first(),
    #                 "name": instance.last_call_status,
    #                 "order":0,
    #                 "task_type": "todo",
    #                 "workflow":instance.workflow.get(),
    #                 "time": instance.updated_on,
    #                 "status": state
    #         }

    #     task = Task.objects.create(**data)
    #     stage = instance.workflow.get().stages.first()
    #     max_order_dict = stage.tasks.aggregate(Max('order'))
    #     max_order_yet = max_order_dict.get('order__max', None)
    #     if max_order_yet:
    #         task.order = max_order_yet+1
    #     else:
    #         task.order = 1
    #     task.save()
    
    if previous.follow_up_date != instance.follow_up_date:
        data=   {
                    "stage":instance.workflow.get().stages.first(),
                    "name": "Follow Up",
                    "order":0,
                    "task_type": "appointment",
                    "workflow":instance.workflow.get(),
                    "appointment_with": instance.name,
                    "appointment_type": "telephonic",
                    "time": timezone.now(),
                    "details":"follow up call with client",
                    "status": state
            }
        task = Task.objects.create(**data)
        stage = instance.workflow.get().stages.first()
        max_order_dict = stage.tasks.aggregate(Max('order'))
        max_order_yet = max_order_dict.get('order__max', None)
        if max_order_yet:
            task.order = max_order_yet+1
        else:
            task.order = 0
        task.save()


@receiver(pre_save, sender=WorkflowDefinition)
def workflowdefinition_pre_save_handler(sender, instance, **kwargs):
    pass


@receiver(post_save, sender=WorkflowDefinition)
def workflowdefinition_post_save_handler(sender, instance, created, **kwargs):
    pass

@receiver(pre_save, sender=Workflow)
def workflow_pre_save_handler(sender, instance, **kwargs):
    try:
        workflowObj = Workflow.objects.get(id=instance.id)
        print('workflowObj:', workflowObj)
        current_stage = workflowObj.current_stage
        print('current_stage:', current_stage, instance.current_stage)
    except Exception as ex:
        print(ex)
        current_stage = None

    if current_stage!=None and instance.current_stage != current_stage:
        notify_user_vp = Users.objects.filter(groups__name='VICE_PRESIDENT').first()
        notify_user_sh = Users.objects.filter(groups__name='SITE_HEAD').first()
        if instance.current_stage == 1 and notify_user_vp:
            # send notification for presales: lead is converted from presales to sales (VP)
            title = "Lead Converted to Sales"
            body = f"{workflowObj.lead.first_name} {workflowObj.lead.last_name} has been converted to Sales."
            data = {'notification_type': 'converted_to_sales' , 'redirect_url': f'/sales/my_visit/lead_details/{workflowObj.lead.id}/0'}

            # Fetch the FCM tokens associated with the VP
            fcm_token_vp = notify_user_vp.fcm_token

            Notifications.objects.create(notification_id=f"lead-{workflowObj.lead.id}-{notify_user_vp.id}", user_id=notify_user_vp,created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{workflowObj.lead.id}/0')

            # Send push notification using your existing method
            send_push_notification(fcm_token_vp, title, body, data)
            
            # Notifications.objects.create(notification_id=f"lead-{workflowObj.lead.id}", user_id=notify_user,created=timezone.now(), notification_message=f"{workflowObj.lead.first_name} {workflowObj.lead.last_name} converted to sales.")
        if instance.current_stage == 2:
            # Notifications.objects.create(notification_id=f"lead-{workflowObj.lead.id}", user_id=notify_user,created=timezone.now(), notification_message=f"{workflowObj.lead.first_name} {workflowObj.lead.last_name} converted to postsales.")

            # send notification for presales: lead is converted from presales to sales (VP)
            title = "Lead Converted to PostSales"
            body = f"{workflowObj.lead.first_name} {workflowObj.lead.last_name} has been converted to PostSales."
            data = {'notification_type': 'converted_to_post_sales' , 'redirect_url': f'/post_sales/all_clients/lead_details/{workflowObj.lead.id}/0'}

            if notify_user_vp:
                fcm_token_vp = notify_user_vp.fcm_token

                Notifications.objects.create(notification_id=f"lead-{workflowObj.lead.id}-{notify_user_vp.id}", user_id=notify_user_vp,created=timezone.now(), notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{workflowObj.lead.id}/0')

                send_push_notification(fcm_token_vp, title, body, data)
            if notify_user_sh:
                fcm_token_sh = notify_user_sh.fcm_token

                Notifications.objects.create(notification_id=f"lead-{workflowObj.lead.id}-{notify_user_sh.id}", user_id=notify_user_sh,created=timezone.now(), notification_message=body, notification_url='')
                data = {'notification_type': 'converted_to_post_sales' , 'redirect_url': ''}
                send_push_notification(fcm_token_sh, title, body, data)


@receiver(post_save, sender=Workflow)
def workflow_post_save_handler(sender, instance, created, **kwargs):
    pass


@receiver(pre_save, sender=StageDefinition)
def stagedefinition_pre_save_handler(sender, instance, **kwargs):
    pass


@receiver(post_save, sender=StageDefinition)
def stagedefinition_post_save_handler(sender, instance, created, **kwargs):
    pass


@receiver(pre_save, sender=Stage)
def stage_pre_save_handler(sender, instance, **kwargs):
    pass


@receiver(post_save, sender=Stage)
def stage_post_save_handler(sender, instance, created, **kwargs):
    pass


pre_save.connect(stagedefinition_pre_save_handler, sender=StageDefinition)
post_save.connect(stagedefinition_post_save_handler, sender=StageDefinition)
pre_save.connect(stage_pre_save_handler, sender=Stage)
post_save.connect(stage_post_save_handler, sender=Stage)
pre_save.connect(workflowdefinition_pre_save_handler, sender=WorkflowDefinition)
post_save.connect(workflowdefinition_post_save_handler, sender=WorkflowDefinition)
pre_save.connect(workflow_pre_save_handler, sender=Workflow)
post_save.connect(workflow_post_save_handler, sender=Workflow)