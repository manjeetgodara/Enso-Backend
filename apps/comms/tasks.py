from celery import shared_task
from workflow.models import *
from lead.models import Lead,Updates
from inventory.models import ProjectDetail,ProjectCostSheet,InventoryCostSheet
from rest_framework import status
import requests
from auth.utils import ResponseHandler


@shared_task()
def send_demand_letters(project_id, event_id):
    try:
        project = ProjectDetail.objects.get(id=project_id)
    except ProjectDetail.DoesNotExist:
        return ResponseHandler(
            True, "Project does not exist", None, status.HTTP_400_BAD_REQUEST
        )

    try:
        project_cost_sheet = ProjectCostSheet.objects.get(
            project=project, id=event_id, event_status="Done"
        )
        event_order = project_cost_sheet.event_order
        if not project_cost_sheet.due_date:
            return ResponseHandler(
                True,
                "ProjectCostSheet Due Date is not marked",
                None,
                status.HTTP_400_BAD_REQUEST,
            )
    except ProjectCostSheet.DoesNotExist:
        return ResponseHandler(
            True,
            'Event not found or not marked as "Done" in ProjectCostSheet',
            None,
            status.HTTP_400_BAD_REQUEST,
        )

    stage = Stage.objects.filter(name="PostSales").first()
    post_sales_leads = Lead.objects.filter(
        workflow__current_stage=stage.order,
        inventorycostsheet__event_order=event_order,
        inventorycostsheet__payment_in_percentage__gt=0,
        primary_email__isnull=False,
    ).distinct()

    for lead in post_sales_leads:
        updates_record, created = Updates.objects.get_or_create(lead=lead)
        inventory_instance = InventoryCostSheet.objects.filter(
            lead=lead, event_order=event_order
        ).first()
        if inventory_instance:
            email_id = lead.primary_email
            lead_name = f"{lead.first_name} {lead.last_name}"
            company_name = lead.organization.name
            due_date = str(project_cost_sheet.due_date.date())
            amount = int(inventory_instance.total_amount)
            send_demand_letter = True

            if updates_record and updates_record.slab:
                if updates_record.slab.event_order > project_cost_sheet.event_order:
                    send_demand_letter = False

            if email_id and due_date and amount and send_demand_letter:
                response = requests.post(
                    "http://3.111.78.151:81/api/email/sendmail/",
                    headers={
                        "Authorization": "token 43fb69c07ff4d2ec5b75bfa16638588a8606e199",
                        "Content-Type": "application/json",
                    },
                    json={
                        "template_id": 21,
                        "email": email_id,
                        "parameters": {
                            "username": lead_name,
                            "company_name": company_name,
                            "due_date": due_date,
                            "amount": amount,
                            "project_name": project.name,
                            "apartment_name": inventory_instance.inventory.apartment_no,
                        },
                    },
                )

                if response.status_code == 200:
                    if (
                        not updates_record.slab
                        or updates_record.slab.event_order
                        < project_cost_sheet.event_order
                    ):
                        updates_record.demand_letter_status = "Sent"
                        updates_record.slab = project_cost_sheet
                        updates_record.save()
    return ResponseHandler(
        False, "Demand letters sent successfully", None, status.HTTP_200_OK
    )
