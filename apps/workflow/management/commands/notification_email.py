from datetime import datetime, timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from workflow.models import *
# from workflow.services import email_services
# from workflow.templates import email_template_task

class Command(BaseCommand):

    help = 'Find notification and save it in a table and send an email'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        """
        Find notifications and save it in a table and send an email.
        """

        today = timezone.now()
        # print('today:', today)
        # task_rem = Task.objects.filter(due_flag=False,time__gt=(today- timedelta(hours=5, minutes=30)),time__lt=(today+timedelta(1)- timedelta(hours=5, minutes=30)))
        task_rem = Task.objects.filter(completed=False,started=True).select_related('current_notification_meta')
        # print('task_rem:', task_rem, today,today+ timedelta(hours=5, minutes=30))
        for task in task_rem:
            
            if task.started_at and task.current_notification_meta and task.current_notification_meta.time_interval:
                print('task:', task.started_at, task.current_notification_meta.time_interval, today)
                if task.started_at + timedelta(hours=task.current_notification_meta.time_interval) <= today:
                    users_from_groups = Users.objects.filter(groups__in=task.current_notification_meta.groups.all())
            
                    # Get individual users assigned to the task
                    individual_users = task.current_notification_meta.users.all()
            
                    # Combine both sets to get unique users for this approval
                    total_users = users_from_groups.union(individual_users)
                    print('Notification trigger:', total_users)

                    if total_users and total_users.count() > 0:
                        # msg = ''
                        title=''
                        body=''
                        data = {'notification_type': 'reminder' , 'redirect_url': f'/pre_sales/all_leads'}
                        if task.name:
                            # msg = f"{task.name} pending for {task.appointment_with}"
                            title = f"{task.name} pending"
                            if task.name == "Site Visit":
                                body = f"{task.name} follow up is pending for {task.appointment_with}."
                            else:
                                body = f"{task.name} is pending for {task.appointment_with}."

                            if task.name == "Stamp Duty":
                                body = f"{task.name} document upload is pending for {task.appointment_with}."

                            if task.name == "Registration Fees":
                                body = f"{task.name} document upload is pending for {task.appointment_with}."   

                        for user in total_users:
                            Notifications.objects.create(notification_id=f"task-{task.id}-{user.id}", user_id=user,created=timezone.now(), notification_message=body)
                
                            send_push_notification(user.fcm_token, title, body, data)

                        task.current_notification_meta.completed = True
                        task.current_notification_meta.completed_at = timezone.now()
                        task.current_notification_meta.save()
                task_notify_meta = NotificationMeta.objects.filter(task=task,completed=False).order_by('time_interval').first()
                print('task_notify_meta:', task_notify_meta)
                if task_notify_meta:
                    task.current_notification_meta = task_notify_meta
                    task.save()
                else:
                    task.current_notification_meta = None
                    task.save()
            # print('task_notify_meta:', task_notify_meta)
        # for task in task_rem:
        #     if not Notifications.objects.filter(notification_id=f"task-{task.id}").exists():
        #         print("Adding New Tasks")
        #         Notifications.objects.create(notification_id=f"task-{task.id}", user_id=task.workflow.assigned_to)


        #Temp -----------------------------------------------------------------------------------
        # today = datetime.today().date()
        # task_rem = Task.objects.filter(due_flag=False,time__gt=(today- timedelta(hours=5, minutes=30)),time__lt=(today+timedelta(1)- timedelta(hours=5, minutes=30)))
        # for task in task_rem:
        #     # Access the notification_recipients field to get the list of user IDs
        #     recipients = task.notification_recipients

        #     for user_id in recipients:
        #         notification_id = f"task-{task.id}-{user_id}"

        #         # Check if the notification with the ID format already exists
        #         if not Notifications.objects.filter(notification_id=notification_id).exists():
        #             print("Adding New Notification")
        #             Notifications.objects.create(notification_id=notification_id, user_id=user_id)
        #-----------------------------------------------------------------------------------------
        
        #send email -TODO
        # emails = Notifications.objects.filter(created__date=today, email=False)
        # for email in emails:
        #     if (email.notification_id).split("-")[0]=="task":
        #         try:
        #             subject = f"About {email.notification_type}"
        #             taskId = (email.notification_id).split("-")[1]
        #             broker_name = (email.broker_id.name).split(" ")[0]
        #             taskObj = Task.objects.get(id=taskId)
        #             redirLink = email_services.create_redirect_url(f"/lead/{taskObj.workflow.lead.id}")

        #             keyValueDict = {}
        #             for key in email_template_task.replace_list:
        #                 keyValueDict[key] = ""

        #             keyValueDict["{user-name}"] = broker_name
        #             keyValueDict["{meeting-with}"] = str(taskObj.appointment_with)
        #             keyValueDict["{follow-up-date}"] = str((taskObj.time + timedelta(hours=5, minutes=30)).strftime("%d %b %Y"))
        #             keyValueDict["{starting-time}"] = str((taskObj.time + timedelta(hours=5, minutes=30)).strftime("%I:%M %p"))
        #             keyValueDict["{redirect-link}"] = redirLink

        #             email_body = email_services.set_email_body(keyValueDict, email_template_task.email_conf)
        #             to_email =email.broker_id.email
        #             email_services.send_email(subject=subject,message=email_body,to_email=to_email)
        #             print(f"send mail to {to_email}")
        #             email.email = True
        #             email.save()
        #         except Exception as ex:
        #             print(str(ex))
        #             pass



        