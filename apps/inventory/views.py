from accounts.models import Payment
from workflow.serializers import PaymentWorkflowCreateSerializer
from river.models.workflow import WorkflowDefinition
from auth.models import Users
from comms.utils import send_push_notification
from auth.utils import ResponseHandler
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from .serializers import *
from .models import *
from rest_framework import generics
from rest_framework import status
from lead.decorator import check_group_access
from rest_framework.parsers import MultiPartParser
from lead.models import Lead
from lead.serializers import LeadSerializer
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Count
from workflow.models import Notifications
from django.db.models import Q
from django.db.models import Sum
from datetime import datetime,timedelta
from django.db.models import Sum
import pandas as pd
import os,json
import pdfkit
from django.template.loader import render_to_string
from django.conf import settings
from lead.models import *
from django.core.files import File
from .utils import reset_property_owner_and_inventory_cost_sheets
from workflow.utils import reset_task_approval_status
from django.shortcuts import get_object_or_404
from river.models import State
from activity.models import SiteVisit
from lead.pagination import CustomLimitOffsetPagination
from workflow.models import TaskDefinition 
class BookingFormCreateView(CreateAPIView):
    serializer_class = BookingFormSerializer
    permission_classes = (IsAuthenticated,)
     
    def create(self, request, *args, **kwargs):
        project = request.data.get('project')
        aprt_no = request.data.get('apartment_no')
        if project and aprt_no:
            try:
                # print('project_inventory:', request.data['apartment_no'],request.data['tower'])
                project_inventory = ProjectInventory.objects.get(tower__project=project,apartment_no=aprt_no)
                print("Project Inventory: ", project_inventory)
                # print('project_inventory:', project_inventory)
            except ProjectInventory.DoesNotExist:
                return ResponseHandler(True, "ProjectInventory not found for the given data", None, status.HTTP_400_BAD_REQUEST)
        else:
            return ResponseHandler(True, "'apartment_no' and project is required in the request data", None, status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            #next_view_link = "/api/collecttoken/"
            #return Response({"next_view": next_view_link}, status=status.HTTP_201_CREATED)
            #return redirect('collecttoken-create')
            lead = Lead.objects.filter(pk=request.data['lead_id']).first()
            lead_workflow = lead.workflow.get()
            booking_form_task = lead_workflow.tasks.filter(name='Booking Form').first()
            booking_form_task.completed = True
            booking_form_task.completed_at = timezone.now()
            booking_form_task.save()
            print('booking_form_task:', booking_form_task)
            return ResponseHandler(False," BookingForm is created", serializer.data, status.HTTP_201_CREATED)
        else:
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
        
    def get(self, request, *args, **kwargs):

        queryset = BookingForm.objects.all()
        if queryset.exists():
            serializer = self.get_serializer(queryset,many=True)
            return ResponseHandler(False,"Booking Form Data",serializer.data,status.HTTP_200_OK)
        else:
            return ResponseHandler(False, "There is no booking form data",[], status.HTTP_400_BAD_REQUEST)
        

class ProjectMetadataAPI(APIView):
    def get(self, request, *args, **kwargs):
        try:

            project_details = ProjectDetail.objects.values('id', 'name')


            project_details_with_towers = []
            for project_detail in project_details:
                project_detail['towers'] = list(
                    ProjectTower.objects.filter(project_id=project_detail['id']).values('id', 'name')
                )


                inventories_by_tower = {}

                project_inventories = ProjectInventory.objects.filter(Q(tower__project_id=project_detail['id'],status="Yet to book")|Q(tower__project_id=project_detail['id'],status="EOI"), in_progress = False).values(
                    'id', 'apartment_no', 'floor_number', 'configuration_id', 'tower__name', 'amount_per_car_parking', 'pre_deal_amount'
                )


                for inventory in project_inventories:
                    inventory["amount_per_car_parking"] = float(inventory["amount_per_car_parking"])
                    inventory["pre_deal_amount"] = float(inventory["pre_deal_amount"])
                    tower_name = inventory['tower__name']
                    if tower_name not in inventories_by_tower:
                        inventories_by_tower[tower_name] = []
                    inventories_by_tower[tower_name].append(inventory)


                project_detail['inventories'] = inventories_by_tower

                project_details_with_towers.append(project_detail)


            distinct_configurations = ProjectInventory.objects.values('configuration_id').annotate(
                configuration_count=Count('configuration_id')
            )


            configurations = Configuration.objects.filter(
                id__in=[config['configuration_id'] for config in distinct_configurations]
            ).values('id', 'name')
            # configurations = Configuration.objects.values('id', 'name')

            metadata = {
                'project_details': project_details_with_towers,
                'configurations': list(configurations),
            }

            return ResponseHandler(False, "Meta data retrieved successfully.", metadata, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, f"Error retrieving meta data: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)



class BookingFormDetailApiView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BookingFormSerializer
    permission_classes = (IsAuthenticated,)
    queryset = BookingForm.objects.all()

    def get(self, request, *args, **kwargs):
       bookingform_id = self.kwargs.get('pk')
       queryset = BookingForm.objects.filter(pk=bookingform_id)
       try:
            instance = BookingForm.objects.get(pk=bookingform_id)
            serializer = self.get_serializer(instance)
            return ResponseHandler(False, 'BookingForm retrieved successfully', serializer.data, status.HTTP_200_OK)
       except BookingForm.DoesNotExist:
            return ResponseHandler(True, 'BookingForm ID not found', None, status.HTTP_404_NOT_FOUND)

    def put(self,request, *args, **kwargs):
        bookingform_id = self.kwargs.get('pk')
        try:
            instance = self.queryset.get(pk=bookingform_id)
        except BookingForm.DoesNotExist:
            return  ResponseHandler(True, 'BookingForm not found', None, status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False , 'Data updated successfully' , serializer.data,status.HTTP_200_OK)
        else:
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        bookingform_id = self.kwargs.get('pk')
        try:
            instance = BookingForm.objects.get(pk=bookingform_id)
            self.perform_destroy(instance)
            return ResponseHandler(False, 'BookingForm deleted successfully' , None,status.HTTP_204_NO_CONTENT)
        except BookingForm.DoesNotExist:
            return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND)    


class BookingFormMetaDataAPIView(generics.RetrieveAPIView):
    queryset = Lead.objects.all()
    serializer_class = BookingFormMetaDataSerializer
    permission_classes = (IsAuthenticated,)

    @check_group_access(['ADMIN','CLOSING_MANAGER','SOURCING_MANAGER', 'SITE_HEAD', 'PROMOTER','VICE_PRESIDENT'])
    def retrieve(self, request, *args, **kwargs):
        try:
            FUNDING_CHOICES = [
                ('loan', 'Banking loan'),
                ('self fund', 'Self Funded'),
            ]
        
            MARITAL_STATUS= [
                ('Unmarried', 'UNMARRIED'),
                ('Married', 'MARRIED'),
                ('Widowed', 'WIDOWED'),
                ('Divorced', 'DIVORCED'),
            ]
        
            CORRESPONDANCE_CHOICES = [
                ('Residence', 'Residence'),
                ('Permanent', 'Permanent'),
            ]

            funding_choices = [
                status[0] for idx, status in enumerate(FUNDING_CHOICES)
            ]

            marital_choices = [
                gender[0] for idx, gender in enumerate(MARITAL_STATUS)
            ]

            correspondance_choices = [
                family[0] for idx, family in enumerate(CORRESPONDANCE_CHOICES)
            ]

            projects = ProjectDetail.objects.all()
            configurations = Configuration.objects.all()

            try:
                instance = self.get_object()
            except Exception as e:
                return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            print('instance:', instance)
            serializer = self.get_serializer(instance)
            project_details = serializer.data

            meta_data = {
                'funding_choices': funding_choices,
                'marital_choices': marital_choices,
                'correspondance_choices': correspondance_choices,
                'project_choices': ProjectDetailSerializer(projects, many=True).data if projects else None,
                'configurations_choices': ConfigurationSerializer(configurations, many=True).data if configurations else None,
                'project_details': project_details if project_details else None
            }

            return ResponseHandler(False, 'Booking form meta data retrieved successfully', meta_data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, str(e), None, status.HTTP_500_INTERNAL_SERVER_ERROR)


# class BookingFormSignatureView(APIView):
#     # permission_classes = [IsAuthenticated]
#     def get_booking_form(self, pk):
#         try:
#             return BookingForm.objects.get(pk=pk)
#         except BookingForm.DoesNotExist:
#             return None

#     def get(self, request, pk, *args, **kwargs):
#         booking_form = self.get_booking_form(pk)
#         if not booking_form:
#             return ResponseHandler(True, "Booking form not found", [], status.HTTP_404_NOT_FOUND)

#         serializer = BookingFormSignatureSerializer(booking_form)
#         return ResponseHandler(False, "Signature data retrieved successfully", serializer.data, status.HTTP_200_OK)    
    
#     def post(self, request, pk, *args, **kwargs):
#         try:
#             booking_form = BookingForm.objects.get(pk=pk)
#         except BookingForm.DoesNotExist:
#             return ResponseHandler(True,"Booking form not found",[],status.HTTP_404_NOT_FOUND)
#         serializer = BookingFormSignatureSerializer(booking_form, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False,"Signature saved successfully",None,status.HTTP_200_OK)
#         return ResponseHandler(True,"Bad Request",serializer.errors,status.HTTP_400_BAD_REQUEST)
#     def put(self, request, pk, *args, **kwargs):
#         booking_form = self.get_booking_form(pk)
#         if not booking_form:
#             return ResponseHandler(True, "Booking form not found", [], status.HTTP_404_NOT_FOUND)
#         serializer = BookingFormSignatureSerializer(booking_form, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False, "Signature updated successfully", None, status.HTTP_200_OK)
#         return ResponseHandler(True, "Bad Request", serializer.errors, status.HTTP_400_BAD_REQUEST)
#     def delete(self, request, pk, *args, **kwargs):
#         booking_form = self.get_booking_form(pk)
#         if not booking_form:
#             return ResponseHandler(True, "Booking form not found", [], status.HTTP_404_NOT_FOUND)
#         # Get which signature to delete from the request body
#         signature_type = request.data.get('signature_type')
#         if signature_type not in ['signature', 'client_signature', 'cm_signature', 'vp_signature', 'co_owner_signature']:
#             return ResponseHandler(True, "Invalid signature type", [], status.HTTP_400_BAD_REQUEST)
#         # Set the specified signature field to null
#         setattr(booking_form, signature_type, None)
#         booking_form.save()
#         return ResponseHandler(False, f"{signature_type.replace('_', ' ').title()} deleted successfully", None, status.HTTP_200_OK)


# class BookingFormSignatureView(APIView):
#     # permission_classes = [IsAuthenticated]

#     def get_booking_form_by_lead(self, lead_id):
#         try:
#             booking_form = BookingForm.objects.get(lead_id=lead_id)
#             print(booking_form.id)
#             return booking_form
#         except BookingForm.DoesNotExist:
#             return None

#     def get(self, request, lead_id, *args, **kwargs):
#         booking_form = self.get_booking_form_by_lead(lead_id)
#         if not booking_form:
#             return ResponseHandler(True, "Booking form not found", [], status.HTTP_404_NOT_FOUND)

#         serializer = BookingFormSignatureSerializer(booking_form)
#         return ResponseHandler(False, "Signature data retrieved successfully", serializer.data, status.HTTP_200_OK)    

#     def post(self, request, lead_id, *args, **kwargs):
#         booking_form = self.get_booking_form_by_lead(lead_id)
#         if not booking_form:
#             return ResponseHandler(True, "Booking form not found", [], status.HTTP_404_NOT_FOUND)

#         serializer = BookingFormSignatureSerializer(booking_form, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False, "Signature saved successfully", None, status.HTTP_200_OK)
#         return ResponseHandler(True, "Bad Request", serializer.errors, status.HTTP_400_BAD_REQUEST)

#     def put(self, request, lead_id, *args, **kwargs):
#         booking_form = self.get_booking_form_by_lead(lead_id)
#         if not booking_form:
#             return ResponseHandler(True, "Booking form not found", [], status.HTTP_404_NOT_FOUND)

#         serializer = BookingFormSignatureSerializer(booking_form, data=request.data, partial=True)
#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False, "Signature updated successfully", None, status.HTTP_200_OK)
#         return ResponseHandler(True, "Bad Request", serializer.errors, status.HTTP_400_BAD_REQUEST)

#     def delete(self, request, lead_id, *args, **kwargs):
#         booking_form = self.get_booking_form_by_lead(lead_id)
#         if not booking_form:
#             return ResponseHandler(True, "Booking form not found", [], status.HTTP_404_NOT_FOUND)

#         # Get which signature to delete from the request body
#         signature_type = request.data.get('signature_type')
#         if signature_type not in ['signature', 'client_signature', 'cm_signature', 'vp_signature', 'co_owner_signature']:
#             return ResponseHandler(True, "Invalid signature type", [], status.HTTP_400_BAD_REQUEST)

#         # Set the specified signature field to null
#         setattr(booking_form, signature_type, None)
#         booking_form.save()
#         return ResponseHandler(False, f"{signature_type.replace('_', ' ').title()} deleted successfully", None, status.HTTP_200_OK)



class ProjectCostSheetListCreateView(generics.ListCreateAPIView):
    queryset = ProjectCostSheet.objects.all()
    serializer_class = ProjectCostSheetSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = CustomLimitOffsetPagination
    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def create(self, request, *args, **kwargs):
        project_id = request.data.get('project')
        events_data = request.data.get('events', [])

        try:
            project = ProjectDetail.objects.get(pk=project_id)
        except ProjectDetail.DoesNotExist:
            return ResponseHandler(False, 'Project not found', None, status.HTTP_404_NOT_FOUND)

        # Create ProjectCostSheet instances
        created_events = []
        for event_data in events_data:
            event_data['project'] = project.id
            serializer = ProjectCostSheetSerializer(data=event_data)
            if serializer.is_valid():
                serializer.save()
                created_events.append(serializer.data)
            else:
                return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)

        return ResponseHandler(True, 'Events created successfully', created_events, status.HTTP_201_CREATED)
    
    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        project_id = self.request.query_params.get('project_id',None)
        search_param = self.request.query_params.get('search',None)
        if search_param:
            queryset = queryset.filter(project__name__icontains=search_param)
        if project_id:
            queryset = queryset.filter(project=project_id)
        queryset = queryset.order_by('id')

        if queryset.exists():
            sheets = self.paginate_queryset(queryset)
            serializer = ProjectCostSheetSerializer(sheets, many=True)
            data = self.get_paginated_response(serializer.data).data  
            return ResponseHandler(False,'Sheets retrieved successfully', data, status.HTTP_200_OK)
        else:
            page = self.paginate_queryset(queryset)
            dummy_data= self.get_paginated_response(page) 
            return ResponseHandler(True, 'No sheets found',dummy_data.data, status.HTTP_404_NOT_FOUND)

 
class ProjectCostSheetDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProjectCostSheet.objects.all()
    serializer_class = ProjectCostSheetSerializer
    permission_classes = (IsAuthenticated,)

    @check_group_access(['ADMIN',"PROMOTER","VICE_PRESIDENT",'CRM_HEAD'])
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        sheet = serializer.data

        return ResponseHandler(False, 'Cost sheet event retrieved successfully', sheet, status.HTTP_200_OK)

    @check_group_access(['ADMIN',"PROMOTER","VICE_PRESIDENT",'CRM_HEAD'])
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data

        # Check for required documents before proceeding
        architect_certificate = data.get('architect_certificate')
        site_image = data.get('site_image')

        if not architect_certificate:
            return ResponseHandler(
                True,
                "Architect's certificate is required to update the cost sheet event.",
                None,
                status.HTTP_400_BAD_REQUEST
            )
        
        if not site_image:
            return ResponseHandler(
                True,
                "Site image is required to update the cost sheet event.",
                None,
                status.HTTP_400_BAD_REQUEST
            )
        
        existing_delayed_reason = instance.delayed_reasons if instance.delayed_reasons else []

        provided_delayed_reason = data.get('delayed_reasons',None)
        if provided_delayed_reason:
            if not isinstance(provided_delayed_reason, list):
                return ResponseHandler(False, "delayed_reasons must be a list", None, status.HTTP_400_BAD_REQUEST)

            if existing_delayed_reason:
                existing_delayed_reason.extend(provided_delayed_reason)
                data['delayed_reasons'] = existing_delayed_reason
            else:
                data['delayed_reasons'] = provided_delayed_reason

            title = "Construction is Delayed"
            body = f"Construction is Delayed due to {provided_delayed_reason[0]}"
            data = {'notification_type': 'key_transfer'}

            promoter_users = Users.objects.filter(groups__name="PROMOTER")
            for promoter_user in promoter_users:
                if promoter_user:
                    fcm_token_promoter = promoter_user.fcm_token
                    Notifications.objects.create(notification_id=f"task-{instance.id}-{promoter_user.id}", user_id=promoter_user,created=timezone.now(),  notification_message=body, notification_url=f'/post_sales/all_clients/')
                    send_push_notification(fcm_token_promoter, title, body, data)

            vp_users = Users.objects.filter(groups__name="VICE_PRESIDENT")
            for vp_user in vp_users:
                if vp_user:
                    fcm_token_vp = vp_user.fcm_token
                    Notifications.objects.create(notification_id=f"task-{instance.id}-{vp_user.id}", user_id=vp_user,created=timezone.now(),  notification_message=body, notification_url=f'/post_sales/all_clients/')
                    send_push_notification(fcm_token_vp, title, body, data)   

        provided_event_status = data.get('event_status',None)
        if provided_event_status and provided_event_status == "Done":
            completed_at_str = data.get('completed_at', None)
            if completed_at_str:
                try:
                    completed_at = datetime.strptime(completed_at_str, "%Y-%m-%dT%H:%M:%S")
                    data['completed_at'] = completed_at
                except ValueError:
                    return ResponseHandler(False, "Invalid date format for completed_at. Use 'YYYY-MM-DDTHH:MM:SS'.", None, status.HTTP_400_BAD_REQUEST)
            else:
                data['completed_at'] = timezone.now()
            
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False, 'Cost sheet event updated successfully', serializer.data, status.HTTP_200_OK)
        return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)

    @check_group_access(['ADMIN',"PROMOTER","VICE_PRESIDENT",'CRM_HEAD'])
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return ResponseHandler(False, 'Cost sheet event deleted successfully', None, status.HTTP_204_NO_CONTENT)
    

class GetInventoryCostSheetAPIView(generics.ListAPIView):
    queryset = InventoryCostSheet.objects.all()
    serializer_class = InventoryCostSheetSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        lead_id = self.request.query_params.get('lead_id')
        apartment_no = self.request.query_params.get('apartment_no')
        project_id = self.request.query_params.get('project_id')
        if lead_id:
            queryset = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=apartment_no, inventory__tower__project=project_id).order_by('event_order')
            if queryset.exists():
                return queryset
            else:
                return InventoryCostSheet.objects.none()

    # @check_group_access(['ADMIN', 'CLOSING_MANAGER', 'CRM_HEAD'])
    def list(self, request, *args, **kwargs):
        try:
            inventories = self.get_queryset()
            project_id = self.request.query_params.get('project_id')
    
            if not inventories:
                return ResponseHandler(True, 'Inventory not found', None, status.HTTP_404_NOT_FOUND)
    
            current_event_order = inventories[0].inventory.tower.project.current_event_order
            amount_per_car_parking = inventories[0].inventory.amount_per_car_parking
            car_parking = inventories[0].inventory.car_parking if inventories[0].inventory.car_parking else 0
            print('current_event_order:', current_event_order)
            inventory_owner = PropertyOwner.objects.filter(lead=request.query_params.get('lead_id')).first()
            print('inventory_owner:', inventory_owner)
    
            serializer = self.get_serializer(inventories, many=True)
            cost_sheets = serializer.data
    
            # slabs_done = ProjectCostSheet.objects.filter(event_order__gt=2,event_status='Done').order_by('event_order')
            # slabs_done = ProjectCostSheet.objects.filter(event_order__gt=2,event_status='Done',project=project_id).order_by('event_order')
            slabs_done = ProjectCostSheet.objects.filter(event_order__gt=1,payment_type="Installment",event_status='Done',project=project_id).order_by('event_order')
            print('slabs_done:', slabs_done)
    
            total_percentage = 0
    
            try:
                for slab in slabs_done:
                    total_percentage += slab.payment_in_percentage
            except Exception as e:
                return ResponseHandler(True, f"An error occurred while calculating total percentage: {str(e)}", None, status.    HTTP_404_NOT_FOUND)
            
            registration_fees = 0
            stamp_duty = 0
    
            for event in cost_sheets:
                if not event["event_order"] == 0 :
                    if event["event_order"] == 1:
                        print('event:', event["payment_in_percentage"], total_percentage)
                        event["payment_in_percentage"] = float(event["payment_in_percentage"]) 
                        print('event:', event["payment_in_percentage"])
                        # event["amount"] = inventory_owner.deal_amount * (float(event["payment_in_percentage"])/100) if     inventory_owner.deal_amount else 0
                        deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0.0
                        payment_percentage = float(event["payment_in_percentage"]) if event["payment_in_percentage"] else 0.0
    
                        event["amount"] = deal_amount * (payment_percentage / 100.0)
                        event["gst"] = float(event["amount"]) * 0.08
                        event["tds"] = float(event["amount"]) * 0.01
                        event["total_amount"] = float(event["amount"]) + float(event["gst"])
                    elif event["event"] == "Registration Fees":
                        registration_fees = event["amount"]  
                        event["amount"] = float(event["amount"]) if event["amount"] is not None else 0.0
                        event["total_amount"] = float(registration_fees) if registration_fees is not None else 0.0
                        event["payment_in_percentage"] = float(event["payment_in_percentage"])
                        print('registration_fees:', registration_fees, event)
                    elif event["payment_type"] == "Stamp Duty":
                        deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0.0
                        payment_percentage = float(event["payment_in_percentage"]) if event["payment_in_percentage"] else 0.0
    
                        event['amount'] = deal_amount * (payment_percentage / 100.0)
                        stamp_duty = event["amount"]
                        event["total_amount"] = float(stamp_duty) if stamp_duty is not None else 0.0
                        event["payment_in_percentage"] = 0
                        print('stamp_duty:', event["amount"], event,event["total_amount"])
                    elif event["event_order"] > current_event_order:
                        event["payment_in_percentage"] = float(event["payment_in_percentage"])
                        # event["amount"] = inventory_owner.deal_amount * (float(event["payment_in_percentage"])/100) if     inventory_owner.deal_amount else 0
    
                        deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0.0
                        payment_percentage = float(event["payment_in_percentage"]) if event["payment_in_percentage"] else 0.0
    
                        event["amount"] = deal_amount * (payment_percentage / 100.0)
                        event["gst"] = float(event["amount"]) * 0.08
                        event["tds"] = float(event["amount"]) * 0.01
                        event["total_amount"] = float(event["amount"]) + float(event["gst"])
                    elif event["event_order"] <= current_event_order:
                        event["payment_in_percentage"] = 0
            
            
    
            lead = Lead.objects.filter(pk=request.query_params.get('lead_id')).first()
            lead_data = LeadSerializer(lead, many=False)
            # print('lead_data:', lead_data)
    
            res = dict()
            res["lead"] = lead_data.data
            res["cost_sheet"] = serializer.data
            res["agreement_value"] = inventory_owner.deal_amount
            deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0
            registration_fees = float(registration_fees) if registration_fees else 0
            stamp_duty = float(stamp_duty) if stamp_duty else 0
            total_car_parking_amount = int(car_parking) * float(amount_per_car_parking)
            
            res["total_value"] = (deal_amount * 0.08) + deal_amount + registration_fees + total_car_parking_amount + stamp_duty
            res["current_slab_order"] = current_event_order
    
            return ResponseHandler(False, 'Inventory Cost sheet retrieved successfully', res, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class GetInventoryCostSheetAPIViewV2(generics.ListAPIView):
    queryset = InventoryCostSheet.objects.all()
    serializer_class = InventoryCostSheetSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        lead_id = self.request.query_params.get('lead_id')
        apartment_no = self.request.query_params.get('apartment_no')
        project_id = self.request.query_params.get('project_id')
        if lead_id:
            queryset = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=apartment_no, inventory__tower__project=project_id).order_by('event_order')
            if queryset.exists():
                return queryset
            else:
                return InventoryCostSheet.objects.none()

    # @check_group_access(['ADMIN', 'CLOSING_MANAGER', 'CRM_HEAD'])
    def list(self, request, *args, **kwargs):
        try:
            print('GetInventoryCostSheetAPIViewV2 trigger')
            project_id = self.request.query_params.get('project_id')
            inventories = self.get_queryset()
    
            if not inventories:
                return ResponseHandler(True, 'Inventory not found', None, status.HTTP_404_NOT_FOUND)
    
            current_event_order = inventories[0].inventory.tower.project.current_event_order
            amount_per_car_parking = inventories[0].inventory.amount_per_car_parking
            car_parking = inventories[0].inventory.car_parking if inventories[0].inventory.car_parking else 0
            print('current_event_order:', current_event_order)
            inventory_owner = PropertyOwner.objects.filter(lead=request.query_params.get('lead_id')).first()
            print('inventory_owner:', inventory_owner)
    
            serializer = self.get_serializer(inventories, many=True)
            cost_sheets = serializer.data
    
            # slabs_done = ProjectCostSheet.objects.filter(event_order__gt=2,event_status='Done',project=project_id).order_by('event_order')
            slabs_done = ProjectCostSheet.objects.filter(event_order__gt=1,payment_type="Installment",event_status='Done',project=project_id).order_by('event_order')
            print('slabs_done:', slabs_done)
    
            total_percentage = 0
    
            try:
                for slab in slabs_done:
                    total_percentage += slab.payment_in_percentage
            except Exception as e:
                return ResponseHandler(True, f"An error occurred while calculating total percentage: {str(e)}", None, status.    HTTP_404_NOT_FOUND)
            
            registration_fees = 0
            stamp_duty = 0

            costsheet_instances = []

            costsheet_instances.append(cost_sheets[0])
    
            for event,inventory in zip(cost_sheets,inventories):
                if not event["event_order"] == 0 :
                    if event["event_order"] == 1:
                        print('event:', event["payment_in_percentage"], total_percentage)
                        project_costsheet_first_event = ProjectCostSheet.objects.filter(event_order=1,project=project_id).first()
                        event["payment_in_percentage"] = float(project_costsheet_first_event.payment_in_percentage) + total_percentage
                        print('event:', event["payment_in_percentage"])
                        # event["amount"] = inventory_owner.deal_amount * (float(event["payment_in_percentage"])/100) if     inventory_owner.deal_amount else 0
                        deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0.0
                        payment_percentage = float(event["payment_in_percentage"]) if event["payment_in_percentage"] else 0.0
    
                        event["amount"] = round(deal_amount * (payment_percentage / 100.0),2)
                        event["gst"] = round(float(event["amount"]) * 0.08,2)
                        event["tds"] = round(float(event["amount"]) * 0.01,2)
                        event["total_amount"] = round(float(event["amount"]) + float(event["gst"]),2)
                    elif event["event"] == "Registration Fees":
                        registration_fees = event["amount"]
                        event["amount"] = float(event["amount"]) if event["amount"] is not None else 0.0
                        event["total_amount"] = float(event["amount"]) if event["total_amount"] is not None else 0.0
                        event["payment_in_percentage"] = float(event["payment_in_percentage"])
                        print('registration_fees:', registration_fees, event)
                    elif event["payment_type"] == "Stamp Duty":
                        deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0.0
                        stamp_duty_percentage = ProjectCostSheet.objects.filter(payment_type="Stamp Duty",project=project_id).first()
                        payment_percentage = float(stamp_duty_percentage.payment_in_percentage) if stamp_duty_percentage.payment_in_percentage else 0.0
    
                        event["amount"] = deal_amount * (payment_percentage / 100.0)
                        stamp_duty = event["amount"]
                        event["total_amount"] = float(event["amount"]) if event["total_amount"] is not None else 0.0
                        event["payment_in_percentage"] = 0
                        print('stamp_duty:', event["amount"], event,event["total_amount"])
                    elif event["event_order"] > current_event_order:
                        project_costsheet_event = ProjectCostSheet.objects.filter(event_order=event["event_order"],project=project_id).first()
                        # event["payment_in_percentage"] = float(event["payment_in_percentage"])
                        event["payment_in_percentage"] = float(project_costsheet_event.payment_in_percentage)
                        # event["amount"] = inventory_owner.deal_amount * (float(event["payment_in_percentage"])/100) if     inventory_owner.deal_amount else 0
    
                        deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0.0
                        payment_percentage = float(event["payment_in_percentage"]) if event["payment_in_percentage"] else 0.0
    
                        event["amount"] = round(deal_amount * (payment_percentage / 100.0),2)
                        event["gst"] = round(float(event["amount"]) * 0.08,2)
                        event["tds"] = round(float(event["amount"]) * 0.01,2)
                        event["total_amount"] = round(float(event["amount"]) + float(event["gst"]),2)
                    elif event["event_order"] <= current_event_order:
                        event["payment_in_percentage"] = 0
                        event["amount"] = 0.00
                        event["gst"] = 0.00
                        event["tds"] = 0.00
                        event["total_amount"] = 0.00
                    
                    # with HistoricalRecords.objects.disable_action():
                    serializer = self.get_serializer(inventory,data=event)
                    # inventory.skip_history_when_saving = True
                    if serializer.is_valid():
                        # print('serializer:', serializer)
                        serializer.save()
                        costsheet_instances.append(serializer.data)
                    else:
                        print('here')
                        print(f"Serializer errors:")
                        for field, errors in serializer.errors.items():
                            for error in errors:
                                print(f"\t- Field '{field}': {error}")
            
            
    
            lead = Lead.objects.filter(pk=request.query_params.get('lead_id')).first()
            lead_data = LeadSerializer(lead, many=False)
            # print('lead_data:', lead_data)
    
            res = dict()
            res["lead"] = lead_data.data
            res["cost_sheet"] = costsheet_instances
            res["agreement_value"] = inventory_owner.deal_amount
            deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0
            registration_fees = float(registration_fees) if registration_fees else 0
            stamp_duty = float(stamp_duty) if stamp_duty else 0
            total_car_parking_amount = int(car_parking) * float(amount_per_car_parking)
            
            res["total_value"] = (deal_amount * 0.08) + deal_amount + registration_fees + total_car_parking_amount + stamp_duty
            res["current_slab_order"] = current_event_order
            res["cost_sheet_deny_reason"] = inventory_owner.cost_sheet_deny_reason if inventory_owner.cost_sheet_deny_reason else None
    
            return ResponseHandler(False, 'Inventory Cost sheet retrieved successfully', res, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)


class InventoryCostSheetListCreateUpdateView(generics.ListCreateAPIView):
    serializer_class = InventoryCostSheetSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        lead_id = self.request.query_params.get('lead_id')
        apartment_no = self.request.query_params.get('apartment_no')
        project_id = self.request.query_params.get('project_id')
        if lead_id:
            queryset = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=apartment_no, inventory__tower__project=project_id).order_by('event_order')
            if queryset.exists():
                return queryset
            else:
                return InventoryCostSheet.objects.none()
        # return InventoryCostSheet.objects.all()

    def create(self, request, *args, **kwargs):
        inventory_id = request.data.get('inventory_id')
        events_data = request.data.get('events', [])

        try:
            inventory = ProjectInventory.objects.get(pk=inventory_id)
        except ProjectInventory.DoesNotExist:
            return ResponseHandler(True, 'Inventory not found', None, status.HTTP_404_NOT_FOUND)

        # Create InventoryCostSheet instances
        created_events = []
        for event_data in events_data:
            event_data['inventory'] = inventory.id
            serializer = InventoryCostSheetSerializer(data=event_data)
            if serializer.is_valid():
                serializer.save()
                created_events.append(serializer.data)
            else:
                return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)

        return ResponseHandler(False, 'Events created successfully', created_events, status.HTTP_201_CREATED)
    
    def list(self, request, *args, **kwargs):
        try:
            project_id = self.request.query_params.get('project_id')
            inventories = self.get_queryset()
            if not inventories:
                return ResponseHandler(False,"Inventory cost sheet not found for lead.",[], status.HTTP_200_OK)
    
            serializer = self.get_serializer(inventories, many=True)
            cost_sheets = serializer.data
    
            current_event_order = inventories[0].inventory.tower.project.current_event_order
            amount_per_car_parking = inventories[0].inventory.amount_per_car_parking
            car_parking = inventories[0].inventory.car_parking if inventories[0].inventory.car_parking else 0
            inventory_owner = PropertyOwner.objects.filter(lead=request.query_params.get('lead_id')).first()
            
            slabs_done = ProjectCostSheet.objects.filter(event_order__gt=1,payment_type="Installment",event_status='Done',project=project_id).order_by('event_order')
            # print('slabs_done:', slabs_done)
    
            total_percentage = 0
    
            try:
                for slab in slabs_done:
                    total_percentage += slab.payment_in_percentage
            except Exception as e:
                return ResponseHandler(True, f"An error occurred while calculating total percentage: {str(e)}", None, status.    HTTP_404_NOT_FOUND)
            
            registration_fees = 0
            stamp_duty = 0
    
            for event in cost_sheets:
                print(event["event_order"],event['amount'],event['payment_in_percentage'],event['amount_paid'],event['total_amount'],event['gst'],event['tds'])
                event["payment_in_percentage"] = float(event["payment_in_percentage"])
                event["amount"] = float(event["amount"]) if event["amount"] is not None else float("0.00")
                event["amount_paid"] = float(event['amount_paid']) if event['amount_paid'] is not None else float("0.00")
                event["gst"] = float(event["gst"]) if event["gst"] is not None else float("0.00")
                event["tds"] = float(event["tds"]) if event["tds"] is not None else float("0.00")
                event["total_amount"] = float(event["total_amount"]) if event["total_amount"] is not None else float("0.00")
                event['remaining_amount'] = float(event['remaining_amount']) if event['remaining_amount'] is not None else float("0.00")
                if event['event_order']==0:
                    event['amount_paid'] = event['total_amount'] if event['total_amount'] is not None else 0.0
                    event['completed'] =True 
                if not event["event_order"] == 0 :
                    if event["event_order"] == 1:
                        print('event:', event["payment_in_percentage"], total_percentage)
                        event["payment_in_percentage"] = float(event["payment_in_percentage"]) 
                        print(total_percentage)
                        deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0.0
                        payment_percentage = float(event["payment_in_percentage"]) if event["payment_in_percentage"] else 0.0
    
                        event["amount"] = deal_amount * (payment_percentage / 100.0)
                        event["gst"] = float(event["amount"]) * 0.08
                        event["tds"] = float(event["amount"]) * 0.01
                        event["total_amount"] = float(event["amount"]) + float(event["gst"])
                        event['remaining_amount'] = float(event['total_amount']) - float(event['amount_paid'])
                    elif event["event"] == "Registration Fees":
                        event["amount"] = float(event["amount"]) if event["amount"] is not None else 0.0
                        event["total_amount"] = float(event['amount']) if event['amount'] is not None else 0.0
                        event["payment_in_percentage"] = float(event["payment_in_percentage"]) if event['payment_in_percentage'] is not None else 0.0
                    elif event["event"] == "Stamp Duty":
                        deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0.0
                        payment_percentage = float(event["payment_in_percentage"]) if event["payment_in_percentage"] else 0.0
                        event['amount'] = deal_amount * (payment_percentage / 100.0)
                        event["total_amount"] = float(event['amount'])
                        event["payment_in_percentage"] = 0
                    elif event["event_order"] > current_event_order:
                        event["payment_in_percentage"] = float(event["payment_in_percentage"])
    
                        deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0.0
                        payment_percentage = float(event["payment_in_percentage"]) if event["payment_in_percentage"] else 0.0
    
                        event["amount"] = deal_amount * (payment_percentage / 100.0)
                        event["gst"] = float(event["amount"]) * 0.08
                        event["tds"] = float(event["amount"]) * 0.01
                        event["total_amount"] = float(event["amount"]) + float(event["gst"])
                    elif event["event_order"] <= current_event_order:
                        event["payment_in_percentage"] = 0
            
            
            lead = Lead.objects.filter(pk=request.query_params.get('lead_id')).first()
            lead_data = LeadSerializer(lead, many=False)
            # print('lead_data:', lead_data)
    
            res = dict()
            res["lead"] = lead_data.data
            res["cost_sheet"] = serializer.data
            res["agreement_value"] = inventory_owner.deal_amount
            deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0
            registration_fees = float(registration_fees) if registration_fees else 0
            stamp_duty = float(stamp_duty) if stamp_duty else 0
            total_car_parking_amount = int(car_parking) * float(amount_per_car_parking)
            
            # res["total_value"] = (deal_amount * 0.08) + deal_amount + registration_fees + total_car_parking_amount + stamp_duty
            res["total_value"] = round(((deal_amount * 0.08) + deal_amount + registration_fees + total_car_parking_amount),2)
            res["current_slab_order"] = current_event_order
            

            # lead = Lead.objects.filter(pk=request.query_params.get('lead_id')).first()
            # lead_data = LeadSerializer(lead, many=False)
            # # print('lead_data:', lead_data)
            
            # res = dict()
            # res["lead"] = lead_data.data
            # res["cost_sheet"] = serializer.data
            # res["agreement_value"] = inventory_owner.deal_amount
            # deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0
            # registration_fees = float(registration_fees) if registration_fees else 0
            # total_car_parking_amount = int(car_parking) * float(amount_per_car_parking)
            
            # res["total_value"] = round(((deal_amount * 0.08) + deal_amount + registration_fees + total_car_parking_amount),2)
            # res["current_slab_order"] = current_event_order        
            return ResponseHandler(False, 'Inventory cost sheet retrieved successfully', res, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, *args, **kwargs):
        events_data = request.data.get('events', [])
        total_value = request.data.get('total_value', None)

        try:
            event_ids = [event['id'] for event in events_data]

            # Fetch existing sheets
            existing_sheets = InventoryCostSheet.objects.filter(id__in=event_ids)
            print('events_data:', events_data)
            print('existing_sheets:', existing_sheets)

            for existing_sheet in existing_sheets:
                # Find the corresponding data from the request
                updated_data = next((event for event in events_data if event['id'] == existing_sheet.id), None)

                if updated_data:
                    # Update the existing sheet with new data
                    serializer = InventoryCostSheetSerializer(existing_sheet, data=updated_data)
                    if serializer.is_valid():
                        print('serializer:', serializer.errors)
                        serializer.save()
                    else:
                        return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
                    
            one_cost_sheet = existing_sheets.first()
            owner = PropertyOwner.objects.filter(property=one_cost_sheet.inventory, lead=one_cost_sheet.lead).first()
            if total_value:
                owner.total_value = total_value
                owner.save()
            print('owner:', owner)

            lead = Lead.objects.filter(pk=owner.lead.id).first()
            lead_workflow = lead.workflow.get()
            cost_sheet_task = lead_workflow.tasks.filter(name='Cost Sheet').first()

            if not cost_sheet_task.status == 'Accept':
                state = get_object_or_404(State, label='Accept')
                print('state:', state)
                cost_sheet_task.status = state

            cost_sheet_task.completed = True
            cost_sheet_task.completed_at = timezone.now()
            cost_sheet_task.save()
            
            if lead.creator and lead.creator.groups.filter(name="INQUIRY_FORM").exists():
                    print("inside inquiry data")
                    lead_workflow.current_stage =2
                    lead_workflow.current_task = 0
                    lead_workflow.save()    

            

            # generate cost_sheet PDF
            generate_form_pdf(lead_id=lead.id, cost_sheet_param=True)

            title = "Cost sheet created"
            body = f"Cost sheet created for '{owner.lead.first_name} {owner.lead.last_name}'."
            data = {'notification_type': 'collect_token', 'redirect_url': f'/sales/my_visit/lead_details/{owner.lead.id}/0'}

            # Fetch the FCM tokens associated with the Site Head SITE_HEAD
            users = []
            # sh_user = Users.objects.filter(groups__name="SITE_HEAD").first()
            # if sh_user:
            #     users.append(sh_user)

            vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
            if vp_user:
                users.append(vp_user)

            ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
            if ah_user:
                users.append(ah_user)

            for user in users:
                user_fcm_token = user.fcm_token
    
                Notifications.objects.create(notification_id=f"cost-sheet-{owner.id}-{user.id}",user_id=user,created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{owner.lead.id}/0')
    
                # Send push notification
                send_push_notification(user_fcm_token, title, body, data)


            return ResponseHandler(False, 'InventoryCostSheet updated successfully', None, status.HTTP_201_CREATED)

        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class CostSheetRequestApproval(generics.ListCreateAPIView):
    serializer_class = InventoryCostSheetSerializer
    permission_classes = (IsAuthenticated,)
    
    @check_group_access(['SITE_HEAD'])
    def post(self, request, *args, **kwargs):
        events_data = request.data.get('events', [])
        total_value = request.data.get('total_value', None)

        try:
            event_ids = [event['id'] for event in events_data]

            # Fetch existing sheets
            existing_sheets = InventoryCostSheet.objects.filter(id__in=event_ids)
            print('events_data:', events_data)
            print('existing_sheets:', existing_sheets)

            for existing_sheet in existing_sheets:
                # Find the corresponding data from the request
                updated_data = next((event for event in events_data if event['id'] == existing_sheet.id), None)

                if updated_data:
                    # Update the existing sheet with new data
                    serializer = InventoryCostSheetSerializer(existing_sheet, data=updated_data)
                    existing_sheet.skip_history_when_saving = True
                    if serializer.is_valid():
                        print('serializer:', serializer.errors)
                        serializer.save()
                    else:
                        return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
                    
            one_cost_sheet = existing_sheets.first()
            owner = PropertyOwner.objects.filter(property=one_cost_sheet.inventory, lead=one_cost_sheet.lead).first()
            if total_value:
                owner.total_value = total_value
                owner.save()
            print('owner:', owner)

            lead = Lead.objects.filter(pk=owner.lead.id).first()
            lead_workflow = lead.workflow.get()
            cost_sheet_task = lead_workflow.tasks.filter(name='Cost Sheet').first()
            # cost_sheet_task.completed = True
            # cost_sheet_task.completed_at = timezone.now()

            state = get_object_or_404(State, label='In Progress')
            print('state:', state)
            cost_sheet_task.status = state
            cost_sheet_task.save()


            title = "Cost sheet approval required"
            body = f"{self.request.user.name} has requested cost sheet approval for {one_cost_sheet.inventory.tower.project.name} - {one_cost_sheet.inventory.apartment_no}"
            data = {'notification_type': 'request_cost_sheet', 'redirect_url': f'/sales/my_visit/lead_details/{owner.lead.id}/0'}

            users = []

            vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
            if vp_user:
                users.append(vp_user)

            SalesActivity.objects.create(
                history_date=datetime.now(),
                history_type="+",
                history_user=self.request.user.name,
                sent_to =vp_user.name if vp_user else "",
                message=f"{self.request.user.name} has requested approval for {owner.property.tower.project.name} - {owner.property.apartment_no}",
                activity_type="SalesActivity",
                lead= lead
            )

            # ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
            # if ah_user:
            #     users.append(ah_user)

            for user in users:
                user_fcm_token = user.fcm_token
    
                Notifications.objects.create(notification_id=f"cost-sheet-{owner.id}-{user.id}",user_id=user,created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{owner.lead.id}/0')
    
                # Send push notification
                send_push_notification(user_fcm_token, title, body, data)


            return ResponseHandler(False, 'Inventory Cost Sheet approval request sent.', None, status.HTTP_201_CREATED)

        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class GetCostSheetApproval(generics.ListCreateAPIView):
    serializer_class = InventoryCostSheetSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        lead_id = self.request.query_params.get('lead_id')
        apartment_no = self.request.query_params.get('apartment_no')
        project_id = self.request.query_params.get('project_id')
        if lead_id:
            queryset = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=apartment_no, inventory__tower__project=project_id).order_by('event_order')
            if queryset.exists():
                return queryset
            else:
                return InventoryCostSheet.objects.none()
            
    
    @check_group_access(['VICE_PRESIDENT'])
    def get(self, request, *args, **kwargs):

        try:
            lead_id = request.query_params.get('lead_id', None)
            lead = get_object_or_404(Lead,pk=lead_id)
            print('lead:', lead)
            lead_workflow = lead.workflow.get()
            task = lead_workflow.tasks.filter(name='Cost Sheet').first()

            cost_sheets = self.get_queryset()

            if not cost_sheets:
                return ResponseHandler(True, 'Cost Sheet not found!', None, status.HTTP_404_NOT_FOUND)
            lead_data = LeadSerializer(lead, many=False)

            res = dict()
            res["lead"] = lead_data.data
            res["approval_status"] = "In Progress"
            res["approval_data"] = None
            inventory_owner = PropertyOwner.objects.filter(lead=request.query_params.get('lead_id')).first()
            res["agreement_value"] = inventory_owner.deal_amount
            deal_amount = float(inventory_owner.deal_amount) if inventory_owner.deal_amount else 0
            registration_fee_event = cost_sheets.filter(event="Registration Fees")
    
            registration_fees = 0
            if registration_fee_event and len(registration_fee_event) > 0:
                registration_fees = registration_fee_event[0].amount
            registration_fees = float(registration_fees) if registration_fees else 0
            amount_per_car_parking = cost_sheets[0].inventory.amount_per_car_parking
            car_parking = cost_sheets[0].inventory.car_parking if cost_sheets[0].inventory.car_parking else 0
            current_event_order = cost_sheets[0].inventory.tower.project.current_event_order
            total_car_parking_amount = int(car_parking) * float(amount_per_car_parking)
            
            res["total_value"] = (deal_amount * 0.08) + deal_amount + registration_fees + total_car_parking_amount
            res["current_slab_order"] = current_event_order
            if task.status == 'Accept':
                res["approval_status"] = "Approved"

            if task:
                workflow = dict()
                approvals = task.river.status.get_available_approvals(as_user=request.user)

                workflow["task_id"] = task.pk
                workflow["task_name"] = task.name
                workflow["approvals"] = []
                temp_list_src_dest = []

                approval_history = []
                if approvals.count()>0:
                    for approval in approvals:
                        if not approval_history:
                            approval_history = approval.history.filter(transactioner_id=request.user.id, object_id=approval.object_id, meta_id=approval.meta_id)
                            # print('approval_history:', approval_history, approval.object_id, request.user.id,approval.meta_id)

                        if not (approval.transition.source_state.label + approval.transition.destination_state.label) in     temp_list_src_dest :
                            temp_list_src_dest.append(approval.transition.source_state.label + approval.transition.    destination_state.label)
                            workflow["approvals"].append(
                                {
                                    "source": approval.transition.source_state.label,
                                    "destination": approval.transition.destination_state.label,
                                    "destination_id": approval.transition.destination_state.pk
                                }
                            )


                if approval_history:
                    workflow['approvals'] = []

                res["approval_data"] = workflow
            
            serializer = self.get_serializer(cost_sheets, many=True)
            cost_sheets_data = serializer.data

            final_cost_sheet_data = []

            for cost_sheet,event in zip(cost_sheets,cost_sheets_data):
                if cost_sheet.is_changed:
                    print(cost_sheet.event_order,">> Cost sheet event updated <<", cost_sheet)

                    old_event = cost_sheet.history.first()
                    print('old_event:', old_event)

                    old_serializer = self.get_serializer(old_event)
                    old_event = old_serializer.data
                    old_event["is_changed"] = False

                    final_cost_sheet_data.append(old_event)

                    final_cost_sheet_data.append(event)

                    # new_serializer = self.get_serializer(cost_sheet)
                    # updated_event = new_serializer.data

                    # final_cost_sheet_data.append(updated_event)

                    # cost_sheet.is_changed = False
                    # cost_sheet.save()
                else:
                    final_cost_sheet_data.append(event)
                    print(cost_sheet.event_order,">> cost sheet default event <<")


            res["cost_sheet"] = final_cost_sheet_data

            # "-------------------------------------------"

            # title = "Cost sheet approval required"
            # body = f"{self.request.user.name} has requested cost sheet approval for {one_cost_sheet.inventory.tower.project.name} - {one_cost_sheet.inventory.apartment_no}"
            # data = {'notification_type': 'request_cost_sheet', 'redirect_url': f'/sales/my_visit/lead_details/{owner.lead.id}/0'}

            # users = []

            # vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
            # if vp_user:
            #     users.append(vp_user)

            # # ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
            # # if ah_user:
            # #     users.append(ah_user)

            # for user in users:
            #     user_fcm_token = user.fcm_token
    
            #     Notifications.objects.create(notification_id=f"cost-sheet-{owner.id}-{user.id}",user_id=user,created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{owner.lead.id}/0')
    
            #     # Send push notification
            #     send_push_notification(user_fcm_token, title, body, data)


            return ResponseHandler(False, 'Cost Sheet approval data retrieved successfully.', res, status.HTTP_201_CREATED)

        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)

class InventoryTotalAPIView(APIView):
    def get(self, request):
        lead_id = self.request.query_params.get('lead_id')
        if not lead_id:
            return ResponseHandler(True, "Lead ID is missing", [], 400)
        
        if not Lead.objects.filter(id=lead_id).exists():
            return ResponseHandler(True, "Lead ID does not exist", [], 404)
        
        try:
            queryset = InventoryCostSheet.objects.filter(inventory__lead__id=lead_id).order_by('event_order')
            if not queryset.exists():
                return ResponseHandler(True, f"No Events for Lead Id {lead_id}", [], 404)
            inventory_owner = PropertyOwner.objects.filter(lead=lead_id).first()
            deal_amount = float(inventory_owner.deal_amount) if inventory_owner and inventory_owner.deal_amount else 0
            serializer = InventoryCostSheetSerializer(queryset, many=True)
            cost_sheets = serializer.data
            registration_fees = next((event["amount"] for event in cost_sheets if event["event_order"] == 2), 0)
            registration_fees = float(registration_fees) if registration_fees else 0
            amount_per_car_parking = queryset[0].inventory.amount_per_car_parking
            car_parking = queryset[0].inventory.car_parking
            total_car_parking_amount = int(car_parking) * float(amount_per_car_parking)
            print("deal_amount: ", deal_amount, registration_fees,total_car_parking_amount)
            total_value = (deal_amount * 0.08) + deal_amount + registration_fees + total_car_parking_amount
            sums = [
                {'payment_in_percentage_sum': queryset.aggregate(payment_in_percentage_sum=Sum('payment_in_percentage'))['payment_in_percentage_sum'],
                'amount_sum': queryset.aggregate(amount_sum=Sum('amount'))['amount_sum'],
                'gst_sum': queryset.aggregate(gst_sum=Sum('gst'))['gst_sum'],
                'tds_sum': queryset.aggregate(tds_sum=Sum('tds'))['tds_sum'],
                'total_amount_sum': queryset.aggregate(total_amount_sum=Sum('total_amount'))['total_amount_sum'],
                'agreement_amount': total_value},
            ]
            return ResponseHandler(False, "Total Cost", sums, 200)
        except Exception as e:
            return ResponseHandler(True, str(e), [], 500)

class InventoryCostSheetDetailView(generics.RetrieveAPIView):
    queryset = InventoryCostSheet.objects.all()
    serializer_class = InventoryCostSheetSerializer
    permission_classes = (IsAuthenticated,)

    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        sheet = serializer.data

        return ResponseHandler(False, 'InventoryCostSheetSheet retrieved successfully', sheet, status.HTTP_200_OK)

    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False, 'InventoryCostSheetSheet updated successfully', serializer.data, status.HTTP_200_OK)
        return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)

    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return ResponseHandler(False, 'InventoryCostSheetSheet deleted successfully', None, status.HTTP_204_NO_CONTENT)
    

class ClosureStepView(generics.RetrieveAPIView):
    queryset = Lead.objects.all()
    serializer_class = ClosureStepSerializer
    permission_classes = (IsAuthenticated,)

    @check_group_access(['ADMIN','CLOSING_MANAGER','SOURCING_MANAGER','PROMOTER','SITE_HEAD','VICE_PRESIDENT'])
    def retrieve(self, request, *args, **kwargs):
        try:
            lead_id = self.kwargs.get('pk')
            instance = self.get_object()
        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)

        if self.request.user.groups.filter(name="CLOSING_MANAGER").exists():
            latest_site_visit = SiteVisit.objects.filter(lead=lead_id).order_by('-visit_date').first()
            latest_cm = latest_site_visit.closing_manager
            # print("Latest_cm: ", latest_cm)
            if self.request.user != latest_cm:
                return ResponseHandler(True, 'Access Denied', None, status.HTTP_400_BAD_REQUEST)
            
        if self.request.user.groups.filter(name="SOURCING_MANAGER").exists():
            latest_site_visit = SiteVisit.objects.filter(lead=lead_id).order_by('-visit_date').first()
            latest_sm = latest_site_visit.sourcing_manager if latest_site_visit else None
            if self.request.user != latest_sm:
                return ResponseHandler(True, 'Access Denied', None, status.HTTP_400_BAD_REQUEST) 
               
        print('instance:', instance)
        serializer = self.get_serializer(instance)
        sheet = serializer.data

        return ResponseHandler(False, 'Current Closure Step retrieved successfully', sheet, status.HTTP_200_OK)
    
class CollectTokenInfoView(generics.RetrieveAPIView):
    queryset = Lead.objects.all()
    serializer_class = CollectTokenInfoSerializer
    permission_classes = (IsAuthenticated,)

    @check_group_access(['ADMIN','CLOSING_MANAGER','SOURCING_MANAGER','PROMOTER','SITE_HEAD','VICE_PRESIDENT'])
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        print('instance:', instance)
        serializer = self.get_serializer(instance)
        sheet = serializer.data

        return ResponseHandler(False, 'Current Closure Step retrieved successfully', sheet, status.HTTP_200_OK)
    
class CollectTokenUpdateView(generics.UpdateAPIView):
    queryset = InventoryCostSheet.objects.all()
    serializer_class = InventoryCostSheetSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        lead_id = self.request.query_params.get('lead_id')
        apartment_no = self.request.query_params.get('apartment_no')
        project_id = self.request.query_params.get('project_id')
        if lead_id:
            queryset = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=apartment_no, inventory__tower__project=project_id).order_by('event_order')
            if queryset.exists():
                return queryset
            else:
                return InventoryCostSheet.objects.none()

    @check_group_access(['ADMIN','PROMOTER','CLOSING_MANAGER', 'SOURCING_MANAGER','SITE_HEAD','VICE_PRESIDENT'])
    def update(self, request, *args, **kwargs):
        try:
            inventories = self.get_queryset()
            payment_in_percentage,token_amount,pay_via_cheque = request.data.get("payment_in_percentage", None), request.data.get("token_amount", None),request.data.get("pay_via_cheque", None)

            if not payment_in_percentage or not token_amount:
                return ResponseHandler(True,"Parameters 'payment_in_percentage' & 'token_amount' are required!",None, status.HTTP_404_NOT_FOUND)

            if not inventories:
                return ResponseHandler(False,"Inventory cost sheet not found for lead.",None, status.HTTP_200_OK)
            
            lead = Lead.objects.filter(pk=request.query_params.get('lead_id')).first()
            lead_workflow = lead.workflow.get()
            collect_token_task = lead_workflow.tasks.filter(name='Collect Token').first()
            
            if inventories[0].inventory.status == 'Booked' and not inventories[0].inventory.lead ==lead:
                # reset approval
                reset_approval = reset_task_approval_status(collect_token_task.id)
                state = get_object_or_404(State, label='Request')
                collect_token_task.completed = False
                collect_token_task.completed_at = None
                collect_token_task.status = state
                collect_token_task.save()

                # reset property_owner & cost_sheet
                reset_data = reset_property_owner_and_inventory_cost_sheets(inventories,lead)

                return ResponseHandler(True, "Inventory has already been booked. Please select another.", None, status.HTTP_409_CONFLICT)
            
            first_cost_sheet_event = inventories.first()
            print('first_cost_sheet_event:', first_cost_sheet_event)
            # in_progress = first_cost_sheet_event.inventory.in_progress
            
            first_cost_sheet_event.payment_in_percentage = payment_in_percentage
            first_cost_sheet_event.amount = token_amount
            first_cost_sheet_event.gst = int(token_amount) * 0.08
            first_cost_sheet_event.total_amount = token_amount + (int(token_amount) * 0.08)
            first_cost_sheet_event.paid = True
            first_cost_sheet_event.paid_date = timezone.now()
            if pay_via_cheque:
                first_cost_sheet_event.paid_date = True if pay_via_cheque == 'true' else False
            first_cost_sheet_event.save()

            # Set 'Collect Token' task as completed
            collect_token_task.completed = True
            collect_token_task.completed_at = timezone.now()
            collect_token_task.save()

            # update property buy date 
            property_owner = PropertyOwner.objects.filter(lead=lead).first()
            property_owner.property_buy_date = timezone.now()
            property_owner.booking_status = "active"
            property_owner.save()

            # Set in_progress to True
            first_cost_sheet_event.inventory.in_progress = True
            first_cost_sheet_event.inventory.status = 'Booked'
            first_cost_sheet_event.inventory.lead = lead
            first_cost_sheet_event.inventory.save()

            # Send push notification to Site Head
            title = "Token amount paid"
            body = f"Token amount paid by '{lead.first_name} {lead.last_name}'."
            data = {'notification_type': 'collect_token', 'redirect_url': f'/sales/my_visit/lead_details/{lead.id}/0'}

            # Fetch the FCM tokens associated with the Site Head SITE_HEAD
            users = []
            sh_user = Users.objects.filter(groups__name="SITE_HEAD").first()
            if sh_user:
                users.append(sh_user)

            vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
            if sh_user:
                users.append(vp_user)

            ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
            if sh_user:
                users.append(ah_user)

            for user in users:
                user_fcm_token = user.fcm_token
    
                Notifications.objects.create(notification_id=f"task-{collect_token_task.id}-{user.id}",user_id=user,created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{lead.id}/0')
    
                # Send push notification
                send_push_notification(user_fcm_token, title, body, data)

            return ResponseHandler(False, 'Collect Token info updated successfully', "", status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class BlockProjectInventoryUpdateView(generics.UpdateAPIView):
    # queryset = ProjectInventory.objects.all()
    # serializer_class = ProjectInventorySerializer
    permission_classes = (IsAuthenticated,)

    @check_group_access(['ADMIN','PROMOTER','CLOSING_MANAGER','SOURCING_MANAGER','SITE_HEAD','VICE_PRESIDENT'])
    def update(self, request, *args, **kwargs):
        try:
            lead_id = self.request.query_params.get('lead_id')
            inventory_owner = PropertyOwner.objects.filter(lead=lead_id).first()
            print('inventory_owner:', inventory_owner)

            if inventory_owner and inventory_owner.property:
                property_instance = inventory_owner.property
                property_instance.status = 'Booked'
                property_instance.save()
            else:
                return ResponseHandler(True,'Project inventory not found!',None, status.HTTP_404_NOT_FOUND)


            lead = Lead.objects.filter(pk=lead_id).first()
            print('lead:', lead)
            lead_workflow = lead.workflow.get()
            booking_form_task = lead_workflow.tasks.filter(name='Block Inventory').first()
            booking_form_task.completed = True
            booking_form_task.completed_at = timezone.now()
            booking_form_task.save()
            

            return ResponseHandler(False, 'Inventory booked successfully', "", status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True,str(e),None, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class ProjectInventoryListAPIView(APIView):

    @check_group_access(['ADMIN','PROMOTER','CLOSING_MANAGER','SOURCING_MANAGER','SITE_HEAD','VICE_PRESIDENT'])
    def get(self, request):
        try:
            project_id = request.query_params.get('project_id')
            inventories = ProjectInventory.objects.filter(tower__project__id=project_id)
            # Group inventories by tower
            grouped_inventories = inventories.values('tower__name').annotate(inventory_list=Count('id')).order_by('tower')

            response_data = []
            for inventory_group in grouped_inventories:
                tower_name = inventory_group['tower__name']
                inventory_list = ProjectInventorySerializer(
                    inventories.filter(tower__name=tower_name).order_by('-floor_number'),
                    many=True
                ).data

                # Check if the tower is already in the response_data list
                tower_data = next((item for item in response_data if item['tower'] == tower_name), None)
                # print('tower_data:', tower_data)
                if tower_data is None:
                    response_data.append({
                        'tower': tower_name,
                        'data': [
                            {
                                'inventories': inventory_list
                            }
                        ]
                    })
                else:
                    tower_data['data'].append({
                        'inventories': inventory_list
                    })

            return ResponseHandler(False,'Project inventories retrieved successfully',response_data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, str(e),None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        

# wing code
# class ProjectInventoryListAPIView(APIView):
#     def get(self, request):
#         try:
#             project_id = request.query_params.get('project_id')
#             inventories = ProjectInventory.objects.filter(wing__project__id=project_id)
#             # Group inventories by wing and tower
#             grouped_inventories = inventories.values('wing__name', 'tower').annotate(inventory_list=Count('id')).order_by('tower','wing')

#             response_data = []
#             for inventory_group in grouped_inventories:
#                 wing_name = inventory_group['wing__name']
#                 tower = inventory_group['tower']
#                 inventory_list = ProjectInventorySerializer(
#                     inventories.filter(wing__name=wing_name, tower=tower).order_by('-floor_number'),
#                     many=True
#                 ).data

#                 # Check if the wing is already in the response_data list
#                 wing_data = next((item for item in response_data if item['wing'] == wing_name), None)
#                 if wing_data is None:
#                     response_data.append({
#                         'wing': wing_name,
#                         'towers': [
#                             {
#                                 'name': tower,
#                                 'inventories': inventory_list
#                             }
#                         ]
#                     })
#                 else:
#                     wing_data['towers'].append({
#                         'name': tower,
#                         'inventories': inventory_list
#                     })

#             return ResponseHandler(False,'Project inventories retrieved successfully',response_data, status.HTTP_200_OK)
#         except Exception as e:
#             return ResponseHandler(True, str(e),None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    
class ProjectDetailCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProjectDetailSerializer


    def get_queryset(self):
        queryset = ProjectDetail.objects.all()
        return queryset
    
    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHandler(False, "ProjectDetail created successfully.", serializer.data, status.HTTP_201_CREATED)
            else:
                return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHandler(True, f"Error creating ProjectDetail: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def get(self, request, *args, **kwargs):
            try:
                projectdetail = self.get_queryset()
                print("Project: ",projectdetail)

                if projectdetail.exists():
                    
                    serializer = ProjectDetailSerializer(projectdetail, many=True)

                    return ResponseHandler(False, "ProjectDetail retrieved successfully.", serializer.data, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "No data is present", None, status.HTTP_400_BAD_REQUEST)                       
            except Exception as e:
                return ResponseHandler(True, f"Error retrieving ProjectDetail: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProjectDetailRetrieveUpdateDeleteAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProjectDetailSerializer
    permission_classes = (IsAuthenticated,)

    queryset = ProjectDetail.objects.all()

    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def get(self, request, *args, **kwargs):
       ProjectDetail_id = self.kwargs.get('pk')
       try:
            instance = ProjectDetail.objects.get(pk=ProjectDetail_id)
            dashboard_type = request.query_params.get('dashboard_type', None)
            if dashboard_type == 'preview':
                serializer = ProjectDetailPreviewSerializer(instance)
            else:
                serializer = serializer = self.get_serializer(instance) 
                
            return ResponseHandler(False, 'ProjectDetail retrieved successfully', serializer.data, status.HTTP_200_OK)
       except ProjectDetail.DoesNotExist:
            return ResponseHandler(True, 'ProjectDetail not found', None, status.HTTP_404_NOT_FOUND)


    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])    
    def put(self,request, *args, **kwargs):
        ProjectDetail_id = self.kwargs.get('pk')
        try:
            instance = self.queryset.get(pk=ProjectDetail_id)
        except ProjectDetail.DoesNotExist:
            return  ResponseHandler(True, 'ProjectDetail not found', None, status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False , 'Data updated successfully' , serializer.data,status.HTTP_200_OK)
        else:
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        ProjectDetail_id = self.kwargs.get('pk')
        try:
            instance = ProjectDetail.objects.get(pk=ProjectDetail_id)
            self.perform_destroy(instance)
            return ResponseHandler(False, 'ProjectDetail deleted successfully' , None,status.HTTP_204_NO_CONTENT)
        except ProjectDetail.DoesNotExist:
            return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND) 
                
class ProjectTowerCreateView(generics.CreateAPIView):
    serializer_class = ProjectTowerSerializer

    def get_queryset(self):
        return ProjectTower.objects.all()
    
    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def create(self, request, *args, **kwargs):
        try:
            tower_names = request.data.get('tower_names', [])

            for tower_name in tower_names:
                serializer = self.get_serializer(data={'name': tower_name, 'project': self.get_project()})
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)

            return ResponseHandler(False, "Towers created successfully", {'tower_names': tower_names}, status.HTTP_201_CREATED)
        
        except ProjectDetail.DoesNotExist:
            return ResponseHandler(True, "Project not found", None, status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return ResponseHandler(True, str(e), None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def perform_create(self, serializer):
        serializer.save(project=self.get_project())

    def get_project(self):
        try:
            project_id = self.kwargs.get('project_id')
            return ProjectDetail.objects.get(pk=project_id)
        except ProjectDetail.DoesNotExist:
            raise ProjectDetail.DoesNotExist("Project not found") 


class ProjectInventoryListCreateAPIView(generics.ListCreateAPIView):
    queryset = ProjectInventory.objects.all()
    serializer_class = ProjectInventorySerializer

    def list(self, request, *args, **kwargs):
        try:
            project_inventories = self.get_queryset()
            serializer = self.get_serializer(project_inventories, many=True)
            return ResponseHandler(False, "Inventory Data: ",serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, str(e), None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return ResponseHandler(False, "Inventory Data: ",serializer.data, status.HTTP_201_CREATED)
        except Exception as e:
            return ResponseHandler(True, str(e), None, status.HTTP_400_BAD_REQUEST)

class ProjectInventoryRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ProjectInventory.objects.all()
    serializer_class = ProjectInventorySerializer

    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return ResponseHandler(False, "Inventory Data: ",serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, str(e), None, status.HTTP_404_NOT_FOUND)
        
    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return ResponseHandler(False, "Inventory Data: ",serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, str(e), None, status.HTTP_400_BAD_REQUEST)
        
    @check_group_access(['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return ResponseHandler(False, "Inventory Data: ",None,status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return ResponseHandler(True, str(e), None, status.HTTP_500_INTERNAL_SERVER_ERROR)



class PropertyOwnerUpdateKeyTransfer(generics.UpdateAPIView):
    serializer_class = PropertyOwnerSerializer
    queryset = PropertyOwner.objects.all()

    def update(self, request, *args, **kwargs):
        lead_id = self.kwargs['lead_id']
        lead_obj = Lead.objects.filter(pk=lead_id).first()
        if lead_obj:
            project_inventory = ProjectInventory.objects.filter(lead=lead_obj).first()
            # project_id = project_inventory.tower.project.id if project_inventory and project_inventory.tower and project_inventory.tower.project else None
            crm_head = Users.objects.filter(groups__name = "CRM_HEAD").first()#,project=project_id
            workflow = lead_obj.workflow.get()
            key_transfer_task = workflow.tasks.filter(name='Key Transfer',completed=False).first()
            if key_transfer_task:
                key_transfer_task.completed = True
                key_transfer_task.completed_at = timezone.now()
                key_transfer_task.save()
                promoter_users = Users.objects.filter(groups__name="PROMOTER")
                vp_users = Users.objects.filter(groups__name="VICE_PRESIDENT")
                title = "Key Transfer Done"
                body = f"Key Transfer Done for {project_inventory.tower.project.name} - {project_inventory.apartment_no}"
                data = {'notification_type': 'key_transfer'}

                for promoter_user in promoter_users:
                    if promoter_user:
                        fcm_token_promoter = promoter_user.fcm_token
                        Notifications.objects.create(notification_id=f"task-{key_transfer_task.id}-{promoter_user.id}", user_id=promoter_user,created=timezone.now(),  notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{lead_obj.id}/0')
                        send_push_notification(fcm_token_promoter, title, body, data)

                for vp_user in vp_users:
                    if vp_user:
                        fcm_token_vp = vp_user.fcm_token
                        Notifications.objects.create(notification_id=f"task-{key_transfer_task.id}-{vp_user.id}", user_id=vp_user,created=timezone.now(),  notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{lead_obj.id}/0')
                        send_push_notification(fcm_token_vp, title, body, data)

                if crm_head:
                    fcm_token_crmhead = crm_head.fcm_token
                    Notifications.objects.create(notification_id=f"task-{key_transfer_task.id}-{crm_head.id}", user_id=crm_head,created=timezone.now(),  notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{lead_obj.id}/0')
                    send_push_notification(fcm_token_crmhead, title, body, data)
        # try:
        #     property_owner = PropertyOwner.objects.get(lead__id=lead_id)
        # except PropertyOwner.DoesNotExist:
        #     return ResponseHandler(True,  "PropertyOwner not found for the given lead ID.",None,status.HTTP_204_NO_CONTENT)

        #property_owner.key_transfer = True
        #property_owner.save()
        # mark all pending tasks completed 
        #serializer = self.get_serializer(property_owner)
        
        return ResponseHandler(False, "Key Transfer Done ",None, status.HTTP_200_OK)
    
class CancelBooking(generics.ListCreateAPIView):
    serializer_class = InventoryCostSheetSerializer
    permission_classes = (IsAuthenticated,)
    
    @check_group_access(['CRM_HEAD', 'VICE_PRESIDENT', 'PROMOTER'])
    def post(self, request, *args, **kwargs):

        try:
            lead_id = self.request.data.get('lead_id', None)
            apartment_no = self.request.data.get('apartment_no', None)
            project_id = self.request.data.get('project_id', None)
            refund_amount = self.request.data.get('refund_amount', 0) 
    
            cost_sheet_events = None
            owner = None
            inventory_owner = None
            if lead_id and apartment_no and project_id:
                cost_sheet_events = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=apartment_no,inventory__tower__project=project_id).order_by('event_order')

                lead = get_object_or_404(Lead,pk=lead_id)
                    

                if not cost_sheet_events.exists():
                    return ResponseHandler(True, 'InventoryCostSheet not found!', None, status.HTTP_404_NOT_FOUND)
                
                
                one_cost_sheet = cost_sheet_events[0]
                inventory_owner = PropertyOwner.objects.filter(property=one_cost_sheet.inventory, lead=lead).first()
                print('owner:', inventory_owner)

                if not inventory_owner:
                    return ResponseHandler(True, 'Inventory owner not found.', None, status.HTTP_404_NOT_FOUND)
                
                if inventory_owner.booking_status=="cancel":
                    return ResponseHandler(True, 'Booking already cancelled.', None, status.HTTP_404_NOT_FOUND)
                
                if not cost_sheet_events[0].inventory.status=="Booked":
                    return ResponseHandler(True, 'Inventory is not booked yet.', None, status.HTTP_400_BAD_REQUEST)
            else:
                return ResponseHandler(True, 'Some required fields are missing from the body.', None, status.HTTP_400_BAD_REQUEST)


            #Adding invoice overview list for refund amount
            AE_slug = VP_slug = P1_slug = P2_slug = P3_slug = AH_slug = ''

            payment_definitions = TaskDefinition.objects.filter(workflow__name='Refund Template')
            print('payment_definitions:', payment_definitions)

            for payment_definition in payment_definitions:
                print('payment_definition:', payment_definition)
                if payment_definition.name == "Refund Approval AE":
                    ae_user = Users.objects.filter(groups__name="ACCOUNTS_EXECUTIVE").first()
                    AE_slug = ae_user.slug
                    print(AE_slug)
                if payment_definition.name == "Refund Approval VP":
                    vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                    print(vp_user)
                    VP_slug = vp_user.slug
                    print(VP_slug)
                if payment_definition.name == "Refund Approval P1":
                    users = payment_definition.users.all() 
                    P1_slug = users[0].slug
                    print(P1_slug)
                if payment_definition.name == "Refund Approval P2":
                    users = payment_definition.users.all() 
                    P2_slug = users[0].slug
                    print(P2_slug)
                if payment_definition.name == "Refund Approval P3":
                    users = payment_definition.users.all() 
                    P3_slug = users[0].slug
                    print(P3_slug)
                if payment_definition.name == "Refund Approval AH":
                    ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
                    AH_slug = ah_user.slug
                    print(AH_slug)

            default_invoice_overview_list = [
                {"role": "AE", "status": "Approval Pending", "slug": AE_slug},        
                {"role": "VP", "status": "Approval Pending", "slug": VP_slug},
                {"role": "P1", "status": "Approval Pending", "slug": P1_slug},
                {"role": "P2", "status": "Approval Pending", "slug": P2_slug},
                {"role": "P3", "status": "Approval Pending", "slug": P3_slug},
                {"role": "AH", "status": "Approval Pending", "slug": AH_slug}
            ]

            print(default_invoice_overview_list)

            project_detail = ProjectDetail.objects.get(id=project_id)
            apartment_no= ProjectInventory.objects.get(apartment_no=apartment_no)
            

            # Create RefundPaymentOverview instance.
            refund_payment = Payment.objects.create(lead=lead,amount=refund_amount,payment_to="Refund",payment_for="Refund",project=project_detail,apartment_no=apartment_no,payment_type="Refund",invoice_overview_list=default_invoice_overview_list)
            refund_payment.save()    
            
          
            #Start first task with in progress
            definition=WorkflowDefinition.objects.filter(organization=self.request.user.organization, workflow_type='accounts',name="Refund Template").last()
            print("definition",definition)
            print("definition_id",definition.id)
                
            if definition:
                workflow_data = {
                    "payment": refund_payment.id,
                    "definition": definition.id,
                    "name": definition.name,
                    "workflow_type": definition.workflow_type,
                    "organization": self.request.user.organization.id if self.request.user.organization else None,
                }
                print("workflow_data",workflow_data)
                workflow_ser = PaymentWorkflowCreateSerializer(data=workflow_data)
                workflow_ser.is_valid(raise_exception=True)
                workflow=workflow_ser.save()
                print("Workflow created")
                first_stage = refund_payment.payment_workflow.get().stages.first()
                print("first_stage",first_stage)
                first_task = first_stage.tasks.filter(completed=False).order_by('order').first()
                print("first_task",first_task)
                state = get_object_or_404(State, label='In Progress')
                print("state",state)
                first_task.status = state
                first_task.save()
                print("first task:",first_task)

            # change inventory status & owner booking status
            one_cost_sheet.inventory.status = "Yet to book"
            one_cost_sheet.in_progress =False
            one_cost_sheet.inventory.save()

            inventory_owner.booking_status = "cancel"
            inventory_owner.booking_cancelled_at = timezone.now()
            inventory_owner.refund_amount = refund_amount  
            inventory_owner.save()
            
            # removed_cost_sheets = cost_sheet_events.delete()
            # inventory_owner = PropertyOwner.objects.filter(lead=lead).first()
            # inventory_owner.delete()

            SalesActivity.objects.create(
                history_date=datetime.now(),
                history_type="+",
                history_user=self.request.user.name,
                message=f"{self.request.user.name} has cancelled booking of {lead.first_name} {lead.last_name} ({one_cost_sheet.inventory.tower.project.name} - {one_cost_sheet.inventory.apartment_no})",
                activity_type="SalesActivity",
                lead= lead
            )
        
            #Send Notifications
            title = "Inventory booking cancelled."
            body = f"{self.request.user.name} has cancelled booking of {lead.first_name} {lead.last_name} ({one_cost_sheet.inventory.tower.project.name} - {one_cost_sheet.inventory.apartment_no})"
            data = {'notification_type': 'cancel_booking', 'redirect_url': f'/post_sales/all_clients/lead_details/{inventory_owner.lead.id}/0'}

            users = []

            ae_user = Users.objects.filter(groups__name="ACCOUNTS_EXECUTIVE").first() 
            if ae_user :
                users.append(ae_user)      

            vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
            if vp_user and not vp_user==request.user:
                users.append(vp_user)

            promoters = Users.objects.filter(groups__name="PROMOTER")[:3]
            if promoters:
                for user in promoters:
                    if not user == request.user:
                        users.append(user)    

            ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
            if ah_user :
                users.append(ah_user)
            

            # ch_user = Users.objects.filter(groups__name="CRM_HEAD").first()
            # if ch_user and not ch_user==request.user:
            #     users.append(ch_user)


            for user in users:
                user_fcm_token = user.fcm_token
    
                Notifications.objects.create(notification_id=f"cost-sheet-{inventory_owner.id}-{user.id}",user_id=user,created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{inventory_owner.lead.id}/0')
    
                # Send push notification
                send_push_notification(user_fcm_token, title, body, data)


            return ResponseHandler(False, 'Inventory booking cancelled successfully.', None, status.HTTP_200_OK)

        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
       
class GetPdf(APIView):
    
    def get(self, request):
        lead_id = request.query_params.get('lead_id')
         
        booking_param = bool(request.query_params.get('booking_form',None))
        cost_sheet_param = bool(request.query_params.get('cost_sheet',None))
        postsales_param = bool(request.query_params.get('postsales_documents',None))
        
        try:
            project_owner = PropertyOwner.objects.get(lead_id=lead_id)
            print("project_owner: ", project_owner)
        except PropertyOwner.DoesNotExist:
            print("Project owner not found.")
            return ResponseHandler(True, "Project owner not found.", None, 404)
        
        response_data = {}
        
        if booking_param:
            booking_form_pdf_url = project_owner.booking_form_pdf.url if project_owner.booking_form_pdf else None
            response_data['booking_form_pdf_url'] = booking_form_pdf_url
        
        if cost_sheet_param:
            cost_sheet_pdf_url = project_owner.cost_sheet_pdf.url if project_owner.cost_sheet_pdf else None
            response_data['cost_sheet_pdf_url'] = cost_sheet_pdf_url

        if postsales_param:    
            booking_form_pdf_url = project_owner.booking_form_pdf.url if project_owner.booking_form_pdf else None
            response_data['booking_form_pdf_url'] = booking_form_pdf_url
            cost_sheet_pdf_url = project_owner.cost_sheet_pdf.url if project_owner.cost_sheet_pdf else None
            response_data['cost_sheet_pdf_url'] = cost_sheet_pdf_url
            pan_card = DocumentSection.objects.filter(lead__id=lead_id, doc_tag='pan_card').first()    
            if pan_card:
                response_data['pan_card_url'] = pan_card.name
            else:
                response_data['pan_card_url'] = ""


        return ResponseHandler(False, "PDF URLs fetched successfully.", response_data, 200)
    
def generate_pdf(request):
    
    try:
        booking_form_param =  bool(request.GET.get('booking_form', None))
        lead_id = request.GET.get('lead_id')

        if not lead_id:
            return ResponseHandler(True, "Lead ID is missing", None, 400)
        
        if not Lead.objects.filter(id=lead_id).exists():
            return ResponseHandler(True, "Lead does not exist", None, 404)
        
        lead_instance =  Lead.objects.get(id=lead_id)

        project_inventory = ProjectInventory.objects.filter(lead=lead_instance).first()
        if not project_inventory:
            return ResponseHandler(True, "Project Inventory does not exist", None, 404)
        
        inventory_queryset = InventoryCostSheet.objects.filter(inventory__lead=lead_instance, inventory=project_inventory)
        if not inventory_queryset.exists():
            return ResponseHandler(True, "Inventory Cost Sheet data does not exist",None, 404)

        booking_form = BookingForm.objects.filter(lead_id=lead_instance).first()
        if not booking_form:
            return ResponseHandler(True, "Booking Form data does not exist", None, 404)

        project_owner = PropertyOwner.objects.get(lead=lead_instance)
        if not project_owner:
            return ResponseHandler(True, "Project Owner data does not exist", None, 404)

        project_details = booking_form.project 

        filename = project_details.name.lower().replace(" ", "_") + ".json"

        json_file_path = filename

        if os.path.exists(json_file_path):
            with open(json_file_path, "r") as file:
                json_data = json.load(file)
            print("JSON data loaded successfully:")
        else:
            return ResponseHandler(True, "JSON file does not exist for the project:", None, 404)

        if booking_form_param:
            image_url = json_data.get("image_url")
            inventory_owner = PropertyOwner.objects.filter(lead=lead_instance).first()
            deal_amount = float(inventory_owner.deal_amount) if inventory_owner and inventory_owner.deal_amount else 0
            # Fetch signature URLs from the Lead model if they exist
            sh_signature_url = lead_instance.sh_signature.url if lead_instance.sh_signature else None
            customer_signature_url = lead_instance.customer_signature.url if lead_instance.customer_signature else None
            co_owner_signature_url = lead_instance.co_owner_signature.url if lead_instance.co_owner_signature else None
            context = {
                'project_name': project_details.name, 
                'configuration': project_inventory.configuration.name,
                'customer_name': getattr(booking_form, 'customer_name', None),
                'deal_amount': deal_amount,
                'pan_no': getattr(booking_form, 'pan_no', None),
                'aadhaar_details': getattr(booking_form, 'aadhaar_details', None),
                "contact_number" : lead_instance.primary_phone_no,
                'nationality': getattr(booking_form, 'nationality', None),
                'residence_address': getattr(booking_form, 'residence_address', None),
                'residence_phone_no': getattr(booking_form, 'residence_phone_no', None),
                'permanent_address': getattr(booking_form, 'permanent_address', None),
                'permanent_address_telephone_no': getattr(booking_form, 'permanent_address_telephone_no', None),
                'correspondance_address': getattr(booking_form, 'correspondance_address', None),
                'company_name': getattr(booking_form, 'company_name', None),
                'designation': getattr(booking_form, 'designation', None),
                'company_address': getattr(booking_form, 'company_address', None),
                'telephone_no': getattr(booking_form, 'telephone_no', None),
                'mobile_no': getattr(booking_form, 'mobile_no', None),
                'fax': getattr(booking_form, 'fax', None),
                'email_id': getattr(booking_form, 'email_id', None),
                'co_owner1_name': getattr(booking_form, 'co_owner1_name', None),
                'co_owner1_pan_no': getattr(booking_form, 'co_owner1_pan_no', None),
                'co_owner1_nationality': getattr(booking_form, 'co_owner1_nationality', None),
                'relation_with_customer1': getattr(booking_form, 'relation_with_customer1', None),
                'co_owner1_company_name': getattr(booking_form, 'co_owner1_company_name', None),
                'co_owner1_designation': getattr(booking_form, 'co_owner1_designation', None),
                'co_owner1_company_address': getattr(booking_form, 'co_owner1_company_address', None),
                'co_owner1_telephone_no': getattr(booking_form, 'co_owner1_telephone_no', None),
                'co_owner1_mobile_no': getattr(booking_form, 'co_owner1_mobile_no', None),
                'co_owner1_fax': getattr(booking_form, 'co_owner1_fax', None),
                'co_owner1_email_id': getattr(booking_form, 'co_owner1_email_id', None),
                'co_owner2_name': getattr(booking_form, 'co_owner2_name', None),
                'co_owner2_pan_no': getattr(booking_form, 'co_owner2_pan_no', None),
                'co_owner2_nationality': getattr(booking_form, 'co_owner2_nationality', None),
                'relation_with_customer2': getattr(booking_form, 'relation_with_customer2', None),
                'co_owner2_company_name': getattr(booking_form, 'co_owner2_company_name', None),
                'co_owner2_designation': getattr(booking_form, 'co_owner2_designation', None),
                'co_owner2_company_address': getattr(booking_form, 'co_owner2_company_address', None),
                'co_owner2_telephone_no': getattr(booking_form, 'co_owner2_telephone_no', None),
                'co_owner2_mobile_no': getattr(booking_form, 'co_owner2_mobile_no', None),
                'co_owner2_fax': getattr(booking_form, 'co_owner2_fax', None),
                'co_owner2_email_id': getattr(booking_form, 'co_owner2_email_id', None),
                'marital_status': getattr(booking_form, 'marital_status', None),
                'date_of_anniversary': getattr(booking_form, 'date_of_anniversary', None),
                'family_configuration': getattr(booking_form, 'family_configuration', None),
                'configuration_id': getattr(booking_form, 'configuration_id', None),
                'tower_id': booking_form.tower.name if booking_form.tower  else None,
                'car_parking_amount':project_inventory.amount_per_car_parking if project_inventory.amount_per_car_parking else None,
                'project_id': getattr(booking_form, 'project_id', None),
                'apartment_no': getattr(booking_form, 'apartment_no', None),
                'floor': getattr(booking_form, 'floor', None),
                'date_of_booking': getattr(booking_form, 'date_of_booking', None),
                'booking_source': getattr(booking_form, 'booking_source', None),
                'sub_source': getattr(booking_form, 'sub_source', None),
                'sales_manager_name_id': booking_form.sales_manager_name.name,
                'contact_person_name': getattr(booking_form, 'contact_person_name', None),
                'contact_person_number': getattr(booking_form, 'contact_person_number', None),
                "image_url": image_url,
                'sh_signature_url' : sh_signature_url,
                'customer_signature_url' : customer_signature_url,
                'co_owner_signature_url' : co_owner_signature_url

            }

            html_content = render_to_string('booking_form_template.html', context)

            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # file_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.html')

            # with open(file_path, "w") as file:
            #     file.write(html_content)

            pdf_file_path = os.path.join(settings.MEDIA_ROOT, f'booking_form_{project_inventory.apartment_no}_{timestamp}.pdf')
        else:
            head_office = json_data.get("head_office") 
            site_address = json_data.get("site_address")
            rera_website = json_data.get("rera_website")
            gst = json_data.get("gst")
            terms_and_conditions = json_data.get("terms_and_conditions")
            image_url = json_data.get("image_url")
            
            queryset = InventoryCostSheet.objects.filter(inventory__lead__id=lead_id, inventory=project_inventory).order_by('event_order')
            if not queryset.exists():
                return ResponseHandler(True, f"No Events for Lead Id {lead_id}", None, 404)

            inventory_owner = PropertyOwner.objects.filter(lead=lead_instance).first()
            deal_amount = float(inventory_owner.deal_amount) if inventory_owner and inventory_owner.deal_amount else 0
            serializer = InventoryCostSheetSerializer(queryset, many=True)
            cost_sheets = serializer.data
            registration_fees = next((event["amount"] for event in cost_sheets if event["event_order"] == 2), 0)
            registration_fees = float(registration_fees) if registration_fees else 0
            amount_per_car_parking = queryset[0].inventory.amount_per_car_parking
            car_parking = queryset[0].inventory.car_parking
            total_car_parking_amount = int(car_parking) * float(amount_per_car_parking)
            
            total_value = (deal_amount * 0.08) + deal_amount + registration_fees + total_car_parking_amount


            context = {
                'date': booking_form.date_of_booking,  
                'project_name': project_details.name,  
                'location': project_details.address, 
                'rera_website': project_details.rera_number + ' and ' + rera_website + ' under registered projects' , 
                'head_office': head_office, 
                'site_address': site_address, 
                'agreement_value': project_owner.deal_amount,  
                'apartment_no': project_inventory.apartment_no,
                'configuration': project_inventory.configuration.name,
                'building': project_inventory.tower.name,
                'floors' : project_inventory.floor_number,
                'car_parking': project_inventory.car_parking, 
                'area': project_inventory.area,
                'cost_sheet_data': inventory_queryset,
                'payment_in_percentage_sum': queryset.aggregate(payment_in_percentage_sum=Sum('payment_in_percentage'))['payment_in_percentage_sum'],
                'amount_sum': queryset.aggregate(amount_sum=Sum('amount'))['amount_sum'],
                'gst_sum': queryset.aggregate(gst_sum=Sum('gst'))['gst_sum'],
                'tds_sum': queryset.aggregate(tds_sum=Sum('tds'))['tds_sum'],
                'total_amount_sum': queryset.aggregate(total_amount_sum=Sum('total_amount'))['total_amount_sum'],
                'agreement_amount': total_value,
                "gst":gst,
                "terms_and_conditions": terms_and_conditions,
                "image_url": image_url,
                "client_signature_url" : booking_form.client_signature.url if booking_form.client_signature else None,
                "cm_signature_url" : booking_form.cm_signature.url if booking_form.cm_signature else None,
                "vp_signature" : booking_form.vp_signature.url if booking_form.vp_signature else None,
                "co_owner_signature" : booking_form.co_owner_signature.url if booking_form.co_owner_signature else None
            }

            html_content = render_to_string('pdf_template.html', context)

            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

            # file_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.html')

            # with open(file_path, "w") as file:
            #     file.write(html_content)

            pdf_file_path = os.path.join(settings.MEDIA_ROOT, f'cost_sheet_{project_inventory.apartment_no}_{timestamp}.pdf')

        # wkhtmltopdf_path = r'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'
        wkhtmltopdf_path = r'/usr/bin/wkhtmltopdf'
        
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

        pdfkit.from_string(html_content, pdf_file_path, configuration=config)

        with open(pdf_file_path, 'rb') as file:
            export_file = ExportFile(file=File(file))
            export_file.save()
    
        os.remove(pdf_file_path) 

        return ResponseHandler(False, 'Pdf Generated successfully',export_file.file.url, status_code=status.HTTP_200_OK)
    except Exception as e:
        return ResponseHandler(True, "Unexpected error: ", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)
    

def update_cost_sheet_and_notify(request, lead_id, apartment_no, project_id, total_value):
    try:
        # event_ids = [event['id'] for event in events_data]

        # # Fetch existing sheets
        # existing_sheets = InventoryCostSheet.objects.filter(id__in=event_ids)
        # print('events_data:', events_data)
        # print('existing_sheets:', existing_sheets)

        # for existing_sheet in existing_sheets:
        #     # Find the corresponding data from the request
        #     updated_data = next((event for event in events_data if event['id'] == existing_sheet.id), None)

        #     if updated_data:
        #         # Update the existing sheet with new data
        #         serializer = InventoryCostSheetSerializer(existing_sheet, data=updated_data)
        #         if serializer.is_valid():
        #             print('serializer:', serializer.errors)
        #             serializer.save()
        #         else:
        #             return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)

        existing_sheets = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=apartment_no, inventory__tower__project=project_id,is_changed=True).order_by('event_order')

        for existing_sheet in existing_sheets:
            existing_sheet.is_changed = False
            existing_sheet.save() 
                
        one_cost_sheet = existing_sheets.first()
        owner = PropertyOwner.objects.filter(property=one_cost_sheet.inventory, lead=one_cost_sheet.lead).first()
        if total_value:
            owner.total_value = total_value
            owner.save()
        print('owner:', owner)

        lead = Lead.objects.filter(pk=owner.lead.id).first()
        lead_workflow = lead.workflow.get()
        cost_sheet_task = lead_workflow.tasks.filter(name='Cost Sheet').first()

        if not cost_sheet_task.status == 'Accept':
            state = get_object_or_404(State, label='Accept')
            print('state:', state)
            cost_sheet_task.status = state

        # cost_sheet_task.completed = True
        # cost_sheet_task.completed_at = timezone.now()
        cost_sheet_task.save()

        SalesActivity.objects.create(
            lead_id =owner.lead.id,
            history_date=datetime.now(),
            history_type="+",
            history_user=request.user.name,
            message=f"{request.user.name} has approved cost sheet for {owner.property.tower.project.name} - {owner.property.apartment_no}",
            activity_type="SalesActivity"
        )

        title = "Cost sheet approved"
        body = f"Cost sheet approved for '{owner.lead.first_name} {owner.lead.last_name}'."
        data = {'notification_type': 'collect_token', 'redirect_url': f'/sales/my_visit/lead_details/{owner.lead.id}/0'}

        # Fetch the FCM tokens associated with the Site Head SITE_HEAD
        users = []
        sh_user = Users.objects.filter(groups__name="SITE_HEAD").first()
        if sh_user:
            users.append(sh_user)

        # vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
        # if vp_user:
        #     users.append(vp_user)

        # ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
        # if ah_user:
        #     users.append(ah_user)

        for user in users:
            user_fcm_token = user.fcm_token

            Notifications.objects.create(notification_id=f"cost-sheet-{owner.id}-{user.id}",user_id=user,created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{owner.lead.id}/0')

            # Send push notification
            send_push_notification(user_fcm_token, title, body, data)


        return ResponseHandler(False, 'InventoryCostSheet updated successfully', None, status.HTTP_201_CREATED)

    except Exception as e:
        return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class ProjectInventoryBulkUpload(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        try:
            file_uploaded = request.FILES.get('file_uploaded', None)
            if file_uploaded is None:
                return ResponseHandler(False, "No file uploaded", None, status.HTTP_400_BAD_REQUEST)
            
            content_type = file_uploaded.content_type
            if content_type != 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                return ResponseHandler(False, "Unsupported file type", None, status.HTTP_400_BAD_REQUEST)
            
            df = pd.read_excel(file_uploaded)

            for _, row in df.iterrows():
                try:
                    configuration = Configuration.objects.get(name=row['Configuration'])
                    print(f"configuration:{configuration}")
                    project_inventory_type = PropertyType.objects.get(name=row['Property Type'])
                    print(f"project_inventory_type:{project_inventory_type}")
                    tower = ProjectTower.objects.get(name=row['Tower'])
                    print(f"tower:{tower}")
                    exact_area = int(row['Area(in sq.ft)'])
                    print(f"exact_area:{exact_area}")
                    area = self.get_area_choice(exact_area)
                    print(f"area:{area}")
                except (Configuration.DoesNotExist, PropertyType.DoesNotExist, ProjectTower.DoesNotExist) as e:
                    if (Configuration.DoesNotExist):
                        return ResponseHandler(False, "Configuration does not exist", None, status.HTTP_400_BAD_REQUEST)
                    elif (PropertyType.DoesNotExist):
                        return ResponseHandler(False, "Property Type does not exist", None, status.HTTP_400_BAD_REQUEST)
                    elif (ProjectTower.DoesNotExist):
                        return ResponseHandler(False, "Project Tower does not exist", None, status.HTTP_400_BAD_REQUEST)
                    
                ProjectInventory.objects.update_or_create(
                    apartment_no=row['Apartment No.'],
                    configuration=configuration,
                    flat_no=row['Flat No.'],
                    area=area,
                    exact_area=exact_area,
                    floor_number=row['Floor No.'],
                    vastu_details=row['Vastu'],
                    no_of_bathrooms=row['No. of Bathrooms'],
                    no_of_bedrooms=row['No. of Bedrooms'],
                    no_of_balcony=row['No. of Balcony'],
                    pre_deal_amount=row['Pre deal Amount'],
                    min_deal_amount_cm=row['Min deal amount CM'],
                    min_deal_amount_sh=row['Min deal amount SH'],
                    min_deal_amount_vp=row['Min deal amount VP'],
                    status='Yet to book',
                    project_inventory_type=project_inventory_type,
                    tower=tower,
                )

            return ResponseHandler(False, "File uploaded and processed successfully", None, status.HTTP_201_CREATED)

        except Exception as e:
            return ResponseHandler(True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_area_choice(self, exact_area):
        if exact_area < 400:
            return '<400 Sqft'
        elif 400 <= exact_area <= 500:
            return '400 - 500 Sqft'
        elif exact_area > 500 and exact_area < 600:
            return '>500 Sqft'
        elif 600 <= exact_area <= 700:
            return '600 - 700 Sqft'
        elif exact_area > 700 and exact_area < 1000:
            return '>700 Sqft'
        elif 1000 <= exact_area <= 1300:
            return '1000 - 1300 Sqft'
        elif exact_area > 1300 and exact_area <= 1500:
            return '1000 - 1500 Sqft'
        elif exact_area > 1500:
            return '>1500 Sqft'
        return '<1000 Sqft'