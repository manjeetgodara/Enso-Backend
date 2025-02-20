import random
from django.core.management.base import BaseCommand
from activity.models import SiteVisit
from datetime import date, timedelta
from workflow.models import *

class Command(BaseCommand):
    help = 'Mark old site visits as missed'

    def handle(self, *args, **kwargs):
        # get all site visits which are scheduled & date is missed 
        site_visits = SiteVisit.objects.filter(site_visit_status='Scheduled', visit_date__lt=date.today())

        notify_user = Users.objects.filter(groups__name='SITE_HEAD').first()

        # update the status of site visits to 'Missed'
        for visit in site_visits:
            visit.site_visit_status = 'Missed'
            visit.save()
            # Notifications.objects.create(notification_id=f"task-site-visit-{visit.id}-{notify_user.id}", user_id=notify_user,created=timezone.now(), notification_message=f"{visit.lead.first_name} {visit.lead.last_name}'s site visit has been missed.")

            title = "Site Visit Missed."
            body = f"{visit.lead.first_name} {visit.lead.last_name}'s site visit has been missed."
            data = {'notification_type': 'site_visit_missed'}

            fcm_token = notify_user.fcm_token

            Notifications.objects.create(notification_id=f"sv-{visit.id}-{notify_user.id}", user_id=notify_user,created=timezone.now(), notification_message=body)

            # Send push notification using your existing method
            send_push_notification(fcm_token, title, body, data)

        self.stdout.write(self.style.SUCCESS('Previous site visits marked as Missed successfully.'))