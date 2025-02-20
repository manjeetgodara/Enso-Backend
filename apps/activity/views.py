from django.shortcuts import render
from rest_framework import generics, status, mixins, permissions
from .models import Notes, SiteVisit
from .serializers import *
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db import IntegrityError
from .serializers import CalendarViewSerializer
from datetime import date, timedelta
from django.db.models import Max, Min, OuterRef, Subquery, F, Value, Q, Count, Sum
import datetime
from rest_framework.response import Response
from auth.utils import ResponseHandler
from lead.models import Lead
from datetime import datetime, timedelta
from django.utils import timezone
from auth.models import Users
from auth.serializers import UserSerializer,UserDataSerializer
from .models import SiteVisit
from workflow.models import Task, Stage
from django.shortcuts import get_object_or_404
from river.models import State
from workflow.tasks import process_task
from .serializers import AvailableTimeslotsSerializer
from calendar import monthrange
import json
from inventory.models import *
from comms.utils import send_push_notification
from workflow.models import Notifications, NotificationMeta
from django.contrib.auth.models import Group
import hashlib
from mcube.models import *
from accounts.models import Payment
import math
from django.db.models import Q, Sum, Avg
from datetime import datetime, timedelta

class NotesListCreateView(generics.ListCreateAPIView):
    queryset = Notes.objects.all()
    serializer_class = NotesSerializer
    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        # Check if 'lead_id' is present in the request data
        request.data["created_by"] = request.user.id
        lead = request.data.get("lead")
        task_complete = request.data.get("task_complete",None)
        accounts_param = request.data.get("accounts_param",None)


        if lead is None:
            # If 'lead_id' is missing, return an error response
            return ResponseHandler(True, 'Lead ID is required in the request data.', None, status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            if accounts_param is None:
                print("Inside accounts")
                lead_obj = Lead.objects.filter(pk=lead).first()
                if lead_obj:
                    workflow = lead_obj.workflow.get()
                    followup_task = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
                    if followup_task and task_complete:
                        followup_task.completed = True
                        followup_task.completed_at = timezone.now()
                        followup_task.save()
            return ResponseHandler(False , 'Remark added successfully.', serializer.data ,status.HTTP_201_CREATED)
        else:
            return ResponseHandler(True , serializer.errors , None,status.HTTP_400_BAD_REQUEST)

class NotesListView(generics.ListAPIView):
    serializer_class = NotesSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        lead_id = self.kwargs.get('lead_id')
        
        try:
            # Check if the Lead exists
            lead = Lead.objects.get(id=lead_id)
            # Fetch notes associated with the Lead
            queryset = Notes.objects.filter(lead=lead)
            return queryset.order_by('-created_on')
        
        except Lead.DoesNotExist:
            return Notes.objects.none()

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        date_range_param = request.GET.get('date_range', None)


        if date_range_param == 'last_7_days':
            seven_days_ago = datetime.now() - timedelta(days=7)
            queryset = queryset.filter(created_on__gte=seven_days_ago)
        elif date_range_param == 'last_2_weeks':
            two_weeks_ago = datetime.now() - timedelta(weeks=2)
            queryset = queryset.filter(created_on__gte=two_weeks_ago)
        elif date_range_param == 'last_1_month':
            one_month_ago = datetime.now() - timedelta(days=30)
            queryset = queryset.filter(created_on__gte=one_month_ago)
        elif date_range_param == 'last_6_months':
            six_months_ago = datetime.now() - timedelta(days=180)
            queryset = queryset.filter(created_on__gte=six_months_ago)
            
        if queryset.exists():

            serializer = self.get_serializer(queryset, many=True)
            return ResponseHandler(False, "Remarks retrieved successfully." , serializer.data,status.HTTP_200_OK)
        else:
            return ResponseHandler(False, "Remarks are not present.", [], status.HTTP_200_OK)


class UpdateOrDeleteNoteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notes.objects.all()
    serializer_class = NotesSerializer
    permission_classes = (IsAuthenticated,)
    lookup_field = 'id'

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return ResponseHandler(False, 'Remarks retrieved successfully', serializer.data, status.HTTP_200_OK)
        except Notes.DoesNotExist:
            return ResponseHandler(True, 'Remarks ID not found', None, status.HTTP_404_NOT_FOUND)
        
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)

            if serializer.is_valid():
                queryset = Notes.objects.get(pk=kwargs['id'])
                if queryset.created_by == self.request.user:
                    serializer.save()
                    return ResponseHandler(False, "Remarks updated successfully.", serializer.data, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, 'Access Denied', None, status.HTTP_400_BAD_REQUEST)
            else:
                return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
        except Notes.DoesNotExist:
            return ResponseHandler(True, "Remark not found.", "Note not found.", status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHandler(True, "An error occurred.", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance:
                instance.delete()
                return ResponseHandler(False, "Remark deleted successfully.", None, status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Remark not found.", None, status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHandler(True, "An error occurred.", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

class SiteVisitBookingView(generics.CreateAPIView):
    queryset = SiteVisit.objects.all()
    serializer_class = SiteVisitSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        lead_id = request.data.get('lead')
        lead_obj = Lead.objects.get(id=lead_id) if lead_id else None
        site_visit_type_param = request.data.get('site_visit_type',None)
        closing_manager = request.data.get('closing_manager',None)
        sourcing_manager = request.data.get('sourcing_manager', None)
        visit_date_str = request.data.get('visit_date')
        visit_date = datetime.strptime(visit_date_str, '%Y-%m-%d').date()
        print('visit_date:', visit_date)
        

        if closing_manager and sourcing_manager:
            return ResponseHandler(False, "Only one of closing manager or sourcing manager should be assigned.", None, status.HTTP_400_BAD_REQUEST)

        # Check if the booking date is in the past
        current_datetime = timezone.now()
        if visit_date < current_datetime.date():
            return ResponseHandler(False, "Cannot book site visit in the past.", None, status.HTTP_400_BAD_REQUEST)
        
        if site_visit_type_param is not None and site_visit_type_param == "Snagging":

            # Check if a site visit record exists for the lead
            site_visits = SiteVisit.objects.filter(lead=lead_id,site_visit_type="Snagging").order_by('-visit_date')

            if site_visits.exists():
                latest_site_visit = site_visits.filter(site_visit_status='Scheduled')

                # Check if the latest site visit has occurred or was missed
                if latest_site_visit.exists():
                    return ResponseHandler(False, "Cannot book a new site visit. Previous visit not completed.", None, status.HTTP_400_BAD_REQUEST)
                # # Create a new rescheduled date entry if the previous visit was missed
                # if latest_site_visit.site_visit_status == "Scheduled Visit Missed":
                #     RescheduledDate.objects.create(site_visit=latest_site_visit, new_date=visit_date)

            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            #
            serializer.save()
            lead = Lead.objects.filter(pk=lead_id).first()
            lead_workflow = lead.workflow.get()
            existing_sitevisit_tasks = lead_workflow.tasks.filter(name='Snagging Site Visit', completed=False).order_by('-time').last()    

            state = get_object_or_404(State, label='Accept')
            current_stage = Stage.objects.filter(workflow = lead_workflow, name = 'PostSales').order_by('order').first()
            data=   {
                        "stage":current_stage,
                        "name": f"Snagging Site Visit",
                        "order":0,
                        "task_type": "appointment",
                        "workflow":lead_workflow,
                        "appointment_with": f"{lead.first_name} {lead.last_name}",
                        "appointment_type": "telephonic",
                        "time": visit_date - timedelta(hours=24),
                        "details":"Site Visit Reminder",
                        "status": state,
                        "minimum_approvals_required": 0
                }
            task = Task.objects.create(**data)
            stage = current_stage
            max_order_dict = stage.tasks.aggregate(Max('order'))
            max_order_yet = max_order_dict.get('order__max', None)
            print('max_order_yet:', max_order_yet)
            if max_order_yet:
                task.order = max_order_yet+1
            else:
                task.order = 1
            task.save()
        else:

            # Check if a site visit record exists for the lead
            site_visits = SiteVisit.objects.filter(lead=lead_id,site_visit_type="Regular").order_by('-visit_date')
            print("site_visits",site_visits)
            if site_visits.exists():
                closing_manager_instance = site_visits.first().closing_manager
                sourcing_manager_instance = site_visits.first().sourcing_manager
                if closing_manager_instance:
                    request.data["closing_manager"] = closing_manager_instance.id
                    closing_manager = request.data.get("closing_manager")
                    print("Closing Manager:", closing_manager)
                elif sourcing_manager_instance:
                    # Handle the case where closing_manager is None
                    request.data["sourcing_manager"] = site_visits.first().sourcing_manager.id
                    sourcing_manager = request.data.get("sourcing_manager")
                    print("Sourcing Manager:", sourcing_manager)
                else:
                    return ResponseHandler(True, "Cannot book a new site visit. Without assigning closing or sourcing manager", None, status.HTTP_400_BAD_REQUEST)    
               
                latest_site_visit = site_visits.filter(site_visit_status='Scheduled')
                print("latest site visit",latest_site_visit)

                # Check if the latest site visit has occurred or was missed
                if latest_site_visit.exists():
                    return ResponseHandler(False, "Cannot book a new site visit. Previous visit not completed.", None, status.HTTP_400_BAD_REQUEST)
                # # Create a new rescheduled date entry if the previous visit was missed
                # if latest_site_visit.site_visit_status == "Scheduled Visit Missed":
                #     RescheduledDate.objects.create(site_visit=latest_site_visit, new_date=visit_date)

            # Book a new site visit
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()

            # sitevisit_booked = serializer.save()
            # Site visit notification to be sent 24hrs before site visit 
            # notify - Executive (pre-sales)
            # notify - CM & Receptionist (sales)
            lead = Lead.objects.filter(pk=lead_id).first()
            lead_workflow = lead.workflow.get()
            existing_sitevisit_tasks = lead_workflow.tasks.filter(name='Site Visit', completed=False).order_by('-time').last()    
            # print('lead:', lead, serializer.data['id'])
            # print('lead:', visit_date - timedelta(hours=24))
            state = get_object_or_404(State, label='Accept')
            current_stage = Stage.objects.filter(workflow = lead_workflow, completed=False).order_by('order').first()
            data=   {
                        "stage": current_stage,
                        "name": f"Site Visit",
                        "order":0,
                        "task_type": "appointment",
                        "workflow":lead_workflow,
                        "appointment_with": f"{lead.first_name} {lead.last_name}",
                        "appointment_type": "telephonic",
                        "time": visit_date - timedelta(hours=24),
                        "details":"Site Visit Reminder",
                        "status": state,
                        "minimum_approvals_required": 0
                }
            task = Task.objects.create(**data)
            task.started = True
            task.started_at = timezone.now()
            # stage = lead.workflow.get().stages.first()
            stage = current_stage
            max_order_dict = stage.tasks.aggregate(Max('order'))
            max_order_yet = max_order_dict.get('order__max', None)
            print('max_order_yet:', max_order_yet)
            if max_order_yet:
                task.order = max_order_yet+1
            else:
                task.order = 1

            # timeslot_start_str = sitevisit_booked.timeslot.split(" to ")[0]
            # print("timselot_stat: ", timeslot_start_str)
            # timeslot_start_datetime = datetime.strptime(timeslot_start_str, "%I:%M %p")
            # current_time = datetime.now()
            # visit_date_str = sitevisit_booked.visit_date
            # timeslot_str = sitevisit_booked.timeslot.split(" to ")[0]

            # visit_datetime_str = f"{visit_date_str} {timeslot_str}"

        
            # visit_datetime = datetime.strptime(visit_datetime_str, "%Y-%m-%d %I:%M %p")
            # followup =  visit_datetime - current_time
            # print("current time:", current_time)
            # print("timeslot_start_datetime:", visit_datetime)
            # print("followup time:", followup)        
            # if followup < timedelta(hours=12):
            #     follow_up_interval = 6
            # elif timedelta(hours=12) <= followup < timedelta(hours=24):
            #     follow_up_interval = 12
            # else:
            #     follow_up_interval = 24
            # print("followup time:", follow_up_interval)
            # follow_up_1 = NotificationMeta.objects.create(task=task,name=f"Site Visit", time_interval=follow_up_interval)
            follow_up_1 = NotificationMeta.objects.create(task=task,name=f"Site Visit",time_interval=24)
            SITE_HEAD = Users.objects.filter(groups__name="SITE_HEAD")
            site_head_ids = SITE_HEAD.values_list('id', flat=True)
            # print('follow_up_1:', follow_up_1)
            follow_up_1.users.set(site_head_ids)# site head CHANGE

            follow_up_2 = NotificationMeta.objects.create(task=task,name=f"Site Visit",time_interval=48)
            VICE_PRESIDENT = Group.objects.get(name="VICE_PRESIDENT")
            follow_up_2.groups.set([VICE_PRESIDENT])

            follow_up_3 = NotificationMeta.objects.create(task=task,name=f"Site Visit",time_interval=168)
            PROMOTER = Group.objects.get(name="PROMOTER")
            follow_up_3.groups.set([PROMOTER])

            task.current_notification_meta = follow_up_1
            task.save()

        if closing_manager:
            user_vp = Users.objects.filter(id=closing_manager).first()
            if user_vp.groups.filter(name="CLOSING_MANAGER").exists():
                title = "You have been assigned a new lead."
                body = f"You have been assigned a new lead, {lead_obj.first_name} {lead_obj.last_name}."
                data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/sales/my_visit/lead_details/{lead_obj.id}/0'}

                fcm_token = user_vp.fcm_token

                Notifications.objects.create(notification_id=f"task-{task.id}-{user_vp.id}", user_id=user_vp,created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{lead_obj.id}/0')

                send_push_notification(fcm_token, title, body, data)   
            elif user_vp.groups.filter(name="CRM_EXECUTIVE").exists():

                followers_list = lead_obj.followers

                if closing_manager not in followers_list:

                    cce_executive_present = False
                    cce_executive_user_id = None
                    for follower_id in followers_list:
                        follower_user = Users.objects.filter(id=follower_id).first()
                        if follower_user and follower_user.groups.filter(name="CRM_EXECUTIVE").exists():
                            cce_executive_present = True
                            cce_executive_user_id = follower_id
                            break

                    if cce_executive_present:
                        lead_obj.followers.remove(cce_executive_user_id)
                        lead_obj.followers.append(closing_manager)
                        lead_obj.save()
                    else:
                        lead_obj.followers.append(closing_manager)
                        lead_obj.save()

                title = "Snagging Site Visit Scheduled."
                body = f"Snagging Site Visit Scheduled for {lead_obj.first_name} {lead_obj.last_name}."
                data = {'notification_type': 'snagging','redirect_url': f'/post_sales/all_clients/lead_details/{lead_obj.id}/0'}

                fcm_token = user_vp.fcm_token

                Notifications.objects.create(notification_id=f"sv-{lead_obj.id}-{user_vp.id}", user_id=user_vp,created=timezone.now(), notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{lead_obj.id}/0')

                send_push_notification(fcm_token, title, body, data) 
        if sourcing_manager:
            user_sm = Users.objects.filter(id=sourcing_manager).first()
            if user_sm.groups.filter(name="SOURCING_MANAGER").exists():
                title = "You have been assigned a new lead."
                body = f"You have been assigned a new lead, {lead_obj.first_name} {lead_obj.last_name}."
                data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/sales/my_visit/lead_details/{lead_obj.id}/0'}

                fcm_token = user_sm.fcm_token

                Notifications.objects.create(notification_id=f"task-{task.id}-{user_sm.id}", user_id=user_sm, created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{lead_obj.id}/0')

                send_push_notification(fcm_token, title, body, data)
            elif user_sm.groups.filter(name="CRM_EXECUTIVE").exists():
                followers_list = lead_obj.followers

                if sourcing_manager not in followers_list:
                    cce_executive_present = False
                    cce_executive_user_id = None
                    for follower_id in followers_list:
                        follower_user = Users.objects.filter(id=follower_id).first()
                        if follower_user and follower_user.groups.filter(name="CRM_EXECUTIVE").exists():
                            cce_executive_present = True
                            cce_executive_user_id = follower_id
                            break

                    if cce_executive_present:
                        lead_obj.followers.remove(cce_executive_user_id)
                        lead_obj.followers.append(sourcing_manager)
                        lead_obj.save()
                    else:
                        lead_obj.followers.append(sourcing_manager)
                        lead_obj.save()

                title = "Snagging Site Visit Scheduled."
                body = f"Snagging Site Visit Scheduled for {lead_obj.first_name} {lead_obj.last_name}."
                data = {'notification_type': 'snagging', 'redirect_url': f'/post_sales/all_clients/lead_details/{lead_obj.id}/0'}

                fcm_token = user_sm.fcm_token

                Notifications.objects.create(notification_id=f"sv-{lead_obj.id}-{user_sm.id}", user_id=user_sm, created=timezone.now(), notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{lead_obj.id}/0')

                send_push_notification(fcm_token, title, body, data)
             
        # setting Follow up task complete 
        followup_task = lead_workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
        if followup_task:
            followup_task.completed = True
            followup_task.completed_at = timezone.now()
            followup_task.save()

        #Checking if previous sitevisit task if exist marking it as completed
        #lead_data = get_object_or_404(Lead, id=lead_id)
        #workflow_previous = lead.workflow.get()

        if existing_sitevisit_tasks:
            print('existing_sitevisit_tasks:', existing_sitevisit_tasks)
            existing_sitevisit_tasks.completed =True
            existing_sitevisit_tasks.completed_at =timezone.now()
            existing_sitevisit_tasks.save()
        # process_task.delay(task.id)

        ## TODO - if follow up to be done tomorrow , then notifications should be sent after 4 hours/ 8 hours etc.
        # setup 

        headers = self.get_success_headers(serializer.data)
        #return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)#add true false
        return ResponseHandler(False, "Site Visit Scheduled ", serializer.data, status.HTTP_201_CREATED)

class SiteVisitDetailsbyId(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, generics.GenericAPIView):
    queryset = SiteVisit.objects.all()
    serializer_class = SiteVisitSerializer
    permission_classes = (IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        lead_id = self.kwargs.get('pk')
        module_param = self.request.query_params.get('module', None)

        try:
            if module_param == "activity":
                today = date.today()

                site_visits = SiteVisit.objects.filter(lead=lead_id).order_by('-visit_date')
                #print("Site visits: ",site_visits )
                date_range_param = request.GET.get('date_range', None)
                if date_range_param == 'last_7_days':
                    seven_days_ago = today - timedelta(days=7)
                    site_visits = site_visits.filter(visit_date__gte=seven_days_ago)
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = today - timedelta(weeks=2)
                    site_visits = site_visits.filter(visit_date__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = today - timedelta(days=30)
                    site_visits = site_visits.filter(visit_date__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = today - timedelta(days=180)
                    site_visits = site_visits.filter(visit_date__gte=six_months_ago)

                site_visits = site_visits.order_by('-visit_date')
                site_visits_data = site_visits
                
                site_visit_history_all = []

                for site_visit in site_visits_data:
                    site_visit_history = []
                    history_records = site_visit.history.all()
                    serialized_history = SiteVisitHistorySerializer(history_records, many=True).data
                    site_visit_history.extend(serialized_history)

                    sorted_history = sorted(site_visit_history, key=lambda x: x['history_date'], reverse=True)

                    for record in sorted_history:
                        if record['history_type'] == "+":
                            if record['activity_type'] == 'SiteVisit':
                                visit_date = record['visit_date']
                                date_obj = datetime.strptime(visit_date, "%Y-%m-%d")
                                formatted_date = date_obj.strftime("%B %d, %Y")
                                timeslot = record['timeslot']
                                start_time = timeslot.split(" to ")[0]
                                record['message'] = f'Site Visit Scheduled at {formatted_date} at {start_time}'

                        if record['history_type'] == "~":
                            previous_record = None
                            if record['activity_type'] == 'SiteVisit':
                                previous_record = next(
                                    (prev for prev in sorted_history if prev['history_date'] < record['history_date'] and prev['activity_type'] == 'SiteVisit'),
                                    None
                                )    
                                                    
                            if previous_record:

                                changed_fields = self.find_changed_fields(previous_record, record)
                                if changed_fields:
                                    record['changed_fields'] = changed_fields


                                    if 'timeslot' in changed_fields and changed_fields['timeslot']['new_value'] or 'visit_date' in changed_fields and changed_fields['visit_date']['new_value']:
                                        if 'timeslot' in changed_fields and changed_fields['timeslot']['new_value'] and 'visit_date' in changed_fields and changed_fields['visit_date']['new_value']:
                                            vist_dt = changed_fields['visit_date']['new_value']
                                            vist_dt_obj = datetime.strptime(vist_dt, "%Y-%m-%d")
                                            formatted_vist_dt = vist_dt_obj.strftime("%B %d, %Y")
                                            timest=changed_fields['timeslot']['new_value']
                                            record['message'] = f'Site Visit Rescheduled to {formatted_vist_dt} at {timest.split(" to ")[0]}'
                                        elif 'visit_date' in changed_fields and changed_fields['visit_date']['new_value']:
                                            old_date = changed_fields['visit_date']['old_value']
                                            old_date_obj = datetime.strptime(old_date, "%Y-%m-%d")
                                            formatted_old_date = old_date_obj.strftime("%B %d, %Y")
                                            new_date = changed_fields['visit_date']['new_value']
                                            new_date_obj = datetime.strptime(new_date, "%Y-%m-%d")
                                            formatted_new_date = new_date_obj.strftime("%B %d, %Y")                                    
                                            record['message'] = f'Site Visit Rescheduled from {formatted_old_date} to {formatted_new_date}'  
                                        else:
                                            timest=changed_fields['timeslot']['new_value']
                                            record['message'] = f'Site Visit Rescheduled to {timest.split(" to ")[0]}'                                         
                                    if 'site_visit_status' in changed_fields and changed_fields['site_visit_status']['new_value'] == "Missed":
                                        record['message'] = 'Site Visit Missed'
                                    if 'site_visit_status' in changed_fields and changed_fields['site_visit_status']['new_value'] == "Site Visit Done" and record['site_visit_type'] =="Regular":
                                        record['message'] = "Site Visit Done"      


                    sorted_history = [record for record in sorted_history if record['message'] not in ["SiteVisit Updated"]]                  
                    site_visit_history_all.extend(sorted_history)

                if site_visits.exists():
                    last_site_visit = site_visits.first()
                    #print("last_site_visit Site visits: ",last_site_visit )
                    if last_site_visit.site_visit_status == 'Scheduled': #and last_site_visit.visit_date >= today: add when cron job is ready
                        #print("UPCOMING : ", )
                        upcoming_instances = site_visits.filter(
                            visit_date__gte=today
                        ).order_by('-visit_date')

                        upcoming_serializer = self.get_serializer(upcoming_instances, many=True)
                        site_visits = self.get_serializer(site_visits, many=True) 
                        response_data = {
                            'upcoming_site_visits': upcoming_serializer.data,
                            'site_visit_history': site_visit_history_all,  
                        }

                        return ResponseHandler(False, 'Site Visit activity retrieved successfully.', response_data, status.HTTP_200_OK)

                    elif last_site_visit.site_visit_status == 'Missed':

                        followups = site_visits.filter(
                             visit_date__lte=today
                        ).order_by('-visit_date')

                        followups_serializer = self.get_serializer(followups, many=True)
                        response_data = {
                            'followups': followups_serializer.data,
                            'site_visit_history': site_visit_history_all,  
                        }

                        return ResponseHandler(False, 'Site Visit activity retrieved successfully.', response_data, status.HTTP_200_OK)

                    elif last_site_visit.site_visit_status == 'Site Visit Done':
  
                        response_data = {
                            'upcoming_site_visits':[] ,
                            'site_visit_history': site_visit_history_all,  
                        }

                        return ResponseHandler(False, 'Site Visit activity retrieved successfully.', response_data, status.HTTP_200_OK)

                else:
                    response_data = {
                        'upcoming_site_visits':[] ,
                        'followups': [],
                        'site_visit_history': [],  
                    }
                    return ResponseHandler(False, 'Site Visit retrieved successfully.', response_data, status.HTTP_200_OK)
            elif module_param == "snagging":
                instances = SiteVisit.objects.filter(lead=lead_id,site_visit_type = 'Snagging').order_by('-id')
                serializer = self.get_serializer(instances, many=True)
                return ResponseHandler(False, 'Site Visit retrieved successfully.', serializer.data, status.HTTP_200_OK)                
            else:
                instances = SiteVisit.objects.filter(lead=lead_id).order_by('-id')
                serializer = self.get_serializer(instances, many=True)
                return ResponseHandler(False, 'Site Visit retrieved successfully.', serializer.data, status.HTTP_200_OK)

        except SiteVisit.DoesNotExist:
            return ResponseHandler(True, 'Site Visit does not exist', None, status.HTTP_404_NOT_FOUND)            
        except Exception as e:
            return ResponseHandler( True, "Error: ",str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    def find_changed_fields(self, previous_record, current_record):
        return {
            key: {
                'old_value': previous_record.get(key),
                'new_value': value,
            }
            for key, value in current_record.items()
            if (
                key not in ('changed_fields', 'history_date', 'history_type', 'history_user', 'message','activity_type')
                and previous_record.get(key) != value
            )
        }
        
class SiteVisitUpdateView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, generics.GenericAPIView):
    queryset = SiteVisit.objects.all()
    serializer_class = SiteVisitSerializer
    

    def get(self, request, *args, **kwargs):
        sitevisit_id = self.kwargs.get('pk')  
        try:
            instance = SiteVisit.objects.get(pk=sitevisit_id)
            serializer = self.get_serializer(instance)
            return ResponseHandler(False, 'Site Visit retrieved successfully', serializer.data, status.HTTP_200_OK)
        except SiteVisit.DoesNotExist:
            return ResponseHandler(True, 'Site Visit ID not found', None, status.HTTP_404_NOT_FOUND)

    def put(self, request, *args, **kwargs):
        sitevisit_id = self.kwargs.get('pk')
        try:
            instance = SiteVisit.objects.get(pk=sitevisit_id)
            site_visit_status = request.data.get("site_visit_status")
            closing_manager =  request.data.get("closing_manager")
            sourcing_manager = request.data.get("sourcing_manager")

            if site_visit_status and site_visit_status == "Site Visit Done":
                if instance.visit_date != datetime.now().date():
                    return ResponseHandler(False, "Site Visit Date has not arrived", None, status.HTTP_400_BAD_REQUEST)
            #print("request.data: ", request.data,request.data['site_visit_status'],site_visit_status)
                
            lead_name = f"{instance.lead.first_name} {instance.lead.last_name}"
 
            # To ensure only one add at a time
            if closing_manager and sourcing_manager:
                return ResponseHandler(True, "Only one of sourcing_manager or closing_manager can be assigned at a time.", None, status.HTTP_400_BAD_REQUEST)
            
            # for assigning closing manager
            if closing_manager:
                instance.closing_manager_id = closing_manager
                instance.sourcing_manager = None
                user_vp = Users.objects.filter(id=closing_manager).first()
                if user_vp.groups.filter(name="CLOSING_MANAGER").exists():
                    title = "You have been assigned a new lead."
                    body = f"You have been assigned a new lead, {lead_name}."
                    data = {'notification_type': 'site_visit','redirect_url': f'/sales/my_visit/lead_details/{instance.lead.id}/0'}

                    fcm_token = user_vp.fcm_token

                    Notifications.objects.create(notification_id=f"sv-{instance.id}-{user_vp.id}", user_id=user_vp,created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{instance.lead.id}/0')

                    send_push_notification(fcm_token, title, body, data)  
                elif user_vp.groups.filter(name="CRM_EXECUTIVE").exists():
                    title = "Snagging Site Visit Scheduled."
                    body = f"Snagging Site Visit Scheduled for {lead_name}."
                    data = {'notification_type': 'snagging','redirect_url': f'/post_sales/all_clients/lead_details/{instance.lead.id}/0'}

                    fcm_token = user_vp.fcm_token

                    Notifications.objects.create(notification_id=f"sv-{instance.id}-{user_vp.id}", user_id=user_vp,created=timezone.now(), notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{instance.lead.id}/0')

                    send_push_notification(fcm_token, title, body, data) 
            # for assigning sourcing manager          
            if sourcing_manager:
                instance.sourcing_manager_id = sourcing_manager
                instance.closing_manager = None
                user_sm = Users.objects.filter(id=sourcing_manager).first()
                if user_sm.groups.filter(name="SOURCING_MANAGER").exists():
                    title = "You have been assigned a new lead."
                    body = f"You have been assigned a new lead, {lead_name}."
                    data = {'notification_type': 'site_visit','redirect_url': f'/sales/my_visit/lead_details/{instance.lead.id}/0'}
                    fcm_token = user_sm.fcm_token
                    Notifications.objects.create(notification_id=f"sv-{instance.id}-{user_sm.id}", user_id=user_sm, created=timezone.now(), notification_message=body, notification_url=f'/sales/my_visit/lead_details/{instance.lead.id}/0')
                    send_push_notification(fcm_token, title, body, data)
                elif user_vp.groups.filter(name="CRM_EXECUTIVE").exists():
                    title = "Snagging Site Visit Scheduled."
                    body = f"Snagging Site Visit Scheduled for {lead_name}."
                    data = {'notification_type': 'snagging','redirect_url': f'/post_sales/all_clients/lead_details/{instance.lead.id}/0'}

                    fcm_token = user_vp.fcm_token

                    Notifications.objects.create(notification_id=f"sv-{instance.id}-{user_vp.id}", user_id=user_vp,created=timezone.now(), notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{instance.lead.id}/0')

                    send_push_notification(fcm_token, title, body, data) 

            instance.save()        

            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)

            self.perform_update(serializer)
            serializer.save()
            # updated_instance = self.get_object()
            # updated_serializer = self.get_serializer(updated_instance)
            return ResponseHandler(False, 'Site Visit updated successfully', serializer.data, status.HTTP_200_OK)
        except SiteVisit.DoesNotExist:
            return ResponseHandler(True, 'Site Visit ID not found', None, status.HTTP_404_NOT_FOUND)

    def perform_update(self, serializer):
        try:
            if 'snagging_status' in serializer.validated_data:
                snagging_status = serializer.validated_data['snagging_status']

                if snagging_status == "Snagging clear":
                    lead = serializer.instance.lead
                    workflow = lead.workflow.get()
                    project_inventory = ProjectInventory.objects.filter(lead=lead).first()
                    sv_followup = workflow.tasks.filter(name='Snagging Site Visit', completed=False).order_by('-time').last()
                    print('sv_followup:', sv_followup)
                    sv_followup.completed =True
                    sv_followup.completed_at =timezone.now()
                    sv_followup.save()
                    crm_head = Users.objects.filter(groups__name = "CRM_HEAD").first()
                    apartment_no = project_inventory.apartment_no if project_inventory and project_inventory.apartment_no else None
                    title = f"Snagging Cleared at {apartment_no} for {lead.first_name} {lead.last_name}"
                    body = f"Snagging Cleared at {apartment_no} for {lead.first_name} {lead.last_name}"
                    data = {'notification_type': 'snagging'}
                    if crm_head:
                        fcm_token_crmhead = crm_head.fcm_token
                        Notifications.objects.create(notification_id=f"task-{lead.id}-{crm_head.id}", user_id=crm_head,created=timezone.now(),  notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{lead.id}/0')
                        send_push_notification(fcm_token_crmhead, title, body, data)

                elif snagging_status == "Defects Spotted":
                    lead = serializer.instance.lead
                    site_visits = SiteVisit.objects.filter(lead=lead,site_visit_type="Snagging", site_visit_status="Scheduled").first()
                    site_visits.site_visit_status = "Site Visit Done"
                    site_visits.save()
                    project_inventory = ProjectInventory.objects.filter(lead=lead).first()
                    workflow = lead.workflow.get()
                    apartment_no = project_inventory.apartment_no if project_inventory and project_inventory.apartment_no else None
                    sv_followup = workflow.tasks.filter(name='Snagging Site Visit', completed=False).order_by('-time').last()
                    print('sv_followup:', sv_followup)
                    sv_followup.completed =True
                    sv_followup.completed_at =timezone.now()
                    sv_followup.save()

                    crm_head = Users.objects.filter(groups__name = "CRM_HEAD").first()

                    title = f"Defects Spotted at {apartment_no} for {lead.first_name} {lead.last_name}"
                    body = f"Defects Spotted at {apartment_no} for {lead.first_name} {lead.last_name}"
                    data = {'notification_type': 'snagging'}

                    if crm_head:
                        fcm_token_crmhead = crm_head.fcm_token
                        Notifications.objects.create(notification_id=f"task-{lead.id}-{crm_head.id}", user_id=crm_head,created=timezone.now(),  notification_message=body, notification_url=f'/post_sales/all_clients/lead_details/{lead.id}/0')
                        send_push_notification(fcm_token_crmhead, title, body, data)  

            if 'site_visit_status' in serializer.validated_data:
                site_visit_status = serializer.validated_data['site_visit_status']

                if site_visit_status == "Site Visit Done":
                    lead = serializer.instance.lead
                    previous_site_visits = SiteVisit.objects.filter(lead=lead, site_visit_status="Site Visit Done")
                    print('previous_site_visits:', previous_site_visits)

                    if not previous_site_visits.exists():
                        lead.converted_on = serializer.instance.visit_date
                        lead.save()

                    workflow = lead.workflow.get()

                    sv_followup = workflow.tasks.filter(name='Site Visit', completed=False).order_by('-time').last()
                    print('sv_followup:', sv_followup)
                    sv_followup.completed =True
                    sv_followup.completed_at =timezone.now()
                    sv_followup.save()


        except Exception as e:
            print(f"An error occurred: {e}")
            return ResponseHandler(True, str(e), None, status.HTTP_400_BAD_REQUEST)

        serializer.save()

    
    def delete(self, request, *args, **kwargs):
        sitevisit_id = self.kwargs.get('pk')
        try:
            instance = SiteVisit.objects.get(pk=sitevisit_id)
            self.perform_destroy(instance)
            return ResponseHandler(False, 'Site Visit deleted successfully' , None,status.HTTP_204_NO_CONTENT)
        except SiteVisit.DoesNotExist:
            return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND)


# class GetClosingManager(generics.ListAPIView):
#     queryset = Lead.objects.all()
#     serializer_class = SiteVisitSerializer

#     def get(self, request, *args, **kwargs):
#         # Check if there are any users in the "CLOSING_MANAGER" group
#         all_closing_managers = Users.objects.filter(groups__name="CLOSING_MANAGER")
        
#         if all_closing_managers.exists():
#             serialized_all_closing_managers = UserDataSerializer(all_closing_managers, many=True)
#             return Response({"available_closing_managers": serialized_all_closing_managers.data}, status=status.HTTP_200_OK)
#         else:
#             return Response({"message": "No closing managers available"}, status=status.HTTP_404_NOT_FOUND)

class GetClosingManager(generics.ListAPIView):
    queryset = Lead.objects.all()
    serializer_class = SiteVisitSerializer

    def get(self, request, *args, **kwargs):
        user = self.request.user
        group_names = user.groups.values_list('name', flat=True)
        
        # Check if the user is in the "Receptionist" group
        if "RECEPTIONIST" in group_names:
            # Get all users in the "CLOSING_MANAGER" group
            all_closing_managers = Users.objects.filter(groups__name="CLOSING_MANAGER")
            # Get all users in the "SOURCING_MANAGER" group
            all_sourcing_managers = Users.objects.filter(groups__name="SOURCING_MANAGER")

            # Serialize the data for both groups
            serialized_closing_managers = UserDataSerializer(all_closing_managers, many=True)
            serialized_sourcing_managers = UserDataSerializer(all_sourcing_managers, many=True)

            combined_data = list(serialized_closing_managers.data) + list(serialized_sourcing_managers.data)

            # Return both lists if the user is a Receptionist
            return Response({
                "available_closing_managers": serialized_closing_managers.data,
                "available_sourcing_managers": serialized_sourcing_managers.data,
                "available_both_managers": combined_data
            }, status=status.HTTP_200_OK)

        # Check if there are any users in the "CLOSING_MANAGER" group
        all_closing_managers = Users.objects.filter(groups__name="CLOSING_MANAGER")

        if all_closing_managers.exists():
            serialized_all_closing_managers = UserDataSerializer(all_closing_managers, many=True)
            return Response({"available_closing_managers": serialized_all_closing_managers.data}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "No closing managers available"}, status=status.HTTP_404_NOT_FOUND)

class GetSourcingManager(generics.ListAPIView):
    queryset = Lead.objects.all()
    serializer_class = SiteVisitSerializer

    def get(self, request, *args, **kwargs):
        user = self.request.user
        group_names = user.groups.values_list('name', flat=True)
        
        # Check if the user is in the "Receptionist" group
        if "RECEPTIONIST" in group_names:
            # Get all users in the "CLOSING_MANAGER" group
            all_closing_managers = Users.objects.filter(groups__name="CLOSING_MANAGER")
            # Get all users in the "SOURCING_MANAGER" group
            all_sourcing_managers = Users.objects.filter(groups__name="SOURCING_MANAGER")

            # Serialize the data for both groups
            serialized_closing_managers = UserDataSerializer(all_closing_managers, many=True)
            serialized_sourcing_managers = UserDataSerializer(all_sourcing_managers, many=True)

            combined_data = list(serialized_closing_managers.data) + list(serialized_sourcing_managers.data)

            # Return both lists if the user is a Receptionist
            return Response({
                "available_closing_managers": serialized_closing_managers.data,
                "available_sourcing_managers": serialized_sourcing_managers.data,
                "available_both_managers": combined_data
            }, status=status.HTTP_200_OK)
        
        # Check if there are any users in the "SOURCING_MANAGER" group
        all_sourcing_managers = Users.objects.filter(groups__name="SOURCING_MANAGER")
        
        if all_sourcing_managers.exists():
            serialized_all_sourcing_managers = UserDataSerializer(all_sourcing_managers, many=True)
            return Response({"available_sourcing_managers": serialized_all_sourcing_managers.data}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "No sourcing managers available"}, status=status.HTTP_404_NOT_FOUND)


class CalendarViewList(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self,request):
        try:
            month_name = self.request.query_params.get('month_name')
            frequency = self.request.query_params.get('frequency', 'monthly')
            year = self.request.query_params.get('year')
            start_date_param = self.request.query_params.get('start_date')
            end_date_param = self.request.query_params.get('end_date')
            if month_name is not None:
                if frequency == 'monthly' and  year is not None:
                    return self.filter_monthly(month_name)
                elif frequency == 'weekly' and start_date_param and end_date_param:
                    return self.filter_weekly()

            raise ValueError("Please provide valid parameters.")

        except ValueError as e:
            return ResponseHandler(True, str(e), None, 400)


    def filter_monthly(self, month_name):
        try:
            year = self.request.query_params.get('year')
            datetime_object = datetime.strptime(month_name, "%B")
            month_number = datetime_object.month
            total_days = monthrange(int(year), month_number)[1]


            site_visits_dict = {day: [] for day in range(1, total_days + 1)}

            site_visits = SiteVisit.objects.filter(visit_date__month=month_number)
            user = self.request.user
            if user.groups.filter(name="CLOSING_MANAGER").exists():
                site_visits = site_visits.filter(closing_manager=self.request.user)
            for site_visit in site_visits:
                day_number = site_visit.visit_date.day
                site_visits_dict[day_number].append(CalendarViewSerializer(site_visit).data)

            return ResponseHandler(False, "Calendar view:", site_visits_dict, 200)

        except ValueError:
            return ResponseHandler(True, "Invalid month name provided.", None, 404)


    def filter_weekly(self):
        start_date_param = self.request.query_params.get('start_date')
        end_date_param = self.request.query_params.get('end_date')

        try:
            if start_date_param and end_date_param:
                start_date = datetime.strptime(start_date_param, "%Y-%m-%d")
                end_date = datetime.strptime(end_date_param, "%Y-%m-%d")
            else:
                current_date = datetime.now().date()
                start_date = current_date - timedelta(days=current_date.weekday())
                end_date = start_date + timedelta(days=6)

            site_visits_dict = {day: {'site_visits': [], 'no_of_sitevisit': 0} for day in range(1, 8)}

            site_visits = SiteVisit.objects.filter(visit_date__range=[start_date, end_date]) 

            user = self.request.user
            if user.groups.filter(name="CLOSING_MANAGER").exists():
                site_visits = site_visits.filter(closing_manager=self.request.user)
                
            site_visits_per_day = site_visits.values('visit_date').annotate(no_of_sitevisit=Count('id'))

            for visit_data in site_visits_per_day:
                day_number = visit_data['visit_date'].isoweekday()
                site_visits_dict[day_number]['no_of_sitevisit'] = visit_data['no_of_sitevisit']

            for site_visit in site_visits:
                day_number = site_visit.visit_date.isoweekday()
                site_visits_dict[day_number]['site_visits'].append(CalendarViewSerializer(site_visit).data)

            return ResponseHandler(False, "Calendar view:", site_visits_dict, 200)


        except ValueError:
            return ResponseHandler(True, "Invalid date format provided.", None, 404)
        
class SiteVisitMetaAPIView(generics.ListAPIView):
    def list(self, request, *args, **kwargs):
        try:
            start_time = datetime.strptime('10:00 AM', '%I:%M %p')
            end_time = datetime.strptime('6:00 PM', '%I:%M %p')
            current_time = start_time

            timeslots = []

            while current_time <= end_time:
                timeslot_str = current_time.strftime('%I:%M %p') + ' to ' + (current_time + timedelta(minutes=30)).strftime('%I:%M %p')
                timeslots.append(timeslot_str)
                current_time += timedelta(minutes=30)

            projects = ProjectDetail.objects.all()
            project_names = [project.name for project in projects]

            meta_data = {'Timeslots': timeslots, 'Properties':project_names}

            return ResponseHandler(False, "Site Visit Meta Data", meta_data, 200)
        except Exception as e:
            return Response({'error': True, 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class AvailableTimeslotsView(generics.RetrieveAPIView):
    queryset = SiteVisit.objects.all()
    serializer_class = AvailableTimeslotsSerializer

    def get(self, request, lead_id, visit_date, *args, **kwargs):
        try:
            # Convert visit_date to a datetime object
            visit_date = datetime.strptime(visit_date, '%Y-%m-%d').date()
            today = datetime.now().date()
            current_time = datetime.now().time()

            if visit_date < today:
                return ResponseHandler(True, 'Invalid visit date', None, status.HTTP_400_BAD_REQUEST)

            # Retrieve existing booked time slots for the given visit date and lead
            existing_timeslots = SiteVisit.objects.filter(lead_id=lead_id, visit_date=visit_date).values_list('timeslot', flat=True)

            # Get all available time slots
            all_timeslots = [choice[0] for choice in SiteVisit.TIMESLOT_CHOICES]

            if visit_date == today:
                # Convert current time to string format for comparison
                current_time_str = current_time.strftime('%I:%M %p')
                # Filter out time slots that have already passed for today
                all_timeslots = [timeslot for timeslot in all_timeslots if self.is_time_after(self.get_time(timeslot), current_time_str)]

            # Filter out booked time slots from the list of all time slots to get available time slots
            available_timeslots = [timeslot for timeslot in all_timeslots if timeslot not in existing_timeslots]

            final_available_timeslots = []

            closing_manager_count = Users.objects.filter(groups__name="CLOSING_MANAGER").count()
            print('closing_manager_count:', closing_manager_count)

            for slot in available_timeslots:
                print('slot:', slot)
                sv_count_for_slot = SiteVisit.objects.filter(timeslot=slot, visit_date=visit_date).count()
                print('sv_count_for_slot:', sv_count_for_slot)
                if sv_count_for_slot <= closing_manager_count + 2:
                    final_available_timeslots.append(slot)
                

            return ResponseHandler(False, "Available slots retrived successfully.",final_available_timeslots, status.HTTP_200_OK)

        except Exception as e:
            return ResponseHandler(True, str(e),None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def is_time_after(self, time_obj, reference_time_str):
        # Convert reference time string to time object
        reference_time_obj = datetime.strptime(reference_time_str, '%I:%M %p').time()

        # Check if the time is after the reference time
        return time_obj > reference_time_obj

    def get_time(self, time_str):
        # Extract only the time portion from the time slot string
        time_portion = time_str.split("to")[0].strip()
        # Convert time portion to time object
        return datetime.strptime(time_portion, '%I:%M %p').time()
    
class GetMISDashboardDetailsView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)

     
    @staticmethod
    def calculate_follow_ups_count(queryset,follow_ups_filter_param):  
            def calculate_missed_follow_ups_today(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                
                if followup_tasks:
                    count = 0
                    now = timezone.now()
                    for task in followup_tasks:
                        task_date = task.time.date()
                        print("Follow-up task date:", task_date)
                        
                        # Check if the task is due today and if the time has passed
                        if task_date == now.date() and task.time < now:
                            count += 1
                            
                    print("Missed follow-ups count:", count)
                    return count

                return 0
            def calculate_missed_follow_ups_yesterday(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                
                if followup_tasks:
                    count = 0
                    now = timezone.now()
                    yesterday = now - timedelta(days=1)
                    for task in followup_tasks:
                        task_date = task.time.date()
                        print("Follow-up task date:", task_date)
                        
                        # Check if the task was due yesterday and if the time has passed
                        if task_date == yesterday.date() and task.time < now:
                            count += 1
                            
                    print("Missed follow-ups count for yesterday:", count)
                    return count

                return 0
            
            def calculate_missed_follow_ups_last_seven_days(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                
                if followup_tasks:
                    count = 0
                    now = timezone.now()
                    seven_days_ago = now - timedelta(days=7)
                    
                    for task in followup_tasks:
                        task_date = task.time.date()
                        print("Follow-up task date:", task_date)
                        
                        # Check if the task is due in the last seven days and if the time has passed
                        if seven_days_ago.date() <= task_date <= now.date() and task.time < now:
                            count += 1
                            
                    print("Missed follow-ups count (last 7 days):", count)
                    return count

                return 0
            
            def calculate_next_follow_up_today(lead):
                print("leads",lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up').order_by('-time')
                print("follow up ",followup_tasks)
                if followup_tasks:
                    count = 0
                    for task in followup_tasks:
                            print("follow up tasks date",task.time.date())
                            if task.time.date() == timezone.now().date():
                                count= count+1
                    print("follow ups count",count)
                    return count
                           # return task.time.date()
                return 0
            
            def calculate_next_follow_up_last_seven_days(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up').order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                
                if followup_tasks:
                    count = 0
                    now = timezone.now()
                    seven_days_ago = now - timedelta(days=7)
                    
                    for task in followup_tasks:
                        task_date = task.time.date()
                        print("Follow-up task date:", task_date)
                        
                        # Check if the task date is within the last seven days
                        if seven_days_ago.date() <= task_date <= now.date():
                            count += 1
                            
                    print("Follow-ups count (last 7 days):", count)
                    return count

                return 0
            
            def calculate_missed_follow_up_last_month(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                
                if followup_tasks:
                    count = 0
                    now = timezone.now()
                    last_month_ago = now - timedelta(days=30)
                    
                    for task in followup_tasks:
                        task_date = task.time.date()
                        print("Follow-up task date:", task_date)
                        
                        # Check if the task date is within the last seven days
                        if last_month_ago.date() <= task_date <= now.date():
                            count += 1
                            
                    print("Follow-ups count (last 30 days):", count)
                    return count

                return 0
            
            def calculate_next_follow_up_last_month(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up').order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                
                if followup_tasks:
                    count = 0
                    now = timezone.now()
                    last_month_ago = now - timedelta(days=30)
                    
                    for task in followup_tasks:
                        task_date = task.time.date()
                        print("Follow-up task date:", task_date)
                        
                        # Check if the task date is within the last seven days
                        if last_month_ago.date() <= task_date <= now.date():
                            count += 1
                            
                    print("Follow-ups count (last 30 days):", count)
                    return count

                return 0
            
            def calculate_next_follow_up_last_two_weeks(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up').order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                
                if followup_tasks:
                    count = 0
                    now = timezone.now()
                    last_two_ago = now - timedelta(days=14)
                    
                    for task in followup_tasks:
                        task_date = task.time.date()
                        print("Follow-up task date:", task_date)
                        
                        # Check if the task date is within the last seven days
                        if last_two_ago.date() <= task_date <= now.date():
                            count += 1
                            
                    print("Follow-ups count (last 30 days):", count)
                    return count

                return 0
            
            def calculate_missed_follow_up_last_two_weeks(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up' , completed = False).order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                
                if followup_tasks:
                    count = 0
                    now = timezone.now()
                    last_two_ago = now - timedelta(days=14)
                    
                    for task in followup_tasks:
                        task_date = task.time.date()
                        print("Follow-up task date:", task_date)
                        
                        # Check if the task date is within the last seven days
                        if last_two_ago.date() <= task_date <= now.date():
                            count += 1
                            
                    print("Follow-ups count (last 30 days):", count)
                    return count

                return 0

            def calculate_total_follow_ups(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up').order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                return followup_tasks.count()
                   
            def calculate_total_missed_follow_ups(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up' , completed=False).order_by('-time')
                print("Follow-up tasks:", followup_tasks)
                return followup_tasks.count()
            
            if follow_ups_filter_param == 'Today':
               # queryset = [lead for lead in queryset if (calculate_next_follow_up_today(lead) is not None) and calculate_next_follow_up(lead) == timezone.now().date()]
                queryset =  sum(calculate_next_follow_up_today(lead) for lead in queryset)
                print("today",queryset)
            elif follow_ups_filter_param == 'Missed_Last_7_Days':
                queryset =   sum(calculate_missed_follow_ups_last_seven_days(lead) for lead in queryset)
            elif follow_ups_filter_param == 'Missed_Today':  
                queryset = sum(calculate_missed_follow_ups_today(lead) for lead in queryset)
            elif follow_ups_filter_param == "Missed_Yesterday":    
                queryset = sum(calculate_missed_follow_ups_yesterday(lead) for lead in queryset)
            elif follow_ups_filter_param == 'Last_7_Days':
                queryset = sum( calculate_next_follow_up_last_seven_days(lead) for lead in queryset)
            elif follow_ups_filter_param == 'Total':
                queryset = sum(calculate_total_follow_ups(lead) for lead in queryset)   
            elif follow_ups_filter_param == 'Missed':
                queryset = sum(calculate_total_missed_follow_ups(lead) for lead in queryset)  
            elif follow_ups_filter_param == 'Missed_Last_Month':
                queryset = sum(calculate_missed_follow_up_last_month(lead) for lead in queryset) 
            elif follow_ups_filter_param == 'Last_Month':
                queryset = sum(calculate_next_follow_up_last_month(lead) for lead in queryset) 
            elif follow_ups_filter_param == 'Last_14_days':
                queryset = sum(calculate_next_follow_up_last_two_weeks(lead) for lead in queryset) 
            elif follow_ups_filter_param == 'Missed_Last_14_days':
                queryset = sum(calculate_missed_follow_up_last_two_weeks(lead) for lead in queryset)         
            # return len(queryset)
            return queryset

    @staticmethod
    def site_visit_calculation(queryset,site_visit_status_param,filter_param):
        # if site_visit_param:
            # stage = Stage.objects.filter(name='PreSales').first()
            # queryset = queryset.filter(workflow__current_stage=stage.order)
            
            if filter_param == "Today":
                start_date = datetime.now().date()
                end_date = start_date
            elif filter_param == "Weekly":
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=7)
            else:
                start_date = None
                end_date = None

            latest_site_visits = SiteVisit.objects.filter(
                lead=OuterRef('pk')
            ).order_by('-visit_date', '-timeslot').values('visit_date')[:1]

            queryset = queryset.annotate(
                latest_site_visit_date=Subquery(latest_site_visits.values('visit_date'))
            ).filter(latest_site_visit_date__isnull=False) 

            leads_with_latest_site_visit = []

            for lead in queryset:
                latest_site_visit = SiteVisit.objects.filter(
                    lead=lead,
                    visit_date=lead.latest_site_visit_date
                ).order_by('-visit_date', '-timeslot').first()

                if latest_site_visit:
                    latest_site_visit_status = latest_site_visit.site_visit_status
                    visit_date = latest_site_visit.visit_date
                else:
                    latest_site_visit_status = None
                    visit_date = None

                if (site_visit_status_param is None or latest_site_visit_status == site_visit_status_param) and \
                (start_date is None or end_date is None or (visit_date and start_date <= visit_date <= end_date)):
                    lead_data = {
                        "id": lead.id
                    }
                    leads_with_latest_site_visit.append(lead_data)

            print(site_visit_status_param,filter_param,len(leads_with_latest_site_visit))        
            
            return len(leads_with_latest_site_visit)

    @staticmethod 
    def generate_color(name):
        hash_object = hashlib.md5(name.encode())
        hex_dig = hash_object.hexdigest()
        color = f"{hex_dig[:6].upper()}"
        return color

    def get(self, request):
        try:
            query_param = request.query_params.get('module', None)
            date_range_param = request.GET.get('date_range', None)

            presales_stage = Stage.objects.filter(name='PreSales').first()
            sales_stage = Stage.objects.filter(name="Sales").first()

            presales_param = request.query_params.get('call_centre_executive_id',None)
            sourcing_id = request.query_params.get('sourcing_manager_id',None)
            closing_param = request.query_params.get('closing_manager_id',None)
            cp_param = request.query_params.get('channel_partner_id',None)
            cp_filtertype = request.query_params.get('channel_partner_filtertype',None)

        
            if query_param == 'PRESALES':
                presale_leads = Lead.objects.filter(workflow__current_stage=presales_stage.order)

                if presales_param is not None:
                    presale_leads = Lead.objects.filter(Q(workflow__current_stage=presales_stage.order) & (Q(workflow__stages__assigned_to_id=presales_param) | Q(creator_id=presales_param))).distinct()

                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    presale_leads = presale_leads.filter(created_on__gte=seven_days_ago)
                    print(presale_leads.count())
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    presale_leads = presale_leads.filter(created_on__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    presale_leads = presale_leads.filter(created_on__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    presale_leads = presale_leads.filter(created_on__gte=six_months_ago)

                #Sources info
                source_list = []
                all_source_ids = list(Source.objects.all().values_list("id", flat=True))
                for source_id in all_source_ids:
                    source_dict=dict()
                    lead_count = presale_leads.filter(source__id=source_id).count()
                    source_name = Source.objects.get(id=source_id).name
                    total_lead_count = presale_leads.filter(source__isnull=False).count()
                    lead_percentage = (lead_count/total_lead_count)*100 if total_lead_count > 0 else 0
                    lead_count = presale_leads.filter(source__id=source_id).count()
                    source_dict[f"{source_name}"] = {
                        "lead_count": lead_count,
                        "lead_percentage": lead_percentage,
                        "color": self.generate_color(source_name),
                        "total_count": presale_leads.count()
                    }
                    source_list.append(source_dict) 


                #Status Info 
                presale_leads_count = presale_leads.count()
                print('presale_lead_count',presale_leads_count)

                new_leads_count = presale_leads.filter(lead_status='New').count()
                hot_leads_count = presale_leads.filter(lead_status='Hot').count()
                cold_leads_count = presale_leads.filter(lead_status='Cold').count()
                warm_leads_count = presale_leads.filter(lead_status='Warm').count()
                lost_leads = presale_leads.filter(lead_status='Lost')
                lost_leads_count = lost_leads.count()

                total_leads_presales = Lead.objects.filter(creation_stage="PreSales")
                if presales_param:
                    total_leads_presales = Lead.objects.filter(Q(workflow__stages__assigned_to_id=presales_param) | Q(creator_id=presales_param)).filter(creation_stage="PreSales").distinct()
                
                site_visits = SiteVisit.objects.filter(lead__in=total_leads_presales)

                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    site_visits = site_visits.filter(created_at__gte=seven_days_ago)
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    site_visits = site_visits.filter(created_at__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    site_visits = site_visits.filter(created_at__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    site_visits = site_visits.filter(created_at__gte=six_months_ago)

                # sv_scheduled_count = SiteVisit.objects.filter(site_visit_status = "Scheduled" , lead__in=total_leads_presales).count()
               
                # sv_done_count = SiteVisit.objects.filter(site_visit_status = "Site Visit Done" , lead__in=total_leads_presales).count()

                sv_scheduled_count = SiteVisit.objects.filter(site_visit_status = "Scheduled").count()
               
                sv_done_count = SiteVisit.objects.filter(site_visit_status = "Site Visit Done").count()

                print("site visit scheduled :- ",sv_scheduled_count) 
                print("site visit done :- ", sv_done_count)
               
                sv_missed_count = self.site_visit_calculation(total_leads_presales,"Missed",None)
                print(sv_missed_count)


                total_reschedule_count = 0
                reschedule_counts = {}

                for lead in presale_leads:
                    site_visits = SiteVisit.history.filter(lead=lead).exclude(site_visit_status__in = ["Site Visit Done", "Missed"])
                    visit_count = 0
                    previous_visit_date = None
                    previous_timeslot = None

                    for visit in site_visits:
                        # Check if visit_date or timeslot has changed compared to the previous visit
                        if previous_visit_date is not None and (visit.visit_date != previous_visit_date or visit.timeslot != previous_timeslot):
                            visit_count += 1
                        
                        previous_visit_date = visit.visit_date
                        previous_timeslot = visit.timeslot

                    reschedule_counts[lead.id] = visit_count
                    total_reschedule_count += visit_count
                
                revisit_count = total_reschedule_count
                
                total_booking_count = ProjectInventory.objects.filter(status="Booked" , lead__isnull=False , lead__creation_stage = "PreSales")
                if presales_param:
                    total_booking_count = ProjectInventory.objects.filter(status="Booked",lead__isnull=False,lead__creator_id=presales_param , lead__creation_stage = "PreSales")

                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    total_booking_count = total_booking_count.filter(created_at__gte=seven_days_ago)
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    total_booking_count = total_booking_count.filter(created_at__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    total_booking_count = total_booking_count.filter(created_at__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    total_booking_count = total_booking_count.filter(created_at__gte=six_months_ago)  

                total_booking_count = total_booking_count.count()
                print(total_booking_count)
                booking_count = total_booking_count 

                total_sv_count =  sv_scheduled_count + sv_done_count  + revisit_count + booking_count
                total_status_info_count = total_sv_count + presale_leads_count
              
                # Follow ups
                # follow_ups = Task.objects.filter(name="Follow Up", stage__name=presales_stage.name).values('appointment_with').annotate(unique_follow_ups=Count('appointment_with')).count()
                # print('follow_ups:', follow_ups)

                # missed_follow_ups = Task.objects.filter(name="Follow Up", completed=False,stage__name=presales_stage.name).count()
                if date_range_param is None:
                    follow_ups = self.calculate_follow_ups_count(total_leads_presales, "Total")
                    missed_follow_ups = self.calculate_follow_ups_count(total_leads_presales,'Missed')
                elif date_range_param == 'last_7_days':
                    follow_ups = self.calculate_follow_ups_count(total_leads_presales,'Last_7_Days')
                    missed_follow_ups = self.calculate_follow_ups_count(total_leads_presales,'Missed_Last_7_Days')
                    
                elif date_range_param == 'last_2_weeks':
                    follow_ups = self.calculate_follow_ups_count(total_leads_presales,'Last_14_days')
                    missed_follow_ups = self.calculate_follow_ups_count(total_leads_presales,'Missed_Last_14_days')
                elif date_range_param == 'last_1_month':
                    follow_ups = self.calculate_follow_ups_count(total_leads_presales,'Last_Month')
                    missed_follow_ups = self.calculate_follow_ups_count(total_leads_presales,'Missed_Last_Month')
               
                #ringingleads data
                ringing_follow_ups = self.calculate_follow_ups_count(lost_leads, "Total")

                average_ringing_per_lead = round((ringing_follow_ups / total_leads_presales.count()),2) if total_leads_presales.count() > 0 else 0

                # Calls Info 
                call_center_executives = Users.objects.filter(groups__name='CALL_CENTER_EXECUTIVE')

                if presales_param:
                    # executive = Users.objects.get(id=cce_param, groups__name='CALL_CENTER_EXECUTIVE')
                    # call_center_executives = [executive]
                    if Users.objects.filter(id=presales_param, groups__name='CALL_CENTER_EXECUTIVE').count() > 0:
                        executive = Users.objects.get(id=presales_param, groups__name='CALL_CENTER_EXECUTIVE')
                        print("executive:", executive)
                        call_center_executives = [executive]
                    else:
                        print(f"No user with ID {presales_param} found in the CALL_CENTER_EXECUTIVE group.")
                        call_center_executives = []

                total_call = LeadCallsMcube.objects.filter(call_type="OUTGOING", executive__in=call_center_executives)

                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    total_call = total_call.filter(created_at__gte=seven_days_ago)
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    total_call = total_call.filter(created_at__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    total_call = total_call.filter(created_at__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    total_call = total_call.filter(created_at__gte=six_months_ago)

                total_call_count = total_call.count()
                connected_call_count = total_call.filter(call_status="ANSWER").count()
                not_connected_call_count = total_call_count - connected_call_count

                res = dict()
                res["source_info"] = source_list
                res["lead_info"] = {
                    "total_leads_presale" : presale_leads_count,
                    "new_leads_count": new_leads_count,
                    "hot_leads_count": hot_leads_count ,
                    "cold_leads_count": cold_leads_count,
                    "warm_leads_count":warm_leads_count ,
                    "lost_leads_count":lost_leads_count,
                    "new_leads_percentage": round(new_leads_count / presale_leads_count * 100, 2) if presale_leads_count > 0 else 0,
                    "hot_leads_percentage": round(hot_leads_count / presale_leads_count * 100, 2) if presale_leads_count > 0 else 0,
                    "cold_leads_percentage": round(cold_leads_count / presale_leads_count * 100, 2) if presale_leads_count > 0 else 0,
                    "warm_leads_percentage": round(warm_leads_count / presale_leads_count * 100, 2) if presale_leads_count > 0 else 0,
                    "lost_leads_percentage": round(lost_leads_count / presale_leads_count * 100, 2) if presale_leads_count > 0 else 0,
                    "ringing_leads_count": lost_leads_count,
                    "average_ringing_leads_count": average_ringing_per_lead,
                    "total_status_info_count":total_status_info_count
                }
                res["site_visit_info"] = {
                    "total_sv_info" : total_sv_count,
                    "reschedule_data" :  reschedule_counts,
                    "sv_scheduled_count": sv_scheduled_count,
                    "sv_scheduled_percentage" : round(sv_scheduled_count / total_sv_count * 100 , 2) if total_sv_count > 0 else 0,
                    "sv_missed_count" : sv_missed_count,
                    "sv_missed_percentage" : round(sv_missed_count / total_sv_count * 100 , 2) if total_sv_count > 0 else 0,
                    "sv_rescheduled_count": revisit_count,
                    "sv_rescheduled_percentage" : round(revisit_count / total_sv_count * 100 , 2) if total_sv_count > 0 else 0,
                    "sv_done_count": sv_done_count ,
                    "sv_done_percentage" : round(sv_done_count / total_sv_count * 100 , 2) if total_sv_count > 0 else 0,
                    "booking_done_count": booking_count,
                    "booking_done_percentage" : round(booking_count / total_sv_count * 100 , 2) if total_sv_count > 0 else 0,
                    "sv_scheduled_sv_done_ratio": f"{sv_scheduled_count}:{sv_done_count}"
                }
                res["calls_info"] = {
                    "total_call_count": total_call_count,
                    "connected_call_count": connected_call_count,
                    "connected_call_percentage" : round(connected_call_count/total_call_count * 100 ,2) if total_call_count > 0 else 0,
                    "not_connected_call_count": not_connected_call_count,
                    "not_connected_call_percentage" : round(not_connected_call_count/total_call_count * 100 ,2) if total_call_count > 0 else 0
                }
                res["follow_ups_info"] = {
                    "follow_ups": follow_ups,
                    "attended_follow_ups": follow_ups - missed_follow_ups, 
                    "missed_follow_ups": missed_follow_ups
                }

                return ResponseHandler(False, "PreSales MIS dashboard data retrieved successfully.", res, 200)

            if query_param == 'SOURCING':
                sourcing_queryset = ChannelPartner.objects.all()
                lead_queryset = Lead.objects.filter(channel_partner__isnull=False)

                if sourcing_id:
                    lead_queryset = lead_queryset.filter(channel_partner__creator__id=sourcing_id)
                    sourcing_queryset = sourcing_queryset.filter(creator__id=sourcing_id)

                total_cp_count = sourcing_queryset.exclude(Q(full_name__isnull=True)& Q(primary_email__isnull=True)& Q(address__isnull=True)& Q(pin_code__isnull=True)).count()     

                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    sourcing_queryset = sourcing_queryset.filter(created_on__gte=seven_days_ago)
                    lead_queryset = lead_queryset.filter(created_on__gte=seven_days_ago)
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    sourcing_queryset = sourcing_queryset.filter(created_on__gte=two_weeks_ago)
                    lead_queryset = lead_queryset.filter(created_on__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    sourcing_queryset = sourcing_queryset.filter(created_on__gte=one_month_ago)
                    lead_queryset = lead_queryset.filter(created_on__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    sourcing_queryset = sourcing_queryset.filter(created_on__gte=six_months_ago)
                    lead_queryset = lead_queryset.filter(created_on__gte=six_months_ago)

                icp = sourcing_queryset.filter(type_of_cp='ICP').count()
                rcp = sourcing_queryset.filter(type_of_cp='RETAIL').count()
                cp_positive = sourcing_queryset.filter(channel_partner_status='Interested').count()
                cp_neutral = sourcing_queryset.filter(channel_partner_status='Might be Interested').count()
                cp_negative = sourcing_queryset.filter(channel_partner_status='Not Interested').count()

                #Meeting info(Fresh and revisit)
                no_of_meetings = fresh_meetings = revisit_meetings = 0
                today_date = datetime.today()

                no_of_meetings = Meeting.objects.all().count()
                if sourcing_id:
                    no_of_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id).exclude(channel_partner__creator_id__isnull=True).count()
                
                print("meet",no_of_meetings)
                fresh_meetings = Meeting.objects.exclude(Q(channel_partner__meetings__date__lt=today_date)).count()
                if sourcing_id:
                    fresh_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id).exclude(
                            Q(channel_partner__meetings__date__lt=today_date)
                        ).count()

                print(fresh_meetings)    

                revisit_meetings = no_of_meetings - fresh_meetings
                print("revisit_meetings",revisit_meetings)

                #Average time for fresh meetings 
                fresh_meeting_durations = Meeting.objects.exclude(Q(channel_partner__meetings__date__lt=today_date)).aggregate(
                    avg_duration=Avg('duration')
                )
                if sourcing_id:
                    fresh_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id).exclude(
                            Q(channel_partner__meetings__date__lt=today_date)
                        ).aggregate(avg_duration=Avg('duration'))
                average_fresh_duration = fresh_meeting_durations['avg_duration']
                average_fresh_minutes = int(average_fresh_duration.total_seconds() // 60) if average_fresh_duration else 0
                print("Average time spent on fresh meetings (minutes):", average_fresh_minutes)
 
                # Average time for revisit meetings
                revisit_meeting_durations = Meeting.objects.filter(Q(channel_partner__meetings__date__lt=today_date)).aggregate(
                    avg_duration=Avg('duration')
                )
                if sourcing_id:
                    revisit_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id).filter(
                            Q(channel_partner__meetings__date__lt=today_date)
                        ).aggregate(avg_duration=Avg('duration'))
                average_revisit_duration = revisit_meeting_durations['avg_duration']
                average_revisit_minutes = int(average_revisit_duration.total_seconds() // 60) if average_revisit_duration else 0
                print("Average time spent on revisit meetings (minutes):", average_revisit_minutes)


                if date_range_param == 'last_7_days':

                    seven_days_ago = datetime.now() - timedelta(days=7)
                    end_date = datetime.today()
                    start_date = end_date - timedelta(days=6)

                    no_of_meetings = Meeting.objects.filter(date__gte=seven_days_ago).count()
                    if sourcing_id:
                        no_of_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id,date__gte=seven_days_ago).exclude(channel_partner__creator_id__isnull=True).count()

                    # fresh_meetings = Meeting.objects.filter(date__gte=seven_days_ago).annotate(
                    #     previous_meetings=Count('channel_partner__meeting', filter=Q(channel_partner__meeting__date__lt=start_date))
                    # ).filter(previous_meetings=0).count()

                    fresh_meetings = Meeting.objects.filter(
                        date__gte=seven_days_ago
                    ).exclude(
                        Q(channel_partner__meetings__date__lt=start_date)
                    ).count()
                    if sourcing_id:
                        fresh_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id, date__gte=seven_days_ago).exclude(
                            Q(channel_partner__meetings__date__lt=start_date)
                        ).count()

                    revisit_meetings = no_of_meetings - fresh_meetings

                    #Average time for fresh meetings 
                    fresh_meeting_durations = Meeting.objects.filter(
                        date__gte=seven_days_ago
                    ).exclude(Q(channel_partner__meetings__date__lt=start_date)).aggregate(
                        avg_duration=Avg('duration')
                    )
                    if sourcing_id:
                        fresh_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id , date__gte=seven_days_ago).exclude(
                                Q(channel_partner__meetings__date__lt=start_date)
                            ).aggregate(avg_duration=Avg('duration'))
                    average_fresh_duration = fresh_meeting_durations['avg_duration']
                    average_fresh_minutes = int(average_fresh_duration.total_seconds() // 60) if average_fresh_duration else 0
                    print("Average time spent on fresh meetings (minutes):", average_fresh_minutes)
    
                    # Average time for revisit meetings
                    revisit_meeting_durations = Meeting.objects.filter(Q(channel_partner__meetings__date__lt=start_date)).filter(
                        date__gte=seven_days_ago
                    ).aggregate(
                        avg_duration=Avg('duration')
                    )
                    if sourcing_id:
                        revisit_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id, date__gte=seven_days_ago).filter(
                                Q(channel_partner__meetings__date__lt=start_date)
                            ).aggregate(avg_duration=Avg('duration'))
                    average_revisit_duration = revisit_meeting_durations['avg_duration']
                    average_revisit_minutes = int(average_revisit_duration.total_seconds() // 60) if average_revisit_duration else 0
                    print("Average time spent on revisit meetings (minutes):", average_revisit_minutes)


                
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    end_date = datetime.today()
                    start_date = end_date - timedelta(days=13)

                    no_of_meetings = Meeting.objects.filter(date__gte=two_weeks_ago).count()
                    if sourcing_id:
                        no_of_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id,date__gte=two_weeks_ago).exclude(channel_partner__creator_id__isnull=True).count()

                    # fresh_meetings = Meeting.objects.filter(date__gte=two_weeks_ago).annotate(
                    #     previous_meetings=Count('channel_partner__meeting', filter=Q(channel_partner__meeting__date__lt=start_date))
                    # ).filter(previous_meetings=0).count()

                    fresh_meetings = Meeting.objects.filter(
                        date__gte=two_weeks_ago
                    ).exclude(
                        Q(channel_partner__meetings__date__lt=start_date)
                    ).count()

                    if sourcing_id:
                        fresh_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id, date__gte=two_weeks_ago).exclude(
                            Q(channel_partner__meetings__date__lt=start_date)
                        ).count()

                    revisit_meetings = no_of_meetings - fresh_meetings

                    #Average time for fresh meetings 
                    fresh_meeting_durations = Meeting.objects.filter(
                        date__gte=two_weeks_ago
                    ).exclude(Q(channel_partner__meetings__date__lt=start_date)).aggregate(
                        avg_duration=Avg('duration')
                    )
                    if sourcing_id:
                        fresh_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id , date__gte=two_weeks_ago).exclude(
                                Q(channel_partner__meetings__date__lt=start_date)
                            ).aggregate(avg_duration=Avg('duration'))
                    average_fresh_duration = fresh_meeting_durations['avg_duration']
                    average_fresh_minutes = int(average_fresh_duration.total_seconds() // 60) if average_fresh_duration else 0
                    print("Average time spent on fresh meetings (minutes):", average_fresh_minutes)
    
                    # Average time for revisit meetings
                    revisit_meeting_durations = Meeting.objects.filter(Q(channel_partner__meetings__date__lt=start_date)).filter(
                        date__gte=two_weeks_ago
                    ).aggregate(
                        avg_duration=Avg('duration')
                    )
                    if sourcing_id:
                        revisit_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id, date__gte=two_weeks_ago).filter(
                                Q(channel_partner__meetings__date__lt=start_date)
                            ).aggregate(avg_duration=Avg('duration'))
                    average_revisit_duration = revisit_meeting_durations['avg_duration']
                    average_revisit_minutes = int(average_revisit_duration.total_seconds() // 60) if average_revisit_duration else 0
                    print("Average time spent on revisit meetings (minutes):", average_revisit_minutes)
                
                elif date_range_param == 'last_1_month':

                    one_month_ago = datetime.now() - timedelta(days=30)
                    end_date = datetime.today() - timedelta(days=30)
                    start_date = end_date - timedelta(days=29)  

                    no_of_meetings = Meeting.objects.filter(date__gte=one_month_ago).count()
                    if sourcing_id:
                        no_of_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id,date__gte=one_month_ago).exclude(channel_partner__creator_id__isnull=True).count()

                    # fresh_meetings = Meeting.objects.filter(date__gte=one_month_ago).annotate(
                    #     previous_meetings=Count('channel_partner__meeting', filter=Q(channel_partner__meeting__date__lt=start_date))
                    # ).filter(previous_meetings=0).count()
                    
                    fresh_meetings = Meeting.objects.filter(
                        date__gte=one_month_ago
                    ).exclude(
                        Q(channel_partner__meetings__date__lt=start_date)
                    ).count()

                    if sourcing_id:
                        fresh_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id, date__gte=one_month_ago).exclude(
                            Q(channel_partner__meetings__date__lt=start_date)
                        ).count()

                    revisit_meetings = no_of_meetings - fresh_meetings

                      #Average time for fresh meetings 
                    fresh_meeting_durations = Meeting.objects.filter(
                        date__gte=one_month_ago
                    ).exclude(Q(channel_partner__meetings__date__lt=start_date)).aggregate(
                        avg_duration=Avg('duration')
                    )
                    if sourcing_id:
                        fresh_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id , date__gte=one_month_ago).exclude(
                                Q(channel_partner__meetings__date__lt=start_date)
                            ).aggregate(avg_duration=Avg('duration'))
                    average_fresh_duration = fresh_meeting_durations['avg_duration']
                    average_fresh_minutes = int(average_fresh_duration.total_seconds() // 60) if average_fresh_duration else 0
                    print("Average time spent on fresh meetings (minutes):", average_fresh_minutes)
    
                    # Average time for revisit meetings
                    revisit_meeting_durations = Meeting.objects.filter(Q(channel_partner__meetings__date__lt=start_date)).filter(
                        date__gte=one_month_ago
                    ).aggregate(
                        avg_duration=Avg('duration')
                    )
                    if sourcing_id:
                        revisit_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id, date__gte=one_month_ago).filter(
                                Q(channel_partner__meetings__date__lt=start_date)
                            ).aggregate(avg_duration=Avg('duration'))
                    average_revisit_duration = revisit_meeting_durations['avg_duration']
                    average_revisit_minutes = int(average_revisit_duration.total_seconds() // 60) if average_revisit_duration else 0
                    print("Average time spent on revisit meetings (minutes):", average_revisit_minutes)
                
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)

                    end_date = datetime.today() - timedelta(days=30) 
                    start_date = end_date - timedelta(days=30*6 - 1)  

                    no_of_meetings = Meeting.objects.filter(date__gte=six_months_ago).count()
                    if sourcing_id:
                        no_of_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id,date__gte=six_months_ago).exclude(channel_partner__creator_id__isnull=True).count()

                    # fresh_meetings = Meeting.objects.filter(date__gte=six_months_ago).annotate(
                    #     previous_meetings=Count('channel_partner__meeting', filter=Q(channel_partner__meeting__date__lt=start_date))
                    # ).filter(previous_meetings=0).count()
                    fresh_meetings = Meeting.objects.filter(
                        date__gte=six_months_ago
                    ).exclude(
                        Q(channel_partner__meetings__date__lt=start_date)
                    ).count()

                    if sourcing_id:
                        fresh_meetings = Meeting.objects.filter(channel_partner__creator_id=sourcing_id, date__gte=six_months_ago).exclude(
                            Q(channel_partner__meetings__date__lt=start_date)
                        ).count()

                    revisit_meetings = no_of_meetings - fresh_meetings

                    #Average time for fresh meetings 
                    fresh_meeting_durations = Meeting.objects.filter(
                        date__gte=six_months_ago
                    ).exclude(Q(channel_partner__meetings__date__lt=start_date)).aggregate(
                        avg_duration=Avg('duration')
                    )
                    if sourcing_id:
                        fresh_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id , date__gte=six_months_ago).exclude(
                                Q(channel_partner__meetings__date__lt=start_date)
                            ).aggregate(avg_duration=Avg('duration'))
                    average_fresh_duration = fresh_meeting_durations['avg_duration']
                    average_fresh_minutes = int(average_fresh_duration.total_seconds() // 60) if average_fresh_duration else 0
                    print("Average time spent on fresh meetings (minutes):", average_fresh_minutes)
    
                    # Average time for revisit meetings
                    revisit_meeting_durations = Meeting.objects.filter(Q(channel_partner__meetings__date__lt=start_date)).filter(
                        date__gte=six_months_ago
                    ).aggregate(
                        avg_duration=Avg('duration')
                    )
                    if sourcing_id:
                        revisit_meeting_durations = Meeting.objects.filter(sourcing_manager__id=sourcing_id, date__gte=six_months_ago).filter(
                                Q(channel_partner__meetings__date__lt=start_date)
                            ).aggregate(avg_duration=Avg('duration'))
                    average_revisit_duration = revisit_meeting_durations['avg_duration']
                    average_revisit_minutes = int(average_revisit_duration.total_seconds() // 60) if average_revisit_duration else 0
                    print("Average time spent on revisit meetings (minutes):", average_revisit_minutes)
                

                today_date = datetime.today().date()
    
                # Get the date range
                date_range = Meeting.objects.aggregate(
                    earliest_date=Min('date'),
                    latest_date=Max('date')
                )
                
                earliest_date = date_range['earliest_date']
                latest_date = date_range['latest_date'] if date_range['latest_date'] else today_date

                if not earliest_date:
                    return {"average_meetings_per_day": 0, "average_fresh_per_day": 0, "average_revisit_per_day": 0}

                total_days = (latest_date - earliest_date).days + 1  
                
                avg_meetings_per_day = round((no_of_meetings / total_days) ,2) if total_days > 0 else 0
                avg_fresh_per_day = round((fresh_meetings / total_days),2) if total_days > 0 else 0
                avg_revisit_per_day = round((revisit_meetings / total_days),2) if total_days > 0 else 0


                total_meetings_count = no_of_meetings

                # total_cp_count = sourcing_queryset.exclude(Q(full_name__isnull=True)& Q(primary_email__isnull=True)& Q(address__isnull=True)& Q(pin_code__isnull=True)).count()            
               

                three_months_ago = timezone.now() - timedelta(days=90)
                last_3_days = datetime.now() - timedelta(days=3)

                # Queryset for active CPs within the last 5 minutes
                active_cps = ChannelPartner.objects.filter(
                    Q(created_on__gte=three_months_ago) |  # Created within the last 90 days
                    Q(lead__projectinventory__status="Booked", lead__projectinventory__booked_on__gte=three_months_ago)  # At least one booking in the last 3 months
                ).exclude(
                    Q(full_name__isnull=True) & 
                    Q(primary_email__isnull=True) & 
                    Q(address__isnull=True) & 
                    Q(pin_code__isnull=True)
                )
                
                newly_active_cps =  active_cps = ChannelPartner.objects.filter(
                    Q(created_on__gte=last_3_days) |  # Created within the last 3 days
                    Q(lead__projectinventory__status="Booked", lead__projectinventory__booked_on__gte=last_3_days) 
                ).exclude(
                    Q(full_name__isnull=True) & 
                    Q(primary_email__isnull=True) & 
                    Q(address__isnull=True) & 
                    Q(pin_code__isnull=True)
                )

                if sourcing_id:
                    active_cps = active_cps.filter(
                        creator_id=sourcing_id 
                    )
                    newly_active_cps = newly_active_cps.filter(creator_id=sourcing_id)
                active_cps = active_cps.distinct()
                newly_active_cps = newly_active_cps.distinct()

                active_channel_partners = active_cps.count()
                newly_active_channel_partners = newly_active_cps.count() 

                print("active cp count",active_channel_partners)

                # Find all Channel Partners without bookings in the last three months
                inactive_channel_partners = total_cp_count - active_channel_partners 

                # Lead info
                new_leads_count = lead_queryset.filter(lead_status='New').count()
                hot_leads_count = lead_queryset.filter(lead_status='Hot').count()
                cold_leads_count = lead_queryset.filter(lead_status='Cold').count()
                warm_leads_count = lead_queryset.filter(lead_status='Warm').count()
                lost_leads_count = lead_queryset.filter(lead_status='Lost').count()
                total_cm_leads = lead_queryset.filter(sitevisit__sourcing_manager__isnull=False).distinct()

                # Count bookings where projectinventory status is "Booked"
                booking_count = total_cm_leads.filter(projectinventory__status="Booked").count()
                print("Booking count:", booking_count)

                total_queryset_count = lead_queryset.count() + booking_count

                interval = 2
                max_value1 = max(active_channel_partners, inactive_channel_partners, newly_active_channel_partners)
                max_value2 = max(cp_positive, cp_negative, cp_neutral)
                res = dict()
                res["outreach_meetings_info"] = {
                    "fresh_meetings_count": fresh_meetings,
                    "fresh_meetings_percentage": round((fresh_meetings/total_meetings_count)*100,2) if total_meetings_count > 0 else 0,
                    "revisit_meetings_count": revisit_meetings,
                    "revisit_meetings_percentage": round((revisit_meetings/total_meetings_count)*100,2) if total_meetings_count > 0 else 0,
                    "total_count": fresh_meetings + revisit_meetings
                }
                res["channel_partners_type_info"] = {
                    "rcp_count": rcp,
                    "rcp_percentage": round(rcp/(rcp+icp),2)*100 if (rcp+icp) > 0 else 0,
                    "icp_count": icp,
                    "icp_percentage": round(icp/(rcp+icp),2)*100 if (rcp+icp) > 0 else 0,
                    "total_count": rcp + icp,
                }
                res["active_vs_inactive_channel_partners_info"] = {
                    "active_channel_partners_count": active_channel_partners,
                    "active_channel_partners_percentage": round(active_channel_partners/(active_channel_partners+inactive_channel_partners),2)*100 if (active_channel_partners+inactive_channel_partners) > 0 else 0,
                    "newly_active_channel_partners_count": newly_active_channel_partners,
                    "inactive_channel_partners_count": inactive_channel_partners,
                    "inactive_channel_partners_percentage": round(inactive_channel_partners/(active_channel_partners+inactive_channel_partners),2)*100 if (active_channel_partners+inactive_channel_partners) > 0 else 0,
                    "interval": interval,
                    "rounded_max_value": math.ceil(max_value1 / interval) * interval,
                    "total_count": active_channel_partners + inactive_channel_partners, 
                }
                res["status_visited_clients_info"] = {
                    "new_count": new_leads_count,
                    "new_count_percentage": round((new_leads_count/total_queryset_count)*100, 2) if total_queryset_count > 0 else 0,
                    "hot_count": hot_leads_count,
                    "hot_count_percentage": round((hot_leads_count/total_queryset_count)*100, 2) if total_queryset_count > 0 else 0,
                    "cold_count": cold_leads_count,
                    "cold_count_percentage": round((cold_leads_count/total_queryset_count)*100, 2) if total_queryset_count > 0 else 0,
                    "warm_count": warm_leads_count,
                    "warm_count_percentage": round((warm_leads_count/total_queryset_count)*100, 2) if total_queryset_count > 0 else 0,
                    "lost_count": lost_leads_count,
                    "lost_count_percentage": round((lost_leads_count/total_queryset_count)*100 , 2) if total_queryset_count > 0 else 0,
                    "total_count": new_leads_count + hot_leads_count + cold_leads_count + warm_leads_count + lost_leads_count
                }
                res["unique_positive_vs_negative_channel_partners"] = {
                    "positive_channel_partners": cp_positive,
                    "maybe_positive_channel_partners": cp_neutral,
                    "negative_channel_partners": cp_negative,
                    "total": cp_positive + cp_negative + cp_neutral,
                    "interval": interval,
                    "rounded_max_value": math.ceil(max_value2 / interval) * interval
                }
                res["avg_time_spend"] = {
                    "fresh": average_fresh_minutes,
                    "revisit": average_revisit_minutes
                }
                res["avg_meetings_per_day"] = { 
                    "fresh": avg_fresh_per_day,
                    "revisit": avg_revisit_per_day,
                    "total_days" : total_days
                }
                return ResponseHandler(False, "Sourcing MIS dashboard data retrieved successfully.", res, 200)
            if query_param == 'CLOSING':
                stage = Stage.objects.filter(name='Sales').first()
                sales_queryset = Lead.objects.filter(workflow__current_stage=stage.order)

                if closing_param is not None:
                    lead_ids = list(sales_queryset.values_list("id", flat=True))
                    site_visits = SiteVisit.objects.filter(lead__in=lead_ids, closing_manager__in=list(closing_param))
                    site_visit_lead_ids = list(site_visits.values_list("lead", flat=True))
                    sales_queryset = sales_queryset.filter(id__in=site_visit_lead_ids)

                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    sales_queryset = sales_queryset.filter(created_on__gte=seven_days_ago)
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    sales_queryset = sales_queryset.filter(created_on__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    sales_queryset = sales_queryset.filter(created_on__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    sales_queryset = sales_queryset.filter(created_on__gte=six_months_ago)
                 
                #Status Info 
                booked_queryset = sales_queryset.filter(projectinventory__status="Booked").order_by('-id')

                booking_count = booked_queryset.count()

                hot_leads = sales_queryset.filter(lead_status='Hot')
                warm_leads = sales_queryset.filter(lead_status='Warm')
                cold_leads = sales_queryset.filter(lead_status='Cold')
                lost_leads = sales_queryset.filter(lead_status='Lost')
                new_leads = sales_queryset.filter(lead_status = "New")
                total_leads_data = hot_leads.count() + warm_leads.count() + cold_leads.count() + lost_leads.count() + new_leads.count() + booking_count

                #Visit Info 
                num_leads_with_revisits = 0
                num_fresh_leads = 0

                for lead in sales_queryset:

                    site_visits = lead.sitevisit_set.filter(site_visit_status='Site Visit Done')

                    if not site_visits.exists():
                        continue

                    min_visit_date = site_visits.aggregate(min_visit_date=Min('visit_date'))['min_visit_date']

                    if site_visits.filter(visit_date__gt=min_visit_date).exists():
                        num_leads_with_revisits += 1
                    else:
                        num_fresh_leads += 1


                total_leads = Lead.objects.filter(creation_stage = "Sales")
                if closing_param:
                    # total_leads = Lead.objects.filter(Q(creation_stage="Sales") & (Q(workflow__stages__assigned_to_id=closing_id) | Q(creator_id=closing_id))).distinct()
                    lead_ids = list(total_leads.values_list("id", flat=True))
                    site_visits = SiteVisit.objects.filter(lead__in=lead_ids, closing_manager__in=list(closing_param))
                    site_visit_lead_ids = list(site_visits.values_list("lead", flat=True))
                    total_leads = total_leads.filter(id__in=site_visit_lead_ids)

                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    total_leads = total_leads.filter(created_on__gte=seven_days_ago)
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    total_leads = total_leads.filter(created_on__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    total_leads = total_leads.filter(created_on__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    total_leads = total_leads.filter(created_on__gte=six_months_ago) 

                sales_queryset = total_leads.annotate(sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done")))
                print(sales_queryset.count())
                sv_data = sales_queryset.filter(sv_done__gt=1)
                revisit_count = 0
                for lead in sv_data:
                    revisit_count += (lead.sv_done -1)      
               

                # Follow ups
                follow_ups = Task.objects.filter(name="Follow Up", stage__name=sales_stage.name).values('appointment_with').annotate(unique_follow_ups=Count('appointment_with')).count()
                print('follow_ups:', follow_ups)

                missed_follow_ups = Task.objects.filter(name="Follow Up", completed=False,stage__name=sales_stage.name).count()
                attended_follow_ups = follow_ups - missed_follow_ups

                res = dict()

                res["visited_clients_info"] = {
                    "fresh": num_fresh_leads,
                    "fresh_percentage": (num_fresh_leads/(num_fresh_leads + num_leads_with_revisits))*100 if (num_fresh_leads + num_leads_with_revisits) > 0 else 0,
                    "revisit": num_leads_with_revisits,
                    "revisit_percentage": (num_leads_with_revisits/(num_fresh_leads + num_leads_with_revisits))*100 if (num_fresh_leads + num_leads_with_revisits) > 0 else 0,
                    "revisit_scheduled": revisit_count,
                    "total_count": num_fresh_leads + num_leads_with_revisits
                }
                res["status_info"] = {
                    "hot_leads_count": hot_leads.count(),
                    "hot_leads_percentage": (hot_leads.count()/total_leads_data)*100 if total_leads_data > 0 else 0,
                    "warm_leads_count": warm_leads.count(),
                    "warm_leads_percentage": (warm_leads.count()/total_leads_data)*100 if total_leads_data > 0 else 0,
                    "cold_leads_count": cold_leads.count(),
                    "cold_leads_percentage": (cold_leads.count()/total_leads_data)*100 if total_leads_data > 0 else 0,
                    "new_leads_count": new_leads.count(),
                    "new_leads_percentage": (new_leads.count()/total_leads_data)*100 if total_leads_data > 0 else 0,
                    "lost_leads_count": lost_leads.count(),
                    "lost_leads_percentage": (lost_leads.count()/total_leads_data)*100 if total_leads_data > 0 else 0,
                    "booking_count" : booking_count,
                    "booking_percentage" : (booking_count/total_leads_data)*100 if total_leads_data > 0 else 0,
                    "total_count": total_leads_data
                }
                res["follow_ups_info"] = {
                    "attended_follow_ups_count": 0,
                    "attended_follow_ups_percentage":  0,
                    "missed_follow_ups_count": 0,
                    "missed_follow_ups_percentage":  0,
                    "total_count": 0
                }
                res["time_spent_info"] = {
                    "average_time_spent_fresh": 30,
                    "average_time_spent_revisit": 20,
                }
                return ResponseHandler(False, "Closing MIS dashboard data retrieved successfully.", res, 200)

            if query_param == 'CHANNEL_PARTNER':
                payment_queryset = Payment.objects.all()
                lead_queryset = Lead.objects.filter(creator__groups__name__in=["INQUIRY_FORM"]) 
                if cp_param :
                    payment_queryset = payment_queryset.filter(channel_partner__id=cp_param)
                    lead_queryset = lead_queryset.filter(channel_partner__id = cp_param)
                if cp_filtertype == 'All':
                    if date_range_param == 'last_7_days':
                        seven_days_ago = datetime.now() - timedelta(days=7)
                        payment_queryset = Payment.objects.filter(created_on__gte=seven_days_ago)
                        lead_queryset = lead_queryset.filter(created_on__gte=seven_days_ago)
                    elif date_range_param == 'last_2_weeks':
                        two_weeks_ago = datetime.now() - timedelta(weeks=2)
                        payment_queryset = Payment.objects.filter(created_on__gte=two_weeks_ago)
                        lead_queryset = lead_queryset.filter(created_on__gte=two_weeks_ago)
                    elif date_range_param == 'last_1_month':
                        one_month_ago = datetime.now() - timedelta(days=30)
                        payment_queryset = Payment.objects.filter(created_on__gte=one_month_ago)
                        lead_queryset = lead_queryset.filter(created_on__gte=one_month_ago)
                    elif date_range_param == 'last_6_months':
                        six_months_ago = datetime.now() - timedelta(days=180)
                        payment_queryset = Payment.objects.filter(created_on__gte=six_months_ago)
                        lead_queryset = lead_queryset.filter(created_on__gte=six_months_ago)

                if cp_filtertype == 'Brokerage_forecast':
                    if date_range_param == 'last_7_days':
                        seven_days_ago = datetime.now() - timedelta(days=7)
                        payment_queryset = Payment.objects.filter(created_on__gte=seven_days_ago)
                        #lead_queryset = lead_queryset.filter(created_on__gte=seven_days_ago)
                    elif date_range_param == 'last_2_weeks':
                        two_weeks_ago = datetime.now() - timedelta(weeks=2)
                        payment_queryset = Payment.objects.filter(created_on__gte=two_weeks_ago)
                        #lead_queryset = lead_queryset.filter(created_on__gte=two_weeks_ago)
                    elif date_range_param == 'last_1_month':
                        one_month_ago = datetime.now() - timedelta(days=30)
                        payment_queryset = Payment.objects.filter(created_on__gte=one_month_ago)
                        #lead_queryset = lead_queryset.filter(created_on__gte=one_month_ago)
                    elif date_range_param == 'last_6_months':
                        six_months_ago = datetime.now() - timedelta(days=180)
                        payment_queryset = Payment.objects.filter(created_on__gte=six_months_ago)
                        #lead_queryset = lead_queryset.filter(created_on__gte=six_months_ago)

                payment_done = payment_queryset.filter(payment_to='Sales', status='Payment Done')
                payment_done_amount = payment_done.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
                approval_pending = payment_queryset.filter(payment_to='Sales', status='Approval Pending')
                approval_pending_amount = approval_pending.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
                bill_submitted = payment_queryset.filter(payment_to='Sales')
                bill_submitted_amount = bill_submitted.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
                bill_overdue = payment_queryset.exclude(status='Payment Done').filter(due_date__lt=timezone.now())
                bill_overdue_amount = bill_overdue.aggregate(total_amount=Sum('amount'))['total_amount'] or 0
                interval = 10000
                max_value = max(payment_done_amount, approval_pending_amount, bill_submitted_amount)
                rounded_max_value = math.ceil(max_value / interval) * interval

                brokerage_forecast_info = {
                    "paid_amount": payment_done_amount,
                    "paid_count": payment_done.count(),
                    "pending_amount": approval_pending_amount,
                    "pending_count": approval_pending.count(),
                    "bill_submitted_amount": bill_submitted_amount,
                    "bill_submitted_count": bill_submitted.count(),
                    "bill_overdue_amount": bill_overdue_amount,
                    "bill_overdue_count" : bill_overdue.count(),
                    "interval" : interval,
                    "max_amount": rounded_max_value
                }
                print(brokerage_forecast_info)
                #CP walkins vs bookings
                if cp_filtertype == 'Walkin_vs_Bookings':
                    if date_range_param == 'last_7_days':
                        seven_days_ago = datetime.now() - timedelta(days=7)
                        #payment_queryset = Payment.objects.filter(created_on__gte=seven_days_ago)
                        lead_queryset = lead_queryset.filter(created_on__gte=seven_days_ago)
                    elif date_range_param == 'last_2_weeks':
                        two_weeks_ago = datetime.now() - timedelta(weeks=2)
                        #payment_queryset = Payment.objects.filter(created_on__gte=two_weeks_ago)
                        lead_queryset = lead_queryset.filter(created_on__gte=two_weeks_ago)
                    elif date_range_param == 'last_1_month':
                        one_month_ago = datetime.now() - timedelta(days=30)
                        #payment_queryset = Payment.objects.filter(created_on__gte=one_month_ago)
                        lead_queryset = lead_queryset.filter(created_on__gte=one_month_ago)
                    elif date_range_param == 'last_6_months':
                        six_months_ago = datetime.now() - timedelta(days=180)
                        #payment_queryset = Payment.objects.filter(created_on__gte=six_months_ago)
                        lead_queryset = lead_queryset.filter(created_on__gte=six_months_ago)

                walkin_vs_booking_dict = []
                all_cp_ids = list(ChannelPartner.objects.all().values_list("id", flat=True))
                if cp_param is not None:
                    all_cp_ids = [cp_param]
                print("all_cps_ids",all_cp_ids)
                for cp_id in all_cp_ids:
                    dict_data = {}
                    channel_partner_details = ChannelPartner.objects.get(id=cp_id)
                    channel_partner_name = channel_partner_details.full_name
                    walkin_leads = lead_queryset.filter(channel_partner__id=cp_id)
                    # site_visits = SiteVisit.objects.filter(lead__in=leads)
                    # site_visits_done_count = site_visits.filter(site_visit_status="Site Visit Done").count()
                    bookings_count = ProjectInventory.objects.filter(lead__in=walkin_leads , status = "Booked" ).count()
                    dict_data[f"{channel_partner_name}"] = {
                        "walkin_count": walkin_leads.count(),
                        "bookings_count": bookings_count
                    }
                    walkin_vs_booking_dict.append(dict_data)
                res = dict()
                res["brokerage_forecast_info"] = brokerage_forecast_info
                res["walkin_vs_booking_info"] = walkin_vs_booking_dict

                return ResponseHandler(False, "Channel Partner MIS dashboard data retrieved successfully.", res, 200)

        except Exception as e:
            return ResponseHandler(True, str(e),None, status.HTTP_500_INTERNAL_SERVER_ERROR)  


class CancelReasonCreateView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = CancelReasonSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False,"Cancel Reason saved successfully",serializer.data, status.HTTP_201_CREATED)
        return ResponseHandler(True, "Bad Request",serializer.errors,status.HTTP_400_BAD_REQUEST)

