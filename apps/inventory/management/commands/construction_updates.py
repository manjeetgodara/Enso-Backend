import datetime
from django.core.management.base import BaseCommand
from inventory.models import ProjectDetail
from firebase_admin import firestore
from django.conf import settings
from datetime import datetime,timedelta

class Command(BaseCommand):

    help = 'Update construction project details'

    def handle(self, *args, **kwargs):
 
        current_date = datetime.now().date().isoformat()

 
        for project_detail in ProjectDetail.objects.all():
 
            # for project_cost_sheet in project_detail.projectcostsheet_set.filter(event_status="Pending").order_by('event_order'):
            project_cost_sheet_current =  project_detail.projectcostsheet_set.filter(event_status="Pending").order_by('event_order').first()
            print("current_cost_sheet: ", project_cost_sheet_current)
            if project_cost_sheet_current:

                fr_data = {
                    "open_popup": True,
                    "date": current_date,
                    "event_name": project_cost_sheet_current.event,
                    "event_id": project_cost_sheet_current.id
                }
                print(f"construction update for Project : {project_detail.name} with current slab : {project_cost_sheet_current.event}")
                db = firestore.client(app=settings.FIREBASE_APPS['mcube'])
                fr_data_ref = db.collection('construction_updates').document(str(project_detail.id)).set(fr_data)
                
