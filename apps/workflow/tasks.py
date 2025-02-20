# from celery.decorators import task
from datetime import datetime, timedelta
from django.utils import timezone
from config.celery import app

# from emails.utils import SendEmailFromTemplate, get_gmail_service,get_creds
from .models import Workflow, Task, Stage
from .utils import get_due_date_from_task
from django.db.models import Q
from django.shortcuts import get_object_or_404
from river.models import State
from auth.models import Users

from django.contrib.auth import get_user_model



@app.task
def process_task_update(task_id):
    print("automation-trigger:",task_id)
    try:
        task = Task.objects.get(id=task_id)
    except Exception as e:
        print(e)
        return
    
    if task.stage.is_complete:
        print("Stage Completed, ", task.stage)
        next_stage = Stage.objects.filter(order__gt = task.stage.order, workflow = task.workflow, completed=False).order_by('order').first()
        task.workflow.current_stage = next_stage.order
        task.workflow.save()
        if next_stage:
            next_stage.started = True
            next_stage.started_at = timezone.now()
            next_stage.save()
            first_task = next_stage.tasks.filter(completed=False).order_by('order').first()
            process_task.delay(first_task.id)
        else:
            print("Workflow Completed, Bye", task.workflow)
            workflow = task.workflow
            workflow.completed = True
            workflow.completed_at = timezone.now()
            workflow.save()

    else:
        dependent_due_id = task.dependent_due.filter(completed=False).values_list('id', flat=True)

        dependent_reminder_id = task.dependent_reminder.filter(completed=False).values_list('id', flat=True)

        dependent_id = dependent_due_id.union(dependent_reminder_id)

        print(dependent_id)

        for taskID in dependent_id:
            process_task.delay(taskID)
        
        next_task_in_order = Task.objects.filter(order__gt = task.order, reminder_flag=False, due_flag=False , stage=task.stage, completed=False).exclude(id__in = dependent_id).first()

        workflow = task.workflow
        workflow.current_task = next_task_in_order.order
        workflow.save()
        
        # if minimum_approvals_required = 0 , setting task to 'Accept' state.
        if next_task_in_order and next_task_in_order.minimum_approvals_required == 0:
            state = get_object_or_404(State, label='Accept')
            next_task_in_order.status = state
            next_task_in_order.save()
        elif next_task_in_order:
            process_task.delay(next_task_in_order.id)





@app.task
def process_task(task_id):
    try:
        task = Task.objects.get(id=task_id)
    except Exception as e:
        print(e)
        return
    
    print('Task Status:', task.status)
    if task.status != 'Accept':
        return
    
    if task.completed:
        return 

    print("starting task processing for", task)

    if not task.started:
        task.started = True
        task.started_at = timezone.now()
        # next_state = get_object_or_404(State, pk=5)
        # print('next_state:', next_state)
        # task.river.status.approve(next_state=next_state)
        # del task.skip_history_when_saving
        task.save()

    if task.task_type == "stage_start" or task.task_type == "stage_end":
        return 
    elif task.task_type == "todo":
        # check for whether the due date is supposed to be flagged
        # if to be flagged, check whether the time has passed
        # if not, call the process_workflow celery task to be run at that time
        if task.reminder_flag:
            args = dict()
            args[task.reminder_period] = task.reminder_count
            reminder_delta = timedelta(**args)
            time_start = timezone.now()
            if task.reminder_trigger == "after_task_start":
                time_start = task.started_at
            elif task.reminder_trigger == "after_task" and task.due_trigger_obj:
                time_start = task.due_trigger_obj.started_at
            
            reminder_date = time_start + reminder_delta

            print("got reminder date", reminder_date)

            if reminder_date > timezone.now():
                process_task.apply_async((task.id,), eta=reminder_date)
            else:
                task.is_reminder_flagged = True
                task.save()

        if task.due_flag:
            due_date = get_due_date_from_task(task)
            print("got due date", due_date)
            now = timezone.now()
            if due_date > now:
                process_task.apply_async((task.id,), eta=due_date)
            else:
                task.is_flagged = True
                task.save()
        return 
    elif task.task_type == "automation":
        # next_state = get_object_or_404(State, pk=5)
        # print('next_state:', next_state)
        # task.status = next_state
        # task.save()

        print("in auto", task.send_automatically)
        if task.send_automatically:
            due_date = get_due_date_from_task(task)
            print("got due date", due_date)
            now = timezone.now()
            if due_date > now:
                print('adding task in queue & will trigger at:', due_date)
                process_task.apply_async((task.id,), eta=due_date)
            else:
                print('Marking task as completed & perform action')
                # todo
                if task.action == "send_mail":
                    # send the mail
                    workflow = task.workflow
                    lead = workflow.lead
                    client = lead.client
                    context_data = {
                        "LeadName": lead.name,
                        "ClientName": client.name,
                        "Organization": workflow.organization.name,
                        "SalesManager": workflow.assigned_to.name,
                    }
                    print("context data is", context_data)
                    reply_to = []
                    service=None
                    
                    User = get_user_model()
                    first_user = User.objects.filter(organization = workflow.organization).first()
                    if first_user and first_user.gmail_connected:
                        # service = get_gmail_service(get_creds(first_user))
                        print('get_email_service_creds:', service)
                        reply_to = 'me'
                    elif workflow.organization.email:
                        reply_to.append(workflow.organization.email)
                        print(reply_to)

                    # SendEmailFromTemplate(
                    #     task.email_template, [client.email], context_data, reply_to, service=service
                    # )
                    print("celery_email_sent:",task.email_template, [client.email], context_data, reply_to, service=service)

                    task.completed = True
                    task.completed_at = timezone.now()                       
                    task.save()
                    
                elif task.action == "send_contract":
                    return 
                else:
                    return 
        else:
            return 

    else:
        print("here")
        return 



   



@app.task
def process_workflow(workflow_id):
    try:
        workflow = Workflow.objects.get(id=workflow_id)
    except Exception as e:
        print(e)
    else:
        first_stage = workflow.stages.all().order_by('order').first()
        workflow.started = True
        workflow.started_at = timezone.now()
        workflow.save()
        first_stage.started = True
        first_stage.started_at = timezone.now()
        first_stage.save()
        # first_task = first_stage.tasks.filter(
        #                     Q(reminder_flag=True, reminder_trigger = "after_task_start") | 
        #                     Q(due_flag = True, due_trigger = "after_task_start"), completed=False).order_by('order').first()
        first_task = first_stage.tasks.filter(completed=False).order_by('order').first()
        process_task(first_task.id)

