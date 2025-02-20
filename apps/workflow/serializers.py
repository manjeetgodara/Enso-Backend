from rest_framework import serializers
from .models import Workflow, Task, TaskDefinition, Stage, Notifications, NotificationMeta, NotificationMetaDefinition
from auth.serializers import UserSerializer
from core.serializers import OrganizationSerializer
from workflow.tasks import process_workflow
from workflow.utils import WorkflowTrackingHelpers
from river.models import State,TransitionApprovalMeta, TransitionMeta
from django.contrib.contenttypes.models import ContentType
from river.models import TransitionApproval
from django.contrib.auth.models import Group
from django.utils import timezone

class WorkflowCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = [
            "name",
            "id",
            "workflow_type",
            "lead",
            "definition",
            "assigned_to",
            "organization",
        ]

    def create(self, validated_data):
        workflow_definition = validated_data["definition"]
        # print("definition:", workflow_definition)

        # Creating states
        request_state, _ = State.objects.update_or_create(label="Request", slug="request")
        in_progress_state, _ = State.objects.update_or_create(label="In Progress", slug="in_progress")
        deny_state, _ = State.objects.update_or_create(label="Deny", slug="deny")
        accept_state, _ = State.objects.update_or_create(label="Accept", slug="accept")
        # TODO optimize
        # state_instances = State.objects.all()
        # request_state = in_progress_state = deny_state = accept_state = None
        # for instance in state_instances:
        #     if instance.slug == 'request': request_state = instance
        #     elif instance.slug == 'in_progress': in_progress_state = instance
        #     elif instance.slug == 'deny': deny_state = instance
        #     elif instance.slug == 'accept': accept_state = instance
    
        # # Creating workflow
        content_type = ContentType.objects.get_for_model(Task)
        workflow, _ = Workflow.objects.update_or_create(**validated_data,content_type=content_type, field_name="status", defaults={"initial_state": request_state})
    
        for stage_definition in workflow_definition.stages.all().order_by('order'):
            stage = Stage.objects.create(
                workflow=workflow,
                definition=stage_definition,
                name=stage_definition.name,
                order=stage_definition.order,
            )
            if stage_definition.order==0 : 
                WorkflowTrackingHelpers.mark_started(stage)
                stage.assigned_to = workflow.assigned_to
                stage.save()
            # print("Tasks:",stage_definition.tasks.all().order_by('order'))

            for task_definition in stage_definition.tasks.all().order_by('order'):
                notify_meta_definitions = NotificationMetaDefinition.objects.filter(task__id=task_definition.id).order_by('time_interval')
                
                fields = [f.name for f in TaskDefinition._meta.get_fields()]
                ignored_fields = ["stage", "workflow", "id", "reminder_trigger_obj", "due_trigger_obj", "dependent_due", "dependent_reminder", "users", "groups", "permissions", "notification_meta", "task_definition_id"]
                capture_task_data = dict()

                for field in fields:
                    if field not in ignored_fields:
                        capture_task_data[field] = getattr(task_definition, field, None)

                content_type = ContentType.objects.get_for_model(Task)
                print('content_type:', content_type)
                workflow, _ = Workflow.objects.update_or_create(**validated_data,content_type=content_type, field_name="status",defaults={"initial_state": request_state})
            
                # workflow = Workflow.objects.create(**validated_data)
                print("workflow created:", workflow)
                # Creating TransitionMeta
                request_to_in_progress, _ = TransitionMeta.objects.update_or_create(workflow=workflow,source_state=request_state,destination_state=in_progress_state)
                in_progress_to_accept, _ = TransitionMeta.objects.update_or_create(workflow=workflow,source_state=in_progress_state,destination_state=accept_state)
                in_progress_to_deny, _ = TransitionMeta.objects.update_or_create(workflow=workflow,source_state=in_progress_state,destination_state=deny_state)
                deny_to_request, _ = TransitionMeta.objects.update_or_create(workflow=workflow, source_state=deny_state,destination_state=request_state)

                # if minimum_approvals_required != 0 , Creating TransitionApprovalMeta
                if task_definition.minimum_approvals_required != 0:

                    # CLOSING_MANAGER = Group.objects.get(name="CLOSING_MANAGER")
                    request_to_in_progress_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,    transition_meta=request_to_in_progress)
                    # request_to_in_progress_meta.users.set(task_definition.users.all())
                    # request_to_in_progress_meta.groups.set([CLOSING_MANAGER])
    
                    in_progress_to_accept_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,    transition_meta=in_progress_to_accept)
                    in_progress_to_accept_meta.users.set(task_definition.users.all())
                    in_progress_to_accept_meta.groups.set(task_definition.groups.all())
            
                    in_progress_to_deny_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,    transition_meta=in_progress_to_deny)
                    in_progress_to_deny_meta.users.set(task_definition.users.all())
                    in_progress_to_deny_meta.groups.set(task_definition.groups.all())
            
                    deny_to_request_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,    transition_meta=deny_to_request)
                    deny_to_request_meta.users.set(task_definition.users.all())
                    deny_to_request_meta.groups.set(task_definition.groups.all())


                due_trigger_obj = None
                reminder_trigger_obj = None

                if task_definition.due_flag and task_definition.due_trigger == "after_task" and task_definition.due_trigger_obj:
                    due_trigger_obj = Task.objects.filter(stage = stage, workflow = workflow, order = task_definition.due_trigger_obj.order).first()

                
                if task_definition.reminder_flag and task_definition.reminder_trigger =="after_task" and task_definition.reminder_trigger_obj:
                    reminder_trigger_obj = Task.objects.filter(stage = stage, workflow = workflow, order = task_definition.reminder_trigger_obj.order).first()

                task = Task.objects.create(
                    **capture_task_data, stage=stage, workflow=workflow, due_trigger_obj = due_trigger_obj,
                    reminder_trigger_obj=reminder_trigger_obj
                )
                task.users.set(task_definition.users.all())
                task.groups.set(task_definition.groups.all())

                if notify_meta_definitions and notify_meta_definitions.count() > 0:
                    for ind,notify_meta in enumerate(notify_meta_definitions):
                        task_notify_meta = NotificationMeta.objects.create(task=task,name=notify_meta.name,time_interval=notify_meta.time_interval)
                        task_notify_meta.groups.set(notify_meta.groups.all())
                        task_notify_meta.users.set(notify_meta.users.all())
                        task_notify_meta.save()
                        if ind==0:
                            task.current_notification_meta = task_notify_meta
                            task.save()
                            
                # task.notification_meta.set(task_definition.notification_meta.all())
                print("task created!", task)
                #To mark 1st task as started
                # if task_definition.order==0: WorkflowTrackingHelpers.mark_started(task)

        WorkflowTrackingHelpers.mark_started(workflow)
        process_workflow.delay(workflow.pk)
        return workflow

class WorkflowBulkUploadCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = [
            "name",
            "id",
            "workflow_type",
            "lead",
            "definition",
            "assigned_to",
            "organization",
        ]

    def create(self, validated_data):
        workflow_definition = validated_data["definition"]
        # print("definition:", workflow_definition)

        # Creating states
        request_state, _ = State.objects.update_or_create(label="Request", slug="request")
        in_progress_state, _ = State.objects.update_or_create(label="In Progress", slug="in_progress")
        deny_state, _ = State.objects.update_or_create(label="Deny", slug="deny")
        accept_state, _ = State.objects.update_or_create(label="Accept", slug="accept")
        # TODO optimize
        # state_instances = State.objects.all()
        # request_state = in_progress_state = deny_state = accept_state = None
        # for instance in state_instances:
        #     if instance.slug == 'request': request_state = instance
        #     elif instance.slug == 'in_progress': in_progress_state = instance
        #     elif instance.slug == 'deny': deny_state = instance
        #     elif instance.slug == 'accept': accept_state = instance
    
        # # Creating workflow
        content_type = ContentType.objects.get_for_model(Task)
        workflow, _ = Workflow.objects.update_or_create(**validated_data,content_type=content_type, field_name="status", defaults={"initial_state": request_state})
    
        for stage_definition in workflow_definition.stages.all().order_by('order'):
            stage = Stage.objects.create(
                workflow=workflow,
                definition=stage_definition,
                name=stage_definition.name,
                order=stage_definition.order,
            )
            if stage_definition.order==0 : 
                WorkflowTrackingHelpers.mark_started(stage)
                #stage.assigned_to = workflow.assigned_to
                stage.save()
            # print("Tasks:",stage_definition.tasks.all().order_by('order'))

            for task_definition in stage_definition.tasks.all().order_by('order'):
                notify_meta_definitions = NotificationMetaDefinition.objects.filter(task__id=task_definition.id).order_by('time_interval')

                fields = [f.name for f in TaskDefinition._meta.get_fields()]
                ignored_fields = ["stage", "workflow", "id", "reminder_trigger_obj", "due_trigger_obj", "dependent_due", "dependent_reminder", "users", "groups", "permissions", "notification_meta", "task_definition_id"]
                capture_task_data = dict()

                for field in fields:
                    if field not in ignored_fields:
                        capture_task_data[field] = getattr(task_definition, field, None)

                content_type = ContentType.objects.get_for_model(Task)
                print('content_type:', content_type)
                workflow, _ = Workflow.objects.update_or_create(**validated_data,content_type=content_type, field_name="status",defaults={"initial_state": request_state})
            
                # workflow = Workflow.objects.create(**validated_data)
                print("workflow created:", workflow)
                # Creating TransitionMeta
                request_to_in_progress, _ = TransitionMeta.objects.update_or_create(workflow=workflow,source_state=request_state,destination_state=in_progress_state)
                in_progress_to_accept, _ = TransitionMeta.objects.update_or_create(workflow=workflow,source_state=in_progress_state,destination_state=accept_state)
                in_progress_to_deny, _ = TransitionMeta.objects.update_or_create(workflow=workflow,source_state=in_progress_state,destination_state=deny_state)
                deny_to_request, _ = TransitionMeta.objects.update_or_create(workflow=workflow, source_state=deny_state,destination_state=request_state)

                # if minimum_approvals_required != 0 , Creating TransitionApprovalMeta
                if task_definition.minimum_approvals_required != 0:

                    # CLOSING_MANAGER = Group.objects.get(name="CLOSING_MANAGER")
                    request_to_in_progress_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,    transition_meta=request_to_in_progress)
                    # request_to_in_progress_meta.users.set(task_definition.users.all())
                    # request_to_in_progress_meta.groups.set([CLOSING_MANAGER])
    
                    in_progress_to_accept_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,    transition_meta=in_progress_to_accept)
                    in_progress_to_accept_meta.users.set(task_definition.users.all())
                    in_progress_to_accept_meta.groups.set(task_definition.groups.all())
            
                    in_progress_to_deny_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,    transition_meta=in_progress_to_deny)
                    in_progress_to_deny_meta.users.set(task_definition.users.all())
                    in_progress_to_deny_meta.groups.set(task_definition.groups.all())
            
                    deny_to_request_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,    transition_meta=deny_to_request)
                    deny_to_request_meta.users.set(task_definition.users.all())
                    deny_to_request_meta.groups.set(task_definition.groups.all())


                due_trigger_obj = None
                reminder_trigger_obj = None

                if task_definition.due_flag and task_definition.due_trigger == "after_task" and task_definition.due_trigger_obj:
                    due_trigger_obj = Task.objects.filter(stage = stage, workflow = workflow, order = task_definition.due_trigger_obj.order).first()

                
                if task_definition.reminder_flag and task_definition.reminder_trigger =="after_task" and task_definition.reminder_trigger_obj:
                    reminder_trigger_obj = Task.objects.filter(stage = stage, workflow = workflow, order = task_definition.reminder_trigger_obj.order).first()

                task = Task.objects.create(
                    **capture_task_data, stage=stage, workflow=workflow, due_trigger_obj = due_trigger_obj,
                    reminder_trigger_obj=reminder_trigger_obj
                )
                task.users.set(task_definition.users.all())
                task.groups.set(task_definition.groups.all())
                # task.notification_meta.set(task_definition.notification_meta.all())
                if notify_meta_definitions and notify_meta_definitions.count() > 0:
                    for ind,notify_meta in enumerate(notify_meta_definitions):
                        task_notify_meta = NotificationMeta.objects.create(task=task,name=notify_meta.name,time_interval=notify_meta.time_interval)
                        task_notify_meta.groups.set(notify_meta.groups.all())
                        task_notify_meta.users.set(notify_meta.users.all())
                        task_notify_meta.save()
                        if ind==0:
                            task.current_notification_meta = task_notify_meta
                            task.save()

                print("task created!", task)
                #To mark 1st task as started
                # if task_definition.order==0: WorkflowTrackingHelpers.mark_started(task)

        WorkflowTrackingHelpers.mark_started(workflow)
        process_workflow.delay(workflow.pk)
        return workflow
    
class PaymentWorkflowCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workflow
        fields = [
            "name",
            "id",
            "workflow_type",
            "payment",
            "definition",
            "organization",
        ]

    def create(self, validated_data):
        workflow_definition = validated_data["definition"]
        # print("definition:", workflow_definition)

        # Creating states
        request_state, _ = State.objects.update_or_create(label="Request", slug="request")
        in_progress_state, _ = State.objects.update_or_create(label="In Progress", slug="in_progress")
        deny_state, _ = State.objects.update_or_create(label="Deny", slug="deny")
        accept_state, _ = State.objects.update_or_create(label="Accept", slug="accept")
        # TODO optimize
        # state_instances = State.objects.all()
        # request_state = in_progress_state = deny_state = accept_state = None
        # for instance in state_instances:
        #     if instance.slug == 'request': request_state = instance
        #     elif instance.slug == 'in_progress': in_progress_state = instance
        #     elif instance.slug == 'deny': deny_state = instance
        #     elif instance.slug == 'accept': accept_state = instance
    
        # # Creating workflow
        content_type = ContentType.objects.get_for_model(Task)
        workflow, _ = Workflow.objects.update_or_create(**validated_data,content_type=content_type, field_name="status", defaults={"initial_state": request_state})
    
        for stage_definition in workflow_definition.stages.all().order_by('order'):
            stage = Stage.objects.create(
                workflow=workflow,
                definition=stage_definition,
                name=stage_definition.name,
                order=stage_definition.order,
            )
            if stage_definition.order==0 : 
                WorkflowTrackingHelpers.mark_started(stage)
                #stage.assigned_to = workflow.assigned_to
                stage.save()
            # print("Tasks:",stage_definition.tasks.all().order_by('order'))

            for task_definition in stage_definition.tasks.all().order_by('order'):
                notify_meta_definitions = NotificationMetaDefinition.objects.filter(task__id=task_definition.id).order_by('time_interval')
                
                fields = [f.name for f in TaskDefinition._meta.get_fields()]
                ignored_fields = ["stage", "workflow", "id", "reminder_trigger_obj", "due_trigger_obj", "dependent_due", "dependent_reminder", "users", "groups", "permissions", "notification_meta", "task_definition_id"]
                capture_task_data = dict()

                for field in fields:
                    if field not in ignored_fields:
                        capture_task_data[field] = getattr(task_definition, field, None)

                content_type = ContentType.objects.get_for_model(Task)
                print('content_type:', content_type)
                workflow, _ = Workflow.objects.update_or_create(**validated_data,content_type=content_type, field_name="status",defaults={"initial_state": request_state})
            
                # workflow = Workflow.objects.create(**validated_data)
                print("workflow created:", workflow)
                # Creating TransitionMeta
                request_to_in_progress, _ = TransitionMeta.objects.update_or_create(workflow=workflow,source_state=request_state,destination_state=in_progress_state)
                in_progress_to_accept, _ = TransitionMeta.objects.update_or_create(workflow=workflow,source_state=in_progress_state,destination_state=accept_state)
                in_progress_to_deny, _ = TransitionMeta.objects.update_or_create(workflow=workflow,source_state=in_progress_state,destination_state=deny_state)
                deny_to_request, _ = TransitionMeta.objects.update_or_create(workflow=workflow, source_state=deny_state,destination_state=request_state)

                # if minimum_approvals_required != 0 , Creating TransitionApprovalMeta
                if task_definition.minimum_approvals_required != 0:
                    print("Task definition: ",task_definition.groups.all(),task_definition.users.all())     
                    # CLOSING_MANAGER = Group.objects.get(name="CLOSING_MANAGER")
                    request_to_in_progress_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,transition_meta=request_to_in_progress)
                    # request_to_in_progress_meta.users.set(task_definition.users.all())
                    # request_to_in_progress_meta.groups.set([CLOSING_MANAGER])
    
                    in_progress_to_accept_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,transition_meta=in_progress_to_accept)
                    in_progress_to_accept_meta.users.set(task_definition.users.all())
                    in_progress_to_accept_meta.groups.set(task_definition.groups.all())
            
                    in_progress_to_deny_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,transition_meta=in_progress_to_deny)
                    in_progress_to_deny_meta.users.set(task_definition.users.all())
                    in_progress_to_deny_meta.groups.set(task_definition.groups.all())
            
                    deny_to_request_meta, _ = TransitionApprovalMeta.objects.update_or_create(workflow=workflow,transition_meta=deny_to_request)
                    deny_to_request_meta.users.set(task_definition.users.all())
                    deny_to_request_meta.groups.set(task_definition.groups.all())


                due_trigger_obj = None
                reminder_trigger_obj = None

                if task_definition.due_flag and task_definition.due_trigger == "after_task" and task_definition.due_trigger_obj:
                    due_trigger_obj = Task.objects.filter(stage = stage, workflow = workflow, order = task_definition.due_trigger_obj.order).first()

                
                if task_definition.reminder_flag and task_definition.reminder_trigger =="after_task" and task_definition.reminder_trigger_obj:
                    reminder_trigger_obj = Task.objects.filter(stage = stage, workflow = workflow, order = task_definition.reminder_trigger_obj.order).first()

                task = Task.objects.create(
                    **capture_task_data, stage=stage, workflow=workflow, due_trigger_obj = due_trigger_obj,
                    reminder_trigger_obj=reminder_trigger_obj
                )
                task.users.set(task_definition.users.all())
                task.groups.set(task_definition.groups.all())

                if notify_meta_definitions and notify_meta_definitions.count() > 0:
                    for ind,notify_meta in enumerate(notify_meta_definitions):
                        task_notify_meta = NotificationMeta.objects.create(task=task,name=notify_meta.name,time_interval=notify_meta.time_interval)
                        task_notify_meta.groups.set(notify_meta.groups.all())
                        task_notify_meta.users.set(notify_meta.users.all())
                        task_notify_meta.save()
                        if ind==0:
                            task.current_notification_meta = task_notify_meta
                            task.save()
                            
                # task.notification_meta.set(task_definition.notification_meta.all())
                print("task created!", task)
                #To mark 1st task as started
                # if task_definition.order==0: WorkflowTrackingHelpers.mark_started(task)

        WorkflowTrackingHelpers.mark_started(workflow)
        process_workflow.delay(workflow.pk)
        return workflow
    
class StageSerializer(serializers.ModelSerializer):
    tasks = serializers.SerializerMethodField()
    
    def get_tasks(self, instance):
        task_list = instance.tasks.all().order_by('order')
        return TaskSerializer(task_list, many = True).data

    class Meta:
        model = Stage
        fields = [
            "id",
            "name",
            "order",
            "tasks",
            "started_at",
            "started",
            "completed",
            "completed_at",
            "workflow"
        ]
        extra_kwargs = {
            'workflow' : {'write_only' : True}
        }


class WorkflowSerializer(serializers.ModelSerializer):
    #lead = NewLeadSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    stages = serializers.SerializerMethodField()

    def get_stages(self, instance):
        stage_list = instance.stages.all().order_by('order')
        return StageSerializer(stage_list, many = True).data

    class Meta:
        model = Workflow
        fields = [
            "id",
            "name",
            "workflow_type",
            "lead",
            "definition",
            "assigned_to",
            "organization",
            "stages",
            "started_at",
            "started",
            "completed",
            "completed_at",
            "current_stage",
            "current_task",
        ]   

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "name",
            "order",
            "task_type",
            "due_count",
            "due_count",
            "due_period",
            "due_trigger",
            "due_trigger_obj",
            "due_flag",
            "reminder_count",
            "reminder_period",
            "reminder_trigger",
            "reminder_trigger_obj",
            "reminder_flag",
            "send_automatically",
            "action",
            "is_flagged",
            # "email_template",
            "is_reminder_flagged",
            "reminder_sent",
            "is_action_sent",
            "started_at",
            "started",
            "completed",
            "completed_at",
            "stage",
            "workflow",
            "lead",
            "lead_id",
            "stage_name",
            "appointment_with",
            "appointment_type",
            "time",
            "contact_number",
            "email",
            "details",
            "groups",
            "users",
            "status"
        ]

        optional_fields = ['owner','due_trigger_obj','reminder_trigger_obj' ]

        extra_kwargs = {
            'workflow' : {'write_only' : True},
            'lead': {'read_only':True}
        }

    lead = serializers.SerializerMethodField( read_only=True)

    def get_lead(self,obj):
        return obj.workflow.lead.first_name + " " + obj.workflow.lead.first_name
    
    lead_id = serializers.SerializerMethodField( read_only=True)

    def get_lead_id(self,obj):
        return obj.workflow.lead.id

    stage_name = serializers.SerializerMethodField(read_only=True)
    def get_stage_name(self,obj):
        return obj.stage.name
    
    groups = serializers.SerializerMethodField(read_only=True)
    def get_groups(self, obj):
        return [group.name for group in obj.groups.all()]
    
    status = serializers.SerializerMethodField(read_only=True)
    def get_status(self, obj):
        return obj.status.label
    
    # users = serializers.SerializerMethodField(read_only=True)
    # def get_users(self, obj):
    #     return [f"{user.name} - {user.mobile}" for user in obj.users.all()]
    
    def update(self, instance, validated_data):
        if 'completed' in validated_data and validated_data['completed']:
            print('validated_data:', validated_data)
            instance.completed = True
            instance.completed_at = timezone.now()
            instance.save()

        if validated_data.get('order', None):
            order = validated_data.pop('order')
            counter = order
            if instance.order != order:
                if instance.due_flag and instance.dependent_due.all().exists() or instance.reminder_flag and instance.dependent_reminder.all().exists():
                    raise serializers.ValidationError("Triggers are attached to it so can't change the position, remove the triggers to update order")

                if (instance.due_flag and instance.due_trigger_obj and instance.due_trigger_obj.order >= order) or (instance.reminder_flag and instance.reminder_trigger_obj and instance.reminder_trigger_obj.order >= order):
                    raise serializers.ValidationError("Trigger task order is greater then the order to be updated")
            if instance.order > order:
                workflow = instance.workflow
                query_list = workflow.flattened_tasks.filter(order__gte = order, order__lt = instance.order).order_by('order')
                for task in query_list:
                    counter +=1
                    task.order = counter
                    task.save()                    
            elif instance.order < order:
                workflow = instance.workflow
                query_list = workflow.flattened_tasks.filter(order__lte = order, order__gt = instance.order).order_by('-order')
                for task in query_list:
                    counter -=1
                    task.order = counter
                    task.save()      
            
            instance.order = order
            instance.save()
        print('fine------------------------------------here')
        return super().update(instance, validated_data)

class ApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransitionApproval
        fields = (
            'id',
            'created_at',
            'transition',
            'object_id',
            'meta',
            'user',
            # Add other fields you want to include in the response
        )

    def to_representation(self, instance):
        # Customize how the data is represented in the JSON response
        data = super().to_representation(instance)
        # You can add more customization here if needed
        return data


class NotificationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notifications
        fields = '__all__'