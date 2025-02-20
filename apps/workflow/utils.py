from datetime import datetime, timedelta
from django.utils import timezone
from auth.models import Users
from river.models import Workflow
from river.models import *

def get_due_date_from_task(task):
    args = dict()
    args[task.due_period] = task.due_count
    due_delta = timedelta(**args)
    print('due_delta:', due_delta)
    time_start = timezone.now()
    print('time_start:', time_start)
    if task.due_trigger == "after_task_start":
        time_start = task.started_at
    elif task.due_trigger == "after_task" and task.due_trigger_obj:
        time_start = task.due_trigger_obj.started_at

    return time_start + due_delta


class WorkflowTrackingHelpers:
    @staticmethod
    def mark_started(entity):
        """
        Sets the values when starting Workflow, Stage Task etc
        """
        print("setting started", entity)
        entity.started = True
        entity.started_at = timezone.now()
        return entity.save()

    @staticmethod
    def mark_complete(entity):
        """
        Marks the entity as complete for tracking
        """
        print("setting completed")
        entity.completed = True
        entity.completed_at = timezone.now()
        return entity.save()

def get_users_with_approval_access(task):
    # Get users from groups
    users_from_groups = Users.objects.filter(groups__in=task.groups.all())

    # Get individual users assigned to the task
    individual_users = task.users.all()

    # Combine both sets to get unique users for this approval
    all_approving_users = users_from_groups.union(individual_users)

    return all_approving_users                    
from workflow.models import Task
def reset_task_approval_status(task_id):
    print('reset_task_approval_status', task_id)

    task = Task.objects.get(id=task_id)

    transitions = Transition.objects.filter(
        object_id=task_id,
    )

    # source_state=initial_state,
    # destination_state=previous_state,

    # Reset approval status to "Pending" for each transition
    print('transitions inside reset function:', transitions)

    for transition in transitions:
        # Fetch the existing TransitionApproval
        old_approval = TransitionApproval.objects.get(transition=transition.id)
        print("OLD APPROVAL: ", old_approval,"Transition: ",transition, "old_approval transition", old_approval.transition)
        # Create new TransitionApproval based on the existing one
        new_approval = TransitionApproval.objects.create(
            workflow=old_approval.workflow,
            workflow_object=old_approval.workflow_object,
            transition=old_approval.transition,
            priority=old_approval.priority,
            meta=old_approval.meta,
        )
        print("cycled_approval Transition_approval: ",new_approval)
        print("old_approval.permissions.all(): ",task.permissions.all())
        print("old_approval.groups.all(): ",task.groups.all())   
        print("old_approval.users.all(): ",task.users.all()) 
        new_approval.permissions.set(task.permissions.all())
        new_approval.groups.set(task.groups.all())
        new_approval.users.set(task.users.all())
        old_approval.delete()