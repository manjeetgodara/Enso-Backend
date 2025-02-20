import hashlib
import math
from django.shortcuts import render
# Create your views here.
from rest_framework import generics, mixins,status,serializers
from comms.utils import send_push_notification
from .models import Lead,LeadRequirements,ChannelPartner,Source, Updates
from django.http import Http404, JsonResponse
from .serializers import *
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.decorators import permission_required
from rest_framework.response import Response
from auth.utils import ResponseHandler
from rest_framework.permissions import IsAuthenticated
from workflow.models import WorkflowDefinition
from workflow.serializers import *
from workflow.tasks import process_workflow
from drf_yasg.utils import swagger_auto_schema
from .pagination import CustomLimitOffsetPagination
from activity.models import *
from django.db.models import Q
from datetime import datetime, timedelta
from rest_framework.parsers import MultiPartParser, FormParser
from auth.models import Users
import pandas as pd
from collections import defaultdict
import os
from pathlib import Path
from auth.decorator import role_check
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from .decorator import restrict_access,group_access,bulk_group_access, check_group_access, check_access
from reportlab.lib import colors
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from .serializers import LeadBulkuploadSerializer
from django.db.models import Count, F, ExpressionWrapper, CharField, DecimalField, Value
from django.db.models.functions import Concat, Coalesce, Cast
from django.db.models import Max, OuterRef, Subquery, F, Value
from tempfile import NamedTemporaryFile
from auth.serializers import *
from rest_framework.views import APIView
#from core.models import Inventory
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import Group
from .models import *
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from workflow.models import *
from workflow.tasks import process_task
from django.utils import timezone
from time import time
from django.shortcuts import get_object_or_404
from river.models import State
from django.db.models import Max
from django.utils import timezone
from workflow.models import Task
from rest_framework import filters
from workflow.serializers import TaskSerializer
from datetime import date, timedelta
from activity.serializers import  SiteVisitSerializer
from inventory.models import *
from rest_framework.exceptions import NotFound
from inventory.serializers import *
from django.core.files import File
from django.conf import settings
from .models import ExportFile
from django.core.files import File
import boto3
from django.utils.timezone import make_aware
import calendar
from mcube.models import * 
from mcube.serializers import *
from accounts.models import Payment
from django.db.models import Sum,  Count, F, Min, Q
# from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum

class LeadCreateAPIView(mixins.ListModelMixin,mixins.CreateModelMixin,generics.GenericAPIView):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = CustomLimitOffsetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['first_name', 'last_name','primary_phone_no', 'creator__name', 'id', 'source__source_id'] 
    #ordering =['-created_on']     

    def get_queryset(self):
        sort_order_param = self.request.GET.get('sort_order', None)
        sort_field_param = self.request.GET.get('sort_field', None)
        if sort_field_param and sort_field_param == 'created_on':
            order_by_param = '-created_on' if sort_order_param == 'desc' else 'created_on'
            queryset = Lead.objects.all().order_by(order_by_param)    
        else:
            queryset = Lead.objects.all().order_by('-created_on')

        
        module_param = self.request.GET.get('module', None)

        if module_param == "PRESALES":

            user = self.request.user
            # queryset = [lead for lead in queryset if lead.current_stage() and lead.current_stage() == 'PreSales']
            stage = Stage.objects.filter(name='PreSales').first()
            queryset = queryset.filter(workflow__current_stage=stage.order)

            if user.groups.filter(name__in=["ADMIN","SITE_HEAD","PROMOTER","VICE_PRESIDENT"]).exists():
                print('here')
                return queryset

            if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                queryset = queryset.filter(followers__contains=[user.id])
            else:
                # If none of the conditions match, return an empty queryset
                queryset = Lead.objects.none()

            return queryset
        
        elif module_param == "SALES":

            #queryset = Lead.objects.filter(sitevisit__site_visit_status="Scheduled")
            # queryset = Lead.objects.filter(
            #     Q(sitevisit__site_visit_status="Scheduled") |
            #     Q(Q(sitevisit__site_visit_status="Occurred"))
            # ).distinct()
            # print(queryset)
            # queryset = [lead for lead in queryset if lead.current_stage() and lead.current_stage() == 'Sales']
            closure_param =  bool(self.request.GET.get('closure',None))
            if closure_param:
                stage = Stage.objects.filter(name='PostSales').first()
                queryset = queryset.filter(workflow__current_stage=stage.order)

                user = self.request.user
                #stage = Stage.objects.filter(name='PostSales').first()
                #queryset = queryset.filter(workflow__current_stage=stage.order)
                if user.groups.filter(name__in=["ADMIN", "RECEPTIONIST", "SITE_HEAD","PROMOTER","VICE_PRESIDENT"]).exists():# SITEHEAD
                    return queryset
                elif user.groups.filter(name__in=["CLOSING_MANAGER","SOURCING_MANAGER"]).exists():
                    # print("Sales: ")
                    # queryset = queryset.filter(bookingform__sales_manager_name=user)
                    # print("Sales queryset: ",queryset)
                    queryset.filter(followers__contains=[user.id])
                else:
                    queryset = Lead.objects.none()
                return queryset
            else:
                stage = Stage.objects.filter(name='Sales').first()
                queryset = queryset.filter(workflow__current_stage=stage.order)

                    #sitevisit__isnull=False
                user = self.request.user

                if user.groups.filter(name__in=["ADMIN","PROMOTER","VICE_PRESIDENT"]).exists():
                    # print("It works")
                    queryset = queryset.filter(sitevisit__isnull=False).distinct()
                    return queryset
                elif user.groups.filter(name__in=["RECEPTIONIST","SITE_HEAD"]).exists():
                    presales_stage = Stage.objects.filter(name='PreSales').first()
                    presales_queryset = Lead.objects.filter(workflow__current_stage=presales_stage.order)

                    # # Filter out Sales stage leads for Receptionists
                    # if user.groups.filter(name="RECEPTIONIST").exists():
                    #     queryset = queryset.exclude(workflow__current_stage=stage.order) 

                    queryset = queryset | presales_queryset
                    if user.groups.filter(name="RECEPTIONIST").exists():
                        # Filter leads where the creator belongs to the "INQUIRY_FORM" group
                        queryset = queryset.filter(creator__groups__name="INQUIRY_FORM")
                    # queryset = queryset.filter(sitevisit__isnull=False).distinct()
                    queryset = queryset.filter(Q(sitevisit__site_visit_status="Scheduled") | Q(sitevisit__site_visit_status="Site Visit Done")).distinct()
                    queryset = queryset.annotate(num_site_visits=Count('sitevisit', distinct=True)).filter(num_site_visits__gt=0)

                    return queryset
                
                elif user.groups.filter(name__in=["CLOSING_MANAGER","SOURCING_MANAGER"]).exists():
                    postsales_stage = Stage.objects.filter(name='PostSales').first()
                   # queryset = Lead.objects.filter(sitevisit__closing_manager=user).exclude(workflow__current_stage=postsales_stage.order).order_by('-created_on')
                    closing_manager_queryset = Lead.objects.filter(sitevisit__closing_manager=user)

                    # Create a queryset for Sourcing Manager
                    sourcing_manager_queryset = Lead.objects.filter(sitevisit__sourcing_manager=user)

                    # Combine both querysets and exclude leads in the PostSales stage
                    queryset = (closing_manager_queryset | sourcing_manager_queryset).exclude(workflow__current_stage=postsales_stage.order).order_by('-created_on')
                    print("queryset----",queryset)
                else:
                    # If none of the conditions match, return an empty queryset
                    queryset = Lead.objects.none()

                return queryset

        elif module_param == "POSTSALES":

            # queryset = [lead for lead in queryset if lead.current_stage() and lead.current_stage() == 'PostSales']
            stage = Stage.objects.filter(name='PostSales').first()
            queryset = queryset.filter(workflow__current_stage=stage.order)

            user = self.request.user

            if user.groups.filter(name__in=["ADMIN", "CRM_HEAD","PROMOTER","VICE_PRESIDENT","ACCOUNTS_HEAD","ACCOUNTS_EXECUTIVE"]).exists():
                return queryset

            if user.groups.filter(name="CRM_EXECUTIVE").exists():
                queryset = queryset.filter(followers__contains=[user.id])
            else:
                # If none of the conditions match, return an empty queryset
                queryset = Lead.objects.none()

            return queryset 

    def filter_leads(self,queryset, query_params):
        status_param = query_params.get('lead_status')
        if status_param is not None:
            status_param = status_param.split(',')
            queryset = queryset.filter(lead_status__in=status_param)

        purpose_param = query_params.get('purpose', None)
        if purpose_param is not None:
            queryset = queryset.filter(lead_requirement__purpose=purpose_param)

        configuration_param = query_params.get('configuration', None)
        if configuration_param is not None:
            queryset = queryset.filter(lead_requirement__configuration=configuration_param)

        funding_param = query_params.get('funding', None)
        if funding_param is not None:
            queryset = queryset.filter(lead_requirement__funding=funding_param)

        budget_min_param = query_params.get('budget_min', None)
        if budget_min_param is not None:
            queryset = queryset.filter(lead_requirement__budget_min__lte=budget_min_param)

        budget_max_param = query_params.get('budget_max', None)
        if budget_max_param is not None:
            queryset = queryset.filter(lead_requirement__budget_max__gte=budget_max_param)

        date_range_param = query_params.get('date_range', None)
        start_date_param = query_params.get('start_date', None)
        end_date_param = query_params.get('end_date', None)

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
        elif date_range_param == 'custom_range' and start_date_param and end_date_param:
            start_date = datetime.strptime(start_date_param, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_param, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            queryset = queryset.filter(created_on__gte=start_date, created_on__lte=end_date)

        return queryset
    
    def calculate_next_follow_up(self, lead):
            workflow = lead.workflow.get()
            followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
            if followup_tasks:
                return followup_tasks.time.date()
            return None
    # Check whethers followers in leads is mapped to user and show the details
    @swagger_auto_schema(
       operation_summary="get all leads",
       operation_description="This api returns a list of leads.",
       responses={200: LeadSerializer(many=True)},
    )

    #@group_access 
    @check_access(required_permissions=["lead.view_lead"])
    #@check_group_access(required_groups=["ADMIN"])
    def get(self, request, *args, **kwargs):


        queryset = self.get_queryset() # all leads based on roles
        module_param = request.GET.get('module', None)
        converted_param = bool(request.GET.get('converted_sales', None))
        site_visit_param = bool(request.GET.get('site_visit',None))
        created_by_param = request.GET.get('created_by',None)
        assigned_to_param = request.GET.get('assigned_to',None)
        unallocated_param = bool(request.GET.get('unallocated_leads',None))
        site_visit_status_param = request.GET.get('site_visit_status',None)
        doc_status_param = request.GET.get('doc_status',None)
        closure_param =  bool(request.GET.get('closure',None))
        follow_ups_param =  bool(request.GET.get('follow_ups',None))
        follow_ups_filter_param =  request.GET.get('follow_ups_filter',None)
        welcome_call_status_param=  request.GET.get('welcome_call_status',None)
        welcome_email_status_param=  request.GET.get('welcome_email_status',None)
        demand_letter_status_param=  request.GET.get('demand_letter_status',None)
        snagging_status_param=  request.GET.get('snagging_status',None)
        source_param =  request.GET.get('source',None)
        tower_param = request.GET.get('tower',None)
        aging_param = request.GET.get('aging',None)
        payment_status_param = request.GET.get('payment_status',None)
        payment_status_event_param = request.GET.get('payment_status_event',None)
        reminder_sent_param = request.GET.get('reminder_sent',None)
        event_name_param = request.GET.get('event_name', None)
        due_date_filter = request.GET.get('due_date_filter', None)  
        due_date_from = request.GET.get('due_date_from', None)  
        due_date_to = request.GET.get('due_date_to', None)
        crm_executive_param = request.GET.get('crm_executive',None)
        sv_status_param = request.GET.get('sv_status',None)

        SITEVISIT_CHOICES = [
            ("Site Visit Done", "Site Visit Done"),
            ("Missed", "Missed"),
            ("Scheduled", "Scheduled"),
        ]

        SiteVisit_choices = dict(SITEVISIT_CHOICES)


        if module_param == 'PRESALES':
            try:

                if not queryset:
                    page = self.paginate_queryset(queryset)
                    dummy_data= self.get_paginated_response(page)
                    return ResponseHandler(False, "GET ALL PRE-SALES DATA: ", dummy_data.data, status.HTTP_200_OK) 
                  
                if converted_param:
                    filtered_queryset = Lead.objects.filter(converted_on__isnull=False).order_by('-id')

                    sort_order_param = self.request.GET.get('sort_order', None)
                    sort_field_param = self.request.GET.get('sort_field', None)
                    if sort_field_param and sort_field_param == 'created_on':
                        order_by_param = '-created_on' if sort_order_param == 'desc' else 'created_on'
                        filtered_queryset = filtered_queryset.order_by(order_by_param)    
                    else:
                        filtered_queryset = filtered_queryset.order_by('-created_on')
                    if self.request.user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                        filtered_queryset = filtered_queryset.filter(followers__contains=[self.request.user.id])
                    if created_by_param:
                        created_by_param_list = map(int, created_by_param.split(','))
                        filtered_queryset = filtered_queryset.filter(creator__in = created_by_param_list)
                    if assigned_to_param:
                        assigned_to_param_list = map(int, assigned_to_param.split(','))
                        filtered_queryset = filtered_queryset.filter(followers__overlap=assigned_to_param_list) 
                    if source_param:
                        filtered_queryset = filtered_queryset.filter(source=source_param)     
                    search_query = request.GET.get('search', None)

                    if search_query is not None:

                        if search_query.isdigit():

                            filtered_queryset = filtered_queryset.filter(
                                Q(id__icontains=search_query) |
                                Q(primary_phone_no__icontains=search_query) |
                                Q(source__source_id__icontains=search_query)
                            )
                        else:

                            filtered_queryset = filtered_queryset.filter(
                                Q(first_name__icontains=search_query) |
                                Q(last_name__icontains=search_query) |
                                Q(creator__name__icontains=search_query)
                            )          
                    if filtered_queryset.exists():
                        #serializer = self.get_serializer(filtered_queryset, many=True)
                        page = self.paginate_queryset(filtered_queryset)
                        serializer = LeadConvertedSales(page, many=True)
                        data = self.get_paginated_response(serializer.data).data
                        return ResponseHandler(False, "Converted to Sales", data, status.HTTP_200_OK)
                    else:
                        page = self.paginate_queryset(filtered_queryset)
                        dummy_data= self.get_paginated_response(page)
                        return ResponseHandler(False, "Converted to Sales", dummy_data.data, status.HTTP_200_OK) 
            
                if unallocated_param:

                    call_center_executive_group = Group.objects.get(name='CALL_CENTER_EXECUTIVE') 

                    users_in_group = list(call_center_executive_group.user_set.values_list('id', flat=True))

                    unallocated_queryset=self.get_queryset()
                    unallocated_queryset = unallocated_queryset.exclude(
                        Q(followers__overlap=users_in_group) | Q(followers__isnull=True)
                    )
 
                    if created_by_param:
                        created_by_param_list = map(int, created_by_param.split(','))
                        unallocated_queryset = unallocated_queryset.filter(creator__in = created_by_param_list)

                    if unallocated_queryset.exists():
                        status_param = request.GET.get('lead_status')
                        if status_param is not None:
                            status_param = status_param.split(',')
                            unallocated_queryset = unallocated_queryset.filter(lead_status__in=status_param)
                        search_query = request.GET.get('search', None)

                        if search_query is not None:

                            if search_query.isdigit():

                                unallocated_queryset = unallocated_queryset.filter(
                                    Q(id__icontains=search_query) |
                                    Q(primary_phone_no__icontains=search_query) |
                                    Q(source__source_id__icontains=search_query)
                                )
                            else:

                                unallocated_queryset = unallocated_queryset.filter(
                                    Q(first_name__icontains=search_query) |
                                    Q(last_name__icontains=search_query) |
                                    Q(creator__name__icontains=search_query)
                                )
                        if follow_ups_filter_param == 'All':
                            unallocated_queryset = [lead for lead in unallocated_queryset if self.calculate_next_follow_up(lead) is not None]
                        elif follow_ups_filter_param == 'Today':
                            unallocated_queryset = [lead for lead in unallocated_queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date()]
                        elif follow_ups_filter_param == 'Tomorrow':
                            unallocated_queryset = [lead for lead in unallocated_queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date() + timedelta(days=1)]
                        elif follow_ups_filter_param == 'Missed':
                            unallocated_queryset = [lead for lead in unallocated_queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) < timezone.now().date()]
                        elif follow_ups_filter_param == 'Next_7_Days':
                            unallocated_queryset = [lead for lead in unallocated_queryset if (self.calculate_next_follow_up(lead) is not None) and timezone.now().date() <= self.calculate_next_follow_up(lead) <= timezone.now().date() + timedelta(days=7)]  
                        page = self.paginate_queryset(unallocated_queryset)
                        serializer = LeadUnallocated(page, many=True)
                        data = self.get_paginated_response(serializer.data).data     
                        #serializer = self.get_serializer(unallocated_queryset, many=True)
                        return ResponseHandler(False,"Unallocated Leads",data,status.HTTP_200_OK)
                    else:
                        page = self.paginate_queryset(unallocated_queryset)
                        dummy_data= self.get_paginated_response(page)
                        return ResponseHandler(False, "Unallocated Leads" , dummy_data.data, status.HTTP_200_OK) 
                     

                if site_visit_param:
                    queryset = self.get_queryset()
                    if source_param:
                        queryset = queryset.filter(source=source_param)  
                    search_query = request.GET.get('search')
                    
                    if search_query is not None:
                        
                        if search_query.isdigit():

                            queryset = queryset.filter(
                                Q(id__icontains=search_query) |
                                Q(primary_phone_no__icontains=search_query) |
                                Q(source__source_id__icontains=search_query)
                            )
                        else:
                            search_words = search_query.split()  
                            queryset = queryset.filter(
                                Q(first_name__icontains=search_query) |
                                Q(last_name__icontains=search_query) |
                                Q(creator__name__icontains=search_query)
                            ) 

                    #print("Filtered count before:", queryset.count())
                    #print("created_by_param: ", created_by_param)
                    if created_by_param:
                        created_by_param_list = map(int, created_by_param.split(','))
                        queryset = queryset.filter(creator__in=created_by_param_list)
                        #print("Filtered count after:", queryset.count())
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
                            latest_site_visit_date = latest_site_visit.visit_date.strftime('%Y-%m-%d')
                        else:
                            latest_site_visit_status = None
                            latest_site_visit_date = None
                        workflow_instance = lead.workflow.get()
                        assigned_to = workflow_instance.assigned_to if workflow_instance else None
                        first_stage = workflow_instance.stages.all().order_by('order').first()

                        if site_visit_status_param is None or latest_site_visit_status == site_visit_status_param:
                            lead_data = {
                                "id": lead.id,
                                "lead_name": f"{lead.first_name} {lead.last_name}",
                                "created_on": lead.created_on.date(),
                                "created_by": UserDataSerializer(lead.creator).data if lead.creator else None ,
                                "assigned_to": UserDataSerializer(first_stage.assigned_to).data if first_stage and first_stage.assigned_to else None ,
                                "phone_no": lead.primary_phone_no,
                                "source_id": {"source_id": lead.source.source_id, "source_data": f"{lead.source.name}"} if lead.source else None,
                                "scheduled_on": latest_site_visit_date,
                                "sv_status_list": [{"status": status, "selected": status == latest_site_visit_status}
                                for status in SiteVisit_choices.keys()],
                                "sv_status": latest_site_visit_status,
                                "has_notes": lead.notes_set.exists(),
                                "no_of_calls": None,
                                "is_important":lead.is_important
                            }
                            leads_with_latest_site_visit.append(lead_data)

                    sort_order_param = self.request.GET.get('sort_order', None)
                    sort_field_param = self.request.GET.get('sort_field', None)
                    if sort_field_param and sort_field_param == 'scheduled_on':
                        order_by_param = True if sort_order_param == 'desc' else False
                        leads_with_latest_site_visit = sorted(leads_with_latest_site_visit, key=lambda x: x['scheduled_on'], reverse=order_by_param) 


                    search_query = request.GET.get('search', '').lower()

                    #leads_with_latest_site_visit = [lead for lead in leads_with_latest_site_visit if search_query in lead["lead_name"].lower()]
                    # if site_visit_status_param:
                    #     leads_with_latest_site_visit = [lead for lead in leads_with_latest_site_visit if search_query in lead["lead_name"].lower()]
                    
                    print(len(leads_with_latest_site_visit))
                    if leads_with_latest_site_visit:
                        page = self.paginate_queryset(leads_with_latest_site_visit)
                        data = self.get_paginated_response(page).data
                        return ResponseHandler(False, "Site Visit Presales", data, status.HTTP_200_OK)
                    else:
                        page = self.paginate_queryset(leads_with_latest_site_visit)
                        dummy_data= self.get_paginated_response(page)
                        return ResponseHandler(False, "Site Visit Presales" , dummy_data.data, status.HTTP_200_OK) 
                
                    
                if follow_ups_param:
                    # status_param = request.GET.get('lead_status')
                    # if status_param is not None:
                    #     status_param = status_param.split(',')
                    #     queryset = queryset.filter(lead_status__in=status_param)
                    queryset = self.filter_leads(queryset, self.request.query_params)    
                    if assigned_to_param:
                        assigned_to_param_list = map(int, assigned_to_param.split(','))
                        queryset = queryset.filter(followers__overlap=assigned_to_param_list)  
                    if created_by_param:
                        created_by_param_list = map(int, created_by_param.split(','))
                        queryset = queryset.filter(creator__in = created_by_param_list)
                    search_query = request.GET.get('search', None)

                    if search_query is not None:

                        if search_query.isdigit():

                            queryset = queryset.filter(
                                Q(id__icontains=search_query) |
                                Q(primary_phone_no__icontains=search_query) |
                                Q(source__source_id__icontains=search_query)
                            )
                        else:

                            queryset = queryset.filter(
                                Q(first_name__icontains=search_query) |
                                Q(last_name__icontains=search_query) |
                                Q(creator__name__icontains=search_query)
                            )    
                    if follow_ups_filter_param == 'All':
                        queryset = [lead for lead in queryset if self.calculate_next_follow_up(lead) is not None]
                    elif follow_ups_filter_param == 'Today':
                        queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date()]
                    elif follow_ups_filter_param == 'Tomorrow':
                        queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date() + timedelta(days=1)]
                    elif follow_ups_filter_param == 'Missed':
                        queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) < timezone.now().date()]
                    elif follow_ups_filter_param == 'Next_7_Days':
                        queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and timezone.now().date() <= self.calculate_next_follow_up(lead) <= timezone.now().date() + timedelta(days=7)] 
                    

                    if queryset:
                        page = self.paginate_queryset(queryset)
                        serializer = LeadPreSalesSerializer(page, many=True)
                        data = self.get_paginated_response(serializer.data).data 
                        #serializer = self.get_serializer(filtered_queryset, many=True)
                        return ResponseHandler(False,"Follow ups",data,status.HTTP_200_OK)
                    else:
                        page = self.paginate_queryset(queryset)
                        dummy_data= self.get_paginated_response(page)
                        return ResponseHandler(False, "Follow ups" , dummy_data.data, status.HTTP_200_OK) 


                if created_by_param:
                    created_by_param_list = map(int, created_by_param.split(','))
                    filtered_queryset = queryset.filter(creator__in = created_by_param_list)
                    search_query = request.GET.get('search', None)

                    if search_query is not None:

                        if search_query.isdigit():

                            filtered_queryset = filtered_queryset.filter(
                                Q(id__icontains=search_query) |
                                Q(primary_phone_no__icontains=search_query) |
                                Q(source__source_id__icontains=search_query)
                            )
                        else:

                            filtered_queryset = filtered_queryset.filter(
                                Q(first_name__icontains=search_query) |
                                Q(last_name__icontains=search_query) |
                                Q(creator__name__icontains=search_query)
                            )
                    if filtered_queryset.exists():
                        page = self.paginate_queryset(filtered_queryset)
                        serializer = LeadPreSalesSerializer(page, many=True)
                        data = self.get_paginated_response(serializer.data).data 
                        #serializer = self.get_serializer(filtered_queryset, many=True)
                        return ResponseHandler(False,"Created by",data,status.HTTP_200_OK)
                    else:
                        page = self.paginate_queryset(filtered_queryset)
                        dummy_data= self.get_paginated_response(page)
                        return ResponseHandler(False, "Created by" , dummy_data.data, status.HTTP_200_OK) 
                    
                if assigned_to_param:
                    print("assigned_to: ",assigned_to_param)
                    assigned_to_param_list = map(int, assigned_to_param.split(','))
                    print("queryset: ",queryset)
                    queryset = queryset.filter(followers__overlap=assigned_to_param_list)
                    print("queryset: ",queryset) 
                    # if filtered_queryset.exists():
                    #     page = self.paginate_queryset(filtered_queryset)
                    #     serializer = LeadPreSalesSerializer(page, many=True)
                    #     data = self.get_paginated_response(serializer.data).data 
                    #     #serializer = self.get_serializer(filtered_queryset, many=True)
                    #     return ResponseHandler(False,"Assigned to",data,status.HTTP_200_OK)
                    # else:
                    #     page = self.paginate_queryset(filtered_queryset)
                    #     dummy_data= self.get_paginated_response(page)
                    #     return ResponseHandler(False, "Assigned to" , dummy_data.data, status.HTTP_200_OK)  
                                       
                status_param = request.GET.get('lead_status')
                if status_param is not None:
                    status_param = status_param.split(',')
                    queryset = queryset.filter(lead_status__in=status_param)
                purpose_param = request.GET.get('purpose', None)
                if purpose_param is not None:
                    queryset = queryset.filter(lead_requirement__purpose=purpose_param)
                configuration_param = request.GET.get('configuration', None)
                if configuration_param is not None:
                    queryset = queryset.filter(lead_requirement__configuration=configuration_param)
                funding_param = request.GET.get('funding', None)
                if funding_param is not None:
                    queryset = queryset.filter(lead_requirement__funding=funding_param)
                budget_min_param = request.GET.get('budget_min', None)
                if budget_min_param is not None:
                    queryset = queryset.filter(lead_requirement__budget_min__lte=budget_min_param) 
                budget_max_param = request.GET.get('budget_max', None)
                if budget_max_param is not None:
                    queryset = queryset.filter(lead_requirement__budget_max__gte=budget_max_param)

                date_range_param = request.GET.get('date_range', None)
                start_date_param = request.GET.get('start_date', None)
                end_date_param = request.GET.get('end_date', None)
                #print(date_range_param)
                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    #print(datetime.now())
                    #print(seven_days_ago)
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
                elif date_range_param == 'custom_range' and start_date_param and end_date_param:
                    start_date = datetime.strptime(start_date_param, '%Y-%m-%d')
                    end_date = datetime.strptime(end_date_param, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                    queryset = queryset.filter(created_on__gte=start_date,created_on__lte=end_date)


                if follow_ups_filter_param == 'All':
                    queryset = [lead for lead in queryset if self.calculate_next_follow_up(lead) is not None]
                elif follow_ups_filter_param == 'Today':
                    queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date()]
                elif follow_ups_filter_param == 'Tomorrow':
                    queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date() + timedelta(days=1)]
                elif follow_ups_filter_param == 'Missed':
                    queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) < timezone.now().date()]
                elif follow_ups_filter_param == 'Next_7_Days':
                    queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and timezone.now().date() <= self.calculate_next_follow_up(lead) <= timezone.now().date() + timedelta(days=7)]    
            # filter based on query params
            # Do pagination 
            # pass paginated data to serializer
                search_query = request.GET.get('search', None)

                if search_query is not None:
                    if search_query.isdigit():

                        if isinstance(queryset, list):

                            queryset = [item for item in queryset if
                                        str(item.id).find(search_query) != -1 or
                                        str(item.primary_phone_no).find(search_query) != -1]
                        else:

                            queryset = queryset.filter(
                                Q(id__icontains=search_query) |
                                Q(primary_phone_no__icontains=search_query) |
                                Q(source__source_id__icontains=search_query)
                            )
                    else:

                        if isinstance(queryset, list):
                            search_query_lower = search_query.lower()
                            queryset = [item for item in queryset if
                                        search_query_lower in str(item.first_name).lower() or
                                        search_query_lower in str(item.last_name).lower() or
                                        search_query_lower in str(item.creator.name).lower()]
                        else:

                            queryset = queryset.filter(
                                Q(first_name__icontains=search_query) |
                                Q(last_name__icontains=search_query) |
                                Q(creator__name__icontains=search_query)
                            )  
                page = self.paginate_queryset(queryset)

                if page is not None:
                    serializer = LeadPreSalesSerializer(page, many=True)
                    #resp = self.get_paginated_response(serializer.data)
                    data = self.get_paginated_response(serializer.data).data
                    return ResponseHandler(False, "GET ALL LEADS DATA: ", data, status.HTTP_200_OK)
                else:
                    page = self.paginate_queryset(queryset)
                    dummy_data= self.get_paginated_response(page)
                    return ResponseHandler(False, "GET ALL LEADS DATA: ", dummy_data.data, status.HTTP_200_OK)
                #serializer = self.get_serializer(queryset, many=True)

            except Exception as e:
                return ResponseHandler(True, "An error occurred", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)
    
        elif module_param == 'SALES':

            queryset = self.get_queryset()

            if not queryset:
                page = self.paginate_queryset(queryset)
                dummy_data= self.get_paginated_response(page)
                return ResponseHandler(False, "GET ALL SALES DATA: ", dummy_data.data, status.HTTP_200_OK)                                        

            search_query = request.GET.get('search')
            
            if search_query is not None:
                
                if search_query.isdigit():

                    queryset = queryset.filter(
                        Q(id__icontains=search_query) |
                        Q(primary_phone_no__icontains=search_query) |
                        Q(source__source_id__icontains=search_query)
                    )
                else:

                    queryset = queryset.filter(
                        Q(first_name__icontains=search_query) |
                        Q(last_name__icontains=search_query) |
                        Q(creator__name__icontains=search_query)
                    ) 
               

            if closure_param:
                queryset = queryset.filter(projectinventory__status="Booked").order_by('-id')
            current_user = self.request.user
        # Annotate the queryset with the latest site visit information for each lead
            queryset = queryset.annotate(
                latest_site_visit_date=Max('sitevisit__visit_date')
            )

                    # Filter leads based on the current user's ID and the 'CLOSING_MANAGER' group
            for obj in queryset:
                print(f"Lead ID: {obj.id}")
                print(f"Lead First Name: {obj.first_name}")
                print("\n")
            #queryset = Lead.objects.filter(sitevisit__scheduled=True)
            # Annotate the queryset with the count of site visits that have occurred (occurred=True)
            queryset = queryset.annotate(sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done")))
            #queryset = queryset.annotate(sv_status=F('sitevisit__get_status'))
            #queryset = queryset.annotate(
                #sv_datetime=ExpressionWrapper(
                    #Concat('sitevisit__visit_date', Value(' '), 'sitevisit__timeslot'),
                    #output_field=CharField()
                #)
            #)
            
            #queryset = queryset.annotate(closing_manager='sitevisit__closing_manager')
            #queryset = queryset = Lead.objects.filter(lead_requirement__sitevisit__scheduled=True)
            #queryset = Lead.objects.all()
            #filtered_queryset =  SiteVisit.objects.all
            #serializer = self.get_serializer(queryset, many=True)
            
            # Fetch the related SiteVisit instances
            #lead_ids = queryset.values_list('id', flat=True)
            #site_visits = SiteVisit.objects.filter(lead__id__in=lead_ids)
            # Calculate and add sv_status to the queryset

            purpose_param = request.GET.get('purpose', None)
            if purpose_param is not None:
                queryset = queryset.filter(lead_requirement__purpose=purpose_param)

            configuration_param = request.GET.get('configuration', None)
            if configuration_param is not None:
                queryset = queryset.filter(lead_requirement__configuration=configuration_param)

            budget_min_param = request.GET.get('budget_min', None)
            if budget_min_param is not None:
                queryset = queryset.filter(lead_requirement__budget_min__lte=budget_min_param) 
            budget_max_param = request.GET.get('budget_max', None)
            if budget_max_param is not None:
                queryset = queryset.filter(lead_requirement__budget_max__gte=budget_max_param)


            leads = list(queryset)
            for lead in leads:
                try:
                    print("LEAD INSIDE SITEVISIT: ",lead)
                    latest_site_visit = SiteVisit.objects.filter(
                        lead=lead,
                        visit_date=lead.latest_site_visit_date,
                    ).order_by('-id').first()
                    lead.sv_id  = latest_site_visit.id
                    lead.sv_status = latest_site_visit.site_visit_status
                    input_date = datetime.strptime(str(latest_site_visit.visit_date), "%Y-%m-%d")
                    formatted_date = input_date.strftime("%d-%m-%Y")
                    lead.sv_datetime = f"{formatted_date} {latest_site_visit.timeslot}" 
                    print("closing manager: ",latest_site_visit.closing_manager)
                    lead.closing_manager=UserDataSerializer(latest_site_visit.closing_manager).data if latest_site_visit.closing_manager else None
                    lead.has_notes = lead.notes_set.exists()
                except SiteVisit.DoesNotExist:
                    lead.sv_status = None
                    lead.sv_id  = None
                    lead.closing_manager = None
                    lead.sv_datetime = None
                    #lead.closing_manager=latest_site_visit.closing_manager.name if latest_site_visit.closing_manager else None
                    #user =  Users.objects.filter(id = latest_site_visit.closing_manager.id)
                    #print(user)
                # except SiteVisit.DoesNotExist:
                #     lead.sv_status = None
                #     lead.sv_id  = None
                #     lead.closing_manager = None
                    #lead.closing_manager =  latest_site_visit.closing_manager

            # Calculate and add sv_status to the queryset
            #for lead in queryset:
                #related_site_visits = site_visits.filter(lead=lead)
                #lead.sv_status = related_site_visits.first().get_status() if related_site_visits else None
                #lead.closing_manager = related_site_visits.first().closing_manager
                #print(related_site_visits.first().get_status())

                #queryset = queryset.filter(lead.sv_status=site_visit_status_param)
                
            # Filter leads based on the site_visit_status_param
            if site_visit_status_param is not None:
                leads = [lead for lead in leads if lead.sv_status == site_visit_status_param]

            # Filter leads based on the closing manager
            closing_manager_param = self.request.query_params.get('closing_manager')
            if closing_manager_param:
                closing_manager_param_list = list(map(int, closing_manager_param.split(',')))
                #print("closing_manager_param_list: ", closing_manager_param_list)
                leads = [lead for lead in leads if lead.closing_manager and lead.closing_manager.get('id') in closing_manager_param_list]

            # Filter leads based on the lead_status
            lead_status_param = self.request.query_params.get('lead_status')
            if lead_status_param:
                lead_status_list = lead_status_param.split(',')
                leads = [lead for lead in leads if lead.lead_status in lead_status_list]

            # Filter leads based on sv_done
            sv_done_param = self.request.query_params.get('sv_done')
            if sv_done_param:
                sv_done_param = int(sv_done_param)  # Convert to integer
                if sv_done_param < 2:
                    leads = [lead for lead in leads if lead.sv_done == sv_done_param]
                elif sv_done_param >= 2:
                    leads = [lead for lead in leads if lead.sv_done >= 2]


                # Filter leads based on the visit_date
            date_range_param = self.request.query_params.get('date_range')
            if date_range_param:
                today = datetime.now()
                if date_range_param == 'today':
                    today_date = today.date()
                    leads = [lead for lead in leads if lead.latest_site_visit_date and  lead.latest_site_visit_date == today_date]
                elif date_range_param == 'tomorrow':
                    tomorrow = today + timedelta(days=1)
                    tomorrow_date = tomorrow.date()
                    leads = [lead for lead in leads if lead.latest_site_visit_date and  lead.latest_site_visit_date == tomorrow_date]
                elif date_range_param == 'next_1_month':
                    next_1_month = today + timedelta(days=30)
                    next_1_month_date = next_1_month.date()
                    leads = [lead for lead in leads if lead.latest_site_visit_date and lead.latest_site_visit_date <= next_1_month_date]

                elif date_range_param == 'next_6_month':
                    next_6_month = today + timedelta(days=6 * 30)
                    next_6_month_date = next_6_month.date()
                    leads = [lead for lead in leads if lead.latest_site_visit_date and lead.latest_site_visit_date <= next_6_month_date]
 
                elif date_range_param == 'custom_range':
                    start_date_param = self.request.query_params.get('start_date')
                    end_date_param = self.request.query_params.get('end_date')
                    if start_date_param and end_date_param:
                        start_datetime = datetime.strptime(start_date_param, '%Y-%m-%d')
                        start_date = start_datetime.date()
                        end_datetime = datetime.strptime(end_date_param, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
                        end_date = end_datetime.date()
                        leads = [lead for lead in leads if start_date <= lead.latest_site_visit_date <= end_date]        


            page = self.paginate_queryset(leads)

  

            if closure_param:
                #return ResponseHandler(False, "NEED TO FIX AFTER INVENTORY: ", None, status.HTTP_200_OK)
                if page is not None:
                    serializer = LeadClosureSerializer(page, many=True)
                    data = self.get_paginated_response(serializer.data).data
                    return ResponseHandler(False, "CLOSURE SALES DATA: ", data, status.HTTP_200_OK)
                else:
                     return ResponseHandler(False, "NO SALES DATA: ", [], status.HTTP_200_OK) 
     
    
            serializer = LeadSalesSerializer(page, many=True)
            data = self.get_paginated_response(serializer.data).data
            #serializer = LeadSalesSerializer(queryset, many=True)
            return ResponseHandler(False,"ALL SALES DATA: ", data,status.HTTP_200_OK)

        elif module_param == 'POSTSALES':
            queryset = self.get_queryset()
            search_query = request.GET.get('search')
            queryset = queryset.annotate(
                latest_site_visit_date=Max('sitevisit__visit_date')
            )
            print("queryset",queryset)
            leads_data = []
            for lead in queryset:
                try:
                    # print("LEAD INSIDE SITEVISIT: ",lead)
                    # latest_site_visit = SiteVisit.objects.filter(
                    #     lead=lead,
                    #     visit_date=lead.latest_site_visit_date,
                    # ).order_by('-id').first()
                    # lead.sv_id  = latest_site_visit.id
                    # lead.sv_status = latest_site_visit.site_visit_status
                    # input_date = datetime.strptime(str(latest_site_visit.visit_date), "%Y-%m-%d")
                    # formatted_date = input_date.strftime("%d-%m-%Y")
                    # lead.sv_datetime = f"{formatted_date} {latest_site_visit.timeslot}" 
                    # print("closing manager: ",latest_site_visit.closing_manager)
                    # lead.closing_manager=UserDataSerializer(latest_site_visit.closing_manager).data if latest_site_visit.closing_manager else None
                    # lead.has_notes = lead.notes_set.exists()
                    latest_site_visit = SiteVisit.objects.filter(
                        lead=lead,
                        visit_date=lead.latest_site_visit_date
                    ).order_by('-id').first()

                    input_date = datetime.strptime(str(latest_site_visit.visit_date), "%Y-%m-%d")
                    formatted_date = input_date.strftime("%d-%m-%Y")
                    timeslot = latest_site_visit.timeslot if latest_site_visit and latest_site_visit.timeslot else ""

                    # Collect data into a dictionary
                    lead_data = {
                        'lead': lead,
                        'sv_id': latest_site_visit.id if latest_site_visit else None,
                        'sv_status': latest_site_visit.site_visit_status if latest_site_visit else None,
                        'sv_datetime': f"{formatted_date} {timeslot}" if latest_site_visit else None,
                        'closing_manager': latest_site_visit.closing_manager if latest_site_visit else None,
                        'has_notes' : lead.notes_set.exists()
                    }
                    leads_data.append(lead_data)

                except SiteVisit.DoesNotExist:
                    # lead.sv_status = None
                    # lead.sv_id  = None
                    # lead.closing_manager = None
                    # lead.sv_datetime = None
                    leads_data.append({
                        'lead': lead,
                        'sv_id': None,
                        'sv_status': None,
                        'sv_datetime': None,
                        'closing_manager': None
                    })
            
            if search_query is not None:
                
                if search_query.isdigit():

                    queryset = queryset.filter(
                        Q(id__icontains=search_query) |
                        Q(primary_phone_no__icontains=search_query) |
                        Q(source__source_id__icontains=search_query)
                    )
                else:
                    search_words = search_query.split()  
                    queryset = queryset.filter(
                        Q(first_name__icontains=search_query) |
                        Q(last_name__icontains=search_query) |
                        Q(creator__name__icontains=search_query)
                    ) 
            if not queryset:
                page = self.paginate_queryset(queryset)
                dummy_data= self.get_paginated_response(page)
                return ResponseHandler(False, "GET ALL POST SALES DATA: ", dummy_data.data, status.HTTP_200_OK) 


            if doc_status_param:
                page = self.paginate_queryset(queryset)
                serializer = LeadDocSerializer(page, many=True)
                data = self.get_paginated_response(serializer.data).data
                return ResponseHandler(False,"POST SALES DATA: ",data,status.HTTP_200_OK)
           
            if assigned_to_param:
                assigned_to_param_list = map(int, assigned_to_param.split(','))
                queryset = queryset.filter(followers__overlap=assigned_to_param_list)  
            if welcome_call_status_param is not None:
                queryset = queryset.filter(updates__welcome_call_status=welcome_call_status_param)
            if welcome_email_status_param is not None:
                queryset = queryset.filter(updates__welcome_email_status=welcome_email_status_param)
            if demand_letter_status_param is not None:
                queryset = queryset.filter(updates__demand_letter_status=demand_letter_status_param)
            if snagging_status_param is not None:
                queryset = queryset.filter(updates__snagging_email_status=snagging_status_param)
            if tower_param:
                tower_list = [tower.strip() for tower in tower_param.split(',')]
                queryset = queryset.filter(projectinventory__tower__name__in=tower_list)

            if sv_status_param:
                if sv_status_param == "Done":
                    queryset = queryset.exclude(sitevisit__site_visit_status__in=["Missed","Scheduled"])
                    print("queryset",queryset.count())
                elif sv_status_param == "All":
                    queryset = queryset
                else:
                    queryset = queryset.filter(sitevisit__site_visit_status = sv_status_param)       
          
            if aging_param:
                queryset = queryset.exclude(
                    updates__demand_letter_status__isnull=True,
                    inventorycostsheet__due_date__isnull=True,
                    inventorycostsheet__paid__isnull=True
                    )   
                if aging_param == ">60 Days":
                    queryset = queryset.filter(
                        updates__demand_letter_status="Sent",
                        inventorycostsheet__due_date__lt=datetime.now() - timedelta(days=60),
                        inventorycostsheet__paid=False
                    )
                elif aging_param == ">30 Days":
                    queryset = queryset.filter(
                        updates__demand_letter_status="Sent",
                        inventorycostsheet__due_date__lte=datetime.now() - timedelta(days=30),
                        inventorycostsheet__due_date__gt=datetime.now() - timedelta(days=60),
                        inventorycostsheet__paid=False
                    )
                elif aging_param == "<=30 Days":
                    queryset = queryset.filter(
                        updates__demand_letter_status="Sent",
                        inventorycostsheet__due_date__gt=datetime.now() - timedelta(days=30),
                        inventorycostsheet__paid=False
                    ) 
            if payment_status_param:
                queryset = queryset.exclude(
                    updates__demand_letter_status__isnull=True,
                    inventorycostsheet__due_date__isnull=True,
                    inventorycostsheet__paid__isnull=True
                    )   
                if payment_status_param == "raised":
                    queryset = queryset.filter(
                        updates__demand_letter_status="Sent",
                        inventorycostsheet__due_date__isnull=False,
                        inventorycostsheet__paid=False,
                        inventorycostsheet__due_date__lte=datetime.now() - timedelta(days=30)
                    )
                elif payment_status_param == "due":
                    queryset = queryset.filter(
                        updates__demand_letter_status="Sent",
                        inventorycostsheet__due_date__isnull=False,
                        inventorycostsheet__paid=False,
                        inventorycostsheet__due_date__gt=datetime.now() - timedelta(days=30),
                        inventorycostsheet__due_date__lte=datetime.now() - timedelta(days=60)
                    )
                elif payment_status_param == "received":
                    queryset = queryset.filter(
                        updates__demand_letter_status="Sent",
                        inventorycostsheet__paid=True
                    )
                elif payment_status_param == "none":
                    queryset = queryset.filter(
                        inventorycostsheet__paid__isnull=True
                    )

            if payment_status_event_param:
                # Filter InventoryCostSheet objects based on the payment status property
                inventory_cost_sheets = InventoryCostSheet.objects.filter(lead__in=queryset)
                
                # Create a mapping of leads that match the payment status
                lead_ids = [
                    inventory_sheet.lead_id for inventory_sheet in inventory_cost_sheets
                    if inventory_sheet.payment_status == payment_status_event_param
                ]

                queryset = queryset.filter(id__in=lead_ids)
            
            if event_name_param:
                # Fetch `Updates` objects related to leads in the queryset
                updates_records = Updates.objects.filter(lead__in=queryset)
                
                # Filter `Updates` records based on `event_name`
                lead_ids_event_name = [
                    update_record.lead_id for update_record in updates_records
                    if update_record.slab and update_record.slab.event == event_name_param
                ]
                
                # Adjust the queryset to include only matching leads
                queryset = queryset.filter(id__in=lead_ids_event_name)

            if due_date_filter:
                today = make_aware(datetime.now())
                due_date_start = None
                due_date_end = None
                if due_date_filter == "Today":
                    due_date_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
                    due_date_end = today.replace(hour=23, minute=59, second=59, microsecond=999999)
                elif due_date_filter == "Next_7_days":
                    due_date_start = today
                    due_date_end = today + timedelta(days=7)
                elif due_date_filter == "Next_1_month":
                    due_date_start = today
                    due_date_end = today + timedelta(days=30)
                elif due_date_filter == "Custom" and due_date_from and due_date_to:
                    due_date_start = make_aware(datetime.strptime(due_date_from, "%Y-%m-%d"))
                    due_date_end = make_aware(datetime.strptime(due_date_to, "%Y-%m-%d")).replace(hour=23, minute=59, second=59, microsecond=999999)

                # Filter InventoryCostSheet objects based on due date range
                inventory_cost_sheets = InventoryCostSheet.objects.filter(
                    lead__in=queryset, due_date__range=(due_date_start, due_date_end)
                )
                lead_ids_due_date = [inventory_sheet.lead_id for inventory_sheet in inventory_cost_sheets]
                queryset = queryset.filter(id__in=lead_ids_due_date)


            if  reminder_sent_param is not None:
                queryset = queryset.annotate(
                    notification_count=Subquery(
                        NotificationCount.objects.filter(
                            lead=OuterRef('pk')
                        ).values('lead')  # Group by the lead
                        .annotate(total_count=Sum('count'))  # Sum of counts for each lead
                        .values('total_count')[:1]  # Get the total count value (ensures single result)
                    )
                )  

                reminder_sent_param = int(reminder_sent_param)
                queryset = queryset.filter(notification_count=reminder_sent_param)

            page = self.paginate_queryset(queryset)
            # serializer = LeadPostSalesSerializer(page, many=True)
            serializer = LeadPostSalesSerializer(page, many=True, context={'leads_data': leads_data})
            data = self.get_paginated_response(serializer.data).data
            #serializer = LeadSalesSerializer(queryset, many=True)
           # return ResponseHandler(False,"ALL SALES DATA: ", data,status.HTTP_200_OK)
            return ResponseHandler(False, "POST SALES DATA: ", data, status.HTTP_200_OK)


        return ResponseHandler(True, "Provide the module info in query params", None, status.HTTP_400_BAD_REQUEST)
    
    @swagger_auto_schema(
    #operation_summary = ""
    operation_description="Create Leads and Lead Requirements",
    responses={200: 'OK'},
        )
    
    @check_access(required_permissions=["lead.add_lead"])
    def post(self, request, *args, **kwargs):
        assigned_to_flag = False   
        user = self.request.user 
        module_param = self.request.GET.get('module', None)
        # check assigned_To in request content
        if request.data.get('assigned_to',None):
            queryset_users = Users.objects.all()
            assigned_to_used_id = request.data.get('assigned_to')
            assigned_to_flag = True
            filtered_users = queryset_users.filter(id=assigned_to_used_id)
            assigned_to = filtered_users
            assigned_to = assigned_to.first()
        else:
            assigned_to = self.request.user  
        if user.groups.filter(name__in=["INQUIRY_FORM"]).exists():
            serializer = LeadInquiryFormSerializer(data=request.data,assigned_to={'assigned_to': assigned_to})  
        elif user.groups.filter(name__in=["CORPORATE_LEADS"]).exists():
            salutation = request.data.get('salutation')
            full_name = request.data.get('full_name')
            primary_phone_number = request.data.get('primary_phone_number')
            primary_email = request.data.get('email')
            if not all([salutation, full_name, primary_phone_number, primary_email]):
                return ResponseHandler(True, 'Please provide all required data (salutation,full_name,primary_email,primary_phone_number)',None,status.HTTP_400_BAD_REQUEST)
            split_name = full_name.split()
            first_name = split_name[0]
            last_name = ' '.join(split_name[1:]) if len(split_name) > 1 else ''
            sourceid = Source.objects.get(name="Corporate Leads")
            if salutation.lower() == 'mr':
                gender = 'Male'
            elif salutation.lower() == 'mrs':
                gender = 'Female'
            else:
                gender = None
            data = {
                'first_name': first_name,
                'last_name': last_name,
                'primary_phone_no': primary_phone_number,
                'primary_email': primary_email,
                'gender': gender,
                'source': sourceid.id,
            }
        
            serializer = CorporateLeadSerializer(data=data,assigned_to={'assigned_to': assigned_to})          
        else:
            serializer = self.get_serializer(data=request.data,assigned_to={'assigned_to': assigned_to})  
        lead=dict()
        if serializer.is_valid():
            self.perform_create(serializer)
            lead = serializer.save(creator=self.request.user) 
            #print("LEAD: ",lead)
            # Update creation_stage if created in sales module
            if module_param == "SALES":
                lead.creation_stage = "Sales"
                lead.save()
            #TODO: If lead is not created throw error, lead.organization is not valid
        else:
            error = True
            message = serializer.errors
            body = None
            return ResponseHandler(error,message,body,status.HTTP_400_BAD_REQUEST)
    #print(assigned_to_value)

        #if assigned_to_value:
            #assigned_to = assigned_to_value
        #else:

        #assigned_to = self.request.user #Pass the assigned to
        # lead = serializer.save(creator=self.request.user)
        # print('assigned_to:', assigned_to)
        workflow_definition = self.request.data.pop("workflow_definition", None)
        print('workflow_definition:', workflow_definition)
        definition=None
        if workflow_definition is None:
            if lead and lead.organization:
                definition=WorkflowDefinition.objects.filter(organization=lead.organization,
                workflow_type='sales').last()
            else:
                definition=WorkflowDefinition.objects.filter(organization=self.request.user.organization,
                workflow_type='sales').last()
        else:
            definition = WorkflowDefinition.objects.get(id=workflow_definition)
        
        if definition:
            # print('definition:', definition, definition.id)
            if lead.workflow.exists():
                workflow=lead.workflow.all().first()
                workflow.assigned_to=assigned_to
                workflow.save()
            else:
                workflow_data = {
                    "lead": lead.id,
                    "definition": definition.id,
                    "name": definition.name,
                    "workflow_type": definition.workflow_type,
                    "assigned_to": assigned_to.id if assigned_to else None,
                    "organization": lead.organization.id if lead.organization else None,
                }
                # print("worfkow data is", workflow_data)
                #workflow_ser = WorkflowCreateSerializer(data=workflow_data)
                if not assigned_to_flag and user.groups.filter(name="ADMIN").exists() or  user.groups.filter(name="PROMOTER").exists():
                    workflow_ser = WorkflowBulkUploadCreateSerializer(data=workflow_data)
                else:
                    workflow_ser = WorkflowCreateSerializer(data=workflow_data)
                workflow_ser.is_valid(raise_exception=True)
                workflow_ser.save()
            #headers = self.get_success_headers(serializer.data)
            # print('workflow_ser:', workflow_ser)
            # process_workflow.delay(workflow_ser.id)
            
            # if lead is getting created in sales stage, maeking presale stage as 'completed' and moving lead to next stage i.e. 'sales'
            if module_param == "SALES":
                print(module_param)

                # #create dummy site visit record
                # site_visit_params = {
                #     'visit_date': lead.created_on.date(), 
                #     'property': 'p1',  
                #     'timeslot': '10:00 AM to 10:30 AM', 
                #     'lead': lead,
                #     'site_visit_status': 'Site Visit Done',
                # }
                # site_visit = SiteVisit.objects.create(**site_visit_params)

                workflow=lead.workflow.all().first()
                workflow.current_stage=1
                workflow.save()
                # print('workflow:', workflow)
                presale_stage = Stage.objects.filter(workflow = workflow, completed=False).order_by('order').first()
                # print('presale_stage:', presale_stage)
                presale_stage.completed = True
                presale_stage.completed_at = timezone.now()
                presale_stage.save()

                next_stage = Stage.objects.filter(order__gte = workflow.current_stage, workflow = workflow, completed=False).order_by('order').first()
                # print('next_stage:', next_stage)
                if next_stage:
                    next_stage.started = True
                    next_stage.started_at = timezone.now()
                    next_stage.save()
                state = get_object_or_404(State, label='Accept')
                first_stage = lead.workflow.get().stages.first()
                followup_time = timezone.now() + timedelta(hours=48)
                followup_time_ist = followup_time.astimezone(timezone.pytz.timezone('Asia/Kolkata'))
                # follow up 48hrs later
                data=   {
                            "stage":first_stage,
                            "name": "Follow Up",
                            "order":0,
                            "task_type": "appointment",
                            "workflow":lead.workflow.get(),
                            "appointment_with": f"{lead.first_name} {lead.last_name}",
                            "appointment_type": "telephonic",
                            "time": followup_time_ist,
                            "details":"Follow up call with lead",
                            "status": state,
                            "minimum_approvals_required": 0
                    }
                task = Task.objects.create(**data)
                first_task = next_stage.tasks.filter(completed=False).order_by('order').first()
                process_task.delay(first_task.id)


                if user.groups.filter(name__in=["INQUIRY_FORM"]).exists():
                    get_receptionist_user = Users.objects.filter(groups__name="RECEPTIONIST").first()
                    title = "New Lead Created"
                    body = f"New lead Created {lead.first_name} {lead.last_name}"
                    data = {'notification_type': 'new_lead', 'redirect_url': f'/sales/lead_verification/{lead.id}'}

                    fcm_token = get_receptionist_user.fcm_token

                    Notifications.objects.create(notification_id=f"lead-{lead.id}-{get_receptionist_user.id}", user_id=get_receptionist_user,created=timezone.now(), notification_message=body, notification_url=f'/sales/lead_verification/{lead.id}')

                    send_push_notification(fcm_token, title, body, data) 
                # else: 
                #     # follow_up_1 = NotificationMeta.objects.create(task=task,name=f"Follow Up",time_interval=24)
                #     # SITE_HEAD = Users.objects.filter(groups__name="SITE_HEAD")
                #     # site_head_ids = SITE_HEAD.values_list('id', flat=True)
                #     # # print('follow_up_1:', follow_up_1)
                #     # follow_up_1.users.set(site_head_ids)# site head CHANGE

                #     # follow_up_2 = NotificationMeta.objects.create(task=task,name=f"Follow Up",time_interval=48)
                #     # VICE_PRESIDENT = Group.objects.get(name="VICE_PRESIDENT")
                #     # follow_up_2.groups.set([VICE_PRESIDENT])

                #     # follow_up_3 = NotificationMeta.objects.create(task=task,name=f"Follow Up",time_interval=168)
                #     # PROMOTER = Group.objects.get(name="PROMOTER")
                #     # follow_up_3.groups.set([PROMOTER])
                #     # RECEPTIONISTS = Users.objects.filter(groups__name="RECEPTIONIST")
                #     #receptionist_ids = RECEPTIONISTS.values_list('id', flat=True)
                #     for user in RECEPTIONISTS:
                #         msg = f'New Lead created {lead.first_name} {lead.last_name}'
                #         Notifications.objects.create(notification_id=f"task-{task.id}-{user.id}", user_id=user,created=timezone.now(), notification_message=msg, notification_url=f'/sales/my_visit/lead_details/{lead.id}')
                #     # task.notification_meta.set([follow_up_1,follow_up_2,follow_up_3])
                #     task.current_notification_meta = follow_up_1
                #     task.started = True
                #     task.started_at = timezone.now()
                #     task.save()
            elif user.groups.filter(name__in=["INQUIRY_FORM"]).exists():
                workflow=lead.workflow.all().first()
                workflow.current_stage=1
                workflow.save()
                # print('workflow:', workflow)
                presale_stage = Stage.objects.filter(workflow = workflow, completed=False).order_by('order').first()
                # print('presale_stage:', presale_stage)
                presale_stage.completed = True
                presale_stage.completed_at = timezone.now()
                presale_stage.save()
            else:
                is_cce = user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists()
                if is_cce or assigned_to_flag:
                    print('-----here---------',assigned_to_flag, is_cce)
                    state = get_object_or_404(State, label='Accept')
                    first_stage = lead.workflow.get().stages.first()
                    followup_time = timezone.now() + timedelta(hours=48)
                    followup_time_ist = followup_time.astimezone(timezone.pytz.timezone('Asia/Kolkata'))

                    # follow up 48hrs later
                    data=   {
                                "stage":first_stage,
                                "name": "Follow Up",
                                "order":0,
                                "task_type": "appointment",
                                "workflow":lead.workflow.get(),
                                "appointment_with": f"{lead.first_name} {lead.last_name}",
                                "appointment_type": "telephonic",
                                "time": followup_time_ist,
                                "details":"Follow up call with lead",
                                "status": state,
                                "minimum_approvals_required": 0
                        }
                    task = Task.objects.create(**data)

                    if is_cce or assigned_to_flag:    
                        follow_up_1 = NotificationMeta.objects.create(task=task,name=f"Follow Up",time_interval=24)
                        # print('follow_up_1:', follow_up_1)
                        follow_up_1.users.set([assigned_to])

                        follow_up_2 = NotificationMeta.objects.create(task=task,name=f"Follow Up",time_interval=48)
                        VICE_PRESIDENT = Group.objects.get(name="VICE_PRESIDENT")
                        follow_up_2.groups.set([VICE_PRESIDENT])

                        follow_up_3 = NotificationMeta.objects.create(task=task,name=f"Follow Up",time_interval=168)
                        PROMOTER = Group.objects.get(name="PROMOTER")
                        follow_up_3.groups.set([PROMOTER])

                        # task.notification_meta.set([follow_up_1,follow_up_2,follow_up_3])
                        task.current_notification_meta = follow_up_1
                        task.started = True
                        task.started_at = timezone.now()
                        task.save()

                    # TODO - notification
                    # group_users = Users.objects.filter(groups__name__in=['SITE_HEAD', 'VICE_PRESIDENT'])
                    # specific_users = Users.objects.filter(id__in=[assigned_to.id])
                    # all_users = list(group_users.values_list('id', flat=True)) + [user.id for user in specific_users]
                    # print('all_users:', all_users)
                    # task.notification_recipients += all_users
                    stage = first_stage
                    max_order_dict = stage.tasks.aggregate(Max('order'))
                    max_order_yet = max_order_dict.get('order__max', None)
                    if max_order_yet:
                        task.order = max_order_yet+1
                    else:
                        task.order = 0
                    print('follow up task:', vars(task))
                    #Enable task.save()
                    task.save()
                
                # # Send push notification Lead Create
                # title = "Lead Created"
                # body = f"New Lead created {lead.first_name} {lead.last_name}."
                # data = {'notification_type': 'lead_created', 'redirect_url': f'/pre_sales/all_leads/lead_details/{lead.id}'}
                
                # # Fetch the FCM tokens associated with the VP
                # get_vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                # vp_user = Users.objects.get(id=get_vp_user.id)
                # vp_user_fcm_token = vp_user.fcm_token
                # send_push_notification(vp_user_fcm_token, title, body, data)

            error = False
            message = 'Lead and LeadRequirement created successfully.'
            body = serializer.data
            return ResponseHandler(error,message,body,status.HTTP_201_CREATED)

        else:
            error = True
            message = serializer.errors
            body = None
            return ResponseHandler(error,message,body,status.HTTP_400_BAD_REQUEST)


        #return self.create(request, *args, **kwargs)


class LeadDetailsByPhone(APIView):
    def get(self, request):
        primary_phone_no = request.GET.get('primary_phone_no')
        try:
            lead = Lead.objects.filter(primary_phone_no=primary_phone_no).order_by('-id').first()
            serializer = LeadSerializer(lead)
            return ResponseHandler(False,'Lead retrieved successfully',serializer.data, 200)
        except Lead.DoesNotExist:
            return ResponseHandler(True, 'Lead not found', None, 404)

class UpdatesListApi(APIView):

    def get_object(self, lead_id):
        lead_instance =  Lead.objects.get(id=lead_id)
        obj, created = Updates.objects.get_or_create(lead=lead_instance)
        return obj

    def get(self, request, lead_id, *args, **kwargs):
        if not lead_id:
            return ResponseHandler(True, "Lead ID is missing", [], 400)
        
        if not Lead.objects.filter(id=lead_id).exists():
            return ResponseHandler(True, "Lead ID does not exist", [], 404)
        lead_instance =  Lead.objects.get(id=lead_id)
        instance = self.get_object(lead_id)
        module_param = self.request.query_params.get('module')
        if module_param == "activity":
            try:
                serializer = UpdatesSerializer(instance)
                return ResponseHandler(False, "Upadtes: ", serializer.data, 200)
            except Exception as e:
                return ResponseHandler(True, f"Error: {str(e)}", None, 500)

        now = datetime.now()
        duration=""
        lead_obj = Lead.objects.filter(pk=lead_id).first()
        booking_form_date = now.date()
        booking_form_time = now.time()
        welcome_call_date = now.date()
        welcome_call_time = now.time()
        welcome_mail_date = now.date()
        welcome_mail_time = now.time()
        demand_letter_date = now.date()
        demand_letter_time = now.time()
        stamp_duty_date = now.date()
        stamp_duty_time = now.time()
        registration_fee_date = now.date()
        registration_fee_time = now.time()

        if lead_obj:
            workflow = lead_obj.workflow.get()
            booking_form_task = workflow.tasks.filter(name='Collect Token', completed=True).first()
            if booking_form_task:
                booking_form_date = booking_form_task.completed_at.date()
                booking_form_time = booking_form_task.completed_at.time()      
            welcome_call_task = workflow.tasks.filter(name='Welcome Call', completed=True).first()
            if welcome_call_task:
                welcome_call_date = welcome_call_task.completed_at.date()
                welcome_call_time = welcome_call_task.completed_at.time()
                # add mcube logic

                # clicktocalldid = "8037898286"

                # welcome_call_queryset = LeadCallsMcube.objects.filter(
                #     Q(request_body__contains={"clicktocalldid": clicktocalldid}) &
                #     Q(call_type='OUTGOING') &
                #     Q(call_status='ANSWER') & 
                #     Q(lead_phone=lead_instance.primary_phone_no)
                # ).order_by('start_time').first()
                # if welcome_call_queryset.start_time and welcome_call_queryset.end_time:
                #     duration = welcome_call_queryset.end_time - welcome_call_queryset.start_time
                #     duration_minutes = int(duration.total_seconds() // 60)
                #     duration_seconds = int(duration.total_seconds() % 60)
                #     if duration_minutes != 0 and duration_seconds != 0:
                #         duration = f"{duration_minutes}min{duration_seconds}sec"
                #     elif duration_seconds != 0:
                #         duration = f"{duration_seconds}sec"

            welcome_mail_task = workflow.tasks.filter(name='Welcome Mail', completed=True).first()
            if welcome_mail_task:
                welcome_mail_date = welcome_mail_task.completed_at.date()
                welcome_mail_time = welcome_mail_task.completed_at.time()            
            demand_letter_task = workflow.tasks.filter(name='Demand Letter', completed=True).order_by('-time').last()
            if demand_letter_task:
                demand_letter_date = demand_letter_task.completed_at.date()
                demand_letter_time = demand_letter_task.completed_at.time()
            # Task: Stamp Duty
            stamp_duty_task = workflow.tasks.filter(name='Stamp Duty', completed=True).first()
            print(stamp_duty_task)
            if stamp_duty_task:
                stamp_duty_date = stamp_duty_task.completed_at.date()
                stamp_duty_time = stamp_duty_task.completed_at.time()


            # Task: Registration Fee
            registration_fee_task = workflow.tasks.filter(name='Registration Fees', completed=True).first()
            print(registration_fee_task)
            if registration_fee_task:
                registration_fee_date = registration_fee_task.completed_at.date()
                registration_fee_time = registration_fee_task.completed_at.time()    

        response_data = {
            "Token Paid": {
                "date": booking_form_date,
                "time": booking_form_time.strftime("%I:%M %p"),
                "message": "Token Amount Paid"
            },
            "Welcome Call": {
                "date": welcome_call_date,
                "time": welcome_call_time.strftime("%I:%M %p"),
                "message": "Welcome Call"
                # "duration": duration
            },
            "Welcome Email": {
                "date": welcome_mail_date,
                "time": welcome_mail_time.strftime("%I:%M %p"),
                "message": "Welcome Mail Sent"
            },
            "Demand Letter": {
                "date": demand_letter_date,
                "time": demand_letter_time.strftime("%I:%M %p"),
                "message": "Sent Demand Letter"
            },
            "Stamp Duty": {
                "date": stamp_duty_date,
                "time": stamp_duty_time.strftime("%I:%M %p"),
                "message": "Stamp Duty Paid"
            },
            "Registration Fees": {
                "date": registration_fee_date,
                "time": registration_fee_time.strftime("%I:%M %p"),
                "message": "Registration Fees Paid"
            }
        }

        if instance.welcome_call_status == "Not Done":
            response_data["Welcome Call"] = None
        if instance.welcome_email_status == "Not Sent":
            response_data["Welcome Email"] = None
        if instance.demand_letter_status == "Not Sent":
            response_data["Demand Letter"] = None

        stamp_duty_tasks_not_completed = workflow.tasks.filter(name='Stamp Duty', completed=False).first() 
        if stamp_duty_tasks_not_completed:
            response_data["Stamp Duty"] = None 
        registeration_fee_tasks_not_completed = workflow.tasks.filter(name='Registration Fees', completed=False).first()
        if registeration_fee_tasks_not_completed:
            response_data["Registration Fees"] = None    
        
        return ResponseHandler(False, "Upadtes: ", response_data, 200)

  
class BulkLeadUploadView(generics.ListCreateAPIView):
    queryset = Lead.objects.all()
    serializer_class = LeadBulkuploadSerializer
    parser_classes = (MultiPartParser,)
    permission_classes = (IsAuthenticated,)

    MANDATORY_COLUMNS = [
        'purpose', 'funding', 'area', 'configuration',
        'first_name', 'last_name', 'primary_phone_no'
    ]

    @bulk_group_access
    def create(self, request, *args, **kwargs):
        file_uploaded = request.FILES.get('file_uploaded',None)
        content_type = file_uploaded.content_type if file_uploaded is not None else None 
        leads_created = 0
        error_rows = {}
        first_error_index = None 
        source, created = Source.objects.get_or_create(name="Bulk Upload", defaults={'source_id': "0001"})
        if content_type and content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            #print(response)
            try:
                # Create a temporary file to save the uploaded Excel file
                with NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
                    for chunk in file_uploaded.chunks():
                        temp_file.write(chunk)

                # Read the Excel file using pandas
                excel_data = pd.ExcelFile(temp_file.name)
                df = pd.read_excel(excel_data)
                #print(df)

                for index, row in df.iterrows():

                    row = row.where(pd.notna(row), None)
                
                    if any(pd.isna(row[self.MANDATORY_COLUMNS])):
                        error_rows[index] = "Mandatory fields are missing in the row"
                        if first_error_index is None:
                            first_error_index = index
                        continue

                    lead_requirement_data = {
                        'purpose': row['purpose'],
                        'funding': row['funding'],
                        'configuration': row['configuration'],
                        'budget_min': row['budget_min'],
                        'budget_max': row['budget_max'],
                        'area': row['area'],
                    }

                    lead_data = {
                        "lead_requirement": lead_requirement_data,
                        'first_name': row['first_name'],
                        'last_name': row['last_name'],
                        'primary_phone_no': row['primary_phone_no'],
                        'primary_email': row['primary_email'],
                        'secondary_phone_no': row['secondary_phone_no'],
                        'secondary_email': row['secondary_email'] if not pd.isna(row['secondary_email']) else None,
                        'gender': row['gender'] ,
                        'occupation': row['occupation'],
                        'source': source.id,
                        'address': row['address'],
                        'city': row['city'],
                        'state': row['state'],
                        'pincode': row['pincode'],
                    }

                    lead_serializer = LeadBulkuploadSerializer(data=lead_data)
                    if not lead_serializer.is_valid():
                        error_rows[index] = lead_serializer.errors
                        if first_error_index is None:
                            first_error_index = index 

                    #print("error_rows: ", error_rows)
                    # If there are no errors, create leads
                if not error_rows:
                    for index, row in df.iterrows():
                            
                        row = row.where(pd.notna(row), None)

                        lead_data = {
                            "lead_requirement": lead_requirement_data,
                            'first_name': row['first_name'],
                            'last_name': row['last_name'],
                            'primary_phone_no': row['primary_phone_no'],
                            'primary_email': row['primary_email'],
                            'secondary_phone_no': row['secondary_phone_no'],
                            'secondary_email': row['secondary_email'] if not pd.isna(row['secondary_email']) else None,
                            'gender': row['gender'],
                            'occupation': row['occupation'],
                            'source': source.id,
                            'address': row['address'],
                            'city': row['city'],
                            'state': row['state'],
                            'pincode': row['pincode'],
                        }

                        lead_serializer = LeadBulkuploadSerializer(data=lead_data)
                        if lead_serializer.is_valid():
                            existing_lead = Lead.objects.filter(
                                primary_phone_no=row['primary_phone_no'],
                                primary_email=row['primary_email'],
                            ).first()

                            if not existing_lead:
                                lead = lead_serializer.save(creator=self.request.user, created_by =self.request.user.name) 
                                #lead_serializer.save()
                                leads_created += 1
                                definition=WorkflowDefinition.objects.filter(organization=lead.organization, workflow_type='sales').last()
                                assigned_to = self.request.user  
                                workflow_data = {                     
                                        "lead": lead.id, 
                                        "definition": definition.id,
                                        "name": definition.name,
                                        "workflow_type": definition.workflow_type,
                                        "assigned_to": assigned_to.id if assigned_to else None,
                                        "organization": lead.organization.id if lead.organization else None,
                                    }


                                # print("worfkow data is", workflow_data)
                                workflow_ser = WorkflowBulkUploadCreateSerializer(data=workflow_data) # 3
                                workflow_ser.is_valid(raise_exception=True)
                                workflow_ser.save() # 4 

                                # state = get_object_or_404(State, label='Accept')
                                # first_stage = lead.workflow.get().stages.first()
                                # # follow up 48hrs later
                                # data=   {
                                #             "stage":first_stage,
                                #             "name": "Follow Up",
                                #             "order":0,
                                #             "task_type": "appointment",
                                #             "workflow":lead.workflow.get(),
                                #             "appointment_with": f"{lead.first_name} {lead.last_name}",
                                #             "appointment_type": "telephonic",
                                #             "time": timezone.now() + timedelta(hours=48),
                                #             "details":"Follow up call with lead",
                                #             "status": state
                                #     }
                                # task = Task.objects.create(**data)
                                # # TODO - notification
                                # # group_users = Users.objects.filter(groups__name__in=['SITE_HEAD', 'VICE_PRESIDENT'])
                                # # specific_users = Users.objects.filter(id__in=[assigned_to.id])
                                # # all_users = list(group_users.values_list('id', flat=True)) + [user.id for user in specific_users]
                                # # print('all_users:', all_users)
                                # # task.notification_recipients += all_users
                                # stage = first_stage
                                # max_order_dict = stage.tasks.aggregate(Max('order'))
                                # max_order_yet = max_order_dict.get('order__max', None)
                                # if max_order_yet:
                                #     task.order = max_order_yet+1
                                # else:
                                #     task.order = 0
                                # print('follow up task:', vars(task))


                excel_data.close()
                    # You can now work with the 'excel_data' object, which contains the Excel file content.

                # Don't forget to remove the temporary file when you're done with it
                os.remove(temp_file.name)

                if error_rows:
                    first_error_message = error_rows.get(first_error_index, "Unknown error")
                    return Response(
                        {
                            "error": True,
                            "message": f"First error at row {first_error_index}",
                            #"message": f"{leads_created} leads created with errors. First error at row {first_error_index}: {first_error_message}",
                            "leads_created": leads_created,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    return Response(
                        {"error": False, "message": f"{leads_created} leads created successfully"},
                        status=status.HTTP_201_CREATED,
                    )
                #response = "POST API and you have uploaded an Excel file"
                #return Response({"error": True, "message": "Excel file found","body":response}, status=status.HTTP_404_NOT_FOUND)
            #except Exception as e:
                #response = "Error: {}".format(str(e))
                #return Response({"error": True, "message": "Excel file not found","body":response}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return Response({"error": True, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                         
        elif content_type and content_type == 'text/csv':
            try:
                csv_data = pd.read_csv(file_uploaded)

                for index, row in csv_data.iterrows():
                    row = row.where(pd.notna(row), None)

                    if any(pd.isna(row[self.MANDATORY_COLUMNS])):
                        error_rows[index] = "Mandatory fields are missing in the row"
                        if first_error_index is None:
                            first_error_index = index
                        continue

                    lead_requirement_data = {
                        'purpose': row['purpose'],
                        'funding': row['funding'],
                        'configuration': row['configuration'],
                        'budget_min': row['budget_min'],
                        'budget_max': row['budget_max'],
                        'area': row['area'],
                    }

                    lead_data = {
                        "lead_requirement": lead_requirement_data,
                        'first_name': row['first_name'],
                        'last_name': row['last_name'],
                        'primary_phone_no': row['primary_phone_no'],
                        'primary_email': row['primary_email'],
                        'secondary_phone_no': row['secondary_phone_no'],
                        'secondary_email': row['secondary_email'] if not pd.isna(row['secondary_email']) else None,
                        'gender': row['gender'],
                        'occupation': row['occupation'],
                        'source': source.id,
                        'address': row['address'],
                        'city': row['city'],
                        'state': row['state'],
                        'pincode': row['pincode'],
                    }

                    lead_serializer = LeadBulkuploadSerializer(data=lead_data)
                    if not lead_serializer.is_valid():
                        error_rows[index] = lead_serializer.errors
                        if first_error_index is None:
                            first_error_index = index

                    if not error_rows:
                        for index, row in csv_data.iterrows():
                            row = row.where(pd.notna(row), None)

                            lead_data = {
                                "lead_requirement": lead_requirement_data,
                                'first_name': row['first_name'],
                                'last_name': row['last_name'],
                                'primary_phone_no': row['primary_phone_no'],
                                'primary_email': row['primary_email'],
                                'secondary_phone_no': row['secondary_phone_no'],
                                'secondary_email': row['secondary_email'] if not pd.isna(row['secondary_email']) else None,
                                'gender': row['gender'],
                                'occupation': row['occupation'],
                                'source': source.id,
                                'address': row['address'],
                                'city': row['city'],
                                'state': row['state'],
                                'pincode': row['pincode'],
                            }

                            lead_serializer = LeadBulkuploadSerializer(data=lead_data)
                            if lead_serializer.is_valid():
                                existing_lead = Lead.objects.filter(
                                    primary_phone_no=row['primary_phone_no'],
                                    primary_email=row['primary_email'],
                                ).first()

                                if not existing_lead:
                                    lead = lead_serializer.save(creator=self.request.user, created_by =self.request.user.name) 
                                    #lead_serializer.save()
                                    leads_created += 1
                                    definition=WorkflowDefinition.objects.filter(organization=lead.organization, workflow_type='sales').last()
                                    assigned_to = self.request.user  
                                    workflow_data = {                     
                                            "lead": lead.id, 
                                            "definition": definition.id,
                                            "name": definition.name,
                                            "workflow_type": definition.workflow_type,
                                            "assigned_to": assigned_to.id if assigned_to else None,
                                            "organization": lead.organization.id if lead.organization else None,
                                        }


                                    # print("worfkow data is", workflow_data)
                                    workflow_ser = WorkflowBulkUploadCreateSerializer(data=workflow_data) # 3
                                    workflow_ser.is_valid(raise_exception=True)
                                    workflow_ser.save() # 4                                    
                    
                                    # state = get_object_or_404(State, label='Accept')
                                    # first_stage = lead.workflow.get().stages.first()
                                    # # follow up 48hrs later
                                    # data=   {
                                    #             "stage":first_stage,
                                    #             "name": "Follow Up",
                                    #             "order":0,
                                    #             "task_type": "appointment",
                                    #             "workflow":lead.workflow.get(),
                                    #             "appointment_with": f"{lead.first_name} {lead.last_name}",
                                    #             "appointment_type": "telephonic",
                                    #             "time": timezone.now() + timedelta(hours=48),
                                    #             "details":"Follow up call with lead",
                                    #             "status": state
                                    #     }
                                    # task = Task.objects.create(**data)
                                    # # TODO - notification
                                    # # group_users = Users.objects.filter(groups__name__in=['SITE_HEAD', 'VICE_PRESIDENT'])
                                    # # specific_users = Users.objects.filter(id__in=[assigned_to.id])
                                    # # all_users = list(group_users.values_list('id', flat=True)) + [user.id for user in specific_users]
                                    # # print('all_users:', all_users)
                                    # # task.notification_recipients += all_users
                                    # stage = first_stage
                                    # max_order_dict = stage.tasks.aggregate(Max('order'))
                                    # max_order_yet = max_order_dict.get('order__max', None)
                                    # if max_order_yet:
                                    #     task.order = max_order_yet+1
                                    # else:
                                    #     task.order = 0
                                    # print('follow up task:', vars(task))


                    if error_rows:
                        first_error_message = error_rows.get(first_error_index, "Unknown error")
                        return Response(
                            {
                                "error": True,
                                "message": f"First error at row {first_error_index}",
                                #"message": f"{leads_created} leads created with errors. First error at row {first_error_index}: {first_error_message}",
                                "leads_created": leads_created,
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    else:
                        return Response(
                            {"error": False, "message": f"{leads_created} leads created successfully"},
                            status=status.HTTP_201_CREATED,
                        )
                        

            except Exception as e:
                return Response({"error": True, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        else:
            return Response({"error": True, "message": f"File type not supported {content_type}", "body": None},
                            status=status.HTTP_400_BAD_REQUEST)

# class BulkChannelPartnerUploadView(generics.ListCreateAPIView):
#     queryset = ChannelPartner.objects.all()
#     serializer_class = ChannelPartnerUploadSerializer
#     parser_classes = (MultiPartParser,)
#     permission_classes = (IsAuthenticated,)

#     MANDATORY_COLUMNS = [ 'full_name', 'primary_phone_no', 'firm', 'primary_email','address','pin_code']

#     @check_group_access(required_groups=['ADMIN','PROMOTER','SOURCING_MANAGER', 'VICE_PRESIDENT', 'SITE_HEAD'])
#     def create(self, request, *args, **kwargs):
#         file_uploaded = request.FILES.get('file_uploaded', None)
#         content_type = file_uploaded.content_type if file_uploaded is not None else None 
#         cps_created = 0
#         error_rows = {}
#         first_error_index = None 
        
#         if content_type and content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
    
#             try:
#                 with NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
#                     for chunk in file_uploaded.chunks():
#                         temp_file.write(chunk)
    
#                 excel_data = pd.ExcelFile(temp_file.name)
#                 df = pd.read_excel(excel_data)
    
#                 for index, row in df.iterrows():
#                     row = row.where(pd.notna(row), None)
                    
#                     if any(pd.isna(row[self.MANDATORY_COLUMNS])):
#                         error_rows[index] = "Mandatory fields are missing in the row"
#                         if first_error_index is None:
#                             first_error_index = index
#                         continue
                    
#                     try:
#                         meetings_data = json.loads(row.get('meeting_data', '[]'))
#                         print('meetings_data:', meetings_data)
#                     except json.JSONDecodeError:
#                         error_rows[index] = "Invalid JSON format in meeting_data column"
#                         if first_error_index is None:
#                             first_error_index = index
#                         continue
                    
#                     cp_data = {
#                         'full_name': row['full_name'],
#                         'primary_phone_no': row['primary_phone_no'],
#                         'primary_email': row['primary_email'],
#                         'firm': row['firm'],
#                         'address': row['address'],
#                         'pin_code': row['pin_code'],
#                         'meetings': meetings_data
#                     }
    
#                     cp_serializer = ChannelPartnerUploadSerializer(data=cp_data)
                    
#                     if not cp_serializer.is_valid():
#                         error_rows[index] = cp_serializer.errors
#                         if first_error_index is None:
#                             first_error_index = index 
    
#                 if not error_rows:
#                     for index, row in df.iterrows():
#                         row = row.where(pd.notna(row), None)
    
#                         meetings_data = json.loads(row.get('meeting_data', '[]'))
        
#                         cp_data = {
#                             'full_name': row['full_name'],
#                             'primary_phone_no': row['primary_phone_no'],
#                             'primary_email': row['primary_email'],
#                             'firm': row['firm'],
#                             'address': row['address'],
#                             'pin_code': row['pin_code'],
#                             'meetings': meetings_data
#                         }
    
#                         cp_serializer = ChannelPartnerUploadSerializer(data=cp_data)
                        
#                         if cp_serializer.is_valid():
#                             existing_cp = ChannelPartner.objects.filter(
#                                 primary_phone_no=row['primary_phone_no'],
#                                 firm=row['firm'],
#                             ).first()
    
#                             if not existing_cp:
#                                 cp = cp_serializer.save(creator=self.request.user)
#                                 cps_created += 1
    
#                 excel_data.close()
#                 os.remove(temp_file.name)
    
#                 if error_rows:
#                     first_error_message = error_rows.get(first_error_index, "Unknown error")
#                     return Response(
#                         {
#                             "error": True,
#                             "message": f"First error at row {first_error_index}: {first_error_message}",
#                             "cps_created": cps_created,
#                         },
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )
#                 else:
#                     return Response(
#                         {"error": False, "message": f"{cps_created} Channel Partners created successfully"},
#                         status=status.HTTP_201_CREATED,
#                     )
            
#             except Exception as e:
#                 return Response({"error": True, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
#         elif content_type and content_type == 'text/csv':
#             try:
#                 csv_data = pd.read_csv(file_uploaded)
    
#                 for index, row in csv_data.iterrows():
#                     row = row.where(pd.notna(row), None)
                    
#                     if any(pd.isna(row[self.MANDATORY_COLUMNS])):
#                         error_rows[index] = "Mandatory fields are missing in the row"
#                         if first_error_index is None:
#                             first_error_index = index
#                         continue
    
#                     try:
#                         meetings_data = json.loads(row.get('meeting_data', '[]'))
#                     except json.JSONDecodeError:
#                         error_rows[index] = "Invalid JSON format in meeting_data column"
#                         if first_error_index is None:
#                             first_error_index is index
#                         continue
                    
#                     cp_data = {
#                         'full_name': row['full_name'],
#                         'primary_phone_no': row['primary_phone_no'],
#                         'primary_email': row['primary_email'],
#                         'firm': row['firm'],
#                         'address': row['address'],
#                         'pin_code': row['pin_code'],
#                         'meetings': meetings_data
#                     }
    
#                     cp_serializer = ChannelPartnerUploadSerializer(data=cp_data)
                    
#                     if not cp_serializer.is_valid():
#                         error_rows[index] = cp_serializer.errors
#                         if first_error_index is None:
#                             first_error_index = index 
    
#                 if not error_rows:
#                     for index, row in csv_data.iterrows():
#                         row = row.where(pd.notna(row), None)
    
#                         meetings_data = json.loads(row.get('meeting_data', '[]'))
    
#                         cp_data = {
#                             'full_name': row['full_name'],
#                             'primary_phone_no': row['primary_phone_no'],
#                             'primary_email': row['primary_email'],
#                             'firm': row['firm'],
#                             'address': row['address'],
#                             'pin_code': row['pin_code'],
#                             'meetings': meetings_data
#                         }
    
#                         cp_serializer = ChannelPartnerUploadSerializer(data=cp_data)
                        
#                         if cp_serializer.is_valid():
#                             existing_cp = ChannelPartner.objects.filter(
#                                 primary_phone_no=row['primary_phone_no'],
#                                 firm=row['firm'],
#                             ).first()
    
#                             if not existing_cp:
#                                 cp_serializer.save(creator=self.request.user) 
#                                 cps_created += 1
    
#                 if error_rows:
#                     first_error_message = error_rows.get(first_error_index, "Unknown error")
#                     return Response(
#                         {
#                             "error": True,
#                             "message": f"First error at row {first_error_index}: {first_error_message}",
#                             "cps_created": cps_created,
#                         },
#                         status=status.HTTP_400_BAD_REQUEST,
#                     )
#                 else:
#                     return Response(
#                         {"error": False, "message": f"{cps_created} Channel Partners created successfully"},
#                         status=status.HTTP_201_CREATED,
#                     )
    
#             except Exception as e:
#                 return Response({"error": True, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
#         else:
#             return Response({"error": True, "message": f"File type not supported {content_type}", "body": None},
#                             status=status.HTTP_400_BAD_REQUEST)

class BulkChannelPartnerUploadView(generics.ListCreateAPIView):
    queryset = ChannelPartner.objects.all()
    serializer_class = ChannelPartnerUploadSerializer
    parser_classes = (MultiPartParser,)
    permission_classes = (IsAuthenticated,)

    MANDATORY_COLUMNS = ['primary_phone_no', 'firm']

    @check_group_access(required_groups=['ADMIN', 'PROMOTER', 'SOURCING_MANAGER', 'VICE_PRESIDENT', 'SITE_HEAD'])
    def create(self, request, *args, **kwargs):
        file_uploaded = request.FILES.get('file_uploaded', None)
        content_type = file_uploaded.content_type if file_uploaded is not None else None
        cps_created = 0
        error_rows = {}
        first_error_index = None
        
        if content_type and content_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            try:
                with NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
                    for chunk in file_uploaded.chunks():
                        temp_file.write(chunk)

                excel_data = pd.ExcelFile(temp_file.name)
                df = pd.read_excel(excel_data)

                for index, row in df.iterrows():
                    row = row.where(pd.notna(row), None)

                    if any(pd.isna(row[self.MANDATORY_COLUMNS])):
                        error_rows[index] = "Mandatory fields are missing in the row"
                        if first_error_index is None:
                            first_error_index = index
                        continue

                    try:
                        meetings_data = json.loads(row.get('meeting_data', '[]'))
                        # Convert date from string if necessary
                        if 'date' in row and row['date']:
                            row['date'] = pd.to_datetime(row['date']).date()
                    except json.JSONDecodeError:
                        error_rows[index] = "Invalid JSON format in meeting_data column"
                        if first_error_index is None:
                            first_error_index = index
                        continue

                    cp_data = {
                        'full_name': row.get('full_name', None),
                        'primary_phone_no': str(row.get('primary_phone_no', None))[:10],
                        'secondary_phone_no': row.get('secondary_phone_no', None),
                        'primary_email': row.get('primary_email', None),
                        #  'secondary_email': row.get('secondary_email', None),
                        'firm': row.get('firm', None),
                        'pan_no': row.get('pan_no', None),
                        'gstin_number': row.get('gstin_number', None),
                        'location': row.get('location', None),
                        'address': row.get('address', None),
                        'pin_code': str(row.get('pin_code', None))[:6],
                        'created_on': row.get('created_on', None),
                        'rera_id': row.get('rera_id', None),
                        'channel_partner_status': row.get('channel_partner_status', 'New'),
                        'category': row.get('category', None),
                        'type_of_cp': row.get('type_of_cp', None),
                        'bank_name': row.get('bank_name', None),
                        'bank_account_number': row.get('bank_account_number', None),
                        'bank_account_holder_name': row.get('bank_account_holder_name', None),
                        'ifsc_code': row.get('ifsc_code', None),
                        'brokerage_category': row.get('brokerage_category', None),
                        'gst_certificate': row.get('gst_certificate', None),
                        'pan_card': row.get('pan_card', None),
                        'rera_certificate': row.get('rera_certificate', None),
                        'business_card': row.get('business_card', None),
                        'meetings': meetings_data 
                    }

                    cp_serializer = ChannelPartnerUploadSerializer(data=cp_data)

                    if not cp_serializer.is_valid():
                        error_rows[index] = cp_serializer.errors
                        if first_error_index is None:
                            first_error_index = index

                if not error_rows:
                    for index, row in df.iterrows():
                        row = row.where(pd.notna(row), None)

                        meetings_data = json.loads(row.get('meeting_data', '[]'))
                        # Convert date from string if necessary
                        if 'date' in row and row['date']:
                            row['date'] = pd.to_datetime(row['date']).date()

                        cp_data = {
                            'full_name': row.get('full_name', None),
                            'primary_phone_no': str(row.get('primary_phone_no', None))[:10],
                            'secondary_phone_no': row.get('secondary_phone_no', None),
                            'primary_email': row.get('primary_email', None),
                            # 'secondary_email': row.get('secondary_email', None),
                            'firm': row.get('firm', None),
                            'pan_no': row.get('pan_no', None),
                            'gstin_number': row.get('gstin_number', None),
                            'location': row.get('location', None),
                            'address': row.get('address', None),
                            'pin_code': str(row.get('pin_code', None))[:6],
                            'created_on': row.get('created_on', None),
                            'rera_id': row.get('rera_id', None),
                            'channel_partner_status': row.get('channel_partner_status', 'New'),
                            'category': row.get('category', None),
                            'type_of_cp': row.get('type_of_cp', None),
                            'bank_name': row.get('bank_name', None),
                            'bank_account_number': row.get('bank_account_number', None),
                            'bank_account_holder_name': row.get('bank_account_holder_name', None),
                            'ifsc_code': row.get('ifsc_code', None),
                            'brokerage_category': row.get('brokerage_category', None),
                            'gst_certificate': row.get('gst_certificate', None),
                            'pan_card': row.get('pan_card', None),
                            'rera_certificate': row.get('rera_certificate', None),
                            'business_card': row.get('business_card', None),
                            'meetings': meetings_data 
                        }
                        
                        cp_serializer = ChannelPartnerUploadSerializer(data=cp_data)

                        if cp_serializer.is_valid():
                            existing_cp = ChannelPartner.objects.filter(
                                primary_phone_no=row['primary_phone_no'],
                                firm=row['firm'],
                            ).first()

                            if not existing_cp:
                                cp = cp_serializer.save(creator=self.request.user)
                                cps_created += 1

                excel_data.close()
                os.remove(temp_file.name)

                if error_rows:
                    first_error_message = error_rows.get(first_error_index, "Unknown error")
                    return Response(
                        {
                            "error": True,
                            "message": f"First error at row {first_error_index}: {first_error_message}",
                            "cps_created": cps_created,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    return Response(
                        {"error": False, "message": f"{cps_created} Channel Partners created successfully"},
                        status=status.HTTP_201_CREATED,
                    )

            except Exception as e:
                return Response({"error": True, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        elif content_type and content_type == 'text/csv':
            try:
                csv_data = pd.read_csv(file_uploaded)

                for index, row in csv_data.iterrows():
                    row = row.where(pd.notna(row), None)

                    if any(pd.isna(row[self.MANDATORY_COLUMNS])):
                        error_rows[index] = "Mandatory fields are missing in the row"
                        if first_error_index is None:
                            first_error_index = index
                        continue

                    try:
                        meetings_data = json.loads(row.get('meeting_data', '[]'))
                        # Convert date from string if necessary
                        if 'date' in row and row['date']:
                            row['date'] = pd.to_datetime(row['date']).date()
                    except json.JSONDecodeError:
                        error_rows[index] = "Invalid JSON format in meeting_data column"
                        if first_error_index is None:
                            first_error_index = index
                        continue

                    cp_data = {
                        'full_name': row.get('full_name', None),
                        'primary_phone_no': str(row.get('primary_phone_no', None))[:10],
                        'secondary_phone_no': row.get('secondary_phone_no', None),
                        'primary_email': row.get('primary_email', None),
                        #  'secondary_email': row.get('secondary_email', None),
                        'firm': row.get('firm', None),
                        'pan_no': row.get('pan_no', None),
                        'gstin_number': row.get('gstin_number', None),
                        'location': row.get('location', None),
                        'address': row.get('address', None),
                        'pin_code': str(row.get('pin_code', None))[:6],
                        'created_on': row.get('created_on', None),
                        'rera_id': row.get('rera_id', None),
                        'channel_partner_status': row.get('channel_partner_status', 'New'),
                        'category': row.get('category', None),
                        'type_of_cp': row.get('type_of_cp', None),
                        'bank_name': row.get('bank_name', None),
                        'bank_account_number': row.get('bank_account_number', None),
                        'bank_account_holder_name': row.get('bank_account_holder_name', None),
                        'ifsc_code': row.get('ifsc_code', None),
                        'brokerage_category': row.get('brokerage_category', None),
                        'gst_certificate': row.get('gst_certificate', None),
                        'pan_card': row.get('pan_card', None),
                        'rera_certificate': row.get('rera_certificate', None),
                        'business_card': row.get('business_card', None),
                        'meetings': meetings_data 
                    }

                    cp_serializer = ChannelPartnerUploadSerializer(data=cp_data)

                    if not cp_serializer.is_valid():
                        error_rows[index] = cp_serializer.errors
                        if first_error_index is None:
                            first_error_index = index

                if not error_rows:
                    for index, row in csv_data.iterrows():
                        row = row.where(pd.notna(row), None)

                        meetings_data = json.loads(row.get('meeting_data', '[]'))
                        # Convert date from string if necessary
                        if 'date' in row and row['date']:
                            row['date'] = pd.to_datetime(row['date']).date()

                        cp_data = {
                            'full_name': row.get('full_name', None),
                            'primary_phone_no': str(row.get('primary_phone_no', None))[:10],
                            'secondary_phone_no': row.get('secondary_phone_no', None),
                            'primary_email': row.get('primary_email', None),
                            # 'secondary_email': row.get('secondary_email', None),
                            'firm': row.get('firm', None),
                            'pan_no': row.get('pan_no', None),
                            'gstin_number': row.get('gstin_number', None),
                            'location': row.get('location', None),
                            'address': row.get('address', None),
                            'pin_code': str(row.get('pin_code', None))[:6],
                            'created_on': row.get('created_on', None),
                            'rera_id': row.get('rera_id', None),
                            'channel_partner_status': row.get('channel_partner_status', 'New'),
                            'category': row.get('category', None),
                            'type_of_cp': row.get('type_of_cp', None),
                            'bank_name': row.get('bank_name', None),
                            'bank_account_number': row.get('bank_account_number', None),
                            'bank_account_holder_name': row.get('bank_account_holder_name', None),
                            'ifsc_code': row.get('ifsc_code', None),
                            'brokerage_category': row.get('brokerage_category', None),
                            'gst_certificate': row.get('gst_certificate', None),
                            'pan_card': row.get('pan_card', None),
                            'rera_certificate': row.get('rera_certificate', None),
                            'business_card': row.get('business_card', None),
                            'meetings': meetings_data 
                        }
                       
                        cp_serializer = ChannelPartnerUploadSerializer(data=cp_data)

                        if cp_serializer.is_valid():
                            existing_cp = ChannelPartner.objects.filter(
                                primary_phone_no=row['primary_phone_no'],
                                firm=row['firm'],
                            ).first()

                            if not existing_cp:
                                cp_serializer.save(creator=self.request.user)
                                cps_created += 1

                if error_rows:
                    first_error_message = error_rows.get(first_error_index, "Unknown error")
                    return Response(
                        {
                            "error": True,
                            "message": f"First error at row {first_error_index}: {first_error_message}",
                            "cps_created": cps_created,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                else:
                    return Response(
                        {"error": False, "message": f"{cps_created} Channel Partners created successfully"},
                        status=status.HTTP_201_CREATED,
                    )

            except Exception as e:
                return Response({"error": True, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        else:
            return Response({"error": True, "message": f"File type not supported {content_type}", "body": None},
                            status=status.HTTP_400_BAD_REQUEST)


import requests
import pandas as pd
import pdfkit
# class DownloadLeadsView(generics.GenericAPIView):
#     queryset = Lead.objects.all()
#     serializer_class = LeadSerializer
#     permission_classes = (IsAuthenticated,)

#     @swagger_auto_schema(
#     #operation_summary = ""
#     operation_description="Download Leads Information in form of excel",
#     responses={200: 'OK'},
#         )
#     @restrict_access
#     def get(self, request, *args, **kwargs):
#         # Get user preference for file format (excel or pdf)
#         #print(request.query_params.get('fileformat', None))
#         #headers={'Authorization': 'token 0bed7b07d44e1e5c41508eb41cc33144376d9e37'}
#         #get_leads_url = "http://127.0.0.1:8000/api/leads/?site_visit=True&module=PRESALES"  # Replace with the actual URL
#         #responses = requests.get(get_leads_url, headers=headers)
#         #print(responses)
#         #print(responses.json())
#         #data1 = responses.json().get('results', [])
#         #print(data1)
#         #data1 = responses.json().get('body', {})
#         #data = data1.get('results', [])
#         #print(data1)
#         #df_test = pd.DataFrame(data)
#         #BASE_DIR1 = Path(__file__).resolve().parent.parent
#         #MEDIA_URL1 = '/media/'
#         #MEDIA_ROOT1 = os.path.join(BASE_DIR1, 'media')
#         #excel_file_path1 = os.path.join(MEDIA_ROOT1,'leadsexportedtest3.xlsx')
#         #print("excel_file_path1: ",excel_file_path1)
#         #df_test.to_excel(excel_file_path1, index=False)
#         #pdf_file_path1 = os.path.join(MEDIA_ROOT1,'pdf_file3.html')
#         #df_test.to_html(pdf_file_path1, index=False)
#         #pdf_output_path1 = os.path.join(MEDIA_ROOT1,'pdf_file3.pdf')
#         #config = pdfkit.configuration(wkhtmltopdf='C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')
#         #pdfkit.from_file(pdf_file_path, pdf_output_path, configuration=config)
#         #pdfkit.from_file(pdf_file_path1, pdf_output_path1, configuration=config)
#         #print(pdf_file_path1,"C:\Users\nithi\enso-backend\apps\media\leadsexportedtest.pdf")
#         #pdfkit.from_file(pdf_file_path, "C:\Users\nithi\enso-backend\media\leadsexportedtest.pdf")


#         file_format = request.GET.get('fileformat', None)  # Default to Excel
#         #print(file_format)
#         #leads = responses.json()
#         leads = self.get_queryset()

#         #print(self.request.user.role)
#         #if self.request.user.role == 'ADMIN':
#         if file_format == 'excel':
#                 # Generate Excel file
#             excel_data = []
#             for lead in leads:
#                 excel_data.append({
#                     'Lead Id': lead.id,
#                     'Lead Name': str(lead.first_name) + " " + str(lead.last_name),
#                     'Created_on'  : lead.created_on.date(), 
#                     'Created By' : lead.creator,                    
#                     'Phone Number': lead.primary_phone_no,
#                     'Source Id': lead.source,
#                     'Lead Status': lead.lead_status,
#                     '': str(lead.lead_requirement.possession_from) + " to " + str(lead.lead_requirement.possession_to),
#                     'Next Follow Up': ''
#                     #'Secondary Phone No':lead.secondary_phone_no,
#                     #'Primary Email': lead.primary_email,
#                     #'Secondary Email': lead.secondary_email,
#                     #'Gender': lead.gender,
#                     #'Address': lead.address,
#                     #'City': lead.city,
#                     #'State': lead.state,
#                     #'Pincode': lead.pincode,
#                     #'Occupation': lead.occupation,
#                     #'No of family': lead.no_of_family,
#                     #'followers': lead.followers,
#                     #'purpose': lead.lead_requirement.purpose,
#                     #'budget_min': lead.lead_requirement.budget_min,
#                     #'budget_max': lead.lead_requirement.budget_max,
#                     #'project': lead.lead_requirement.project,
#                     #'funding': lead.lead_requirement.funding,
#                     #'possession_from': lead.lead_requirement.possession_from,
#                     #'possession_to': lead.lead_requirement.possession_to,
#                     #'area_min': lead.lead_requirement.area_min,
#                     #'area_max': lead.lead_requirement.area_max,
#                     #'configuration': lead.lead_requirement.configuration,
#                     #'bathroom': lead.lead_requirement.bathroom
#                 })

#             excel_df = pd.DataFrame(excel_data)
#             BASE_DIR = Path(__file__).resolve().parent.parent
#             MEDIA_URL = '/media/'
#             MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
#             excel_file_path = os.path.join(MEDIA_ROOT,'leadsexported.xlsx')
#             excel_writer = pd.ExcelWriter(excel_file_path, engine='xlsxwriter', mode='w')
#             excel_df.to_excel(excel_writer, sheet_name='Leads', index=False)
#             excel_writer.close()

#             return Response({"error": False, "message": "Excel file saved successfully"})
            
#         elif file_format == 'pdf':

#             BASE_DIR = Path(__file__).resolve().parent.parent
#             MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
#             pdf_file_path = os.path.join(MEDIA_ROOT,'leadsexported.pdf')
#             #save_path = "/path/to/save/leadsexported.pdf"

#             # Check if the PDF file already exists at the specified location
#             if os.path.exists(pdf_file_path):
#                 # If it exists, remove the existing PDF file
#                 os.remove(pdf_file_path)
#             # Generate PDF content
#             pdf_data = []
#             for lead in leads:
#                 pdf_data.append([
#                     lead.id,
#                     str(lead.first_name) + " " + str(lead.last_name),
#                     lead.created_on.date(),
#                     lead.creator,
#                     lead.primary_phone_no,
#                     lead.source,
#                     lead.lead_status,
#                     "",
#                     #lead.tenure,
#                     #str(lead.lead_requirement.possession_from) + " to " + str(lead.lead_requirement.possession_to),
#                     "",
#                 ])
#             column_headers = [
#                     'Lead Id',
#                     'Lead Name',
#                     'Created_on',
#                     'Created By',
#                     'Phone Number',
#                     'Source Id', 
#                     'Lead Status',
#                     'Tenure',
#                     'Next Follow Up',                 

#             ]
#             # Create a temporary PDF file
#             pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
#             # Create the PDF document with adjusted page size (landscape) and wider column widths
#             doc = SimpleDocTemplate(pdf_file, pagesize=(792, 612))  # 792x612 points is landscape letter size

#             # Calculate the width of each column
#             num_columns = len(column_headers)
#             column_width = 792 / num_columns  # Divide the page width by the number of columns

#             # Set the width of each column
#             col_widths = [column_width] * num_columns

#             # Generate the PDF content
#             pdf_data.insert(0, column_headers)  # Insert column headers at the beginning

#             # Create the table
#             table = Table(pdf_data, colWidths=col_widths, repeatRows=1)

#             # Style the table 
#             style = TableStyle([
#                 ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
#                 ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
#                 ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#                 ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#                 ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#                 ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
#                 ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
#             ])

#             table.setStyle(style)

#             # Build the PDF document with the table
#             doc.build([table])

#             # Close the PDF file
#             pdf_file.close()

#             # Move the generated PDF to the specified location
#             os.rename(pdf_file.name, pdf_file_path)            
                
#             return Response({"error": False, "message": "PDF file saved successfully"})

class ExportLeadsView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]


    def calculate_next_follow_up(self, lead):
            workflow = lead.workflow.get()
            followup_tasks = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
            if followup_tasks:
                return followup_tasks.time.date()
            return None
    
    def filter_leads(self,queryset, query_params):
        status_param = query_params.get('lead_status')
        if status_param is not None:
            status_param = status_param.split(',')
            queryset = queryset.filter(lead_status__in=status_param)

        purpose_param = query_params.get('purpose', None)
        if purpose_param is not None:
            queryset = queryset.filter(lead_requirement__purpose=purpose_param)

        configuration_param = query_params.get('configuration', None)
        if configuration_param is not None:
            queryset = queryset.filter(lead_requirement__configuration=configuration_param)

        funding_param = query_params.get('funding', None)
        if funding_param is not None:
            queryset = queryset.filter(lead_requirement__funding=funding_param)

        budget_min_param = query_params.get('budget_min', None)
        if budget_min_param is not None:
            queryset = queryset.filter(lead_requirement__budget_min__lte=budget_min_param)

        budget_max_param = query_params.get('budget_max', None)
        if budget_max_param is not None:
            queryset = queryset.filter(lead_requirement__budget_max__gte=budget_max_param)

        date_range_param = query_params.get('date_range', None)
        start_date_param = query_params.get('start_date', None)
        end_date_param = query_params.get('end_date', None)

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
        elif date_range_param == 'custom_range' and start_date_param and end_date_param:
            start_date = datetime.strptime(start_date_param, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_param, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            queryset = queryset.filter(created_on__gte=start_date, created_on__lte=end_date)

        return queryset
    
    def get_data(self, request):


        sort_order_param = self.request.GET.get('sort_order', None)
        sort_field_param = self.request.GET.get('sort_field', None)
        if sort_field_param and sort_field_param == 'created_on':
            order_by_param = '-created_on' if sort_order_param == 'desc' else 'created_on'
            queryset = Lead.objects.all().order_by(order_by_param)    
        else:
            queryset = Lead.objects.all().order_by('-created_on')

        module_param = request.GET.get('module', None)
        converted_param = bool(request.GET.get('converted_sales', None))
        site_visit_param = bool(request.GET.get('site_visit',None))
        created_by_param = request.GET.get('created_by',None)
        unallocated_param = bool(request.GET.get('unallocated_leads',None))
        site_visit_status_param = request.GET.get('site_visit_status',None)
        doc_status_param = request.GET.get('doc_status',None)
        closure_param =  bool(request.GET.get('closure',None))
        follow_ups_param =  bool(request.GET.get('follow_ups',None))
        follow_ups_filter_param =  request.GET.get('follow_ups_filter',None)
        crm_executive_param = request.GET.get('crm_executive',None)
        assigned_to_param = request.GET.get('assigned_to',None)
        data = []
        stage = Stage.objects.filter(name='PreSales').first()
        queryset = queryset.filter(workflow__current_stage=stage.order)
 
        if converted_param:
            filtered_queryset = Lead.objects.filter(converted_on__isnull=False).order_by('-id')
            sort_order_param = self.request.GET.get('sort_order', None)
            sort_field_param = self.request.GET.get('sort_field', None)
            if sort_field_param and sort_field_param == 'created_on':
                order_by_param = '-created_on' if sort_order_param == 'desc' else 'created_on'
                filtered_queryset = filtered_queryset.order_by(order_by_param)    
            else:
                filtered_queryset = filtered_queryset.order_by('-created_on')
            if self.request.user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                filtered_queryset = filtered_queryset.filter(followers__contains=[self.request.user.id])
            if assigned_to_param:
                assigned_to_param_list = map(int, assigned_to_param.split(','))
                filtered_queryset = filtered_queryset.filter(followers__overlap=assigned_to_param_list) 
            # Filter by 'created_by' if provided
            if created_by_param:
                created_by_param_list = map(int, created_by_param.split(','))
                filtered_queryset = filtered_queryset.filter(creator__in=created_by_param_list)
            search_query = request.GET.get('search', None)

            if search_query is not None:

                if search_query.isdigit():

                    filtered_queryset = filtered_queryset.filter(
                        Q(id__icontains=search_query) |
                        Q(primary_phone_no__icontains=search_query) |
                        Q(source__source_id__icontains=search_query)
                    )
                else:

                    filtered_queryset = filtered_queryset.filter(
                        Q(first_name__icontains=search_query) |
                        Q(last_name__icontains=search_query) |
                        Q(creator__name__icontains=search_query)
                    )  
            if filtered_queryset.exists():
                # Serialize the filtered queryset
                serializer = LeadConvertedSalesExport(filtered_queryset, many=True)
                #print(serializer.data)
                return serializer.data

            else:
                return data

        
        if unallocated_param:

            call_center_executive_group = Group.objects.get(name='CALL_CENTER_EXECUTIVE') 

            users_in_group = list(call_center_executive_group.user_set.values_list('id', flat=True))

            unallocated_queryset=queryset
            unallocated_queryset = unallocated_queryset.exclude(
                Q(followers__overlap=users_in_group) | Q(followers__isnull=True)
            )

            if created_by_param:
                created_by_param_list = map(int, created_by_param.split(','))
                unallocated_queryset = unallocated_queryset.filter(creator__in = created_by_param_list)

            if unallocated_queryset.exists():
                status_param = request.GET.get('lead_status')
                if status_param is not None:
                    status_param = status_param.split(',')
                    unallocated_queryset = unallocated_queryset.filter(lead_status__in=status_param)
                search_query = request.GET.get('search', None)

                if search_query is not None:

                    if search_query.isdigit():

                        unallocated_queryset = unallocated_queryset.filter(
                            Q(id__icontains=search_query) |
                            Q(primary_phone_no__icontains=search_query) |
                            Q(source__source_id__icontains=search_query)
                        )
                    else:
                        unallocated_queryset = unallocated_queryset.filter(
                            Q(first_name__icontains=search_query) |
                            Q(last_name__icontains=search_query) |
                            Q(creator__name__icontains=search_query)
                        )
                        # search_words = search_query.split()  
                        # temp_queryset = unallocated_queryset.filter(
                        #     Q(first_name__icontains=search_query) |
                        #     Q(last_name__icontains=search_query) |
                        #     Q(creator__name__icontains=search_query)
                        # ) 
    
                        # for word in search_words:
                        #     temp_queryset |= unallocated_queryset.filter(
                        #         Q(first_name__icontains=word) |
                        #         Q(last_name__icontains=word) |
                        #         Q(creator__name__icontains=word)
                        #     )
        
                        # unallocated_queryset = temp_queryset.distinct()

                if follow_ups_filter_param == 'All':
                    unallocated_queryset = [lead for lead in unallocated_queryset if self.calculate_next_follow_up(lead) is not None]
                elif follow_ups_filter_param == 'Today':
                    unallocated_queryset = [lead for lead in unallocated_queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date()]
                elif follow_ups_filter_param == 'Tomorrow':
                    unallocated_queryset = [lead for lead in unallocated_queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date() + timedelta(days=1)]
                elif follow_ups_filter_param == 'Missed':
                    unallocated_queryset = [lead for lead in unallocated_queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) < timezone.now().date()]
                elif follow_ups_filter_param == 'Next_7_Days':
                    unallocated_queryset = [lead for lead in unallocated_queryset if (self.calculate_next_follow_up(lead) is not None) and timezone.now().date() <= self.calculate_next_follow_up(lead) <= timezone.now().date() + timedelta(days=7)] 
    
                serializer = LeadUnallocatedExport(unallocated_queryset, many=True)
                data = serializer.data    
                #serializer = self.get_serializer(unallocated_queryset, many=True)
                return data
            else:
                return data    

        if site_visit_param:

            search_query = request.GET.get('search')
            
            if search_query is not None:
                
                if search_query.isdigit():

                    queryset = queryset.filter(
                        Q(id__icontains=search_query) |
                        Q(primary_phone_no__icontains=search_query) |
                        Q(source__source_id__icontains=search_query)
                    )
                else:
                    search_words = search_query.split()  
                    queryset = queryset.filter(
                        Q(first_name__icontains=search_query) |
                        Q(last_name__icontains=search_query) |
                        Q(creator__name__icontains=search_query)
                    ) 

            if created_by_param:
                created_by_param_list = map(int, created_by_param.split(','))
                queryset = queryset.filter(creator__in=created_by_param_list)
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
                    latest_site_visit_date = latest_site_visit.visit_date.strftime('%Y-%m-%d')
                else:
                    latest_site_visit_status = None
                    latest_site_visit_date = None

                workflow_instance = lead.workflow.get()
                assigned_to = workflow_instance.assigned_to if workflow_instance else None
                first_stage = workflow_instance.stages.all().order_by('order').first()

                if site_visit_status_param is None or latest_site_visit_status == site_visit_status_param:
                    lead_data = {
                        "id": lead.id,
                        "lead_name": f"{lead.first_name} {lead.last_name}",
                        "created_on": lead.created_on.date(),
                        "created_by": lead.creator.name if lead.creator else None ,
                        "assigned_to": first_stage.assigned_to.name if first_stage and first_stage.assigned_to else None ,
                        "phone_no": lead.primary_phone_no,
                        "source_id": f"{lead.source.source_id} - {lead.source.name}" if lead.source else None,
                        "scheduled_on": latest_site_visit_date,
                        "sv_status": latest_site_visit_status,
                    }
                    leads_with_latest_site_visit.append(lead_data)

            sort_order_param = self.request.GET.get('sort_order', None)
            sort_field_param = self.request.GET.get('sort_field', None)
            if sort_field_param and sort_field_param == 'scheduled_on':
                order_by_param = True if sort_order_param == 'desc' else False
                leads_with_latest_site_visit = sorted(leads_with_latest_site_visit, key=lambda x: x['scheduled_on'], reverse=order_by_param) 


            #search_query = request.GET.get('search', '').lower()

            #leads_with_latest_site_visit = [lead for lead in leads_with_latest_site_visit if search_query in lead["lead_name"].lower()]
            # if site_visit_status_param:
            #     leads_with_latest_site_visit = [lead for lead in leads_with_latest_site_visit if search_query in lead["lead_name"].lower()]

            if leads_with_latest_site_visit:
                data = leads_with_latest_site_visit
                return data
            else:
                return data 
            

            
        if follow_ups_param:
            queryset = self.filter_leads(queryset, self.request.query_params)    
            if assigned_to_param:
                assigned_to_param_list = map(int, assigned_to_param.split(','))
                queryset = queryset.filter(followers__overlap=assigned_to_param_list)    
            if created_by_param:
                created_by_param_list = map(int, created_by_param.split(','))
                queryset = queryset.filter(creator__in = created_by_param_list)
            if follow_ups_filter_param == 'All':
                queryset = [lead for lead in queryset if self.calculate_next_follow_up(lead) is not None]
            elif follow_ups_filter_param == 'Today':
                queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date()]
            elif follow_ups_filter_param == 'Tomorrow':
                queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date() + timedelta(days=1)]
            elif follow_ups_filter_param == 'Missed':
                queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) < timezone.now().date()]
            elif follow_ups_filter_param == 'Next_7_Days':
                queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and timezone.now().date() <= self.calculate_next_follow_up(lead) <= timezone.now().date() + timedelta(days=7)] 

            
            if queryset:
                serializer = LeadPreSalesExportSerializer(queryset, many=True)
                data = serializer.data
                #serializer = self.get_serializer(filtered_queryset, many=True)
                return data
            else:
                return data 
                    
        if created_by_param:
            created_by_param_list = map(int, created_by_param.split(','))
            filtered_queryset = queryset.filter(creator__in = created_by_param_list)
            if filtered_queryset.exists():
                serializer = LeadPreSalesExportSerializer(filtered_queryset, many=True)
                data = serializer.data
                return data
            else:
                return data 
            
        if assigned_to_param:
            assigned_to_param_list = map(int, assigned_to_param.split(',')) 
            queryset = queryset.filter(followers__overlap=assigned_to_param_list) 
            
        status_param = request.GET.get('lead_status')
        if status_param is not None:
            status_param = status_param.split(',')
            queryset = queryset.filter(lead_status__in=status_param)
        purpose_param = request.GET.get('purpose', None)
        if purpose_param is not None:
            queryset = queryset.filter(lead_requirement__purpose=purpose_param)
        configuration_param = request.GET.get('configuration', None)
        if configuration_param is not None:
            queryset = queryset.filter(lead_requirement__configuration=configuration_param)
        funding_param = request.GET.get('funding', None)
        if funding_param is not None:
            queryset = queryset.filter(lead_requirement__funding=funding_param)
        budget_min_param = request.GET.get('budget_min', None)
        if budget_min_param is not None:
            queryset = queryset.filter(lead_requirement__budget_min__lte=budget_min_param) 
        budget_max_param = request.GET.get('budget_max', None)
        if budget_max_param is not None:
            queryset = queryset.filter(lead_requirement__budget_max__gte=budget_max_param)

        date_range_param = request.GET.get('date_range', None)
        start_date_param = request.GET.get('start_date', None)
        end_date_param = request.GET.get('end_date', None)
        #print(date_range_param)
        if date_range_param == 'last_7_days':
            seven_days_ago = datetime.now() - timedelta(days=7)
            #print(datetime.now())
            #print(seven_days_ago)
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
        elif date_range_param == 'custom_range' and start_date_param and end_date_param:
            start_date = datetime.strptime(start_date_param, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_param, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            queryset = queryset.filter(created_on__gte=start_date,created_on__lte=end_date)


        if follow_ups_filter_param == 'All':
            queryset = [lead for lead in queryset if self.calculate_next_follow_up(lead) is not None]
        elif follow_ups_filter_param == 'Today':
            queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date()]
        elif follow_ups_filter_param == 'Tomorrow':
            queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) == timezone.now().date() + timedelta(days=1)]
        elif follow_ups_filter_param == 'Missed':
            queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and self.calculate_next_follow_up(lead) < timezone.now().date()]
        elif follow_ups_filter_param == 'Next_7_Days':
            queryset = [lead for lead in queryset if (self.calculate_next_follow_up(lead) is not None) and timezone.now().date() <= self.calculate_next_follow_up(lead) <= timezone.now().date() + timedelta(days=7)]    


        if queryset:
            serializer = LeadPreSalesExportSerializer(queryset, many=True)
            data = serializer.data
            return data
        else:
            return data


    def get_leads_data(self, request, *args, **kwargs):
        user = self.request.user  # Assuming your custom Users model is used for authentication
        user_token = user.auth_token  # Adjust this based on your custom Users model   
        # print("USER: ", user)
        # print("USER TOKEN: ", user_token)     
        headers = {'Authorization': f'token {user_token}'}
        base_url = "http://3.109.203.186/api/leads/"
        get_leads_url = f"{base_url}"
        #get_leads_url = "http://127.0.0.1:8000/api/leads/?module=PRESALES"
        try:
            #responses = requests.get(get_leads_url, headers=headers, params=self.request.query_params)
            #responses.raise_for_status()
            response = self.get_data(request=self.request)
            data1 = response
            return data1
            #data1 = responses.json().get('body', {})
            #return data1.get('results', [])
        except requests.RequestException as e:
            raise e

    def export_to_excel(self, data):
        try:
            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            excel_file_path = os.path.join(settings.MEDIA_ROOT, f'leadsexported_{timestamp}.xlsx')
            df.to_excel(excel_file_path, index=False)

            with open(excel_file_path, 'rb') as file:

                export_file = ExportFile(file=File(file))
                export_file.save()
            os.remove(excel_file_path)
            return export_file.file.url
        except Exception as e:
            raise e

    # def export_to_pdf(self, data):
    #     try:
    #         df = pd.DataFrame(data)
    #         timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    #         pdf_file_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.html')
    #         df.to_html(pdf_file_path, index=False)
    #         pdf_output_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.pdf')
    #         config = pdfkit.configuration(wkhtmltopdf='C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')
    #         pdfkit.from_file(pdf_file_path, pdf_output_path, configuration=config)
    #         return pdf_output_path
    #     except Exception as e:
    #         raise e
        
    def export_to_pdf(self,data):
        try:
            #print("Data: ", data)
            df = pd.DataFrame(data)

            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            pdf_file_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.html')
            df.to_html(pdf_file_path, index=False)
            pdf_output_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.pdf')
            

            #wkhtmltopdf_path = r'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'
            wkhtmltopdf_path = r'/usr/bin/wkhtmltopdf'
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            pdfkit.from_file(pdf_file_path, pdf_output_path, configuration=config)

            os.remove(pdf_file_path)

            with open(pdf_output_path, 'rb') as file:
                export_file = ExportFile(file=File(file))
                export_file.save()
            
            os.remove(pdf_output_path)
            return export_file.file.url
        
        except Exception as e:
            raise e
             
    @check_group_access(required_groups=['ADMIN','PROMOTER','VICE_PRESIDENT'])
    def retrieve(self, request, *args, **kwargs):
        try:

            data = self.get_leads_data(request=self.request)
            if data is None or not data:
                return ResponseHandler(True, "Error fetching leads data", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

            file_format = request.GET.get('fileformat', None)

            if file_format == 'pdf':
                print("Data: ", type(data))
                file_path = self.export_to_pdf(data)
                if file_path:
                    return ResponseHandler(False, "File saved successfully at:", file_path, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Error exporting to PDF", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

            else:
                file_path = self.export_to_excel(data)
                if file_path:
                    return ResponseHandler(False, "File saved successfully at:", file_path, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Error exporting to Excel", None, status.HTTP_500_INTERNAL_SERVER_ERROR)


        except Exception as e:
            return ResponseHandler(True, "Unexpected error: ", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)
  


class ExportPostSalesDataView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_data(self, request): 
        stage = Stage.objects.filter(name='PostSales').first()
        queryset = Lead.objects.filter(workflow__current_stage=stage.order)
        # Add additional filtering based on user groups, if necessary
        print("Queryset",queryset)
        return queryset
    

    # def get_leads_data(self, request, *args, **kwargs):
    #     user = self.request.user  # Assuming your custom Users model is used for authentication
    #     user_token = user.auth_token  # Adjust this based on your custom Users model   
    #     # print("USER: ", user)
    #     # print("USER TOKEN: ", user_token)     
    #     headers = {'Authorization': f'token {user_token}'}
    #     base_url = "http://3.109.203.186/api/leads/"
    #     get_leads_url = f"{base_url}"
    #     #get_leads_url = "http://127.0.0.1:8000/api/leads/?module=PRESALES"
    #     try:
    #         #responses = requests.get(get_leads_url, headers=headers, params=self.request.query_params)
    #         #responses.raise_for_status()
    #         response = self.get_data(request=self.request)
    #         data1 = response
    #         return data1
    #         #data1 = responses.json().get('body', {})
    #         #return data1.get('results', [])
    #     except requests.RequestException as e:
    #         raise e

    def get_leads_data(self, request):
        queryset = self.get_data(request)
        serialized_data = LeadPostSalesExportSerializer(queryset, many=True).data
        return serialized_data

    
    def export_to_excel(self, data):
        try:
            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            excel_file_path = os.path.join(settings.MEDIA_ROOT, f'leadsexported_{timestamp}.xlsx')
            df.to_excel(excel_file_path, index=False)

            with open(excel_file_path, 'rb') as file:

                export_file = ExportFile(file=File(file))
                export_file.save()
            os.remove(excel_file_path)
            return export_file.file.url
        except Exception as e:
            raise e

    def export_to_pdf(self,data):
        try:
            #print("Data: ", data)
            df = pd.DataFrame(data)

            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            pdf_file_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.html')
            df.to_html(pdf_file_path, index=False)
            pdf_output_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.pdf')
            

            #wkhtmltopdf_path = r'C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe'
            wkhtmltopdf_path = r'/usr/bin/wkhtmltopdf'
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            pdfkit.from_file(pdf_file_path, pdf_output_path, configuration=config)

            os.remove(pdf_file_path)

            with open(pdf_output_path, 'rb') as file:
                export_file = ExportFile(file=File(file))
                export_file.save()
            
            os.remove(pdf_output_path)
            return export_file.file.url
        
        except Exception as e:
            raise e

    @check_group_access(required_groups=['ADMIN','PROMOTER','VICE_PRESIDENT', "CRM_HEAD","ACCOUNTS_HEAD","CRM_EXECUTIVE"])
    def retrieve(self, request, *args, **kwargs):
        try:

            data = self.get_leads_data(request=self.request)
            if data is None or not data:
                return ResponseHandler(True, "Error fetching leads data", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

            file_format = request.GET.get('fileformat', None)

            if file_format == 'pdf':
                print("Data: ", type(data))
                file_path = self.export_to_pdf(data)
                if file_path:
                    return ResponseHandler(False, "File saved successfully at:", file_path, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Error exporting to PDF", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

            else:
                file_path = self.export_to_excel(data)
                if file_path:
                    return ResponseHandler(False, "File saved successfully at:", file_path, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Error exporting to Excel", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return ResponseHandler(True, "Unexpected error: ", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)
  

             


class ExportChannelPartnerView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def transform_data(channel_partners):
        data = []
        for cp in channel_partners:
            base_data = {
                "id": cp['id'],
                "full_name": cp['full_name'],
                "sourcing_manager": cp['sourcing_manager'],
                "firm": cp['firm'],
                "ph_number": cp['ph_number'],
                "rera_id": cp['rera_id'],
                "pan_no": cp['pan_no'],
                "cp_status": cp['cp_status'],
                "category": cp['category'],
                "type_of_cp": cp['type_of_cp'],
                "pin_code": cp['pin_code'],
                "address": cp['address'],
                "email": cp['email'],
            }

            if 'meetings' not in cp or not cp['meetings']:
                # Skip processing if there are no meetings
                data.append(base_data)
                continue
            # Filter out any invalid meetings (None or without date)
            valid_meetings = [m for m in cp['meetings'] if m and 'date' in m]
            # Sort meetings by 'date' in descending order
            sorted_meetings = sorted(valid_meetings, key=lambda m: m['date'], reverse=True)
            for i, meeting in enumerate(sorted_meetings):
                meeting_data = {
                    "meeting_no." : i+1,
                   # "meeting_id": meeting['id'],
                    "meeting_date": meeting['date'],
                    "meeting_location" :  meeting['location'],
                    "meeting_start_time": meeting['start_time'],
                    "meeting_end_time": meeting['end_time'],
                    "meeting_duration" : meeting['duration'],
                    "meeting_notes" :  meeting['notes']
                }
                if i == 0:
                    row_data = {**base_data, **meeting_data}
                    data.append(row_data)
                else:
                    row_data = {**dict.fromkeys(base_data.keys(), ""), **meeting_data}
                    data.append(row_data)
        return data

    def get_queryset(self):
        sort_order_param = self.request.GET.get('sort_order', None)
        sort_field_param = self.request.GET.get('sort_field', None)
        order_by_param = '-created_on'

        if sort_field_param == 'created_on':
            order_by_param = '-created_on' if sort_order_param == 'desc' else 'created_on'

            queryset = ChannelPartner.objects.all().order_by(order_by_param).prefetch_related('meetings')   
        else:
            queryset = ChannelPartner.objects.all().order_by('-created_on').prefetch_related('meetings')
        user = self.request.user

        if user.groups.filter(name__in=["ADMIN", "PROMOTER", "SITE_HEAD", "VICE_PRESIDENT"]).exists():
            return queryset

        if user.groups.filter(name="SOURCING_MANAGER").exists():
            queryset = queryset.filter(creator=user)
        else:
            queryset = ChannelPartner.objects.none()

        print("get_queryset :- ",queryset)
        return queryset 
    
    def get_data(self, request):
        data = []
        queryset = self.get_queryset()
        search_query = request.GET.get('search')
        module_param = request.GET.get('module', None)
        cp_status_param = request.GET.get('cp_status', None)
        sourcing_manager_param = request.GET.get('sourcing_manager', None)

        if cp_status_param:
            queryset = queryset.filter(channel_partner_status=cp_status_param)
        if sourcing_manager_param:
            queryset = queryset.filter(creator=sourcing_manager_param)

        if module_param == "incomplete_cp":
            incomplete_records = queryset.filter(
                Q(full_name__isnull=True) & Q(primary_email__isnull=True) & 
                Q(address__isnull=True) & Q(pin_code__isnull=True)
            ).exclude(firm__isnull=True, primary_phone_no__isnull=True)
            
            if search_query:
                if search_query.isdigit():
                    incomplete_records = incomplete_records.filter(
                        Q(id__icontains=search_query) | Q(primary_phone_no__icontains=search_query)
                    )
                else:
                    incomplete_records = incomplete_records.filter(firm__icontains=search_query)
            
            if incomplete_records.exists():
                serializer = ChannelPartnerIncompleteExportSerializer(incomplete_records, many=True)
                data = serializer.data
                print("data inside incomplete cps :- ", data)
                return data
            else:
                return []

        else:
            queryset = queryset.exclude(
                Q(full_name__isnull=True) | Q(primary_email__isnull=True) | 
                Q(address__isnull=True) | Q(pin_code__isnull=True) | 
                Q(firm__isnull=True) | Q(primary_phone_no__isnull=True)
            )
            
            if search_query:
                if search_query.isdigit():
                    queryset = queryset.filter(
                        Q(id__icontains=search_query) | Q(primary_phone_no__icontains=search_query)
                    )
                else:
                    search_words = search_query.split()
                    queryset = queryset.filter(
                        Q(full_name__icontains=search_query) | Q(firm__icontains=search_query)
                    )

            if queryset.exists():
                serializer = ChannelPartnerExportSerializer(queryset, many=True)
                data = serializer.data
                print("complete_cp_data :-", data)
                return data
            else:
                return []

    def get_cps_data(self, request, *args, **kwargs):
        try:
            print("inside cps")
            response = self.get_data(request)
            print("response:", response)
            transformed_data = self.transform_data(response)
            print("transformed_data: ", transformed_data)
            return transformed_data
        except requests.RequestException as e:
            raise e

    def export_to_excel(self, data):
        try:
            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            excel_file_path = os.path.join(settings.MEDIA_ROOT, f'cpsexported_{timestamp}.xlsx')
            df.to_excel(excel_file_path, index=False)

            with open(excel_file_path, 'rb') as file:
                export_file = ExportFile(file=File(file))
                export_file.save()
            os.remove(excel_file_path)
            return export_file.file.url
        except Exception as e:
            raise e

    def export_to_pdf(self, data):
        try:
            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            html_file_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.html')
            pdf_file_path = os.path.join(settings.MEDIA_ROOT, f'pdf_file_{timestamp}.pdf')

            html_content = df.to_html(index=False)
            styled_html_content = f"""
            <html>
            <head>
                <style>
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                    }}
                    th, td {{
                        border: 1px solid black;
                        padding: 4px;
                        text-align: left;
                        font-size: 10px;
                        word-wrap: break-word;
                    }}
                    th {{
                        background-color: #f2f2f2;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """

            with open(html_file_path, 'w') as f:
                f.write(styled_html_content)

            wkhtmltopdf_path = r'/usr/bin/wkhtmltopdf'
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            pdfkit.from_file(html_file_path, pdf_file_path, configuration=config)

            os.remove(html_file_path)

            with open(pdf_file_path, 'rb') as file:
                export_file = ExportFile(file=File(file))
                export_file.save()

            os.remove(pdf_file_path)

            return export_file.file.url
        except Exception as e:
            raise e

    @check_group_access(required_groups=['ADMIN', 'PROMOTER', 'SOURCING_MANAGER', 'SITE_HEAD', 'VICE_PRESIDENT'])
    def retrieve(self, request, *args, **kwargs):
        try:
            data = self.get_cps_data(request)
            print(f"retrieved_data:{data}")
            if not data:
                return ResponseHandler(True, "No Channel Partner data is Present", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

            file_format = request.GET.get('fileformat', None)
            if file_format == 'pdf':
                print("Data: ", type(data))
                file_path = self.export_to_pdf(data)
                if file_path:
                    return ResponseHandler(False, "File saved successfully at:", file_path, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Error exporting to PDF", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                file_path = self.export_to_excel(data)
                if file_path:
                    return ResponseHandler(False, "File saved successfully at:", file_path, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Error exporting to Excel", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            print(f"Exception in retrieve: {e}")
            return ResponseHandler(True, f"Error in exporting data: ", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

        
class LeadRetrieveUpdateDeleteAPIView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, generics.GenericAPIView):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer
    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
    #operation_summary = ""
    operation_description="Get Leads Information by passing LeadId",
    responses={200: 'OK'},
        )
    
    @check_access(required_permissions=["lead.view_lead"])    
    def get(self, request, *args, **kwargs):
        lead_id = self.kwargs.get('pk')  # Assuming your URL parameter is 'pk'

        try:
            instance = Lead.objects.get(pk=lead_id)
            serializer =  LeadPostSaleReterieveSerializer(instance)
            error  = False
            message = 'Lead retrieved successfully'
            body = serializer.data
            #status=status.HTTP_200_OK
            return ResponseHandler(error,message,body,status.HTTP_200_OK)
        except Lead.DoesNotExist:
            error = True
            message =  'Lead ID not found'
            body = None,
            #status=status.HTTP_200_OK
            return ResponseHandler(error, message, body, status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
    #operation_summary = ""
    operation_description="Update Leads Information by passing LeadId",
    responses={200: 'OK'},
        )

    @check_access(required_permissions=["lead.change_lead"])   
    def put(self, request, *args, **kwargs):
        lead_id = self.kwargs.get('pk')  # Assuming your URL parameter is 'pk'

        try:
            instance = Lead.objects.get(pk=lead_id)
            prev_lead_status = instance.lead_status
            #serializer = self.get_serializer(instance)
            #instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)

            if serializer.is_valid():
            # Perform the update
                serializer.save()
            #status=status.HTTP_200_OK
                
                # id lead_staus is changed then making follow up task as complete
                current_lead_status = serializer.data.get('lead_status')
                print('current_lead_status:', current_lead_status, prev_lead_status)
                if prev_lead_status != current_lead_status:
                    workflow = instance.workflow.get()
                    followup_task = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').last()
                    if followup_task:
                        followup_task.completed = True
                        followup_task.completed_at = timezone.now()
                        followup_task.save()
                return ResponseHandler(False , "Data Updated Successfully", serializer.data, status.HTTP_200_OK)
            else:
                return ResponseHandler(True , serializer.errors , None,status.HTTP_400_BAD_REQUEST)
                #return self.update(request, *args, **kwargs)
        except Lead.DoesNotExist:
            return ResponseHandler(True, "Lead Id not Found", None, status.HTTP_404_NOT_FOUND)


    @swagger_auto_schema(
    #operation_summary = ""
    operation_description="Delete Leads Information by passing LeadId",
    responses={200: 'OK'},
        )
    

    @check_access(required_permissions=["lead.delete_lead"]) 
    def delete(self, request, *args, **kwargs):
        lead_id = self.kwargs.get('pk')
        try:
            instance = Lead.objects.get(pk=lead_id)
            self.perform_destroy(instance)
            return ResponseHandler(False, 'Lead deleted successfully' , None, status.HTTP_204_NO_CONTENT)
        except Lead.DoesNotExist:
            return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND)
        #return JsonResponse({'message': 'Record is deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)



class ChannelPartnerCreateView(mixins.ListModelMixin,mixins.CreateModelMixin, generics.GenericAPIView):
    
    # serializer_class = ChannelPartnerSerializer
    serializer_class = ChannelPartnerSerializerFirmName
    permission_classes = (IsAuthenticated,)
    pagination_class = CustomLimitOffsetPagination

    # @staticmethod 
    # def get_brokerage_percentage(brokerage_category, booked_count):
    #     # Fetch the appropriate BrokerageDeal based on the booked_count
    #     print("inside",brokerage_category)
    #     print(brokerage_category.id)
    #     deal_ranges = BrokerageDeal.objects.filter(category=brokerage_category.id)
    #     print(deal_ranges)
    #     for deal in deal_ranges:
    #         range_start, range_end = map(int, deal.deal_range.split('-'))
    #         print(range_start,booked_count,range_end)
    #         if range_start <= booked_count <= range_end:
    #             return str(deal.percentage)
    #     return "3.00"

    def get_queryset(self):
        sort_order_param = self.request.GET.get('sort_order', None)
        sort_field_param = self.request.GET.get('sort_field', None)
        if sort_field_param and sort_field_param == 'created_on':
            order_by_param = '-created_on' if sort_order_param == 'desc' else 'created_on'
            queryset = ChannelPartner.objects.all().order_by(order_by_param)    
        else:
            queryset = ChannelPartner.objects.all().order_by('-created_on')
       
        user = self.request.user

        if user.groups.filter(name__in=["ADMIN","PROMOTER","SITE_HEAD","VICE_PRESIDENT"]).exists():
            return queryset

        if user.groups.filter(name="SOURCING_MANAGER").exists():
            queryset = queryset.filter(creator=user.id)
        else:
            queryset = ChannelPartner.objects.none()

        return queryset 

    @check_access(required_permissions=["lead.view_channelpartner"]) 
    def get(self, request, *args, **kwargs):


        #print(request.GET.get('lead_status'))
        queryset = self.get_queryset()
        print("queryset : ",queryset)

        search_query = request.GET.get('search')
        module_param = request.GET.get('module', None)
        cp_status_param = request.GET.get('cp_status', None)
        sourcing_manager_param = request.GET.get('sourcing_manager', None)
        status_param = request.GET.get('status',None)
        category_param = request.GET.get('category',None)
        if cp_status_param is not None:
            queryset = queryset.filter(channel_partner_status=cp_status_param)
        if sourcing_manager_param is not None:
            queryset = queryset.filter(creator=sourcing_manager_param)

        if status_param:
            three_months_ago = timezone.now() - timedelta(days=90)

            active_cps = ChannelPartner.objects.filter(
                Q(created_on__gte=three_months_ago) |  
                Q(lead__projectinventory__status="Booked", lead__projectinventory__booked_on__gte=three_months_ago)
            ).exclude(
                Q(full_name__isnull=True) & 
                Q(primary_email__isnull=True) & 
                Q(address__isnull=True) & 
                Q(pin_code__isnull=True)
            ).distinct()

            if status_param == "Active":
                queryset = queryset.filter(id__in=active_cps.values('id'))
            elif status_param == "Inactive":
                queryset = queryset.exclude(id__in=active_cps.values('id'))   

        if category_param:
            queryset = queryset.filter(brokerage_category__name__iexact=category_param)        
        

        if module_param == "incomplete_cp":

            incomplete_records = queryset.filter(Q(full_name__isnull=True)& Q(primary_email__isnull=True)& Q(address__isnull=True)& Q(pin_code__isnull=True)).exclude(firm__isnull=True, primary_phone_no__isnull=True)
            if search_query is not None:
                
                if search_query.isdigit():

                    incomplete_records = incomplete_records.filter(
                        Q(id__icontains=search_query) |
                        Q(primary_phone_no__icontains=search_query) 
                    )
                else:
                    incomplete_records = incomplete_records.filter(firm__icontains=search_query) 
            
            if incomplete_records:
                page = self.paginate_queryset(incomplete_records)
                serializer = self.get_serializer(page, many=True)
                data = self.get_paginated_response(serializer.data).data
                return ResponseHandler(False, 'Data retrieved successfully' , data, status.HTTP_200_OK)
            else:
                page = self.paginate_queryset(incomplete_records)
                dummy_data= self.get_paginated_response(page)
                return ResponseHandler(False, 'No data present' , dummy_data.data,status.HTTP_200_OK)
        else:

            queryset = queryset.exclude(
                Q(full_name__isnull=True) | 
                Q(primary_email__isnull=True) | 
                Q(address__isnull=True) | 
                Q(pin_code__isnull=True) | 
                Q(firm__isnull=True) | 
                Q(primary_phone_no__isnull=True)
            )

            if search_query is not None:
                
                if search_query.isdigit():

                    queryset = queryset.filter(
                        Q(id__icontains=search_query) |
                        Q(primary_phone_no__icontains=search_query) 
                    )
                else:
                    search_words = search_query.split()  
                    queryset = queryset.filter(
                        Q(full_name__icontains=search_query) | Q(firm__icontains=search_query)
                    ) 

            print(queryset)         
            
            if queryset:
                page = self.paginate_queryset(queryset)
                serializer = self.get_serializer(page, many=True)
                data = self.get_paginated_response(serializer.data).data
                return ResponseHandler(False, 'Data retrieved successfully' , data, status.HTTP_200_OK)
            else:
                page = self.paginate_queryset(queryset)
                dummy_data= self.get_paginated_response(page)
                return ResponseHandler(False, 'No data present' , dummy_data.data,status.HTTP_200_OK)


        


    check_access(required_permissions=["lead.add_channelpartner"]) 
    def post(self, request, *args, **kwargs):

        user = self.request.user
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            channel_partner = serializer.save(creator=self.request.user)
            # brokerage_category = channel_partner.brokerage_category
            # # brokerage_category = BrokerageCategory.objects.filter(id = brokerage_category_id).first()
            # print("brokerage category",brokerage_category.id)
            # # booked_count = ChannelPartner.objects.filter(
            # #     lead__projectinventory__status="Booked", id=channel_partner.id
            # # ).annotate(
            # #     booked_count=Count('lead__projectinventory')
            # # ).first().booked_count

            # booked_count =1

            # # Get the brokerage percentage
            # brokerage_percentage = self.get_brokerage_percentage(brokerage_category, booked_count)
            # print("brokerage_percenatge",brokerage_percentage) 
            # # Create a ChannelPartnerBrokerage entry
            # ChannelPartnerBrokerage.objects.create(
            #     channel_partner=channel_partner,
            #     brokerage_category=brokerage_category,
            #     brokerage_percentage=brokerage_percentage
            # )
            # return Response({"message": "ChannelPartner created successfully."}, status=status.HTTP_201_CREATED)
            return ResponseHandler(False, 'Channel Partner created successfully.' , serializer.data, status.HTTP_201_CREATED)
        # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return ResponseHandler(True, serializer.errors , None, status.HTTP_400_BAD_REQUEST)

class CheckCPuniqueness(APIView):
    serializer_class = ChannelPartnerSerializerFirmName
    permission_classes = (IsAuthenticated,)

    def post(self,request):
        phone_number = request.data.get('primary_phone_number')
        firm = request.data.get('firm')
        queryset1 = ChannelPartner.objects.filter(primary_phone_no=phone_number,firm__iexact=firm)
        queryset2= ChannelPartner.objects.filter(primary_phone_no=phone_number)
        queryset3= ChannelPartner.objects.filter(firm__iexact=firm)
        if queryset1.exists() or queryset2.exists() or queryset3.exists():
            return ResponseHandler(False, "Channel Partner is not unique" ,True, status.HTTP_200_OK)
        else :
            return ResponseHandler(False, "Channel Partner is unique" ,False, status.HTTP_200_OK)

class ChannelPartnerBrokerageView(APIView):
    
    def get(self, request, pk=None, *args, **kwargs):
        channel_partner_id = request.query_params.get('channel_partner', None)
    
        if channel_partner_id:
            # Fetch all ChannelPartnerBrokerage instances for the specific channel_partner
            brokerages = ChannelPartnerBrokerage.objects.filter(channel_partner_id=channel_partner_id)
            serializer = ChannelPartnerBrokerageSerializer(brokerages, many=True)
            return ResponseHandler(False, "Data retrieved", serializer.data, status.HTTP_200_OK)
        
        elif pk:
            # Get a specific ChannelPartnerBrokerage instance by pk
            try:
                brokerage = ChannelPartnerBrokerage.objects.get(pk=pk)
                serializer = ChannelPartnerBrokerageSerializer(brokerage)
                return ResponseHandler(False, "Data retrieved", serializer.data, status.HTTP_200_OK)
            except ChannelPartnerBrokerage.DoesNotExist:
                return ResponseHandler(True, "An error occurred", "Channel Partner Brokerage not found.", status.HTTP_404_NOT_FOUND)
        
        else:
            # List all ChannelPartnerBrokerage instances
            brokerages = ChannelPartnerBrokerage.objects.all()
            serializer = ChannelPartnerBrokerageSerializer(brokerages, many=True)
            return ResponseHandler(False, "All CP brokerage data", serializer.data, status=status.HTTP_200_OK)
        
    
    def post(self, request, *args, **kwargs):
        serializer = ChannelPartnerBrokerageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False,"Channel Partner Brokerage created successfully",None, status.HTTP_201_CREATED)
        return ResponseHandler(True,"An error occured",serializer.errors,status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, pk, *args, **kwargs):
        try:
            # Fetch the existing entry
            brokerage = ChannelPartnerBrokerage.objects.get(pk=pk)
            
            # Create a serializer instance with the existing brokerage and updated data
            serializer = ChannelPartnerBrokerageSerializer(brokerage, data=request.data)
            
            # Check if the serializer data is valid
            if serializer.is_valid():
                # Save the updated data to the existing entry
                serializer.save(updated_on=timezone.now())
                return ResponseHandler(False, "Channel Partner Brokerage updated successfully.", None, status.HTTP_200_OK)
            
            # Return validation errors if data is not valid
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
        
        except ChannelPartnerBrokerage.DoesNotExist:
            # Handle case where the entry does not exist
            return ResponseHandler(True, "Channel Partner Brokerage not found.", None, status.HTTP_404_NOT_FOUND)
        
    def delete(self, request, pk, *args, **kwargs):
        try:
            brokerage = ChannelPartnerBrokerage.objects.get(pk=pk)
            brokerage.delete()
            return ResponseHandler(False, "Channel Partner Brokerage deleted successfully.",None,status.HTTP_200_OK)
        except ChannelPartnerBrokerage.DoesNotExist:
            return ResponseHandler(True,"error" ,"Channel Partner Brokerage not found.", status.HTTP_404_NOT_FOUND)

        
# class ChannelPartnerUpdateView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, generics.GenericAPIView):
#     queryset = ChannelPartner.objects.all()
#     serializer_class = ChannelPartnerByIdSerializer
#     def perform_update(self, serializer):
#         instance = serializer.save()

#         aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
#         aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
#         aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
#         aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")           

#         s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_s3_region_name)

#         files = {
#             'gst_certificate': self.request.data.get('gst_certificate'),
#             'pan_card': self.request.data.get('pan_card'),
#             'rera_certificate': self.request.data.get('rera_certificate'),
#             'business_card': self.request.data.get('business_card'),
#         }

#         for key, file in files.items():
#             if file:
#                 try:
#                     s3.upload_fileobj(file,settings.AWS_STORAGE_BUCKET_NAME,f'{instance.id}/{file.name}')

#                 except Exception as e:
#                     return Response({"error": f"Error uploading {key}: {e}"}, status=status.HTTP_400_BAD_REQUEST)
#                 # Update the model instance with the new file key
#                 setattr(instance, key, f'{instance.id}/{file.name}')
#                 instance.save()

#     def delete(self, request, *args, **kwargs):
#         response = super().delete(request, *args, **kwargs)
#         if response.status_code == status.HTTP_204_NO_CONTENT:
#             # Delete files from S3 upon successful deletion of ChannelPartner instance
#             instance_id = kwargs.get('pk')
            
#             aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
#             aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
#             aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
#             aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")  

#             s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_s3_region_name)

#             try:
                
#                 for file_key in ['gst_certificate', 'pan_card', 'rera_certificate', 'business_card']:
#                     s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME,Key=f'{instance_id}/{file_key}')

#             except Exception as e:
#                 return Response({"error": f"Error deleting files from S3: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#         return response
    
#     @swagger_auto_schema(
#     #operation_summary = ""
#     operation_description="Get ChannelPartner Information by passing ChannelPartnerId",
#     responses={200: 'OK'},
#         )
    

#     @check_access(required_permissions=["lead.view_channelpartner"]) 
#     def get(self, request, *args, **kwargs):
#         channelpartner_id = self.kwargs.get('pk')  # Assuming your URL parameter is 'pk'

#         try:
#             instance = ChannelPartner.objects.get(pk=channelpartner_id)
#             serializer = self.get_serializer(instance)
#             return ResponseHandler(False, 'ChannelPartner retrieved successfully', serializer.data, status.HTTP_200_OK)
#         except ChannelPartner.DoesNotExist:
#             return ResponseHandler(True, 'ChannelPartner ID not found', None, status.HTTP_404_NOT_FOUND)

#     @swagger_auto_schema(
#     #operation_summary = ""
#     operation_description="Update ChannelPartner Information by passing ChannelPartnerId",
#     responses={200: 'OK'},
#         )
    

#     @check_access(required_permissions=["lead.change_channelpartner"]) 
#     def put(self, request, *args, **kwargs):
#         instance = self.get_object()
#         serializer = self.get_serializer(instance, data=request.data, partial=True)

#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False , 'Data updated successfully' , serializer.data,status.HTTP_200_OK)
#         else:
#             return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)

#     @swagger_auto_schema(
#     #operation_summary = ""
#     operation_description="Delete ChannelPartner Information by passing ChannelPartnerId",
#     responses={200: 'OK'},
#         )
    

#     @check_access(required_permissions=["lead.delete_channelpartner"]) 
#     def delete(self, request, *args, **kwargs):
#         channelpartner_id = self.kwargs.get('pk')
#         try:
#             instance = ChannelPartner.objects.get(pk=channelpartner_id)
#             self.perform_destroy(instance)
#             return ResponseHandler(False, 'ChannelPartner deleted successfully' , None,status.HTTP_204_NO_CONTENT)
#         except ChannelPartner.DoesNotExist:
#             return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND)

class ChannelPartnerUpdateView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, generics.GenericAPIView):
    queryset = ChannelPartner.objects.all()
    serializer_class = ChannelPartnerByIdSerializer

    def perform_brokerage_update(self,serializer):
        try:   
            channel_partner = serializer
            print("channel_partner",channel_partner)
            brokerage_category = channel_partner.brokerage_category
            # brokerage_category = BrokerageCategory.objects.filter(id = brokerage_category_id).first()
            print("brokerage category",brokerage_category.id)

            booked_count =1

            percentage = "3.00"
            deal_ranges = BrokerageDeal.objects.filter(category=brokerage_category.id)
            print(deal_ranges)
            for deal in deal_ranges:
                range_start, range_end = map(int, deal.deal_range.split('-'))
                print(range_start,booked_count,range_end)
                if range_start <= booked_count <= range_end:
                    percentage = str(deal.percentage)
            

            # Get the brokerage percentage
            brokerage_percentage = percentage
            print("brokerage_percenatge",brokerage_percentage) 
            # Create a ChannelPartnerBrokerage entry
            ChannelPartnerBrokerage.objects.create(
                channel_partner=channel_partner,
                brokerage_category=brokerage_category,
                brokerage_percentage=brokerage_percentage
            )
            channel_partner.brokerage_updated = True

            # Save the instance again to persist the change
            channel_partner.save()

            print("After saving, brokerage_updated:", channel_partner.brokerage_updated)
        except Exception as e:
        
                return Response({"error": f"Error coming in brokerage category adding"}, status=status.HTTP_400_BAD_REQUEST)     

    def perform_update(self, serializer):
        instance = serializer.save()

        print("instance",instance)

        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
        aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

        s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_s3_region_name)

        files = {
            'gst_certificate': self.request.data.get('gst_certificate'),
            'pan_card': self.request.data.get('pan_card'),
            'rera_certificate': self.request.data.get('rera_certificate'),
            'business_card': self.request.data.get('business_card'),
        }


        for key, file in files.items():
            if file:
                try:
                    # Upload each file to S3
                    print("file_name",file.name)
                    print("aws_storage_buket",aws_storage_bucket_name)
                    s3.upload_fileobj(file, aws_storage_bucket_name, f'{instance.id}/{file.name}')

                    # Update the model instance with the new file key
                    setattr(instance, key, f'{instance.id}/{file.name}')
                    instance.save()

                except Exception as e:
        
                    return Response({"error": f"Error uploading {key}: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        if response.status_code == status.HTTP_204_NO_CONTENT:
            # Delete files from S3 upon successful deletion of ChannelPartner instance
            instance_id = kwargs.get('pk')

            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
            aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

            s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_s3_region_name)

            try:
                for file_key in ['gst_certificate', 'pan_card', 'rera_certificate', 'business_card']:
                    s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=f'{instance_id}/{file_key}')

            except Exception as e:
                return Response({"error": f"Error deleting files from S3: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return response

    @swagger_auto_schema(
        operation_description="Get ChannelPartner Information by passing ChannelPartnerId",
        responses={200: 'OK'},
    )
    @check_access(required_permissions=["lead.view_channelpartner"]) 
    def get(self, request, *args, **kwargs):
        channelpartner_id = self.kwargs.get('pk')

        try:
            instance = ChannelPartner.objects.get(pk=channelpartner_id)
            serializer =  self.get_serializer(instance)
            return ResponseHandler(False, 'ChannelPartner retrieved successfully', serializer.data, status.HTTP_200_OK)
        except ChannelPartner.DoesNotExist:
            return ResponseHandler(True, 'ChannelPartner ID not found', None, status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        operation_description="Update ChannelPartner Information by passing ChannelPartnerId",
        responses={200: 'OK'},
    )
    @check_access(required_permissions=["lead.change_channelpartner"]) 
    def put(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            # Perform update (including file uploads)
            self.perform_update(serializer)

            if not instance.brokerage_updated:
                print("Brokerage not updated, performing update...")
                self.perform_brokerage_update(instance)
                print("after_upadted",instance)
                  
            return ResponseHandler(False , 'Data updated successfully' , serializer.data,status.HTTP_200_OK)
        else:
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)

    @swagger_auto_schema(
        operation_description="Delete ChannelPartner Information by passing ChannelPartnerId",
        responses={200: 'OK'},
    )
    @check_access(required_permissions=["lead.delete_channelpartner"]) 
    def delete(self, request, *args, **kwargs):
        channelpartner_id = self.kwargs.get('pk')
        try:
            instance = ChannelPartner.objects.get(pk=channelpartner_id)
            self.perform_destroy(instance)
            return ResponseHandler(False, 'ChannelPartner deleted successfully' , None,status.HTTP_204_NO_CONTENT)
        except ChannelPartner.DoesNotExist:
            return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND)
                
# edge case no duplicates , include all ids with starting
class CreateMeetingAPIView(mixins.ListModelMixin,mixins.CreateModelMixin,generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    def post(self, request, *args, **kwargs):

        user = self.request.user
        request.data['sourcing_manager'] = user.id  
        channel_partner_id = request.data.get('channel_partner')
        channel_partner_instance = ChannelPartner.objects.filter(id=channel_partner_id).first()
        
        if channel_partner_instance and channel_partner_instance.primary_phone_no is None or channel_partner_instance.firm is None:
            return ResponseHandler(True, "Firm and Mobile Number missing", None, status.HTTP_400_BAD_REQUEST)

        serializer = MeetingSerializer(data=request.data)
        try:
            if serializer.is_valid():
                serializer.save()
                return ResponseHandler(False, "Meeting created successfully", serializer.data, status.HTTP_201_CREATED)
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHandler(True, "An error occurred", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

# Default Brokerage Ladder related code
class BrokerageCategoryList(APIView):
    # To get brokerage ladder
    def get(self, request):
        categories = BrokerageCategory.objects.all()
        serializer = BrokerageCategorySerializer(categories, many=True)
        data = serializer.data
        filtered_data = [category for category in data if category['deals']]
        
        # response_data = {
        #     "error": False,
        #     "message": "Category data retrieved",
        #     "body": filtered_data
        # }
        return ResponseHandler(False,"Category data reterieved",filtered_data,status.HTTP_200_OK)
    # To add Brokerage Ladder
    def post(self, request):
        serializer = BrokerageCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False,"Category created successfully",serializer.data,status.HTTP_201_CREATED)
        return ResponseHandler(True,serializer.errors,None,status.HTTP_400_BAD_REQUEST)


class BrokerageCategoryDetail(APIView):
    def get_object(self, pk):
        try:
            return BrokerageCategory.objects.get(pk=pk)
            # return ResponseHandler(False,"Category data",category,status.HTTP_200_OK)
        except BrokerageCategory.DoesNotExist:
            raise NotFound("object not found")

    def get(self, request, pk):
        category = self.get_object(pk)
        serializer = BrokerageCategorySerializer(category)
        return ResponseHandler(False,"Category data obtained",serializer.data,status.HTTP_302_FOUND)

    def put(self, request, pk):
        category = self.get_object(pk)
        serializer = BrokerageCategorySerializer(category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False,"Category updated successfully",serializer.data,status.HTTP_200_OK)
        return ResponseHandler(True,"Error occured",serializer.errors,status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        category = self.get_object(pk)
        category.delete()
        return ResponseHandler(False,"Deleted successfully",None,status.HTTP_200_OK)

class BrokerageDealList(APIView):     
    def get(self, request):
        deals = BrokerageDeal.objects.all()
        serializer = BrokerageDealSerializer(deals, many=True)
        return ResponseHandler(False,"Data reterieved successfully",serializer.data,status.HTTP_302_FOUND)

    def post(self, request):
        serializer = BrokerageDealSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False,"Brokerage Deal created successfully",serializer.data,status.HTTP_201_CREATED)
        return ResponseHandler(True,"An error occured",serializer.errors,status.HTTP_400_BAD_REQUEST)
    
    def put(self, request):
        data = request.data
        if not isinstance(data, list):
            return ResponseHandler(True, "Expected a list of categories", None, status.HTTP_400_BAD_REQUEST)

        updated_categories = []
        for category_data in data:
            category_name = category_data.get('name')
            try:
                brokerage_category = BrokerageCategory.objects.get(name=category_name)
            except BrokerageCategory.DoesNotExist:
                return ResponseHandler(True, f"Category with name {category_name} does not exist", None, status.HTTP_400_BAD_REQUEST)

            for deal_data in category_data.get('deals', []):
                deal_id = deal_data.get('id')
                try:
                    deal = BrokerageDeal.objects.get(pk=deal_id, category=brokerage_category)
                except BrokerageDeal.DoesNotExist:
                    return ResponseHandler(True, f"Deal with id {deal_id} in category {category_name} does not exist", None, status.HTTP_400_BAD_REQUEST)

                deal_serializer = BrokerageDealSerializer(deal, data=deal_data, partial=True)
                if deal_serializer.is_valid():
                    deal_serializer.save()
                    updated_categories.append(deal_serializer.data)
                else:
                    return ResponseHandler(True, "Error", deal_serializer.errors, status.HTTP_400_BAD_REQUEST)
        
        return ResponseHandler(False, "Updated successfully", updated_categories, status.HTTP_202_ACCEPTED)
    

class BrokerageDealDetail(APIView):
    def get_object(self, pk):
        try:
            return BrokerageDeal.objects.get(pk=pk)
        except BrokerageDeal.DoesNotExist:
            return ResponseHandler(True,"An error occured",None,status.HTTP_400_BAD_REQUEST)

    def get(self, request, pk):
        deal = self.get_object(pk)
        serializer = BrokerageDealSerializer(deal)
        return ResponseHandler(False,"Data reterieved successfully",serializer.data,status.HTTP_200_OK)

    # def put(self, request, pk):
    #     deal = self.get_object(pk)
    #     serializer = BrokerageDealSerializer(deal, data=request.data)
    #     if serializer.is_valid():
    #         serializer.save()
    #         return ResponseHandler(False,"Updated successfully",serializer.data,status.HTTP_202_ACCEPTED)
    #     return ResponseHandler(True,"Error",serializer.errors,status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        deal = self.get_object(pk)
        deal.delete()
        return ResponseHandler(False,"Deleted succesfully",None,status.HTTP_204_NO_CONTENT)





class MeetingDetailAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    def get(self, request, meeting_id, *args, **kwargs):
        try:
            meeting = Meeting.objects.get(pk=meeting_id)
            serializer = MeetingSerializer(meeting)
            return ResponseHandler(False, "Meeting retrieved successfully", serializer.data, status.HTTP_200_OK)
        except Meeting.DoesNotExist:
            return ResponseHandler(True, "Meeting not found", None, status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHandler(True, "An error occurred", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, meeting_id, *args, **kwargs):
        try:
            meeting = Meeting.objects.get(pk=meeting_id)
            serializer = MeetingSerializer(meeting, data=request.data, partial = True)
            if serializer.is_valid():
                serializer.save()
                return ResponseHandler(False, "Meeting updated successfully", serializer.data, status.HTTP_200_OK)
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
        except Meeting.DoesNotExist:
            return ResponseHandler(True, "Meeting not found", None, status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHandler(True, "An error occurred", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, meeting_id, *args, **kwargs):
        try:
            meeting = Meeting.objects.get(pk=meeting_id)
            meeting.delete()
            return ResponseHandler(False, "Meeting deleted successfully", None, status.HTTP_204_NO_CONTENT)
        except Meeting.DoesNotExist:
            return ResponseHandler(True, "Meeting not found", None, status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHandler(True, "An error occurred", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MeetingDetailsbyId(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, generics.GenericAPIView):
    queryset = Meeting.objects.all()
    serializer_class = MeetingSerializer
    permission_classes = (IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        cp_id = self.kwargs.get('pk')
        
        try:
            instances = Meeting.objects.filter(channel_partner=cp_id).order_by('-id')
            serializer = self.get_serializer(instances, many=True)
            return ResponseHandler(False, 'Channel Partner retrieved successfully.', serializer.data, status.HTTP_200_OK)

        except ChannelPartner.DoesNotExist:
            return ResponseHandler(True, 'Channel Partner does not exist', None, status.HTTP_404_NOT_FOUND)            
        except Exception as e:
            return ResponseHandler( True, "Error: ",str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class LeadSearchAPIView(generics.ListAPIView):
    serializer_class = LeadSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        
        search_query = self.request.query_params.get('search', '')
        search_scope = self.request.GET.get("scope", "all")
        module_param = self.request.GET.get("module_param", "PRESALES")

        print(search_scope)

        queryset = Lead.objects.none()
        try:
 
            number_query = int(search_query)

            if search_scope in ["leads", "all"]:
                queryset = Lead.objects.filter(id__icontains=number_query)
            if search_scope in ["source", "all"]:
                source_queryset = Lead.objects.filter(source=number_query)
                queryset = queryset | source_queryset
            if search_scope in ["mobile", "all"]:
                mobile_users = Lead.objects.filter(primary_phone_no__icontains=number_query)
                queryset = queryset | mobile_users
            return queryset

        except ValueError:
            

            if search_scope in ["leads", "all"]:
                queryset = Lead.objects.filter(
                    Q(first_name__icontains=search_query) | Q(last_name__icontains=search_query)
                )
            
            if search_scope in ["executive", "all"]:
                matching_users = Users.objects.filter(name__icontains=search_query)

                if matching_users.exists():
                    
                    user_id = matching_users.first().id

                    user_leads = Lead.objects.filter(followers=user_id)

                    queryset = queryset | user_leads

        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())

            if not queryset.exists():
                return JsonResponse({'message': 'No matching results'}, status=404)

            module_param = self.request.GET.get("module_param")

            if module_param == "PRESALES":
                #queryset = queryset.filter(Q(sitevisit__isnull=True) )
                #| Q(sitevisit__visit_occurred=False) check pre
                serializer = LeadSerializer(queryset, many=True)

            elif module_param == "SALES":


                queryset = queryset.filter(sitevisit__isnull=False)
                queryset = queryset.annotate(
                    latest_site_visit_date=Max('sitevisit__visit_date'),
                    latest_site_visit_timeslot=Max('sitevisit__timeslot')
                )

                queryset = queryset.annotate(sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done")))

                queryset = queryset.annotate(sv_datetime=ExpressionWrapper(
                    Concat('latest_site_visit_date', Value(' '), 'latest_site_visit_timeslot'),
                    output_field=CharField()
                )
                )
            
                leads = list(queryset)
                for lead in leads:
                    try:
                        latest_site_visit = SiteVisit.objects.get(
                            lead=lead,
                            visit_date=lead.latest_site_visit_date,
                            timeslot=lead.latest_site_visit_timeslot
                        )
                        lead.sv_status = latest_site_visit.site_visit_status
                        lead.closing_manager=latest_site_visit.closing_manager.name if latest_site_visit.closing_manager else None
                        #print("closing manager ",lead.closing_manager)
                    except SiteVisit.DoesNotExist:
                        lead.sv_status = None


                paginator = CustomLimitOffsetPagination()
                page = paginator.paginate_queryset(leads, request)
                
                if page is not None:
                    serializer = LeadSalesSerializer(page, many=True)
                    return paginator.get_paginated_response(serializer.data)
                
                serializer = LeadSalesSerializer(leads, many=True)

            elif module_param == "POSTSALES":
                serializer = LeadSerializer(queryset, many=True)

                leads = queryset
                lead_data = []
                    

                for lead in leads:
                    crm_executive = None
                    for follower_id in lead.followers:
                        try:
                            follower = Users.objects.get(id=follower_id)

                            user_groups = follower.groups.all()
                            if user_groups.filter(name='CRM_EXECUTIVE').exists():
                                crm_executive = follower.name
                                break  
                        except Users.DoesNotExist:
                            pass

                    updates_data = None

                    if crm_executive is not None:
                        try:
                            updates_data = Updates.objects.values(
                                'welcome_call_status',
                                'welcome_email_status',
                                'demand_letter_status'
                            ).get(lead=lead)
                        except Updates.DoesNotExist:
                            Updates.objects.create(lead=lead)
                            updates_data = {
                                'welcome_call_status': 'Not Done',
                                'welcome_email_status': 'Not Done',
                                'demand_letter_status': 'Not Done',
                            }
                    print("updates_data: ",updates_data)        
                
                    welcome_call_status_filter = self.request.GET.get('welcome_call_status', None)
                    if welcome_call_status_filter is not None:
                        
                        if crm_executive is None or updates_data is None or updates_data['welcome_call_status'] != welcome_call_status_filter:
                            continue


                    welcome_email_status_filter = self.request.GET.get('welcome_email_status', None)
                    if welcome_email_status_filter is not None:

                        if crm_executive is None or updates_data is None or updates_data['welcome_email_status'] != welcome_email_status_filter:
                            continue


                    demand_letter_status_filter = self.request.GET.get('demand_letter_status', None)
                    if demand_letter_status_filter is not None:

                        if crm_executive is None or updates_data is None or updates_data['demand_letter_status'] != demand_letter_status_filter:
                            continue

                    lead_dict = {
                        'lead_id': lead.id,
                        'lead_name': f"{lead.first_name} {lead.last_name}",
                        'crm_executive': crm_executive,
                        'phone_no': lead.primary_phone_no,
                        'updates': updates_data,

                    }

                    lead_data.append(lead_dict)
                
                return ResponseHandler(False, "POST SALES DATA: ", lead_data, status.HTTP_200_OK)


            return JsonResponse(serializer.data, safe=False, status=200)
        except Exception as e:
            return JsonResponse({'message': 'Error: {}'.format(str(e))}, status=500)


class UsersList(generics.ListAPIView):
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name'] 
    def get_queryset(self):
        queryset = Users.objects.all()
        group_name = self.request.query_params.get('group_name', None)
        search_query = self.request.query_params.get('search', None)
        if group_name == "CLOSING_MANAGER":
            # Filter users by the "CLOSING_MANAGER" group
            queryset = Users.objects.filter(groups__name="CLOSING_MANAGER")
        elif group_name == "CALL_CENTER_EXECUTIVE":
            # Filter users by the "CALL_CENTER_EXECUTIVE" group
            queryset = Users.objects.filter(groups__name="CALL_CENTER_EXECUTIVE")
        elif group_name == "CRM_EXECUTIVE":
            # Filter users by the "CRM_EXECUTIVE" group
            queryset = Users.objects.filter(groups__name="CRM_EXECUTIVE")
        elif group_name == "MARKETING_EXECUTIVE":
            queryset = Users.objects.filter(groups__name="MARKETING_EXECUTIVE")
        else:
            queryset = Users.objects.all()
        if search_query:
            queryset = queryset.filter(Q(name__icontains=search_query))
        return queryset
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return ResponseHandler(False, "Users retrieved successfully", serializer.data, status.HTTP_200_OK)

class UserAllocationView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserAllocationSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            lead_ids = serializer.validated_data['lead_ids']
            
            try:
                user = Users.objects.get(pk=user_id)
            except Users.DoesNotExist:
                print('User not found with ID:', user_id)
                return ResponseHandler(True,'User not found', None, status.HTTP_404_NOT_FOUND)


            leads = Lead.objects.filter(pk__in=lead_ids)
            followup_time = timezone.now() + timedelta(hours=48)
            followup_time_ist = followup_time.astimezone(timezone.pytz.timezone('Asia/Kolkata'))
            print("followup_time: ",followup_time)            
            print("followup_time_ist: ",followup_time_ist)
            if user.groups.filter(name="CALL_CENTER_EXECUTIVE").exists():
                for lead in leads:
                    state = get_object_or_404(State, label='Accept')
                    first_stage = lead.workflow.get().stages.first()
                    data=   {
                                "stage":first_stage,
                                "name": "Follow Up",
                                "order":0,
                                "task_type": "appointment",
                                "workflow":lead.workflow.get(),
                                "appointment_with": f"{lead.first_name} {lead.last_name}",
                                "appointment_type": "telephonic",
                                "time": followup_time_ist,
                                "details":"Follow up call with lead",
                                "status": state,
                                "minimum_approvals_required": 0
                        }
                    task = Task.objects.create(**data)

                    follow_up_1 = NotificationMeta.objects.create(task=task,name=f"Follow Up",time_interval=24)
                    # print('follow_up_1:', follow_up_1)
                    follow_up_1.users.set([user_id])

                    follow_up_2 = NotificationMeta.objects.create(task=task,name=f"Follow Up",time_interval=48)
                    VICE_PRESIDENT = Group.objects.get(name="VICE_PRESIDENT")
                    follow_up_2.groups.set([VICE_PRESIDENT])

                    follow_up_3 = NotificationMeta.objects.create(task=task,name=f"Follow Up",time_interval=168)
                    PROMOTER = Group.objects.get(name="PROMOTER")
                    follow_up_3.groups.set([PROMOTER])

                    # task.notification_meta.set([follow_up_1,follow_up_2,follow_up_3])
                    task.current_notification_meta = follow_up_1
                    task.started = True
                    task.started_at = timezone.now()
                    task.save()

                    # Send notification to the user
                    title = "New Lead Assigned"
                    body = f"You have been assigned new leads. Please follow up with the leads."
                    data = {'notification_type': 'lead_assignment','redirect_url': f'/pre_sales/all_leads/lead_details/{lead.id}/0'}
                    fcm_token = user.fcm_token  
                    print("fcm:",fcm_token)
                    if fcm_token:
                        Notifications.objects.create(notification_id=f"lead-assignment-{user.id}", user_id=user, created=timezone.now(), notification_message=body, notification_url= f'/pre_sales/all_leads/lead_details/{lead.id}/0')
                        send_push_notification(fcm_token, title, body, data)   


            if user.groups.filter(name="CRM_EXECUTIVE").exists():
                for lead in leads:
                    if lead.workflow.exists():
                        workflow = lead.workflow.get()

                        welcome_call_task = workflow.tasks.filter(name='Welcome Call').first()
                        if welcome_call_task:
                            welcome_call_task.started = True
                            welcome_call_task.started_at = timezone.now()
                            welcome_call_task.save()

                        welcome_mail_task = workflow.tasks.filter(name='Welcome Mail').first()
                        if welcome_mail_task:
                            welcome_mail_task.started = True
                            welcome_mail_task.started_at = timezone.now()
                            welcome_mail_task.save()

                        demand_letter_task = workflow.tasks.filter(name='Demand Letter').first()
                        if demand_letter_task:
                            demand_letter_task.started = True
                            demand_letter_task.started_at = timezone.now()
                            demand_letter_task.save()
 
            for lead in leads:
                if lead.workflow.exists():
                    workflow=lead.workflow.all().first()
                    workflow.assigned_to=user
                    workflow.save() 
                    first_stage = workflow.stages.all().order_by('order').first()
                    if first_stage:
                        first_stage.assigned_to = user 
                        first_stage.save()
                followers = lead.followers or []
                
                if not isinstance(followers, list):
                    followers = [followers]
                
                if user.id not in followers:
                    followers.append(user.id)
                
                lead.followers = followers
                lead.save()

                # Send notification to the user
                title = "New Lead Assigned"
                body = f"You have been assigned new leads. Please follow up with the leads."
                data = {'notification_type': 'lead_assignment','redirect_url': f'/post_sales/all_clients/lead_details/{lead.id}/0'}
                fcm_token = user.fcm_token  
                print("fcm:",fcm_token)
                if fcm_token:
                    Notifications.objects.create(notification_id=f"lead-assignment-{lead.id}", user_id=user, created=timezone.now(), notification_message=body, notification_url= f'/post_sales/all_clients/lead_details/{lead.id}/0')
                    send_push_notification(fcm_token, title, body, data)   
                
                print(f'User {user_id} added to followers of lead {lead.id}')

            print(f'Leads assigned successfully for user {user_id}')
            return ResponseHandler(False,'Leads assigned successfully', None, status.HTTP_200_OK)
        else:
            print('Invalid serializer data:', serializer.errors)
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)






class UserReallocationView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserReallocationSerializer(data=request.data)
        if serializer.is_valid():
            new_user_id = serializer.validated_data['user_id']
            lead_id = serializer.validated_data['lead_id']
            
            try:
                new_user = Users.objects.get(pk=new_user_id)
            except Users.DoesNotExist:
                return ResponseHandler(True,'User not found', None, status.HTTP_404_NOT_FOUND)


            try:
                lead = Lead.objects.get(pk=lead_id)
            except Lead.DoesNotExist:
                return ResponseHandler(True,'Lead not found', None, status.HTTP_404_NOT_FOUND)
            
            sales_stage = Stage.objects.filter(name='Sales').first()
            if Lead.objects.filter(pk=lead_id, workflow__current_stage=sales_stage.order).exists():
                return ResponseHandler(True,'Executive Cannot be Changed', None, status.HTTP_404_NOT_FOUND)

            if lead.workflow.exists():
                workflow=lead.workflow.all().first() 
                first_stage = workflow.stages.all().order_by('order').first()
                if first_stage:
                    previous_assigned_user_id = first_stage.assigned_to.id if first_stage and first_stage.assigned_to else None 
                    first_stage.assigned_to = new_user 
                    first_stage.save()

            followers = lead.followers or []
            if not isinstance(followers, list):
                followers = [followers]
            #print("Before followers: ", followers)
            
            if previous_assigned_user_id in followers:
                followers.remove(previous_assigned_user_id)
            #print("After removal followers: ", followers)

            if new_user.id not in followers:
                followers.append(new_user.id)
            #print("After new user addition followers: ", followers)
            lead.followers = followers
            lead.save()
            
            return ResponseHandler(False,'Lead assigned successfully', None, status.HTTP_200_OK)
        else:
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)


class GetMetaDataAPIView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            sources = Source.objects.values('id', 'source_id', 'name')
            source_data = [{'id': source['id'], 'value': f"{source['name']}"} for source in sources]

            channel_partners = ChannelPartner.objects.values('id', 'full_name', 'firm', 'primary_phone_no')
            #channel_partner_dict = {'channel_partner': list(channel_partners)}
            channel_partner_dict =[{'id': channel_partner['id'], 'value': channel_partner['full_name'],'firm': channel_partner['firm'], 'primary_phone_no': channel_partner['primary_phone_no'], } for channel_partner in channel_partners]

            call_center_executives = Users.objects.filter(groups__name="CALL_CENTER_EXECUTIVE").values('id', 'name')

            call_center_executive_dict =[{'id': call_center_executive['id'], 'value': call_center_executive['name']} for call_center_executive in call_center_executives]

            closing_managers =  Users.objects.filter(groups__name="CLOSING_MANAGER").values('id', 'name')

            closing_managers_dict =[{'id': closing_manager['id'], 'value': closing_manager['name']} for closing_manager in closing_managers]

            sourcing_managers = Users.objects.filter(groups__name="SOURCING_MANAGER").values('id', 'name')

            sourcing_managers_dict =[{'id': sourcing_manager['id'], 'value': sourcing_manager['name']} for sourcing_manager in sourcing_managers]

            projects = ProjectDetail.objects.values('id', 'name')

            projects_dict =[{'id': project['id'], 'name': project['name']} for project in projects]
  

            configurations = Configuration.objects.all()
            configurations_list = []
            configurations_list = [configuration.name for configuration in configurations]
            area_list = {
                "1BHK": ['<400 Sqft', '400 - 500 Sqft', '>500 Sqft'],
                "2BHK": ['<600 Sqft', '600 - 700 Sqft', '>700 Sqft'],
                "3BHK": ['<1000 Sqft', '1000 - 1300 Sqft', '>1300 Sqft'],
            }
            age_choices = ["25 - 30","31 - 35", "36 - 40", "41 - 45", "46 - 50","51 - 55", "56 - 60", ">60"]

            income_choices = ['Upto 12 Lacs', '12 - 18 Lacs', '18 - 25 Lacs', '25 - 30 Lacs', '> 30 Lacs']
            budget_choices =  ['1.50 -2.00 Cr','2.00 - 2.50 Cr', '2.50 - 3.00 Cr' ,'> 3 Cr' ]
            meta_data = {'source': source_data, 'channel_partner': channel_partner_dict, \
                         'call_center_executives': call_center_executive_dict,'sourcing_managers': sourcing_managers_dict, 'closing_managers': closing_managers_dict, \
                         'configurations_choices': configurations_list,'area_choices': area_list, 'age_choices':age_choices, \
                            'annual_income':income_choices, 'budget': budget_choices, 'project':projects_dict}

            return ResponseHandler(False, "Meta data retrieved successfully.", meta_data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, f"Error retrieving meta data: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

class BrokerageMetaDataAPIView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            brokerage_percentage_choices = ["0.50","1.00","1.50","2.00","2.50","3.00","3.50","4.00","4.50","5.00","5.50","6.00"]
            meta_data = {'brokerage_meta_data':brokerage_percentage_choices}

            return ResponseHandler(False, "Brokerage Meta data retrieved successfully.", meta_data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, f"Error retrieving meta data: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)     



class DocumentSectionAPIView(generics.ListCreateAPIView):
    serializer_class = DocumentSectionSerializer

    def get_queryset(self):
        tag = self.request.query_params.get('tag', None)

        if tag:
            return DocumentSection.objects.filter(doc_tag=tag)
        else:
            return DocumentSection.objects.all()

    def perform_create(self, serializer):
        lead_id = self.request.data.get('lead', None)
        lead = get_object_or_404(Lead, id=lead_id)

        uploaded_file = self.request.FILES.get('upload_docs')
        if uploaded_file:
            serializer.validated_data['doc_name'] = uploaded_file.name
            serializer.validated_data['lead'] = lead

            try:
                serializer.save()
            except ValidationError as e:
                raise serializers.ValidationError({"detail": str(e)})
        else:
            raise serializers.ValidationError({"detail": "No file uploaded."})
        
class DocumentSectionBulkUploadView(generics.CreateAPIView):
    queryset = DocumentSection.objects.all()
    serializer_class = DocumentSectionSerializer

    def create(self, request, *args, **kwargs):
        document_data_list = []

        # Extract data from the request
        lead_id = request.data.get('lead', None)
        doc_tag = request.data.get('doc_tag', None)
        uploaded_files = request.FILES.getlist('upload_docs', None)
        id_proof_front = self.request.FILES.get('id_proof_front', None)
        id_proof_back = self.request.FILES.get('id_proof_back', None)
        payment_proof = self.request.FILES.get('payment_proof', None)
        pan_card = self.request.FILES.get('pan_card', None)
        passport = request.FILES.get('passport', None)

        if not lead_id or not doc_tag:
            return ResponseHandler(True,'Lead Id & doc_tag required', None, status.HTTP_400_BAD_REQUEST)

        try:
            lead = get_object_or_404(Lead, pk=lead_id)  # Ensuring lead is assigned
        except Exception as e:
            return ResponseHandler(True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)  

        def delete_existing_documents(slug, lead_id, doc_tag):
            # Delete existing documents with the same lead, doc_tag, and slug
            DocumentSection.objects.filter(lead_id=lead_id, doc_tag=doc_tag, slug=slug).delete()
            print(f"Lead id {lead_id} doc tag {doc_tag} deleted successfully with slug {slug}" ) 
        
        # if not uploaded_files:
        #     return ResponseHandler(True,'uploaded_files required', None, status.HTTP_400_BAD_REQUEST)
        if doc_tag == "stamp_duty":
            try:
                lead_obj = get_object_or_404(Lead, pk=lead_id)
                workflow = lead_obj.workflow.get()
                stamp_duty_task = workflow.tasks.filter(name='Stamp Duty').first()
                if stamp_duty_task:
                    state = get_object_or_404(State, label='Accept')
                    stamp_duty_task.status = state
                    stamp_duty_task.completed = True
                    stamp_duty_task.completed_at = datetime.now()
                    stamp_duty_task.save()

                    registration_fees_task = workflow.tasks.filter(name='Registration Fees').first()
                    if registration_fees_task:
                        registration_fees_task.started = True
                        registration_fees_task.started_at = timezone.now()
                        registration_fees_task.save()

                    get_vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                    print("get_vp_user",get_vp_user)
                    if get_vp_user:
                        vp_user = Users.objects.get(id=get_vp_user.id)
                        fcm_token = vp_user.fcm_token
                        # Send notification to the VP
                        title = "Stamp Duty uploaded."
                        body = f"The lead has uploaded a stamp duty."
                        data = {'notification_type': 'lead_assignment','redirect_url': f'/post_sales/all_clients/lead_details/{lead_id}/0'} 
                        print("fcm:",fcm_token)
                        if fcm_token:
                            Notifications.objects.create(notification_id=f"lead-assignment-{lead_id}", user_id=vp_user, created=timezone.now(), notification_message=body, notification_url= f'/post_sales/all_clients/lead_details/{lead_id}/0')
                            send_push_notification(fcm_token, title, body, data)  
                    else:
                        return ResponseHandler(True, f"Vp user not found", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

         
            except Exception as e:
                return ResponseHandler(True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
            

        if doc_tag == "registration_fees":
            try:
                lead_obj = get_object_or_404(Lead, pk=lead_id)
                workflow = lead_obj.workflow.get()
                registration_fees_task = workflow.tasks.filter(name='Registration Fees').first()
                if registration_fees_task:
                    state = get_object_or_404(State, label='Accept')
                    registration_fees_task.status = state
                    registration_fees_task.completed = True
                    registration_fees_task.completed_at = datetime.now()
                    registration_fees_task.save()

                    get_vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                    if get_vp_user:
                        vp_user = Users.objects.get(id=get_vp_user.id)
                        fcm_token = vp_user.fcm_token
                        # Send notification to the VP
                        title = "Registration Fees document uploaded."
                        body = f"The lead has uploaded a registration fees document."
                        data = {'notification_type': 'lead_assignment','redirect_url': f'/post_sales/all_clients/lead_details/{lead_id}/0'} 
                        print("fcm:",fcm_token)
                        if fcm_token:
                            Notifications.objects.create(notification_id=f"lead-assignment-{lead_id}", user_id=vp_user, created=timezone.now(), notification_message=body, notification_url= f'/post_sales/all_clients/lead_details/{lead_id}/0')
                            send_push_notification(fcm_token, title, body, data)
                    else:
                        return ResponseHandler(True, f"Vp user not found", None, status.HTTP_500_INTERNAL_SERVER_ERROR)        
         
            except Exception as e:
                return ResponseHandler(True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)    
            


        if doc_tag == "no_dues":
            try:
                owner = get_object_or_404(PropertyOwner, lead=lead_id)
            except Exception as e:
                return ResponseHandler(True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # print('project:', owner.property.tower.project)
            project_slabs = ProjectCostSheet.objects.filter(project=owner.property.tower.project,event_status="Pending")
            # print('project_slabs:', project_slabs)
            if project_slabs.exists():
                return ResponseHandler(True,'Project slabs not completed!', None, status.HTTP_400_BAD_REQUEST)
            else:
                get_vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                if get_vp_user:
                    vp_user = Users.objects.get(id=get_vp_user.id)
                    fcm_token = vp_user.fcm_token
                    # Send notification to the VP
                    title = "No Due letter uploaded."
                    body = f"The lead has uploaded a no due letter."
                    data = {'notification_type': 'lead_assignment','redirect_url': f'/post_sales/all_clients/lead_details/{lead_id}/0'} 
                    print("fcm:",fcm_token)
                    if fcm_token:
                        Notifications.objects.create(notification_id=f"lead-assignment-{lead_id}", user_id=vp_user, created=timezone.now(), notification_message=body, notification_url= f'/post_sales/all_clients/lead_details/{lead_id}/0')
                        send_push_notification(fcm_token, title, body, data)  
                else:
                    return ResponseHandler(True, f"Vp user not found", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        try:
            lead = get_object_or_404(Lead,pk=lead_id)
        except Exception as e:
            return ResponseHandler(True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

        if uploaded_files:
            # Validate and prepare data for each document
            doc_exists=DocumentSection.objects.filter(lead=lead, doc_tag=doc_tag).exists()
            if doc_exists:
                DocumentSection.objects.filter(lead=lead, doc_tag=doc_tag).delete()
                print(f"Lead id {lead_id} doc tag {doc_tag} deleted successfully without slug" ) 
            for uploaded_file in uploaded_files:
                document_data = {
                    'upload_docs': uploaded_file,
                    'doc_name': uploaded_file.name,
                    'lead': lead_id,
                    'doc_tag': doc_tag,
                }
                document_data_list.append(document_data)
        else:
            if id_proof_front:
                delete_existing_documents('id_proof_front', lead_id, doc_tag)
                document_data = {
                    'upload_docs': id_proof_front,
                    'doc_name': id_proof_front.name,
                    'lead': lead_id,
                    'doc_tag': doc_tag,
                    'slug': "id_proof_front"
                }
                document_data_list.append(document_data)
            if id_proof_back:
                delete_existing_documents('id_proof_back', lead_id, doc_tag)
                document_data = {
                    'upload_docs': id_proof_back,
                    'doc_name': id_proof_back.name,
                    'lead': lead_id,
                    'doc_tag': doc_tag,
                    'slug': "id_proof_back"
                }
                document_data_list.append(document_data)
            if payment_proof:
                delete_existing_documents('payment_proof', lead_id, doc_tag)
                document_data = {
                    'upload_docs': payment_proof,
                    'doc_name': payment_proof.name,
                    'lead': lead_id,
                    'doc_tag': doc_tag,
                    'slug': "payment_proof"
                }
                document_data_list.append(document_data)
            if pan_card:
                delete_existing_documents('pan_card', lead_id, doc_tag)
                document_data = {
                    'upload_docs': pan_card,
                    'doc_name': pan_card.name,
                    'lead': lead_id,
                    'doc_tag': doc_tag,
                    'slug': "pan_card"
                }
                document_data_list.append(document_data)
            if passport:  # Handle passport document upload
                delete_existing_documents('passport', lead_id, doc_tag)
                document_data = {
                    'upload_docs': passport,
                    'doc_name': passport.name,
                    'lead': lead_id,
                    'doc_tag': doc_tag,
                    'slug': "passport"  # Set slug to 'passport'
                }
                document_data_list.append(document_data)    

        # Validate and save each document
        serializer = self.get_serializer(data=document_data_list, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if doc_tag == 'closure':

            project_inventory = ProjectInventory.objects.get(lead=lead_id)                 
            booking_form = BookingForm.objects.filter(lead_id=lead_id).first()
            if booking_form:
                SalesActivity.objects.create(
                    history_date=datetime.now(),
                    history_type="+",
                    history_user=booking_form.sales_manager_name.name,
                    sent_to ="",
                    message=f"{booking_form.sales_manager_name.name} has uploaded documents for {project_inventory.tower.project.name} - {project_inventory.apartment_no}",
                    activity_type="SalesActivity",
                    lead= lead
                )


            users = []
            sh_user = Users.objects.filter(groups__name="SITE_HEAD").first()
            if sh_user:
                users.append(sh_user)

            booking_form = BookingForm.objects.filter(lead_id__id=lead_id).first()
            if booking_form:
                user_cm = booking_form.sales_manager_name
            title = "Documents Uploaded."
            body = f"{user_cm.name} has uploaded documents for {project_inventory.tower.project.name} - {project_inventory.apartment_no}"
            data = {'notification_type': 'documents_upload', 'redirect_url': f'/sales/my_visit/lead_details/{lead_id}/0'}

            for user in users:
                fcm_token = user.fcm_token

                Notifications.objects.create(notification_id=f"Doc-{user.id}", user_id=user,    created=timezone.now(), notification_message=body,notification_url=f'/sales/my_visit/lead_details/{lead_id}/0')

                send_push_notification(fcm_token, title, body, data) 
    
            lead_workflow = lead.workflow.get()
            booking_form_task = lead_workflow.tasks.filter(name='Upload Documents').first()
            booking_form_task.completed = True
            booking_form_task.completed_at = timezone.now()
            booking_form_task.save()

        return ResponseHandler(False,'Documents Bulk upload successful', None, status.HTTP_201_CREATED)
        

class DocumentSectionRetrieveByLeadAndTagView(generics.ListAPIView):
    serializer_class = DocumentSectionSerializer

    def get_queryset(self):
        lead_id = self.kwargs.get('lead_id')
        tag = self.request.query_params.get('tag')

        if lead_id and tag:
            queryset = DocumentSection.objects.filter(lead__id=lead_id, doc_tag=tag)
        elif lead_id:
            queryset = DocumentSection.objects.filter(lead__id=lead_id)
        elif tag:
            queryset = DocumentSection.objects.filter(doc_tag=tag)
        else:
            queryset = DocumentSection.objects.none()

        return queryset

    def list(self, request, *args, **kwargs):


        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)


        return ResponseHandler(False, 'Documents retrieved successfully.', serializer.data, status.HTTP_200_OK)
        

class HistoryRetrievalView(APIView):                
    def get(self, request, lead_id):
        try:
            lead = get_object_or_404(Lead, id=lead_id)
            activity_param = request.query_params.get('activity', 'All')
            date_range_param = request.query_params.get('date_range',None)

            if activity_param == 'All':

                workflow = lead.workflow.get()

                today = datetime.today().date()
                followup_data = workflow.tasks.filter(name='Follow Up',completed=False).first()
                #followup_data = TaskSerializer(followup_tasks, many=True).data
                followup_activity_data = []
                if followup_data:
                #     for followup_tasks in followup_data:
                    data = TaskSerializer(followup_data).data
                    data['visit_date'] = followup_data.time.date()
                    data['follow_up_type'] = 'follow_up'

                    data['follow_up_pending'] = True if followup_data.time <= timezone.now() else False
                    data['workflow_id'] = followup_data.workflow_id
                    followup_activity_data.append(data)
                        
                # add upcoming site visits to follow_activity_data                   

                today = date.today()

                sales_data  = SalesActivity.objects.filter(lead=lead).order_by('id')

                sales_history = SalesActivitySerializer(sales_data, many= True).data

                sales_history_list = []

                sales_history_list.extend(sales_history)


                booking_form = BookingForm.objects.filter(lead_id=lead_id).first()

                booking_form_history_data = []
                
                if booking_form:
                    # Access the historical records associated with the booking_form
                    history = booking_form.history.all()
                
                    bookingform_history_data = BookingFormHistorySerializer(history, many=True).data

                    booking_form_history_data =bookingform_history_data
                lead_history = lead.history.all()

                lead_history_data = LeadHistorySerializer(lead_history, many=True).data

                lead_requirement_history_data = []

                if lead and lead.lead_requirement:

                    lead_requirement_history = lead.lead_requirement.history.all()

                    if lead_requirement_history:

                        lead_requirement_history_data = LeadRequirementHistorySerializer(lead_requirement_history, many=True).data

                    
                site_visits = lead.sitevisit_set.all()
                site_visit_history = []

                for site_visit in site_visits:
                    history_records = site_visit.history.all()

                    serialized_history = SiteVisitHistorySerializer(history_records, many=True).data

                    site_visit_history.extend(serialized_history)

                if site_visits.exists():
                    last_site_visit = site_visits.first()

                    if last_site_visit.site_visit_status == 'Scheduled'and last_site_visit.visit_date >= today:
                        upcoming_instances = site_visits.filter(
                            visit_date__gte=today
                        )

                        upcoming_serializer = SiteVisitSerializer(upcoming_instances, many=True)                

                        for item in upcoming_serializer.data:
                            str_visit_date = item.get('visit_date') if item else None

                            visit_date_object = datetime.strptime(str_visit_date, '%Y-%m-%d').date() if str_visit_date else None

                            item['visit_date'] = visit_date_object
                            item['follow_up_type'] = 'site_visit'


                        followup_activity_data.extend(upcoming_serializer.data)
                followup_activity_data=sorted(followup_activity_data, key=lambda x: x['visit_date'])

                notes = lead.notes_set.all()
                notes_history = []

                for note in notes:
                    history_records = note.history.all()

                    serialized_history = NotesHistorySerializer(history_records, many=True).data

                    notes_history.extend(serialized_history)

                updates_exist = Updates.objects.filter(lead=lead).exists()
                updates_history = []
                if updates_exist:
                    updates =  Updates.objects.get(lead=lead)
                    update_history = updates.history.all()
                    serialized_history = UpdatesHistorySerializer(update_history, many=True).data
                    updates_history.extend(serialized_history)

                calls_history = []
                calls_queryset = LeadCallsMcube.objects.filter(lead_phone=lead.primary_phone_no).order_by('-created_at')
                if calls_queryset.exists():                 
                    calls_serializer = LeadCallsMcubeActivitySerializer(calls_queryset, many=True).data
                    calls_history.extend(calls_serializer)
                all_history = lead_history_data + site_visit_history + notes_history + updates_history + lead_requirement_history_data + calls_history + sales_history_list + booking_form_history_data 
                
                call_center_executive_assigned = False
                assigned_variable = None 
                sorted_history_ascending = sorted(all_history, key=lambda x: x['history_date'], reverse=False)
                for record in sorted_history_ascending:
                    if record['activity_type'] == 'Lead':
                        followers = record['followers']
                        for follower_id in followers:
                            
                            if Users.objects.filter(id=follower_id, groups__name="CALL_CENTER_EXECUTIVE").exists():
                                if not call_center_executive_assigned:
                                    assigned_variable = follower_id
                                    call_center_executive_assigned = True
                                elif assigned_variable != follower_id:
                                    assigned_variable_instance = Users.objects.get(id=assigned_variable)
                                    assigned_variable_name = assigned_variable_instance.name
                                    followers_instance = Users.objects.get(id=follower_id)
                                    followers_name = followers_instance.name
                                    record['message'] = f'Call Center Executive Re-assigned from {assigned_variable_name} to {followers_name}'
                                    call_center_executive_assigned = False
                                    assigned_variable = None

                sorted_history = sorted(sorted_history_ascending, key=lambda x: x['history_date'], reverse=True)
                date_range_param = self.request.query_params.get('date_range')
                if date_range_param:
                    today = datetime.now()
                    if date_range_param == 'last_7_days':
                        seven_days_ago = today - timedelta(days=7)
                        seven_days_ago_date = seven_days_ago.date()
                        sorted_history = [record for record in sorted_history if datetime.strptime(record['history_date'], '%Y-%m-%dT%H:%M:%S.%f%z').date() >= seven_days_ago_date]
                    elif date_range_param == 'last_2_weeks':
                        two_weeks_ago = today - timedelta(weeks=2)
                        two_weeks_ago_date = two_weeks_ago.date()
                        sorted_history = [record for record in sorted_history if datetime.strptime(record['history_date'], '%Y-%m-%dT%H:%M:%S.%f%z').date() >= two_weeks_ago_date]
                    elif date_range_param == 'last_1_month':
                        one_month_ago = today - timedelta(days=30)
                        one_month_ago_date = one_month_ago.date()
                        sorted_history = [record for record in sorted_history if datetime.strptime(record['history_date'], '%Y-%m-%dT%H:%M:%S.%f%z').date() >= one_month_ago_date]
                    elif date_range_param == 'last_6_months':
                        six_month_ago = today - timedelta(days=180)
                        six_month_ago_date = six_month_ago.date()
                        sorted_history = [record for record in sorted_history if datetime.strptime(record['history_date'], '%Y-%m-%dT%H:%M:%S.%f%z').date() >= six_month_ago_date]
   
                for record in sorted_history:
                    if record['history_type'] == "+":
                        if record['activity_type'] == 'SiteVisit':
                            visit_date = record['visit_date']
                            date_obj = datetime.strptime(visit_date, "%Y-%m-%d")
                            formatted_date = date_obj.strftime("%B %d, %Y")
                            timeslot = record['timeslot']
                            start_time = timeslot.split(" to ")[0]
                            record['message'] = f'Site Visit Scheduled at {formatted_date} at {start_time}'
                        if record['activity_type'] == 'Notes':
                            record['message'] = "Remarks Added"
                        if record['activity_type'] == 'BookingForm':
                            record['message'] = "Booking Form Created"
                    if record['history_type'] == "~":
                        previous_record = None
                        if record['activity_type'] == 'Lead':
                            previous_record = next(
                                (prev for prev in sorted_history if prev['history_date'] < record['history_date'] and prev['activity_type'] == 'Lead'),
                                None
                            )
                        if record['activity_type'] == 'LeadRequirements':
                            previous_record = next(
                                (prev for prev in sorted_history if prev['history_date'] < record['history_date'] and prev['activity_type'] == 'LeadRequirements'),
                                None
                            )    
                        if record['activity_type'] == 'SiteVisit':
                            previous_record = next(
                                (prev for prev in sorted_history if prev['history_date'] < record['history_date'] and prev['activity_type'] == 'SiteVisit'),
                                None
                            )    
                        if record['activity_type'] == 'Updates':
                            previous_record = next(
                                (prev for prev in sorted_history if prev['history_date'] < record['history_date'] and prev['activity_type'] == 'Updates'),
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
                                if 'closing_manager' in changed_fields and changed_fields['closing_manager']['new_value'] is not None:
                                    old_closing_manager = changed_fields.get("closing_manager").get("old_value")  
                                    new_closing_manager = changed_fields.get("closing_manager").get("new_value") 
                                    if old_closing_manager is None:
                                        if new_closing_manager:
                                            instance = Users.objects.get(id=new_closing_manager)
                                            lead_id = record.get('lead')
                                            lead_instance = Lead.objects.filter(id=lead_id).first() 
                                            record['message'] = f'{instance.name} was assigned as Closing Manager to {lead_instance.first_name}' 
                                    else:
                                        instance = Users.objects.get(id=new_closing_manager)
                                        lead_id = record.get('lead')
                                        lead_instance = Lead.objects.filter(id=lead_id).first() 
                                        record['message'] = f'{instance.name} was Reassigned as Closing Manager to {lead_instance.first_name}'                                            
                                if 'site_visit_status' in changed_fields and changed_fields['site_visit_status']['new_value'] == "Missed":
                                    record['message'] = 'Site Visit Missed'
                                if 'site_visit_status' in changed_fields and changed_fields['site_visit_status']['new_value'] == "Site Visit Done" and record['site_visit_type'] =="Regular":
                                    record['message'] = "Site Visit Done"      
                                if 'converted_on' in changed_fields:
                                    record['message'] = 'Lead Converted to Sales'
                                    continue
                                if 'snagging_status' in changed_fields and changed_fields['snagging_status']['new_value'] == "Snagging clear":
                                    project_inventory = ProjectInventory.objects.filter(lead=lead).first()
                                    apartment_no = project_inventory.apartment_no if project_inventory and project_inventory.apartment_no else None
                                    record['message'] = f"Snagging Cleared at {apartment_no} for {lead.first_name} {lead.last_name}" 
                                if 'snagging_issues' in changed_fields and isinstance(changed_fields['snagging_issues'], dict) and changed_fields['snagging_issues']['new_value'] and changed_fields['snagging_issues']['old_value'] == []:
                                    project_inventory = ProjectInventory.objects.filter(lead=lead).first()
                                    apartment_no = project_inventory.apartment_no if project_inventory and project_inventory.apartment_no else None
                                    record['message'] = f"Defects Spotted at {apartment_no} for {lead.first_name} {lead.last_name}"  
                                if 'lead_status' in changed_fields and changed_fields['lead_status']['old_value'] is not None:
                                    old_status = changed_fields['lead_status']['old_value']
                                    new_status = changed_fields['lead_status']['new_value']
                                    record['message'] = f'Lead Status Changed from {old_status} to {new_status}'
                                    continue
                                if record['activity_type'] == 'Lead':
                                    messages = []
                                    if 'first_name' in changed_fields and 'last_name' in changed_fields:
                                        old_first_name = changed_fields.get("first_name").get("old_value") if 'old_value' in changed_fields.get("first_name") else record.get("first_name")
                                        old_last_name = changed_fields.get("last_name").get("old_value") if 'old_value' in changed_fields.get("last_name") else record.get("last_name")
                                        new_first_name = changed_fields.get("first_name").get("new_value") if 'new_value' in changed_fields.get("first_name")else record.get("first_name")
                                        new_last_name = changed_fields.get("last_name").get("new_value") if 'new_value' in changed_fields.get("last_name") else record.get("last_name")
                                        messages.append(f'Lead Name Changed from {old_first_name} {old_last_name} to {new_first_name} {new_last_name}')   
                                    elif 'first_name' in changed_fields and changed_fields.get("first_name").get("old_value") is not None:
                                        old_first_name = changed_fields.get("first_name").get("old_value")
                                        new_first_name = changed_fields.get("first_name").get("new_value") if 'new_value' in changed_fields.get("first_name") else record.get("first_name")
                                        #record['message'] = f'Lead Name Changed from {old_first_name} to {new_first_name}'
                                        messages.append(f'Lead First Name Changed from {old_first_name} to {new_first_name}')
                                    elif 'last_name' in changed_fields and changed_fields.get("last_name").get("old_value") is not None:
                                        old_last_name = changed_fields.get("last_name").get("old_value")
                                        new_last_name = changed_fields.get("last_name").get("new_value")if 'new_value' in changed_fields.get("last_name") else record.get("last_name")
                                        #record['message'] = f'Lead Name Changed from {old_last_name} to {new_last_name}'
                                        messages.append(f'Lead Last Name Changed from {old_last_name} to {new_last_name}')

                                    if 'primary_phone_no' in changed_fields and changed_fields.get("primary_phone_no").get("old_value") is not None:
                                        old_no = changed_fields.get("primary_phone_no").get("old_value")
                                        new_no = changed_fields.get("primary_phone_no").get("new_value")    
                                        #record['message'] = f'Lead Phone Number Changed from {old_no} to {new_no}'    
                                        messages.append(f'Lead Phone Number Changed from {old_no} to {new_no}')
                                    if 'secondary_phone_no' in changed_fields and changed_fields.get("secondary_phone_no").get("new_value")  is not None:
                                        old_no = changed_fields.get("secondary_phone_no").get("old_value")
                                        new_no = changed_fields.get("secondary_phone_no").get("new_value") 
                                        if old_no is None and new_no != "":
                                            messages.append(f'Lead Secondary Phone Number added {new_no}')
                                        elif old_no != new_no and new_no != "":  
                                            messages.append(f'Lead Secondary Phone Number Changed from {old_no} to {new_no}')
                                    if 'primary_email' in changed_fields and changed_fields.get("primary_email").get("new_value")  is not None:
                                        old_email= changed_fields.get("primary_email").get("old_value")
                                        new_email = changed_fields.get("primary_email").get("new_value") 
                                        if old_email is None and new_email != "":
                                            messages.append(f'Lead Primary Email added {new_email}')
                                        elif old_email != new_email and new_email != "":   
                                            #record['message'] = f'Lead Email Changed from {old_email} to {new_email}' 
                                            messages.append(f'Lead Email Changed from {old_email} to {new_email}') 
                                    if 'secondary_email' in changed_fields and changed_fields.get("secondary_email").get("new_value") is not None:
                                        old_email= changed_fields.get("secondary_email").get("old_value")
                                        new_email = changed_fields.get("secondary_email").get("new_value") 
                                        if old_email is None and new_email != "":
                                            messages.append(f'Lead Secondary Email added {new_email}')
                                        elif old_email != new_email and new_email != "":    
                                            messages.append(f'Lead Secondary Email Changed from {old_email} to {new_email}')    
                                        #record['message'] = f'Lead Secondary Email Changed from {old_email} to {new_email}'   
                                    if 'gender' in changed_fields and changed_fields.get("gender").get("old_value") is not None:
                                        old_gender = changed_fields.get("gender").get("old_value")
                                        new_gender = changed_fields.get("gender").get("new_value") 
                                        messages.append(f'Lead Gender Changed from {old_gender} to {new_gender}')    
                                        #record['message'] = f'Lead Gender Changed from {old_gender} to {new_gender}'      
                                    if 'address' in changed_fields and changed_fields.get("address").get("new_value")  is not None:
                                        old_address = changed_fields.get("address").get("old_value") 
                                        new_address = changed_fields.get("address").get("new_value")  
                                        if old_address is None and new_address != "":
                                            messages.append(f'Lead Address added {new_address}')
                                        elif old_address != new_address and new_address != "":    
                                            messages.append(f'Lead Address Changed from {old_address} to {new_address}')                                            
                                        #record['message'] = f'Lead Address Changed from {old_address} to {new_address}'    
                                    if 'city' in changed_fields and changed_fields.get("city").get("old_value")  is not None:
                                        old_city = changed_fields.get("city").get("old_value") 
                                        new_city = changed_fields.get("city").get("new_value")  
                                        messages.append(f'Lead City Changed from {old_city} to {new_city}')  
                                        #record['message'] = f'Lead City Changed from {old_city} to {new_city}'  
                                    if 'state' in changed_fields and changed_fields.get("state").get("new_value") is not None:

                                        old_state = changed_fields.get("state").get("old_value") 
                                        new_state = changed_fields.get("state").get("new_value")  
                                        if old_state is None and new_state != "":
                                            messages.append(f'Lead State added {new_state}')
                                        elif old_state != new_state and new_state != "":  
                                            messages.append(f'Lead State Changed from {old_state} to {new_state}')     
                                        #record['message'] = f'Lead State Changed from {old_state} to {new_state}'     
                                    if 'pincode' in changed_fields and changed_fields.get("pincode").get("new_value") is not None:
                                        old_pincode = changed_fields.get("pincode").get("old_value") 
                                        new_pincode = changed_fields.get("pincode").get("new_value")  
                                        if old_pincode is None and new_pincode != "":
                                            messages.append(f'Lead Pincode added {new_pincode}')  
                                        elif old_pincode != new_pincode and new_pincode != "":   
                                            messages.append(f'Lead Pincode Changed from {old_pincode} to {new_pincode}')       
                                        #record['message'] = f'Lead Pincode Changed from {old_pincode} to {new_pincode}'      
                                    if 'occupation' in changed_fields and changed_fields.get("occupation").get("old_value") is not None:
                                        old_occupation = changed_fields.get("occupation").get("old_value") 
                                        new_occupation = changed_fields.get("occupation").get("new_value") 
                                        messages.append(f'Lead Occupation Changed from {old_occupation} to {new_occupation}') 
                                        #record['message'] = f'Lead Occupation Changed from {old_occupation} to {new_occupation}'    
                                    if 'source' in changed_fields and changed_fields.get("source").get("old_value") is not None:
                                        old_source = changed_fields.get("source").get("old_value") 
                                        old_source_data = Source.objects.get(id=old_source).name
                                        new_source = changed_fields.get("source").get("new_value") 
                                        new_source_data  = Source.objects.get(id=new_source).name
                                        messages.append(f'Lead source Changed from {old_source_data} to {new_source_data}')  
                                        #record['message'] = f'Lead source Changed from {old_source} to {new_source}'   
                                    if 'no_of_family' in changed_fields and changed_fields.get("no_of_family").get("new_value") is not None:
                                        old_no_of_family = changed_fields.get("no_of_family").get("old_value") 
                                        new_no_of_family = changed_fields.get("no_of_family").get("new_value")  
                                        if old_no_of_family is None and new_no_of_family != "":
                                            messages.append( f'Lead Family added {new_no_of_family}')
                                        elif old_no_of_family != new_no_of_family and new_no_of_family != "": 
                                            messages.append( f'Lead Family Changed from {old_no_of_family} to {new_no_of_family}')      
                                    if 'remarks' in changed_fields and changed_fields.get("remarks").get("new_value") is not None:
                                        old_remarks= changed_fields.get("remarks").get("old_value")
                                        new_remarks = changed_fields.get("remarks").get("new_value") 
                                        if old_remarks is None and new_remarks != "":
                                            messages.append(f'Lead Remarks added {new_remarks}')
                                        elif old_remarks != new_remarks and new_remarks != "":
                                            messages.append( f'Lead Remarks Changed from {old_remarks} to {new_remarks}')    
                                    if messages:
                                        record['message'] = ', '.join(messages)      
                                        #record['message'] = f'Lead Family Changed from {old_no_of_family} to {new_no_of_family}'  
                                if record.get("activity_type") == 'LeadRequirements':  #get("closing_manager").get("new_value") 
                                    messages = []    
                                    if 'purpose' in changed_fields and changed_fields.get("purpose").get("new_value") is not None:
                                        old_purpose = changed_fields.get("purpose").get("old_value") 
                                        new_purpose = changed_fields.get("purpose").get("new_value")
                                        if old_purpose is None and new_purpose != "":
                                            messages.append(f'Lead Requirement purpose added {new_purpose}')
                                        #record['message'] = f'Purpose  Changed from {old_purpose} to {new_purpose}'
                                        elif old_purpose != new_purpose and new_purpose != "":
                                            messages.append(f'Purpose Changed from {old_purpose} to {new_purpose}')
                                    if 'budget_min' in changed_fields and changed_fields.get("budget_min").get("new_value") is not None:
                                        old_budget_min = changed_fields.get("budget_min").get("old_value") 
                                        new_budget_min = changed_fields.get("budget_min").get("new_value")     
                                        #record['message'] = f'Minimum Budget Changed from {old_no} to {new_no}'    
                                        messages.append(f'Minimum Budget Changed from {old_budget_min} to {new_budget_min}')

                                    if 'budget_max' in changed_fields and changed_fields.get("budget_max").get("new_value") is not None:
                                        old_budget_max = changed_fields.get("budget_max").get("old_value")
                                        new_budget_max = changed_fields.get("budget_max").get("new_value")     
                                        #record['message'] = f'Maximum Budget  Number Changed from {old_no} to {new_no}' 
                                        messages.append(f'Maximum Budget Changed from {old_budget_max} to {new_budget_max}')

                                    if 'funding' in changed_fields and changed_fields.get("funding").get("new_value") is not None:
                                        old_funding = changed_fields.get("funding").get("old_value")
                                        new_funding = changed_fields.get("funding").get("new_value")
                                        if old_funding is None and new_funding != "":
                                            messages.append(f'Lead Requirement funding added {new_funding}')
                                        elif old_funding != new_funding and new_funding != "":
                                            messages.append(f'Funding Changed from  {old_funding} to {new_funding}')    
                                        #record['message'] = f'Funding Changed from {old_funding} to {new_funding}' 
      
                                    if 'area' in changed_fields and changed_fields.get("area").get("new_value") is not None:
                                        old_area = changed_fields.get("area").get("old_value")
                                        new_area = changed_fields.get("area").get("new_value")
                                        messages.append(f'Area Changed from {old_area} to {new_area}')    
                                        #record['message'] = f'Area Changed from {old_area} to {new_area}'   
                                    if 'configuration' in changed_fields and changed_fields.get("configuration").get("new_value") is not None:
                                        old_configuration = changed_fields.get("configuration").get("old_value")
                                        new_configuration = changed_fields.get("configuration").get("new_value")  
                                        messages.append(f'Configuration Changed from {old_configuration} to {new_configuration}')    
                   
                                    if messages:
                                        record['message'] = ', '.join(messages)                                         
                                if 'welcome_call_status' in changed_fields and changed_fields['welcome_call_status']['new_value'] == "Done":
                                    record['message'] = "Welcome Call Done" 
                                if 'welcome_email_status' in changed_fields and changed_fields['welcome_email_status']['new_value'] == "Sent":
                                    record['message'] = "Welcome mail Sent"   
                                if 'demand_letter_status' in changed_fields and changed_fields['demand_letter_status']['new_value'] == "Sent":
                                    record['message'] = "Demand letter Sent"             
                                          
                            else:
                                # Remove 'changed_fields' key if it's an empty dictionary
                                pass
                                # record.pop('changed_fields', None)
                                # if not record.get('changed_fields'):
                                #     sorted_history.remove(record)

                sorted_history = [record for record in sorted_history if record['message'] not in ["Lead Updated", "SiteVisit Updated","LeadRequirements Updated", "Updates Updated", "LeadRequirements Created", "BookingForm Updated"]]                  
                response_data = {
                            'follow_ups': followup_activity_data,
                            'activity_history': sorted_history,  
                        }
                return ResponseHandler(False, 'Data retrieved successfully', response_data, 200)

            elif activity_param == 'Notes':
                notes = lead.notes_set.all()
                notes_history = []

                for note in notes:
                    history_records = note.history.all()
                    serialized_history = NotesHistorySerializer(history_records, many=True).data
                    notes_history.extend(serialized_history)

                sorted_history = sorted(notes_history, key=lambda x: x['history_date'], reverse=True)
                return ResponseHandler(False, 'Data retrieved successfully', sorted_history, 200)
                # Return notes history data

            elif activity_param == 'Sitevisit':
                site_visits = lead.sitevisit_set.all()
                site_visit_history = []

                for site_visit in site_visits:
                    history_records = site_visit.history.all()
                    serialized_history = SiteVisitHistorySerializer(history_records, many=True).data
                    site_visit_history.extend(serialized_history)

                sorted_history = sorted(site_visit_history, key=lambda x: x['history_date'], reverse=True)
                return ResponseHandler(False, 'Data retrieved successfully', sorted_history, 200)

            # elif activity_param == "Refund":
            #     customer_payments = lead.customer_payments.filter(payment_type="Refund")
            #     payment_history = []

            #     for payment in customer_payments:
            #         history_records = payment.history.all()
            #         serialized_history = CustomerPaymentHistorySerializer(history_records, many=True).data
            #         payment_history.extend(serialized_history)

            #     sorted_history = sorted(payment_history, key=lambda x: x['history_date'], reverse=True)
            #     return ResponseHandler(False, 'Data retrieved successfully', sorted_history, 200)

            elif activity_param == "Refund":
                def get_date_filter(date_range_param):
                    today = timezone.now()
                    start_of_today = today.replace(hour=0, minute=0, second=0, microsecond=0)

                    if date_range_param == 'today':
                        return start_of_today
                    elif date_range_param == 'last_7_days':
                        return today - timedelta(days=7)
                    elif date_range_param == 'last_2_weeks':
                        return today - timedelta(weeks=2)
                    elif date_range_param == 'last_1_month':
                        return today - timedelta(days=30)  # Approximate month
                    elif date_range_param == 'last_6_months':
                        return today - timedelta(days=180)  # Approximate 6 months
                    else:
                        return None 
                    
                date_filter = get_date_filter(date_range_param)
                # Fetch CustomerPayment history records where payment_type is "Refund" related to the lead
                payment_history = CustomerPayment.history.filter(
                    lead=lead, payment_type="Refund"
                ).order_by("-history_date")

                if date_filter:
                    payment_history = payment_history.filter(history_date__gte=date_filter)

                # Serialize CustomerPayment history records
                serialized_payment_history = CustomerPaymentHistorySerializer(payment_history, many=True).data

                # Fetch PropertyOwner history records where booking_status is "cancel" related to the lead
                property_owner_history = PropertyOwner.history.filter(
                    lead=lead, booking_status="cancel"
                ).order_by("-history_date")

                if date_filter:
                    property_owner_history = property_owner_history.filter(history_date__gte=date_filter)

                # Serialize PropertyOwner history records
                serialized_property_owner_history = PropertyOwnerHistorySerializer(
                    property_owner_history, many=True
                ).data

                # Combine both histories into a single list
                combined_history = serialized_payment_history + serialized_property_owner_history

                # Sort the combined history by history_date in descending order
                sorted_combined_history = sorted(combined_history, key=lambda x: x['history_date'], reverse=True)

                return ResponseHandler(False, 'Data retrieved successfully', sorted_combined_history, 200)

            else:
                return ResponseHandler(True, 'Invalid activity parameter', None, 400)

        except Exception as e:
            return ResponseHandler(True, 'Error retrieving activity data', str(e), 500)


    # def find_changed_fields(self, previous_record, current_record):

    #     changed_fields = {}
    #     for key, value in current_record.items():
    #         if key != 'changed_fields' and previous_record.get(key) != value:
    #             if key != 'history_date' and key != 'history_type' and key != "history_user" and key != 'message':
    #                 changed_fields[key] = {
    #                     'old_value': previous_record.get(key),
    #                     'new_value': value,
    #                 }
                
    #     return changed_fields
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



class CommunicationAPI(APIView):
    def post(self, request, *args, **kwargs):
        try:
            email_type = request.query_params.get('email_type')
            lead_id = request.data.get('lead_id')
            if not lead_id:
                return ResponseHandler(True, "Lead ID is missing", [], 400)
            lead_obj = Lead.objects.get(id=lead_id)

            workflow = lead_obj.workflow.get()

            # comms_api_url = ''
            # response = requests.post(comms_api_url, json=request.data)

            # if response.status_code == 200:
    
            if email_type == 'welcome_mail':

                workflow = lead_obj.workflow.get()
                welcome_mail_task = workflow.tasks.filter(name='Welcome Mail', completed=False).first()
                if welcome_mail_task:
                    state = get_object_or_404(State, label='Accept')
                    welcome_mail_task.status = state
                    welcome_mail_task.completed = True
                    welcome_mail_task.completed_at = datetime.now()
                    welcome_mail_task.save()

                    stamp_duty_task = workflow.tasks.filter(name='Stamp Duty').first()
                    if stamp_duty_task:
                        stamp_duty_task.started = True
                        stamp_duty_task.started_at = timezone.now()
                        stamp_duty_task.save()
                    updates_record = Updates.objects.get(lead=lead_obj.id)
                    if updates_record.welcome_email_status != 'Sent':
                        updates_record.welcome_email_status = 'Sent'
                        updates_record.save()  
                elif workflow.tasks.filter(name='Welcome Mail', completed=True).exists():
                    return ResponseHandler(False, "Welcome Mail task has already been completed.", None, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Welcome Mail task not found.", None, status.HTTP_404_NOT_FOUND)      
            elif email_type == 'demand_draft_email':
                demand_letter_task = workflow.tasks.filter(name='Demand Letter', completed=False).first()
                if demand_letter_task:
                    state = get_object_or_404(State, label='Accept')
                    demand_letter_task.status = state
                    demand_letter_task.completed = True
                    demand_letter_task.completed_at = datetime.now()
                    demand_letter_task.save()
                    updates_record = Updates.objects.get(lead=lead_obj.id)
                    if updates_record.demand_letter_status != 'Sent':
                        updates_record.demand_letter_status = 'Sent'
                        updates_record.save()  
                elif workflow.tasks.filter(name='Demand Letter', completed=True).exists():
                    return ResponseHandler(False, "Demand Letter task has already been completed.", None, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Demand Letter task not found.", None, status.HTTP_404_NOT_FOUND)        
            elif email_type == 'snagging_email':
                snagging_email_task = workflow.tasks.filter(name='Snagging Mail', completed=False).first()
                if snagging_email_task:
                    state = get_object_or_404(State, label='Accept')
                    snagging_email_task.status = state
                    snagging_email_task.completed = True
                    snagging_email_task.completed_at = datetime.now()
                    snagging_email_task.save()
                    updates_record = Updates.objects.get(lead=lead_obj.id)
                    if updates_record.snagging_email_status != 'Sent':
                        updates_record.snagging_email_status = 'Sent'
                        updates_record.save()  
                elif workflow.tasks.filter(name='Snagging Mail', completed=True).exists():
                    return ResponseHandler(False, "Snagging Mail task has already been completed.", None, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Snagging Mail task not found.", None, status.HTTP_404_NOT_FOUND)       
            elif email_type == 'possession_due_email':
                possession_due_task = workflow.tasks.filter(name='Possession Due Email', completed=False).first()
                if possession_due_task:
                    state = get_object_or_404(State, label='Accept')
                    possession_due_task.status = state
                    possession_due_task.completed = True
                    possession_due_task.completed_at = datetime.now()
                    possession_due_task.save()
                    updates_record = Updates.objects.get(lead=lead_obj.id)
                    if updates_record.possession_due_email_status != 'Sent':
                        updates_record.possession_due_email_status = 'Sent'
                        updates_record.save()
                    vp_users = Users.objects.filter(groups__name="VICE_PRESIDENT")
                    title = "Possession Due Email Sent"
                    body = f"Possession Due Email Sent to {lead_obj.first_name} {lead_obj.last_name}"
                    data = {'notification_type': 'possession_due_email'}
                    # project_inventory = ProjectInventory.objects.filter(lead=lead_obj).first()
                    # project_id = project_inventory.tower.project.id if project_inventory and project_inventory.tower and project_inventory.tower.project else None
                    crm_head = Users.objects.filter(groups__name = "CRM_HEAD").first()#,project=project_id
                    for vp_user in vp_users:
                        if vp_user:
                            fcm_token_vp = vp_user.fcm_token
                            Notifications.objects.create(notification_id=f"task-{possession_due_task.id}-{vp_user.id}", user_id=vp_user,created=timezone.now(),  notification_message=body, notification_url='')
                            send_push_notification(fcm_token_vp, title, body, data)      
                    if crm_head:
                        fcm_token_crmhead = crm_head.fcm_token
                        Notifications.objects.create(notification_id=f"task-{possession_due_task.id}-{crm_head.id}", user_id=crm_head,created=timezone.now(),  notification_message=body, notification_url='')
                        send_push_notification(fcm_token_crmhead, title, body, data)        
                elif workflow.tasks.filter(name='Possession Due Email', completed=True).exists():
                    return ResponseHandler(False, "Possession Due Email task has already been completed.", None, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Possession Due Email task not found.", None, status.HTTP_404_NOT_FOUND)    
            elif email_type == 'welcome_call':
                welcome_call_task = workflow.tasks.filter(name='Welcome Call', completed=False).first()
                if welcome_call_task:
                    state = get_object_or_404(State, label='Accept')
                    welcome_call_task.status = state
                    welcome_call_task.completed = True
                    welcome_call_task.completed_at = datetime.now()
                    welcome_call_task.save()
                    updates_record = Updates.objects.get(lead=lead_obj.id)
                    if updates_record.welcome_call_status != 'Done':
                        updates_record.welcome_call_status = 'Done'
                        updates_record.save()  
                elif workflow.tasks.filter(name='Welcome Call', completed=True).exists():
                    return ResponseHandler(False, "Welcome Call task has already been completed.", None, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Welcome Call task not found.", None, status.HTTP_404_NOT_FOUND)            
            return ResponseHandler(False, "Task Updated successfully.", None, status.HTTP_200_OK)
            # else:
            #     return ResponseHandler(True, "Failed to send email.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
                    return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)



class DocumentActions(APIView):

    def put(self, request, doc_id, *args, **kwargs):
        try:
            new_doc_name = request.data.get('new_doc_name', '')
            document = DocumentSection.objects.get(id=doc_id)

            if not new_doc_name:
                return ResponseHandler(True, "New document name is required.", None, status.HTTP_400_BAD_REQUEST)

            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
            aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

            s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_s3_region_name)

            current_file_key = str(document.upload_docs)
            new_file_path = f"{os.path.dirname(current_file_key)}/{new_doc_name}"

            s3.copy_object(Bucket=aws_storage_bucket_name, CopySource=f"{aws_storage_bucket_name}/{current_file_key}", Key=new_file_path)
            s3.delete_object(Bucket=aws_storage_bucket_name, Key=current_file_key)

            document.doc_name = new_doc_name
            document.upload_docs.name = new_file_path
            document.save()

            return ResponseHandler(False, "Document renamed successfully.", None, status.HTTP_200_OK)
        except DocumentSection.DoesNotExist:
            return ResponseHandler(True, "Document not found.", None, status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

        
    def delete(self, request, doc_id, *args, **kwargs):
        try:
            document = DocumentSection.objects.get(id=doc_id)

            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
            aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

            s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key, region_name=aws_s3_region_name)

            file_key = str(document.upload_docs)

            s3.delete_object(Bucket=aws_storage_bucket_name, Key=file_key)

            document.delete()
            # file_path = document.upload_docs.name
            # if os.path.exists(file_path):
            #     os.remove(file_path)

            #document.delete()
            return ResponseHandler(False, "Document deleted successfully.", None, status.HTTP_204_NO_CONTENT)
        except DocumentSection.DoesNotExist:
            return ResponseHandler(True, "Document not found.", None, status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)


class TopPerformanceAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    def get(self, request):

        query_param = request.query_params.get('module', None)

        if query_param == 'PRESALES':

            call_center_executives = Users.objects.filter(groups__name='CALL_CENTER_EXECUTIVE')

            top_performers_data = []


            for user in call_center_executives:

                converted_leads = Lead.objects.filter(converted_on__isnull=False, followers__contains=[user.id])
                
                conversion_count = converted_leads.count()

                if conversion_count > 0:

                    top_performers_data.append({'user_id': user.id, 'username': user.name, 'count': conversion_count})

            top_performers_data = sorted(top_performers_data, key=lambda x: x['count'], reverse=True)

            return ResponseHandler(False, "Top Performance data", top_performers_data[:4], 200)
        
        elif query_param == 'SALES':
 
            closing_managers = Users.objects.filter(groups__name='CLOSING_MANAGER')

            closed_deals_counts = {}

            for manager in closing_managers:
                closed_deals = 0

                booking_forms = BookingForm.objects.filter(sales_manager_name=manager)

                for booking_form in booking_forms:
                    apartment_no = booking_form.apartment_no

                    if ProjectInventory.objects.filter(apartment_no=apartment_no, status='Booked').exists():
 
                        closed_deals += 1

                closed_deals_counts[manager.id] = closed_deals

            sorted_managers = sorted(closed_deals_counts.items(), key=lambda x: x[1], reverse=True)

            top_performers = [{'user_id': manager_id, 'name': Users.objects.get(id=manager_id).name, 'closed_deals': closed_deals} for manager_id, closed_deals in sorted_managers[:4] if closed_deals > 0]

            return ResponseHandler(False, "Top Performance data", top_performers, 200)
        
        elif query_param == 'SOURCING':
            
            channel_partners = ChannelPartner.objects.all()

            closed_deals_counts = {}

            for channelpartner in channel_partners:
                closed_deals = 0

                channel_partner_leads = Lead.objects.filter(channel_partner=channelpartner)

                booked_leads = channel_partner_leads.filter(projectinventory__status="Booked").count()

                closed_deals_counts[channelpartner.id] = booked_leads

            sorted_cps = sorted(closed_deals_counts.items(), key=lambda x: x[1], reverse=True)

            top_performers = [{'user_id': channelpartner_id, 'name': ChannelPartner.objects.get(id=channelpartner_id).full_name, 'closed_deals': closed_deals} for channelpartner_id, closed_deals in sorted_cps[:4] if closed_deals > 0]

            return ResponseHandler(False, "Top Performance data", top_performers, 200)
        else:
            return ResponseHandler(True, "Invalid query_param", '',400) 
        


class LeadsOverviewAPIView(APIView):
    def get(self, request, format=None):

        query_param = request.query_params.get('module', None)
        year = request.query_params.get('year', None)
        if not year:
            return ResponseHandler(True, "Year parameter is required", '',400) 

        try:
            year = int(year)
        except ValueError:
            return ResponseHandler(True,"Invalid year parameter", '',400) 
        if query_param == 'PRESALES':
            
            leads_overview_list = {'all_months': []}

            presales_stage = Stage.objects.filter(name='PreSales').first()

            sales_stage = Stage.objects.filter(name='Sales').first()
            
            postsales_stage = Stage.objects.filter(name='PostSales').first()



            for month in range(1, 13):
    
                num_days = calendar.monthrange(year, month)[1]

                start_timestamp = make_aware(datetime(year, month, 1))
                end_timestamp = make_aware(datetime(year, month, num_days, 23, 59, 59))  

                presales_count = Lead.objects.filter(created_on__gte=start_timestamp, created_on__lte=end_timestamp, workflow__current_stage=presales_stage.order).count()

                sales_count = Lead.objects.filter(created_on__gte=start_timestamp, created_on__lte=end_timestamp, workflow__current_stage=sales_stage.order).count()

                postsales_count = Lead.objects.filter(created_on__gte=start_timestamp, created_on__lte=end_timestamp, workflow__current_stage=postsales_stage.order).count()

                # leads_overview[start_timestamp.strftime('%B')] = {
                #     'Presales': presales_count,
                #     'Sales': sales_count,
                #     'Postsales': postsales_count
                # }
                month_data = {
                    'month': start_timestamp.strftime('%B'),
                    'presales': presales_count,
                    'sales': sales_count,
                    'postsales': postsales_count
                }
                leads_overview_list['all_months'].append(month_data)

            max_presales_count = max(month_data['presales'] for month_data in leads_overview_list['all_months'])

            max_sales_count = max(month_data['sales'] for month_data in leads_overview_list['all_months'])

            max_postsales_count = max(month_data['postsales'] for month_data in leads_overview_list['all_months'])

            max_data = {
                'presales': max_presales_count,
                'sales': max_sales_count,
                'postsales': max_postsales_count
            }

            leads_overview_list['max_data'] = max_data  

        elif query_param == 'SALES':

            leads_overview_list = {'all_months': []}

            for month in range(1, 13):
    
                num_days = calendar.monthrange(year, month)[1]

                start_timestamp = make_aware(datetime(year, month, 1))

                end_timestamp = make_aware(datetime(year, month, num_days, 23, 59, 59))  

                converted_leads_count = Lead.objects.filter(converted_on__gte=start_timestamp, converted_on__lte=end_timestamp).count()
                
                inquiry_form_group = Group.objects.get(name='INQUIRY_FORM')
                
                inquiry_form_users = inquiry_form_group.user_set.all()
                
                booking_forms_custom_range = BookingForm.objects.filter(date_of_booking__gte=start_timestamp.date(), date_of_booking__lte=end_timestamp.date())
                
                overall_count = 0
                
                for booking_form in booking_forms_custom_range:
                    apartment_no = booking_form.apartment_no
                    if ProjectInventory.objects.filter(apartment_no=apartment_no, status='Booked').exists():
                        overall_count += 1
                closed_deals_count = overall_count

                walking_leads_count = Lead.objects.filter(creator__in=inquiry_form_users, created_on__gte=start_timestamp, created_on__lte=end_timestamp).count()
                
                month_data = {
                    'month': start_timestamp.strftime('%B'),
                    'converted_leads': converted_leads_count,
                    'walking_leads': walking_leads_count,
                    'closed_deals': closed_deals_count,
                }

                leads_overview_list['all_months'].append(month_data)

            max_converted_leads_count = max(month_data['converted_leads'] for month_data in leads_overview_list['all_months'])

            max_walking_leads_count = max(month_data['walking_leads'] for month_data in leads_overview_list['all_months'])
            
            max_closed_deals_count = max(month_data['closed_deals'] for month_data in leads_overview_list['all_months'])

            max_data = {
                'converted_leads': max_converted_leads_count,
                'walking_leads': max_walking_leads_count,
                'closed_deals': max_closed_deals_count
            }

            leads_overview_list['max_data'] = max_data  

        else:
            return ResponseHandler(True, "Provide the module info in query params", None, 400)
        
        return ResponseHandler(False, "Leads Overview", leads_overview_list,200)

class LeadSummaryAPIView(APIView):
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
        # Generate a hash of the name
        hash_object = hashlib.md5(name.encode())
        hex_dig = hash_object.hexdigest()
        # Use the first 6 characters of the hash as the color code
        color = f"{hex_dig[:6].upper()}"
        return color
    
    @staticmethod
    def fetch_city_from_pincode(pincode):
        url = f'https://dev.estogroup.in/api/leads/location/{pincode}/'
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if not data['error']:
                return data['body']['city']
        return None

    @check_access(required_groups=["ADMIN","PROMOTER","VICE_PRESIDENT","SITE_HEAD","CLOSING_MANAGER","CALL_CENTER_EXECUTIVE","SOURCING_MANAGER"])
    def get(self, request, format=None):
        
        try:
            query_param = request.query_params.get('module', None)

            closing_manager_param = request.query_params.get('closing_manager_id',None)
            sourcing_manager_param = request.query_params.get('sourcing_manager_id',None)
            # cce_param = request.query_params.get('cc_executive_id',None)
            if query_param == 'PRESALES':

                # user = self.request.user
                # group_names = user.groups.values_list('name', flat=True)
                
                # cce_param = None
                # if  "CALL_CENTER_EXECUTIVE" in group_names:
                #     cce_param = user.id
                # print(cce_param) 

                cce_param = request.query_params.get('user_id',None)

                # Lead Info
                presales_stage = Stage.objects.filter(name='PreSales').first()

                presale_leads = Lead.objects.filter(workflow__current_stage=presales_stage.order)
        

                if cce_param:
                    presale_leads = Lead.objects.filter(Q(workflow__current_stage=presales_stage.order) & (Q(workflow__stages__assigned_to_id=cce_param) | Q(creator_id=cce_param))).distinct()
                presale_leads_count = presale_leads.count()

                new_leads_count = presale_leads.filter(lead_status='New').count()

                hot_leads_count = presale_leads.filter(lead_status='Hot').count()

                cold_leads_count = presale_leads.filter(lead_status='Cold').count()

                warm_leads_count = presale_leads.filter(lead_status='Warm').count()

                lost_leads_count = presale_leads.filter(lead_status='Lost').count()

                # Site Visit Info
                
                total_leads_presales = Lead.objects.filter(creation_stage="PreSales")
                print("count total leads presales",total_leads_presales.count())
                if cce_param:
                    total_leads_presales = Lead.objects.filter(Q(workflow__stages__assigned_to_id=cce_param) | Q(creator_id=cce_param)).filter(creation_stage="PreSales").distinct()
                    print("cce param leads in presale",total_leads_presales.count())
               
                sv_scheduled_count = SiteVisit.objects.filter(site_visit_status = "Scheduled" , lead__in=total_leads_presales).count()
               
                sv_done_count = SiteVisit.objects.filter(site_visit_status = "Site Visit Done" , lead__in=total_leads_presales).count()

                print("site visit scheduled :- ",sv_scheduled_count) 
                print("site visit done :- ", sv_done_count)
               
                sv_missed_count = self.site_visit_calculation(total_leads_presales,"Missed",None)


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
                if cce_param:
                    total_booking_count = ProjectInventory.objects.filter(status="Booked",lead__isnull=False,lead__creator_id=cce_param , lead__creation_stage = "PreSales")
                print("booking_queryset",total_booking_count)
                total_booking_count = total_booking_count.count()
                print(total_booking_count)
                booking_count = total_booking_count 


                total_sv_count =  sv_scheduled_count + sv_done_count  + revisit_count + booking_count

                today = timezone.now().date()  # Get today's date
                one_week_ago = today - timedelta(days=7)  # Date one week ago

                # Calculate follow-ups and missed follow-ups
                follow_ups = self.calculate_follow_ups_count(total_leads_presales, "Today")
                missed_follow_ups = self.calculate_follow_ups_count(total_leads_presales, "Missed_Today")

                # Site visits
                site_visit_scheduled = SiteVisit.objects.filter(
                    site_visit_status="Scheduled", 
                    lead__in=total_leads_presales, 
                    visit_date=today
                ).count()

                site_visit_done = SiteVisit.objects.filter(
                    site_visit_status="Site Visit Done", 
                    lead__in=total_leads_presales, 
                    visit_date=today
                ).count()

                print("sv_scheduled", site_visit_scheduled)
                print("sv_done", site_visit_done)

                # Calls Yesterday & Today's
                call_center_executives = Users.objects.filter(groups__name='CALL_CENTER_EXECUTIVE')
                if cce_param:
                    # executive = Users.objects.get(id=cce_param, groups__name='CALL_CENTER_EXECUTIVE')
                    # call_center_executives = [executive]
                    if Users.objects.filter(id=cce_param, groups__name='CALL_CENTER_EXECUTIVE').count() > 0:
                        executive = Users.objects.get(id=cce_param, groups__name='CALL_CENTER_EXECUTIVE')
                        print("executive:", executive)
                        call_center_executives = [executive]
                    else:
                        print(f"No user with ID {cce_param} found in the CALL_CENTER_EXECUTIVE group.")
                        call_center_executives = []

                yesterday = today - timedelta(days=1)
                total_todays_call = LeadCallsMcube.objects.filter(
                    call_type="OUTGOING",
                    start_time__date=today,
                    executive__in=call_center_executives
                )
                total_todays_call_count = total_todays_call.count()
                connected_todays_call_count = total_todays_call.filter(call_status="ANSWER").count()
                not_connected_todays_call_count = total_todays_call_count - connected_todays_call_count

                total_yesterday_call = LeadCallsMcube.objects.filter(
                    call_type="OUTGOING",
                    start_time__date=yesterday,
                    executive__in=call_center_executives
                )
                total_yesterday_call_count = total_yesterday_call.count()
                connected_yesterday_call_count = total_yesterday_call.filter(call_status="ANSWER").count()
                not_connected_yesterday_call_count = total_yesterday_call_count - connected_yesterday_call_count

                # Weekly follow-ups and missed follow-ups
                weekly_follow_ups = self.calculate_follow_ups_count(total_leads_presales, "Last_7_Days")
                weekly_missed_follow_ups = self.calculate_follow_ups_count(total_leads_presales, "Missed_Last_7_Days")

                # Weekly site visits
                weekly_site_visit_scheduled = SiteVisit.objects.filter(
                    site_visit_status="Scheduled",
                    lead__in=total_leads_presales,
                    visit_date__range=[one_week_ago, today]
                ).count()

                weekly_site_visit_done = SiteVisit.objects.filter(
                    site_visit_status="Site Visit Done",
                    lead__in=total_leads_presales,
                    visit_date__range=[one_week_ago, today]
                ).count()

                res = dict()
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
                    "booking_done_percentage" : round(booking_count / total_sv_count * 100 , 2) if total_sv_count > 0 else 0
                }
                res["todays_calls"] = {
                    "total_todays_call_count": total_todays_call_count,
                    "connected_todays_call_count": connected_todays_call_count,
                    "connected_todays_call_percentage" : round(connected_todays_call_count/total_todays_call_count * 100 ,2) if total_todays_call_count > 0 else 0,
                    "not_connected_todays_call_count": not_connected_todays_call_count,
                    "not_connected_todays_call_percentage" : round(not_connected_todays_call_count/total_todays_call_count * 100 ,2) if total_todays_call_count > 0 else 0
                }
                res["yesterday_calls"] = {
                    "total_yesterday_call_count": total_yesterday_call_count,
                    "connected_yesterday_call_count": connected_yesterday_call_count,
                    "connected_yesterday_call_percentage" : round(connected_yesterday_call_count / total_yesterday_call_count * 100 , 2) if  total_yesterday_call_count > 0 else 0,
                    "not_connected_yesterday_call_count": not_connected_yesterday_call_count,
                    "not_connected_yesterday_call_percentage" : round(not_connected_yesterday_call_count / total_yesterday_call_count * 100 ,2) if total_yesterday_call_count > 0 else 0
                }
                res["day_view"] = {
                    "follow_ups": follow_ups,
                    "missed_follow_ups": missed_follow_ups,
                    "site_visit_scheduled": site_visit_scheduled,
                    "site_visit_done": site_visit_done
                }
                res["weekly_view"] = {
                    "follow_ups" : weekly_follow_ups,
                    "missed_follow_ups" : weekly_missed_follow_ups,
                    "site_visit_scheduled" : weekly_site_visit_scheduled,
                    "site_visit_done" : weekly_site_visit_done
                }

               # res["top_performers"] = top_performers_data[:4]

                return ResponseHandler(False, "PreSales dashboard data retrieved successfully.", res,200)
            
            elif query_param == 'SALES':

                date_range_param = self.request.query_params.get('date_range','all_time')

                start_date_param = self.request.query_params.get('start_date', None)

                end_date_param = self.request.query_params.get('end_date', None)

                total_inventory = ProjectInventory.objects.count()

                booked_inventory = ProjectInventory.objects.filter(status='Booked').count()

                sales_stage = Stage.objects.filter(name='Sales').first()

                sales_count = Lead.objects.filter(workflow__current_stage=sales_stage.order).count()

                inquiry_form_group = Group.objects.get(name='INQUIRY_FORM')

                inquiry_form_users = inquiry_form_group.user_set.all()

                leads_count = Lead.objects.filter(creator__in=inquiry_form_users).count()

                site_visits = SiteVisit.objects.filter(site_visit_status="Site Visit Done", site_visit_type = "Regular").count()

                if date_range_param:

                    today = datetime.now()

                    today_date = today.date()

                    if date_range_param == 'today':
     
                        booking_forms_today = BookingForm.objects.filter(date_of_booking=today_date)

                        overall_count = 0

                        for booking_form in booking_forms_today:

                            apartment_no = booking_form.apartment_no

                            if ProjectInventory.objects.filter(apartment_no=apartment_no, status='Booked').exists():

                                overall_count += 1
                        booked_inventory = overall_count

                        sales_count = Lead.objects.filter(created_on__date=today_date, workflow__current_stage=sales_stage.order).count()
                        
                        leads_count = Lead.objects.filter(creator__in=inquiry_form_users, created_on__date=today_date).count()
                        
                        site_visits = SiteVisit.objects.filter(visit_date=today_date,site_visit_status="Site Visit Done",site_visit_type="Regular").count()
                    
                    elif date_range_param == 'last_1_week':

                        one_week_ago = datetime.now() - timedelta(weeks=1)

                        booking_forms_last_week = BookingForm.objects.filter(date_of_booking__gte=one_week_ago, date_of_booking__lte=today_date)
                        
                        overall_count = 0
                        
                        for booking_form in booking_forms_last_week:
                            apartment_no = booking_form.apartment_no
                            if ProjectInventory.objects.filter(apartment_no=apartment_no, status='Booked').exists():
                                overall_count += 1
                        booked_inventory = overall_count
                        
                        sales_count = Lead.objects.filter(created_on__date__gte=one_week_ago, created_on__date__lte=today_date, workflow__current_stage=sales_stage.order).count()
                        
                        leads_count = Lead.objects.filter(creator__in=inquiry_form_users, created_on__date__gte=one_week_ago, created_on__date__lte=today_date).count()
      
                        site_visits = SiteVisit.objects.filter(visit_date__gte=one_week_ago, visit_date__lte=today_date, site_visit_status="Site Visit Done", site_visit_type="Regular").count()
                    
                    elif date_range_param == 'last_1_month':

                        one_month_ago = today_date - timedelta(days=30)
                        
                        booking_forms_last_month = BookingForm.objects.filter(date_of_booking__gte=one_month_ago, date_of_booking__lte=today_date)
                        
                        overall_count = 0
                        
                        for booking_form in booking_forms_last_month:
                            apartment_no = booking_form.apartment_no
                            if ProjectInventory.objects.filter(apartment_no=apartment_no, status='Booked').exists():
                                overall_count += 1
                        booked_inventory = overall_count
                        
                        sales_count = Lead.objects.filter(created_on__date__gte=one_month_ago, created_on__date__lte=today_date, workflow__current_stage=sales_stage.order).count()
                        
                        leads_count = Lead.objects.filter(creator__in=inquiry_form_users, created_on__date__gte=one_month_ago, created_on__date__lte=today_date).count()

                        site_visits = SiteVisit.objects.filter(visit_date__gte=one_month_ago, visit_date__lte=today_date, site_visit_status="Site Visit Done", site_visit_type="Regular").count()
                    
                    elif date_range_param == 'custom_range' and start_date_param and end_date_param:

                        start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()

                        end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
                        
                        booking_forms_custom_range = BookingForm.objects.filter(date_of_booking__gte=start_date, date_of_booking__lte=end_date)
                        
                        overall_count = 0
                        
                        for booking_form in booking_forms_custom_range:
                            apartment_no = booking_form.apartment_no
                            if ProjectInventory.objects.filter(apartment_no=apartment_no, status='Booked').exists():
                                overall_count += 1
                        booked_inventory = overall_count
                        
                        sales_count = Lead.objects.filter(created_on__date__gte=start_date, created_on__date__lte=end_date, workflow__current_stage=sales_stage.order).count()
                        
                        leads_count = Lead.objects.filter(creator__in=inquiry_form_users, created_on__date__gte=start_date, created_on__date__lte=end_date).count()
                        
                        site_visits = SiteVisit.objects.filter(visit_date__gte=start_date, visit_date__lte=end_date, site_visit_status="Site Visit Done", site_visit_type="Regular").count()
                

                summary = {
                    'total_inventory': total_inventory,
                    'inventory_booked': booked_inventory,
                    'no_of_leads': sales_count,
                    'walkin_leads': leads_count,
                    'site_visits': site_visits
                }

                return ResponseHandler(False, "Summary data", summary,200) 

            elif query_param == 'CLOSING':
                if closing_manager_param is not None:
                    cm_instance = Users.objects.get(id=closing_manager_param)
                    print(cm_instance)
                    stage = Stage.objects.filter(name='Sales').first()

                    queryset = Lead.objects.filter(sitevisit__closing_manager=cm_instance ).distinct()

                    # postsales_stage = Stage.objects.filter(name='PostSales').first()
                    # queryset = Lead.objects.filter(sitevisit__closing_manager=cm_instance).exclude(workflow__current_stage=postsales_stage.order).order_by('-created_on') 

                    print("queryset",queryset)    
                    total_queryset_count = queryset.count()
                    print("total_queryset_count",total_queryset_count)

                    new_leads_count = queryset.filter(lead_status = "New").count()

                    hot_leads_count = queryset.filter(lead_status='Hot').count()

                    cold_leads_count = queryset.filter(lead_status='Cold').count()

                    warm_leads_count = queryset.filter(lead_status='Warm').count()

                    lost_leads_count = queryset.filter(lead_status='Lost').count()

                   
                    total_cm_leads = Lead.objects.filter(sitevisit__closing_manager=cm_instance ).distinct()

                   # revisit_count = queryset.annotate(num_site_visits=Count('sitevisit', distinct=True)).filter(num_site_visits__gt=1).count()  #include 
                    queryset = total_cm_leads.annotate(sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done")))
                    sv_data = queryset.filter(sv_done__gt=1)
                    revisit_count = 0
                    for lead in sv_data:
                       revisit_count += (lead.sv_done -1)
                       print("Lead ID:", lead.id, "Site Visits Done:", lead.sv_done)

                    booking_count = total_cm_leads.filter(projectinventory__status="Booked").count() 
                   

                    total_count = hot_leads_count + cold_leads_count + warm_leads_count + lost_leads_count + revisit_count + booking_count
                    
                   # new_leads_percentage = (new_leads_count / total_count *100) if total_count > 0 else 0
                    hot_leads_percentage = round(hot_leads_count / total_count * 100 , 2) if total_count > 0 else 0
                    cold_leads_percentage = round(cold_leads_count / total_count * 100 , 2) if total_count > 0 else 0
                    warm_leads_percentage = round(warm_leads_count / total_count * 100 , 2) if total_count > 0 else 0
                    lost_leads_percentage = round(lost_leads_count / total_count * 100, 2) if total_count > 0 else 0
                    revisit_percentage = round(revisit_count / total_count * 100 , 2) if total_count > 0 else 0
                    booking_percentage = round(booking_count / total_count * 100 , 2)  if total_count > 0 else 0

                    summary = {
                        #"total_leads_count": total_queryset_count,
                        "total_count" : total_count,
                        # "new_leads_count" : new_leads_count,
                        # "new_leads_percentage" : new_leads_percentage,
                        "hot_leads_count": hot_leads_count,
                        "hot_leads_percentage": hot_leads_percentage,
                        "cold_leads_count": cold_leads_count,
                        "cold_leads_percentage": cold_leads_percentage,
                        "warm_leads_count": warm_leads_count,
                        "warm_leads_percentage": warm_leads_percentage,
                        "lost_leads_count": lost_leads_count,
                        "lost_leads_percentage": lost_leads_percentage,
                        #"reschedule_data" : reschedule_counts,
                        "revisit_count": revisit_count,
                        "revisit_percentage": revisit_percentage,
                        "booking_count": booking_count,
                        "booking_percentage": booking_percentage
                    }

                    return ResponseHandler(False, "Summary data", summary,200) 

                else:
                    return ResponseHandler(True, "Provide Closing Manager Id", None,400) 
                
            elif query_param == 'CLOSING_DASHBOARD':
                if closing_manager_param is not None:
                    cm_instance = Users.objects.get(id=closing_manager_param)
                    print(cm_instance)

                    stage = Stage.objects.filter(name='Sales').first()

                    queryset = Lead.objects.filter(workflow__current_stage=stage.order, sitevisit__closing_manager=cm_instance)
                    print("querysetcount", queryset.count())

                    current_date = timezone.now().date()
                    yesterday_date = current_date - timedelta(days=1)
                    start_date = current_date - timedelta(days=7)
                    today = timezone.now().date()
                    start_of_week = today - timedelta(days=today.weekday() + 7)  
                    end_of_week = start_of_week + timedelta(days=6)  
                    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    today_end = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)

                    # Weekly
                    total_leads_cm =Lead.objects.filter(sitevisit__closing_manager=cm_instance).distinct()
                    total_leads_cm_nd = Lead.objects.filter(sitevisit__closing_manager=cm_instance)
                    site_visits_this_week = SiteVisit.objects.filter(
                        visit_date__range=(start_date, current_date),
                        lead__in=total_leads_cm
                    )

                    print("site visit queryset", list(site_visits_this_week.values()))
                    print("site_visit_this_week_count", site_visits_this_week.count())


                    total_cm_leads = Lead.objects.filter(
                        sitevisit__closing_manager=cm_instance,
                        sitevisit__visit_date__range=[start_of_week, today]  # Filter by date range
                    ).distinct()

                    # Annotate the number of site visits marked as "Site Visit Done" within the date range
                    queryset = total_cm_leads.annotate(
                        sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done"))
                    )

                    # Filter leads where more than one site visit was done
                    sv_data = queryset.filter(sv_done__gt=1)

                    # Calculate the revisit count
                    revisit_count_week = 0
                    for lead in sv_data:
                        revisit_count_week += (lead.sv_done - 1)
                        print("Lead ID:", lead.id, "Site Visits Done:", lead.sv_done)


                    follow_ups_for_week = self.calculate_follow_ups_count(total_leads_cm, "Last_7_Days")
                    client_attended_weekly = site_visits_this_week.filter(site_visit_status="Site Visit Done").count()

                    weekly_booking_count = total_leads_cm.filter(
                        projectinventory__status="Booked",
                        projectinventory__booked_on__range=[start_of_week, today]
                    ).count()

                    # Day and Summary
                    total_cm_leads = Lead.objects.filter(
                        sitevisit__closing_manager=cm_instance,
                        sitevisit__visit_date=today  # Filter by today's date
                    ).distinct()

                    # Annotate the number of site visits marked as "Site Visit Done" for today
                    queryset = total_cm_leads.annotate(
                        sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done"))
                    )

                    # Filter leads where more than one site visit was done today
                    sv_data = queryset.filter(sv_done__gt=1)

                    # Calculate the revisit count for today
                    revisit_count_today = 0
                    for lead in sv_data:
                        revisit_count_today += (lead.sv_done - 1)
                        print("Lead ID:", lead.id, "Site Visits Done:", lead.sv_done)

                    site_visits_today = SiteVisit.objects.filter(visit_date=current_date, lead__in=total_leads_cm_nd)
                    follow_ups_for_day = self.calculate_follow_ups_count(total_leads_cm,"Today")
                   
                    missed_follow_ups_for_day =self.calculate_follow_ups_count(total_leads_cm, "Missed_Today")

                    
                    #Summary of the day
                    client_attended_for_day = site_visits_today.filter(site_visit_status="Site Visit Done").count()
                    booking_count_today = total_leads_cm.filter(projectinventory__status="Booked", projectinventory__booked_on__range=(today_start, today_end)).count()
                    total_summary_count = client_attended_for_day + booking_count_today + follow_ups_for_day
                    booking_done_percentage = round(booking_count_today /  total_summary_count * 100, 2) if  total_summary_count > 0 else 0
                    client_attended_percentage = round(client_attended_for_day /  total_summary_count * 100, 2) if  total_summary_count > 0 else 0
                    follow_ups_percentage = round(follow_ups_for_day /  total_summary_count * 100, 2) if  total_summary_count > 0 else 0

                    #Yesterday View
                    site_visits_yesterday_data = SiteVisit.objects.filter(
                        visit_date=yesterday_date,
                        lead__in=total_leads_cm_nd
                    )
                    site_visits_yesterday = site_visits_yesterday_data.filter(visit_date=yesterday_date)
                    clients_attended_yesterday = site_visits_yesterday.filter(site_visit_status="Site Visit Done").count()
                    missed_follow_ups_yesterday = self.calculate_follow_ups_count(total_leads_cm,"Missed_Yesterday")
                    total_data_yesterday = clients_attended_yesterday + missed_follow_ups_yesterday

                    summary = {
                        "day_view": {
                            "revisit_scheduled_for_day": revisit_count_today,
                            "follow_ups_for_day": follow_ups_for_day,
                            "missed_follow_ups": missed_follow_ups_for_day
                        },
                        "day_summary": {
                            "follow_ups_today": follow_ups_for_day,
                            "follow_ups_percentage": follow_ups_percentage,
                            "client_attended_today": client_attended_for_day,
                            "client_attended_percentage": client_attended_percentage,
                            "booking_done_percentage": booking_done_percentage,
                            "booking_count_today": booking_count_today
                        },
                        "yesterday_view": {
                            "total_data_yesterday": total_data_yesterday,
                            "client_attended_yesterday": clients_attended_yesterday,
                            "client_attended_yesterday_percentage": round(clients_attended_yesterday / total_data_yesterday * 100, 2) if total_data_yesterday > 0 else 0,
                            "missed_follow_ups_yesterday": missed_follow_ups_yesterday,
                            "missed_follow_ups_yesterday_percentage": round(missed_follow_ups_yesterday / total_data_yesterday * 100, 2) if total_data_yesterday > 0 else 0
                        },
                        "weekly_summary": {
                            "follow_ups_done_weekly": follow_ups_for_week,
                            "revisit_count_weekly": revisit_count_week,
                            "client_attended_weekly": client_attended_weekly,
                            "booking_done_weekly": weekly_booking_count
                        }
                    }
                    return ResponseHandler(False, "Summary data for Closing DashBoard", summary,200) 
               
                else:
                    return ResponseHandler(True, "Provide Closing Manager Id", None,400) 
        
            elif query_param == 'SOURCING':
                
                # first find lead created by channel partner
                leads_with_channel_partner = Lead.objects.filter(channel_partner__isnull=False)
               
                total_queryset_count = leads_with_channel_partner.count()
                
                # lead info
                new_leads_count = leads_with_channel_partner.filter(lead_status = 'New').count()
                hot_leads_count = leads_with_channel_partner.filter(lead_status='Hot').count()
                cold_leads_count = leads_with_channel_partner.filter(lead_status='Cold').count()
                warm_leads_count = leads_with_channel_partner.filter(lead_status='Warm').count()
                lost_leads_count = leads_with_channel_partner.filter(lead_status='Lost').count()

                # Today meetings data
                today = date.today()
                yesterday = date.today() - timedelta(days=1)
                no_of_meetings_today = Meeting.objects.filter(date=today).count()
                # fresh_meetings_today = Meeting.objects.filter(date=today).annotate(
                #     previous_meetings=Count('channel_partner__meeting', filter=Q(channel_partner__meeting__date__lt=today))
                # ).filter(previous_meetings=0).count()
                fresh_meetings_today = Meeting.objects.filter(date=today).exclude(
                    channel_partner__meetings__date__lt=today
                ).count()
                revisit_meetings_today = no_of_meetings_today - fresh_meetings_today
                no_of_meetings_today_percentage = round((no_of_meetings_today / no_of_meetings_today * 100), 2) if no_of_meetings_today > 0 else 0
                fresh_meetings_today_percentage = round((fresh_meetings_today / no_of_meetings_today * 100), 2) if no_of_meetings_today > 0 else 0
                revisit_meetings_today_percentage = round((revisit_meetings_today / no_of_meetings_today * 100), 2) if no_of_meetings_today > 0 else 0

                # Yesterday meeting data
                no_of_meetings_yesterday = Meeting.objects.filter(date=yesterday).count()
                # fresh_meetings_yesterday = Meeting.objects.filter(date=yesterday).annotate(
                #     previous_meetings=Count('channel_partner__meeting', filter=Q(channel_partner__meeting__date__lt=yesterday))
                # ).filter(previous_meetings=0).count()
                fresh_meetings_yesterday = Meeting.objects.filter(date=yesterday).exclude(
                    channel_partner__meetings__date__lt=yesterday
                ).count()
                revisit_meetings_yesterday = no_of_meetings_yesterday - fresh_meetings_yesterday
                sales_payments_pending = Payment.objects.filter(payment_to='Sales', status='Approval Pending')
                brokerage_bills_to_be_paid = sales_payments_pending.aggregate(total_amount=Sum('amount'))['total_amount']
                sales_payments_paid = Payment.objects.filter(payment_to='Sales', status='Payment Done')
                brokerage_paid = sales_payments_paid.aggregate(total_amount=Sum('amount'))['total_amount']
                

                # If time factor also need to be added
                # now = timezone.now()

                # # Calculate the first day of the current month
                # start_of_current_month = now.replace(day=1)

                # # Calculate the last day of the previous month
                # end_of_last_month = start_of_current_month - timedelta(days=1)

                # # Calculate the first day of the last month
                # start_of_last_month = end_of_last_month.replace(day=1)

                # pin_code_counts = ChannelPartner.objects.filter(
                #     created_on__gte=start_of_last_month,
                #     created_on__lte=now
                # ).values('pin_code').annotate(count=Count('id'))
                
                # pin_code_counts = ChannelPartner.objects.exclude(pin_code__isnull=True).values('pin_code').annotate(count=Count('id'))
                # region_wise_cp_data = {}

                # for entry in pin_code_counts:
                #     pin_code = entry['pin_code']
                #     count = entry['count']
                #     # percentage = (count / total_cp_count) * 100
                
                #     city = self.fetch_city_from_pincode(pin_code)  # Fetch city using the API
                    
                #     if city:
                #         region_key = city
                #     else:
                #         continue  # Skip if city cannot be determined
                    
                #     if region_key in region_wise_cp_data:
                #         region_wise_cp_data[region_key]['count'] += count
                #        # region_wise_cp_data[region_key]['percentage'] = (region_wise_cp_data[region_key]['count'] / total_cp_count) * 100
                #     else:
                #         region_wise_cp_data[region_key] = {
                #             'count': count,
                #            # 'percentage': percentage,
                #             'color': self.generate_color(region_key)
                #         }
                # region_wise_cp_list = [
                #     {
                #         'name': region,
                #         'count': data['count'],
                #        # 'percentage': round(data['percentage'], 2),
                #         'color': data['color']
                #     }
                #     for region, data in region_wise_cp_data.items()
                # ]

                # total_region_wise_cp_count = sum(item['count'] for item in region_wise_cp_list)

                # for item in region_wise_cp_list:
                #     item['percentage'] = round((item['count'] / total_region_wise_cp_count) * 100, 2) if total_region_wise_cp_count > 0 else 0
                pin_code_counts = ChannelPartner.objects.exclude(pin_code__isnull=True).values('pin_code', 'location').annotate(count=Count('id'))

                region_wise_cp_data = {}

                for entry in pin_code_counts:
                    pin_code = entry['pin_code']
                    location = entry['location']
                    count = entry['count']

                    if location:
                        region_key = location  # Use location directly from the model
                    else:
                        continue  # Skip if location is not available
                    
                    if region_key in region_wise_cp_data:
                        region_wise_cp_data[region_key]['count'] += count
                    else:
                        region_wise_cp_data[region_key] = {
                            'count': count,
                            'color': self.generate_color(region_key)
                        }

                # Convert region-wise CP data into a list format
                region_wise_cp_list = [
                    {
                        'name': region,
                        'count': data['count'],
                        'color': data['color']
                    }
                    for region, data in region_wise_cp_data.items()
                ]

                # Calculate the total count for all regions
                total_region_wise_cp_count = sum(item['count'] for item in region_wise_cp_list)

                # Calculate the percentage for each region
                for item in region_wise_cp_list:
                    item['percentage'] = round((item['count'] / total_region_wise_cp_count) * 100, 2) if total_region_wise_cp_count > 0 else 0

                
                #To find active and inactive channel partners

               # three_months_ago = timezone.now() - timedelta(days=90)

                # total_cp_count = ChannelPartner.objects.all().count()

                # # Annotate ChannelPartner with the count of related booked ProjectInventory entries
                # channel_partner_counts = ChannelPartner.objects.filter(
                #     lead__projectinventory__status="Booked",
                #    # lead__projectinventory__booked_on__gte=three_months_ago
                #    # lead__projectinventory__inventorycostsheet__completed_at__range=(three_months_ago, timezone.now())
                # ).annotate(
                #     booked_count=Count('lead__projectinventory')
                # )

                three_months_ago = timezone.now() - timedelta(days=90)
                total_cp_count = ChannelPartner.objects.exclude(
                    Q(full_name__isnull=True) & 
                    Q(primary_email__isnull=True) & 
                    Q(address__isnull=True) & 
                    Q(pin_code__isnull=True)
                ).distinct().count()

                # Queryset for active CPs within the last 5 minutes
                active_cps = ChannelPartner.objects.filter(
                    Q(created_on__gte=three_months_ago) |  # Created within the last 90 days
                    Q(lead__projectinventory__status="Booked", lead__projectinventory__booked_on__gte=three_months_ago)  # At least one booking in the last 3 months
                ).exclude(
                    Q(full_name__isnull=True) & 
                    Q(primary_email__isnull=True) & 
                    Q(address__isnull=True) & 
                    Q(pin_code__isnull=True)
                ).distinct()

                print("Channel partner those having booking",active_cps)
                print("active_channel_partner",active_cps.count())

                active_channel_partners = active_cps.count()

                # Find all Channel Partners without bookings in the last three months
                inactive_channel_partners = total_cp_count - active_channel_partners

                summary = {
                    "total_leads_count": total_queryset_count,
                    "new_leads_count" : new_leads_count,
                    "new_leads_percentage" : round(new_leads_count / total_queryset_count * 100 ,2) if total_queryset_count > 0 else 0,
                    "hot_leads_count": hot_leads_count,
                    "hot_leads_percentage" : round(hot_leads_count / total_queryset_count * 100 ,2) if total_queryset_count > 0 else 0,
                    "cold_leads_count": cold_leads_count,
                    "cold_leads_percentage" : round(cold_leads_count / total_queryset_count * 100 ,2) if total_queryset_count > 0 else 0,
                    "warm_leads_count": warm_leads_count,
                    "warm_leads_percentage" : round(warm_leads_count / total_queryset_count * 100 ,2) if total_queryset_count > 0 else 0,
                    "lost_leads_count": lost_leads_count,
                    "lost_leads_percentage" : round(lost_leads_count / total_queryset_count * 100 ,2) if total_queryset_count > 0 else 0,
                    'no_of_meetings_today': no_of_meetings_today,
                    'fresh_meetings_today': fresh_meetings_today,
                    'revisit_meetings_today': revisit_meetings_today,
                    'no_of_meetings_today_percentage': no_of_meetings_today_percentage,
                    'fresh_meetings_today_percentage': fresh_meetings_today_percentage,
                    'revisit_meetings_today_percentage': revisit_meetings_today_percentage,
                    'no_of_meetings_yesterday': no_of_meetings_yesterday,
                    'fresh_meetings_yesterday': fresh_meetings_yesterday,
                    'revisit_meetings_yesterday': revisit_meetings_yesterday,
                    'brokerage_bills_submitted': Payment.objects.filter(payment_to='Sales').count(),
                    'brokerage_bills_to_be_paid': brokerage_bills_to_be_paid if brokerage_bills_to_be_paid else 0,
                    'brokerage_paid':brokerage_paid if brokerage_paid else 0 ,
                    'total_region_wise_cp_count' : total_region_wise_cp_count,
                    'region_wise_cp_data':region_wise_cp_list,
                    "total_active_inactive_cps" : active_channel_partners + inactive_channel_partners,
                    'active_cps':active_channel_partners,
                    'active_cps_percentage' : round(active_channel_partners / total_cp_count * 100 ,2) if total_queryset_count > 0 else 0,
                    'inactive_cps' : inactive_channel_partners,
                    'inactive_cps_percentage' : round(inactive_channel_partners / total_cp_count * 100 ,2) if total_queryset_count > 0 else 0  
                }

                return ResponseHandler(False, "Summary data", summary,200) 

            elif query_param == 'SOURCING_MANAGER': 
                if sourcing_manager_param is not None:     
                    sm_instance = Users.objects.get(id=sourcing_manager_param)
                    print(sm_instance)
                    stage = Stage.objects.filter(name='Sales').first()

                    queryset = Lead.objects.filter(sitevisit__sourcing_manager=sm_instance ).distinct()

                    # postsales_stage = Stage.objects.filter(name='PostSales').first()
                    # queryset = Lead.objects.filter(sitevisit__closing_manager=cm_instance).exclude(workflow__current_stage=postsales_stage.order).order_by('-created_on') 

                    print("queryset",queryset)    
                    total_queryset_count = queryset.count()
                    print("total_queryset_count",total_queryset_count)

                    new_leads_count = queryset.filter(lead_status = "New").count()

                    hot_leads_count = queryset.filter(lead_status='Hot').count()

                    cold_leads_count = queryset.filter(lead_status='Cold').count()

                    warm_leads_count = queryset.filter(lead_status='Warm').count()

                    lost_leads_count = queryset.filter(lead_status='Lost').count()

                   
                    total_cm_leads = Lead.objects.filter(sitevisit__sourcing_manager=sm_instance ).distinct()

                   # revisit_count = queryset.annotate(num_site_visits=Count('sitevisit', distinct=True)).filter(num_site_visits__gt=1).count()  #include 
                    queryset = total_cm_leads.annotate(sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done")))
                    sv_data = queryset.filter(sv_done__gt=1)
                    revisit_count = 0
                    for lead in sv_data:
                       revisit_count += (lead.sv_done -1)
                       print("Lead ID:", lead.id, "Site Visits Done:", lead.sv_done)

                    booking_count = total_cm_leads.filter(projectinventory__status="Booked").count() 
                   

                    total_count = hot_leads_count + cold_leads_count + warm_leads_count + lost_leads_count + revisit_count + booking_count
                    
                   # new_leads_percentage = (new_leads_count / total_count *100) if total_count > 0 else 0
                    hot_leads_percentage = round(hot_leads_count / total_count * 100 , 2) if total_count > 0 else 0
                    cold_leads_percentage = round(cold_leads_count / total_count * 100 , 2) if total_count > 0 else 0
                    warm_leads_percentage = round(warm_leads_count / total_count * 100 , 2) if total_count > 0 else 0
                    lost_leads_percentage = round(lost_leads_count / total_count * 100, 2) if total_count > 0 else 0
                    revisit_percentage = round(revisit_count / total_count * 100 , 2) if total_count > 0 else 0
                    booking_percentage = round(booking_count / total_count * 100 , 2)  if total_count > 0 else 0

                    summary = {
                        #"total_leads_count": total_queryset_count,
                        "total_count" : total_count,
                        # "new_leads_count" : new_leads_count,
                        # "new_leads_percentage" : new_leads_percentage,
                        "hot_leads_count": hot_leads_count,
                        "hot_leads_percentage": hot_leads_percentage,
                        "cold_leads_count": cold_leads_count,
                        "cold_leads_percentage": cold_leads_percentage,
                        "warm_leads_count": warm_leads_count,
                        "warm_leads_percentage": warm_leads_percentage,
                        "lost_leads_count": lost_leads_count,
                        "lost_leads_percentage": lost_leads_percentage,
                        #"reschedule_data" : reschedule_counts,
                        "revisit_count": revisit_count,
                        "revisit_percentage": revisit_percentage,
                        "booking_count": booking_count,
                        "booking_percentage": booking_percentage
                    }
    

                    return ResponseHandler(False, "Summary data for Sourcing", summary,200) 
                else:
                    return ResponseHandler(True, "Provide sourcing manager id", None,200)
            elif query_param == 'SOURCING_MANAGER_DASHBOARD':
                if sourcing_manager_param is not None:    
                    sm_instance = Users.objects.get(id=sourcing_manager_param)
                    print(sm_instance)

                    stage = Stage.objects.filter(name='Sales').first()

                    queryset = Lead.objects.filter(workflow__current_stage=stage.order, sitevisit__sourcing_manager=sm_instance)
                    print("querysetcount", queryset.count())

                    current_date = timezone.now().date()
                    yesterday_date = current_date - timedelta(days=1)
                    start_date = current_date - timedelta(days=7)
                    today = timezone.now().date()
                    start_of_week = today - timedelta(days=today.weekday() + 7)  
                    end_of_week = start_of_week + timedelta(days=6)  
                    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    today_end = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)

                    # Weekly
                    total_leads_cm =Lead.objects.filter(sitevisit__sourcing_manager=sm_instance).distinct()
                    total_leads_cm_nd = Lead.objects.filter(sitevisit__sourcing_manager=sm_instance)
                    site_visits_this_week = SiteVisit.objects.filter(
                        visit_date__range=(start_date, current_date),
                        lead__in=total_leads_cm
                    )

                    print("site visit queryset", list(site_visits_this_week.values()))
                    print("site_visit_this_week_count", site_visits_this_week.count())


                    total_cm_leads = Lead.objects.filter(
                        sitevisit__sourcing_manager=sm_instance,
                        sitevisit__visit_date__range=[start_of_week, today]  # Filter by date range
                    ).distinct()

                    # Annotate the number of site visits marked as "Site Visit Done" within the date range
                    queryset = total_cm_leads.annotate(
                        sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done"))
                    )

                    # Filter leads where more than one site visit was done
                    sv_data = queryset.filter(sv_done__gt=1)

                    # Calculate the revisit count
                    revisit_count_week = 0
                    for lead in sv_data:
                        revisit_count_week += (lead.sv_done - 1)
                        print("Lead ID:", lead.id, "Site Visits Done:", lead.sv_done)


                    follow_ups_for_week = self.calculate_follow_ups_count(total_leads_cm, "Last_7_Days")
                    client_attended_weekly = site_visits_this_week.filter(site_visit_status="Site Visit Done").count()

                    weekly_booking_count = total_leads_cm.filter(
                        projectinventory__status="Booked",
                        projectinventory__booked_on__range=[start_of_week, today]
                    ).count()

                    # Day and Summary
                    total_cm_leads = Lead.objects.filter(
                        sitevisit__sourcing_manager=sm_instance,
                        sitevisit__visit_date=today  # Filter by today's date
                    ).distinct()

                    # Annotate the number of site visits marked as "Site Visit Done" for today
                    queryset = total_cm_leads.annotate(
                        sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done"))
                    )

                    # Filter leads where more than one site visit was done today
                    sv_data = queryset.filter(sv_done__gt=1)

                    # Calculate the revisit count for today
                    revisit_count_today = 0
                    for lead in sv_data:
                        revisit_count_today += (lead.sv_done - 1)
                        print("Lead ID:", lead.id, "Site Visits Done:", lead.sv_done)

                    site_visits_today = SiteVisit.objects.filter(visit_date=current_date, lead__in=total_leads_cm_nd)
                    follow_ups_for_day = self.calculate_follow_ups_count(total_leads_cm,"Today")
                   
                    missed_follow_ups_for_day =self.calculate_follow_ups_count(total_leads_cm, "Missed_Today")

                    
                    #Summary of the day
                    client_attended_for_day = site_visits_today.filter(site_visit_status="Site Visit Done").count()
                    booking_count_today = total_leads_cm.filter(projectinventory__status="Booked", projectinventory__booked_on__range=(today_start, today_end)).count()
                    total_summary_count = client_attended_for_day + booking_count_today + follow_ups_for_day
                    booking_done_percentage = round(booking_count_today /  total_summary_count * 100, 2) if  total_summary_count > 0 else 0
                    client_attended_percentage = round(client_attended_for_day /  total_summary_count * 100, 2) if  total_summary_count > 0 else 0
                    follow_ups_percentage = round(follow_ups_for_day /  total_summary_count * 100, 2) if  total_summary_count > 0 else 0

                    #Yesterday View
                    site_visits_yesterday_data = SiteVisit.objects.filter(
                        visit_date=yesterday_date,
                        lead__in=total_leads_cm_nd
                    )
                    site_visits_yesterday = site_visits_yesterday_data.filter(visit_date=yesterday_date)
                    clients_attended_yesterday = site_visits_yesterday.filter(site_visit_status="Site Visit Done").count()
                    missed_follow_ups_yesterday = self.calculate_follow_ups_count(total_leads_cm,"Missed_Yesterday")
                    total_data_yesterday = clients_attended_yesterday + missed_follow_ups_yesterday

                    summary = {
                        "day_view": {
                            "revisit_scheduled_for_day": revisit_count_today,
                            "follow_ups_for_day": follow_ups_for_day,
                            "missed_follow_ups": missed_follow_ups_for_day
                        },
                        "day_summary": {
                            "follow_ups_today": follow_ups_for_day,
                            "follow_ups_percentage": follow_ups_percentage,
                            "client_attended_today": client_attended_for_day,
                            "client_attended_percentage": client_attended_percentage,
                            "booking_done_percentage": booking_done_percentage,
                            "booking_count_today": booking_count_today
                        },
                        "yesterday_view": {
                            "total_data_yesterday": total_data_yesterday,
                            "client_attended_yesterday": clients_attended_yesterday,
                            "client_attended_yesterday_percentage": round(clients_attended_yesterday / total_data_yesterday * 100, 2) if total_data_yesterday > 0 else 0,
                            "missed_follow_ups_yesterday": missed_follow_ups_yesterday,
                            "missed_follow_ups_yesterday_percentage": round(missed_follow_ups_yesterday / total_data_yesterday * 100, 2) if total_data_yesterday > 0 else 0
                        },
                        "weekly_summary": {
                            "follow_ups_done_weekly": follow_ups_for_week,
                            "revisit_count_weekly": revisit_count_week,
                            "client_attended_weekly": client_attended_weekly,
                            "booking_done_weekly": weekly_booking_count
                        }
                    }
                    return ResponseHandler(False, "Summary data for Sourcing Manager", summary,200)
                else:
                    return ResponseHandler(True, "Provide sourcing manager id", None ,400)   
            else:
                return ResponseHandler(True, "Invalid query_param", '',400) 
        except Exception as e:
            return ResponseHandler(True, str(e), '', 500) 

# from .serializers import InventorySerializer, BookingFormSerializer, CollectTokenSerializer
# from .models import Project, Inventory, BookingForm, CollectToken
# # Create your views here.
# from rest_framework import generics
# from rest_framework.generics import CreateAPIView
# from rest_framework.permissions import IsAuthenticated

# from auth.utils import ResponseHandler
# from rest_framework import status

# class InventoryCreateView(CreateAPIView):
#     serializer_class = InventorySerializer
#     permission_classes = (IsAuthenticated,)
     
#     def create(self, request, *args, **kwargs):
#         project_data = request.data["project"]
#         print(project_data)
#         if isinstance(project_data,str):
#             project, created = Project.objects.get_or_create(name=project_data)
#             request.data["project"]=project.id
#         print(request.data)
#         print(request)
#         serializer = self.get_serializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False,"Inventory is created", serializer.data, status.HTTP_201_CREATED)
#         else:
#             return ResponseHandler(True,"There is an Error in code",serializer.errors, status.HTTP_400_BAD_REQUEST)
        

#     def get(self, request, *args, **kwargs):

#         queryset = Inventory.objects.all()
#         if queryset.exists():
#             serializer = self.get_serializer(queryset,many=True)
#             return ResponseHandler(False,"Inventory Data",serializer.data,status.HTTP_200_OK)
#         else:
#             return ResponseHandler(False, "There is no inventory data",[], status.HTTP_400_BAD_REQUEST)
        
        
# class InventoryDetailApiView(generics.RetrieveUpdateDestroyAPIView):
#     serializer_class = InventorySerializer
#     permission_classes = (IsAuthenticated,)
#     queryset = Inventory.objects.all()

#     def get(self, request, *args, **kwargs):
#        inventory_id = self.kwargs.get('pk')
#        queryset = Inventory.objects.filter(pk=inventory_id)
#        try:
#             instance = Inventory.objects.get(pk=inventory_id)
#             serializer = self.get_serializer(instance)
#             return ResponseHandler(False, 'Inventory retrieved successfully', serializer.data, status.HTTP_200_OK)
#        except Inventory.DoesNotExist:
#             return ResponseHandler(True, 'Inventory ID not found', None, status.HTTP_404_NOT_FOUND)

#     def put(self,request, *args, **kwargs):
#         inventory_id = self.kwargs.get('pk')
#         try:
#             instance = self.queryset.get(pk=inventory_id)
#         except Inventory.DoesNotExist:
#             return  ResponseHandler(True, 'Inventory not found', None, status.HTTP_404_NOT_FOUND)
        
#         serializer = self.get_serializer(instance, data=request.data)

#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False , 'Data updated successfully' , serializer.data,status.HTTP_200_OK)
#         else:
#             return ResponseHandler(True, 'Validation error.' , serializer.errors, status.HTTP_400_BAD_REQUEST)

#     def delete(self, request, *args, **kwargs):
#         inventory_id = self.kwargs.get('pk')
#         try:
#             instance = Inventory.objects.get(pk=inventory_id)
#             self.perform_destroy(instance)
#             return ResponseHandler(False, 'Inventory deleted successfully' , None,status.HTTP_204_NO_CONTENT)
#         except Inventory.DoesNotExist:
#             return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND)
   
# from rest_framework.response import Response
# class BookingFormCreateView(CreateAPIView):
#     serializer_class = BookingFormSerializer
#     permission_classes = (IsAuthenticated,)
     
#     def create(self, request, *args, **kwargs):

#         serializer = self.get_serializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             #next_view_link = "/api/collecttoken/"
#             #return Response({"next_view": next_view_link}, status=status.HTTP_201_CREATED)
#             #return redirect('collecttoken-create')
#             return ResponseHandler(False," BookingForm is created", serializer.data, status.HTTP_201_CREATED)
#         else:
#             return ResponseHandler(True,"There is an Error in code",serializer.errors, status.HTTP_400_BAD_REQUEST)
        
#     def get(self, request, *args, **kwargs):

#         queryset = BookingForm.objects.all()
#         if queryset.exists():
#             serializer = self.get_serializer(queryset,many=True)
#             return ResponseHandler(False,"Booking Form Data",serializer.data,status.HTTP_200_OK)
#         else:
#             return ResponseHandler(False, "There is no booking form data",[], status.HTTP_400_BAD_REQUEST)


# class BookingFormDetailApiView(generics.RetrieveUpdateDestroyAPIView):
#     serializer_class = BookingFormSerializer
#     permission_classes = (IsAuthenticated,)
#     queryset = BookingForm.objects.all()

#     def get(self, request, *args, **kwargs):
#        bookingform_id = self.kwargs.get('pk')
#        queryset = BookingForm.objects.filter(pk=bookingform_id)
#        try:
#             instance = BookingForm.objects.get(pk=bookingform_id)
#             serializer = self.get_serializer(instance)
#             return ResponseHandler(False, 'BookingForm retrieved successfully', serializer.data, status.HTTP_200_OK)
#        except BookingForm.DoesNotExist:
#             return ResponseHandler(True, 'BookingForm ID not found', None, status.HTTP_404_NOT_FOUND)

#     def put(self,request, *args, **kwargs):
#         bookingform_id = self.kwargs.get('pk')
#         try:
#             instance = self.queryset.get(pk=bookingform_id)
#         except BookingForm.DoesNotExist:
#             return  ResponseHandler(True, 'BookingForm not found', None, status.HTTP_404_NOT_FOUND)
        
#         serializer = self.get_serializer(instance, data=request.data)

#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False , 'Data updated successfully' , serializer.data,status.HTTP_200_OK)
#         else:
#             return ResponseHandler(True, 'Validation error.' , serializer.errors, status.HTTP_400_BAD_REQUEST)

#     def delete(self, request, *args, **kwargs):
#         bookingform_id = self.kwargs.get('pk')
#         try:
#             instance = BookingForm.objects.get(pk=bookingform_id)
#             self.perform_destroy(instance)
#             return ResponseHandler(False, 'BookingForm deleted successfully' , None,status.HTTP_204_NO_CONTENT)
#         except BookingForm.DoesNotExist:
#             return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND)    

# class CollectTokenCreateView(CreateAPIView):
#     serializer_class = CollectTokenSerializer
#     permission_classes = (IsAuthenticated,)
     
#     def create(self, request, *args, **kwargs):

#         serializer = self.get_serializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False," CollectToken is created", serializer.data, status.HTTP_201_CREATED)
#         else:
#             return ResponseHandler(True,"There is an Error in code",serializer.errors, status.HTTP_400_BAD_REQUEST) 

#     def get(self, request, *args, **kwargs):

#         queryset = CollectToken.objects.all()
#         if queryset.exists():
#             serializer = self.get_serializer(queryset,many=True)
#             return ResponseHandler(False,"Collect Token Data",serializer.data,status.HTTP_200_OK)
#         else:
#             return ResponseHandler(True, "There is no Collect Token form data",None, status.HTTP_400_BAD_REQUEST)


# class CollectTokenDetailApiView(generics.RetrieveUpdateDestroyAPIView):
#     serializer_class = CollectTokenSerializer
#     permission_classes = (IsAuthenticated,)
#     queryset = CollectToken.objects.all()

#     def get(self, request, *args, **kwargs):
#        CollectToken_id = self.kwargs.get('pk')
#        queryset = CollectToken.objects.filter(pk=CollectToken_id)
#        try:
#             instance = CollectToken.objects.get(pk=CollectToken_id)
#             serializer = self.get_serializer(instance)
#             return ResponseHandler(False, 'CollectToken retrieved successfully', serializer.data, status.HTTP_200_OK)
#        except CollectToken.DoesNotExist:
#             return ResponseHandler(True, 'CollectToken ID not found', None, status.HTTP_404_NOT_FOUND)

#     def put(self,request, *args, **kwargs):
#         CollectToken_id = self.kwargs.get('pk')
#         try:
#             instance = self.queryset.get(pk=CollectToken_id)
#         except CollectToken.DoesNotExist:
#             return  ResponseHandler(True, 'CollectToken not found', None, status.HTTP_404_NOT_FOUND)
        
#         serializer = self.get_serializer(instance, data=request.data)

#         if serializer.is_valid():
#             serializer.save()
#             return ResponseHandler(False , 'Data updated successfully' , serializer.data,status.HTTP_200_OK)
#         else:
#             return ResponseHandler(True, 'Validation error.' , serializer.errors, status.HTTP_400_BAD_REQUEST)

#     def delete(self, request, *args, **kwargs):
#         CollectToken_id = self.kwargs.get('pk')
#         try:
#             instance = CollectToken.objects.get(pk=CollectToken_id)
#             self.perform_destroy(instance)
#             return ResponseHandler(False, 'CollectToken deleted successfully' , None,status.HTTP_204_NO_CONTENT)
#         except CollectToken.DoesNotExist:
#             return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND)  
        
class LocationByPincodeView(APIView):
    def get(self, request, pincode):
        api_url = f'https://api.postalpincode.in/pincode/{pincode}'
        response = requests.get(api_url)

        if response.status_code == 200:
            data = response.json()

            if data and data[0]["Status"] == "Success" and data[0]["PostOffice"]:
                post_office = data[0]["PostOffice"][0]

                city = post_office.get("District", "")
                state = post_office.get("State", "")

                # Use your ResponseHandler here
                response_data = {"city": city, "state": state}
                return ResponseHandler(False, "Data fetched successfully", response_data, status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Invalid or no data for the given pincode", None, status.HTTP_404_NOT_FOUND)
        else:
            return ResponseHandler(True, "Error fetching data from the external API", None, response.status_code)


class CheckLeadExists(APIView):
    def get(self, request):
        phone_number = request.query_params.get('phone_number', None)
        if phone_number:
            try:
                lead = Lead.objects.filter(primary_phone_no=phone_number).first()
                if lead:
                    get_receptionist_users = Users.objects.filter(groups__name="RECEPTIONIST")
                    for receptionist_user in get_receptionist_users:
                        title = "Lead Already Exists"
                        body = f"Lead with lead id {lead.id} already exists  "
                        data = {'notification_type': 'new_lead', 'redirect_url': f'/sales/lead_verification/{lead.id}'}

                        fcm_token = receptionist_user.fcm_token

                        Notifications.objects.create(notification_id=f"lead-{lead.id}-{receptionist_user.id}", user_id=receptionist_user,created=timezone.now(), notification_message=body, notification_url=f'/sales/lead_verification/{lead.id}')

                        send_push_notification(fcm_token, title, body, data) 
                    return ResponseHandler(False, "Lead Exists", True, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, "Lead Does Not Exist", False, status.HTTP_404_NOT_FOUND)
            except Exception as e:
                return ResponseHandler(True, str(e), '', 500)    
        else:
            return ResponseHandler(True, "Please Provide Phone Number", None, status.HTTP_400_BAD_REQUEST)




class SalesSummaryAPIView(APIView): 
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

            def calculate_all_follow_ups(lead):
                print("Lead:", lead)
                workflow = lead.workflow.get()
                followup_tasks = workflow.tasks.filter(name='Follow Up')
                count = followup_tasks.count()
                print("Total follow-ups count (no date filter):", count)
                return count    
           
            if follow_ups_filter_param == 'Today':
               # queryset = [lead for lead in queryset if (calculate_next_follow_up_today(lead) is not None) and calculate_next_follow_up(lead) == timezone.now().date()]
                queryset =  sum(calculate_next_follow_up_today(lead) for lead in queryset)
                print("today",queryset)
            elif follow_ups_filter_param == 'Missed_Last_7_Days':
                queryset =   sum(calculate_missed_follow_ups_last_seven_days(lead) for lead in queryset)
            elif follow_ups_filter_param == 'Missed_Today':  
                queryset = sum(calculate_missed_follow_ups_today(lead) for lead in queryset)
                print("missed today",queryset)
            elif follow_ups_filter_param == 'Last_7_Days':
                queryset = sum( calculate_next_follow_up_last_seven_days(lead) for lead in queryset)
            elif follow_ups_filter_param == 'All':
                queryset = sum(calculate_all_follow_ups(lead) for lead in queryset)    
            # return len(queryset)
            return queryset



    @check_access(required_groups=["ADMIN","PROMOTER","VICE_PRESIDENT","SITE_HEAD","CLOSING_MANAGER","SOURCING_MANAGER"])
    def get(self, request):
        try:
            date_range_param = request.GET.get('date_range', None)
            module_param = request.GET.get('module', None)

            if module_param == "PRESALES": 
                cce_param = request.GET.get('user_id',None)

                stage = Stage.objects.filter(name='PreSales').first()
                presales_queryset = Lead.objects.filter(workflow__current_stage=stage.order).distinct()
                if cce_param :
                    presales_queryset = Lead.objects.filter(Q(workflow__current_stage=stage.order) & (Q(workflow__stages__assigned_to_id=cce_param) | Q(creator_id=cce_param))).distinct()
                print(presales_queryset.count())

                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    presales_queryset = presales_queryset.filter(created_on__gte=seven_days_ago)
                    print(presales_queryset.count())
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    presales_queryset = presales_queryset.filter(created_on__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    presales_queryset = presales_queryset.filter(created_on__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    presales_queryset = presales_queryset.filter(created_on__gte=six_months_ago)

                clicktocalldid = "8037898286"

                primary_phone_numbers = presales_queryset.values_list('primary_phone_no', flat=True)

                leads_connected= LeadCallsMcube.objects.filter(
                    Q(request_body__contains={"clicktocalldid": clicktocalldid}) &
                    Q(call_type='OUTGOING') &
                    Q(call_status='ANSWER') &
                    Q(lead_phone__in=primary_phone_numbers)
                ).values('lead_phone').distinct()

                leads_not_connected = LeadCallsMcube.objects.filter(
                    Q(request_body__contains={"clicktocalldid": clicktocalldid}) &
                    Q(call_type='OUTGOING') &
                    Q(call_status='BUSY') &
                    Q(lead_phone__in=primary_phone_numbers)
                ).exclude(lead_phone__in=leads_connected.values('lead_phone')).values('lead_phone').distinct()

                # leads_with_followup_task_not_completed_count = 0

                # for lead in presales_queryset:
                #     workflow = lead.workflow.get()
                #     followup_task = workflow.tasks.filter(name='Follow Up').order_by('-time').first()
                #     if followup_task:
                #         leads_with_followup_task_not_completed_count += 1
                

                total_leads = Lead.objects.filter(creation_stage="PreSales")
                if cce_param:
                    total_leads = Lead.objects.filter(Q(creation_stage="PreSales") & (Q(workflow__stages__assigned_to_id=cce_param) | Q(creator_id=cce_param))).distinct()

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

                leads_with_followup_task_not_completed_count  = self.calculate_follow_ups_count(total_leads,"All")
                print(leads_with_followup_task_not_completed_count)


                hot_leads = presales_queryset.filter(lead_status='Hot')
                warm_leads = presales_queryset.filter(lead_status='Warm')
                cold_leads = presales_queryset.filter(lead_status='Cold')
                lost_leads = presales_queryset.filter(lead_status='Lost')
                new_leads = presales_queryset.filter(lead_status = 'New')


                total_reschedule_count = 0
                reschedule_counts = {}
                total_leads_presales = Lead.objects.filter(creation_stage = "PreSales")
                if cce_param:
                    total_leads_presales = Lead.objects.filter(Q(creation_stage="PreSales") & (Q(workflow__stages__assigned_to_id=cce_param) | Q(creator_id=cce_param))).distinct()

                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    total_leads_presales = total_leads.filter(created_on__gte=seven_days_ago)
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    total_leads_presales = total_leads.filter(created_on__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    total_leads_presales = total_leads.filter(created_on__gte=one_month_ago)  
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    total_leads_presales = total_leads.filter(created_on__gte=six_months_ago)     
              
                site_visits_scheduled = SiteVisit.objects.filter(site_visit_status = "Scheduled" , lead__in=total_leads_presales)
               
                #sv_done_count = presales_site_visits.filter(site_visit_status="Site Visit Done").count()
                site_visits_done = SiteVisit.objects.filter(site_visit_status = "Site Visit Done" , lead__in=total_leads_presales)
                
                for lead in presales_queryset :
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
                
                print(reschedule_counts)
                site_visits_revisit = total_reschedule_count
                 

                total_leads_counting = hot_leads.count() + cold_leads.count() + warm_leads.count() + lost_leads.count()
                connected_total_leads = leads_connected.count() + leads_not_connected.count() +  leads_with_followup_task_not_completed_count
                site_visits_counting = site_visits_done.count() + site_visits_revisit + site_visits_scheduled.count()
                

                data = {
                    'total_connected_leads' :  connected_total_leads,
                    'leads_connected': leads_connected.count(),
                    'leads_connected_percentage' : round(leads_connected.count()/connected_total_leads * 100 ,2) if connected_total_leads > 0 else 0,
                    'leads_not_connected': leads_not_connected.count(),
                    'leads_not_connected_percentage' : round(leads_not_connected.count()/connected_total_leads * 100 ,2) if connected_total_leads > 0 else 0,
                    'followups': leads_with_followup_task_not_completed_count,
                    "followups_percentage" :  round(leads_with_followup_task_not_completed_count/connected_total_leads * 100 ,2) if connected_total_leads > 0 else 0,
                    'total_leads': presales_queryset.count() - new_leads.count(),
                    'hot_leads': hot_leads.count(),
                    'hot_leads_percentage': round(hot_leads.count()/total_leads_counting * 100 ,2) if total_leads_counting > 0 else 0,
                    'warm_leads': warm_leads.count(),
                    'warm_leads_percentage': round(warm_leads.count()/total_leads_counting * 100 ,2) if total_leads_counting > 0 else 0,
                    'cold_leads': cold_leads.count(),
                    'cold_leads_percentage': round(cold_leads.count()/total_leads_counting * 100 ,2) if total_leads_counting > 0 else 0,
                    'lost_leads': lost_leads.count(),
                    'lost_leads_percentage': round(lost_leads.count()/total_leads_counting * 100 ,2) if total_leads_counting > 0 else 0,
                    'total_site_visits' : site_visits_counting,
                    'site_visits_done': site_visits_done.count(),
                    'site_visits_done_percentage' : round(site_visits_done.count()/site_visits_counting * 100 ,2) if site_visits_counting > 0 else 0,
                    'site_visits_revisit': site_visits_revisit,
                    'site_visits_revisit_percentage' : round(site_visits_revisit/site_visits_counting * 100 ,2) if site_visits_counting > 0 else 0,
                    'site_visits_scheduled': site_visits_scheduled.count(),
                    'site_visits_scheduled_percentage' : round(site_visits_scheduled.count()/site_visits_counting * 100 ,2) if site_visits_counting > 0 else 0,
                }

                return ResponseHandler(False, "PRESALES DATA", data, status.HTTP_200_OK)
            
            elif module_param == "SOURCING": 
                sourcing_id = request.GET.get('sourcing_id',None)

                sourcing_queryset = ChannelPartner.objects.all()
                if sourcing_id:
                    sourcing_queryset = ChannelPartner.objects.filter(creator__id=sourcing_id).distinct()
                print("sourcing queryset count",sourcing_queryset.count())
                if date_range_param == 'last_7_days':
                    seven_days_ago = datetime.now() - timedelta(days=7)
                    sourcing_queryset = sourcing_queryset.filter(created_on__gte=seven_days_ago)
                elif date_range_param == 'last_2_weeks':
                    two_weeks_ago = datetime.now() - timedelta(weeks=2)
                    sourcing_queryset = sourcing_queryset.filter(created_on__gte=two_weeks_ago)
                elif date_range_param == 'last_1_month':
                    one_month_ago = datetime.now() - timedelta(days=30)
                    sourcing_queryset = sourcing_queryset.filter(created_on__gte=one_month_ago)
                elif date_range_param == 'last_6_months':
                    six_months_ago = datetime.now() - timedelta(days=180)
                    sourcing_queryset = sourcing_queryset.filter(created_on__gte=six_months_ago)

                positive_count = sourcing_queryset.filter(channel_partner_status='Interested')
                negative_count = sourcing_queryset.filter(channel_partner_status='Not Interested')
                maybe_count = sourcing_queryset.filter(channel_partner_status='Might be Interested')
                total_cp_count =  sourcing_queryset.exclude(Q(full_name__isnull=True)& Q(primary_email__isnull=True)& Q(address__isnull=True)& Q(pin_code__isnull=True)).count()            
                icp = sourcing_queryset.filter(type_of_cp='ICP')
                rcp = sourcing_queryset.filter(type_of_cp='RETAIL')
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
                
                total_cp_counting = positive_count.count() + negative_count.count() + maybe_count.count()
                total_rcp_icp_count = rcp.count() + icp.count()


                # booked_inventories = ProjectInventory.objects.filter(status="Booked")
                # print("boked",booked_inventories)

                 # three_months_ago = timezone.now() - timedelta(days=90)

                # Annotate ChannelPartner with the count of related booked ProjectInventory entries
                # channel_partner_counts =  sourcing_queryset.filter(
                #     lead__projectinventory__status="Booked",
                #     # lead__projectinventory__booked_on__gte=three_months_ago
                # ).annotate(
                #     booked_count=Count('lead__projectinventory')
                # )

                # print("Channel partner those having booking",channel_partner_counts)

                # print("active_channel_partner",channel_partner_counts.count())

                # active_channel_partners = channel_partner_counts.count()

                # ninety_days_ago = timezone.now() - timedelta(days=90)

                # # Queryset for active CPs
                # active_cps = ChannelPartner.objects.filter(
                #     Q(created_on__gte=ninety_days_ago) |  # Created within the last 90 days
                #     Q(lead__projectinventory__status="Booked", lead__projectinventory__booked_on__gte=ninety_days_ago)  # At least one booking in the last 90 days
                # ).exclude(Q(full_name__isnull=True)& Q(primary_email__isnull=True)& Q(address__isnull=True)& Q(pin_code__isnull=True)).distinct()
                
                three_months_ago = timezone.now() - timedelta(days=90)

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

                if sourcing_id:
                    active_cps = active_cps.filter(
                        creator_id=sourcing_id 
                    )
                active_cps = active_cps.distinct()


                print("Channel partner those having booking",active_cps)
                
                for cp in active_cps:
                   # print(f"Channel Partner: {cp.full_name or cp.firm}")
                    cp_name = cp.full_name or cp.firm
                    cp_created_on = cp.created_on.strftime('%Y-%m-%d')  # Format the date as YYYY-MM-DD
                    
                    print(f"Channel Partner: {cp_name}")
                    print(f"Created On: {cp_created_on}")
                    
                    # Get bookings associated with this CP in the last 90 days
                    bookings = cp.lead_set.filter(
                        projectinventory__status="Booked",
                        projectinventory__booked_on__gte=three_months_ago
                    ).values_list('projectinventory__id', flat=True)
                    
                    if bookings:
                        print(f"Bookings (IDs) in the last 90 days: {list(bookings)}")
                    else:
                        print("No bookings in the last 90 days")

                # Count of active CPs
                active_channel_partners = active_cps.count()

                print("active cp count",active_channel_partners)

                # Find all Channel Partners without bookings in the last three months
                inactive_channel_partners = total_cp_count - active_channel_partners  

                data = {
                    'total_cp_count': total_cp_counting,
                    'positive_count': positive_count.count(),
                    'positive_count_percentage' : round(positive_count.count()/total_cp_counting * 100 , 2) if  total_cp_counting > 0 else 0,
                    'negative_count': negative_count.count(),
                    'negative_count_percentage' : round(negative_count.count()/total_cp_counting * 100 , 2) if  total_cp_counting > 0 else 0,
                    'maybe_count': maybe_count.count(),
                    'maybe_count_percentage' : round(maybe_count.count()/total_cp_counting * 100 , 2) if  total_cp_counting > 0 else 0,
                    'total_rcp_icp_count' : total_rcp_icp_count,
                    'rcp': rcp.count(),
                    'rcp_percentage' : round(rcp.count()/total_rcp_icp_count * 100 , 2) if total_rcp_icp_count > 0 else 0,
                    'icp': icp.count(),
                    'icp_percentage' : round(icp.count()/total_rcp_icp_count * 100 , 2) if total_rcp_icp_count > 0 else 0,
                    'no_of_meetings': no_of_meetings,
                    'fresh_meetings': fresh_meetings,
                    'fresh_meetings_percentage' : round(fresh_meetings/no_of_meetings * 100 , 2) if no_of_meetings > 0 else 0,
                    'revisit_meetings': revisit_meetings,
                    'revisit_meetings_percentage' : round(revisit_meetings/no_of_meetings * 100 , 2) if no_of_meetings > 0 else 0,
                    'total_active_inactive_cps' : total_cp_count,
                    'active_cps' : active_channel_partners,
                    'active_cps_percentage' : round(active_channel_partners / total_cp_count * 100 ,2) if total_cp_count > 0 else 0,
                    'inactive_cps' : inactive_channel_partners,
                    'inactive_cps_percentage' : round(inactive_channel_partners/total_cp_count * 100 ,2) if total_cp_count > 0 else 0
                }

                return ResponseHandler(False, "SOURCING DATA", data, status.HTTP_200_OK)
            
            elif module_param == "CLOSING":
                closing_id = request.GET.get('closing_id',None) 

                stage = Stage.objects.filter(name='Sales').first()
                presales_stage = Stage.objects.filter(name='PreSales').first()
                presales_queryset = Lead.objects.filter(workflow__current_stage=presales_stage.order).distinct()
                if closing_id:
                    presales_queryset = Lead.objects.filter(Q(workflow__current_stage=presales_stage.order) & (Q(workflow__stages__assigned_to_id=closing_id) | Q(creator_id=closing_id))).distinct()
                sales_queryset = Lead.objects.filter(workflow__current_stage=stage.order).distinct()
                if closing_id:
                    # sales_queryset = Lead.objects.filter(Q(workflow__current_stage=stage.order) & (Q(workflow__stages__assigned_to_id=closing_id) | Q(creator_id=closing_id))).distinct()
                    lead_ids = list(sales_queryset.values_list("id", flat=True))
                    site_visits = SiteVisit.objects.filter(lead__in=lead_ids, closing_manager__in=list(closing_id))
                    site_visit_lead_ids = list(site_visits.values_list("lead", flat=True))
                    sales_queryset = sales_queryset.filter(id__in=site_visit_lead_ids)

                print("sales_queryset",sales_queryset)
                print("sales_queryset_count",sales_queryset.count())
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

               # booked_queryset = sales_queryset.filter(projectinventory__status="Booked").order_by('-id')
                cp_count = sales_queryset.filter(channel_partner__isnull=False) 
                source_model = Source.objects.filter(name='Referral')
                referral_count = 0
                if source_model.exists():
                    referral_count = sales_queryset.filter(source_id=source_model.first().id).count()         

                source_model = Source.objects.filter(name='Direct')
                direct_leads = 0
                if source_model.exists():
                    direct_leads = sales_queryset.filter(source_id=source_model.first().id).count()
               # direct_leads = sales_queryset.filter(creator__groups__name__in=["INQUIRY_FORM"])  

                
                hot_leads = sales_queryset.filter(lead_status='Hot')
                warm_leads = sales_queryset.filter(lead_status='Warm')
                cold_leads = sales_queryset.filter(lead_status='Cold')
                lost_leads = sales_queryset.filter(lead_status='Lost')
                new_leads = sales_queryset.filter(lead_status = "New")
                for lead in hot_leads:
                    print(lead.id , lead.lead_status)
                for lead in cold_leads:
                    print(lead.id,lead.lead_status)    

                print(new_leads.count())

                #If need to go with sales created leads only 
                total_leads = Lead.objects.filter(creation_stage = "Sales")
                if closing_id:
                    # total_leads = Lead.objects.filter(Q(creation_stage="Sales") & (Q(workflow__stages__assigned_to_id=closing_id) | Q(creator_id=closing_id))).distinct()
                    lead_ids = list(total_leads.values_list("id", flat=True))
                    site_visits = SiteVisit.objects.filter(lead__in=lead_ids, closing_manager__in=list(closing_id))
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
                    print("Lead ID:", lead.id, "Site Visits Done:", lead.sv_done)

                # sales_queryset = sales_queryset.annotate(sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done")))
                # print(sales_queryset.count())
                # sv_data = sales_queryset.filter(sv_done__gt=1)
                # revisit_count = 0
                # for lead in sv_data:
                #     revisit_count += (lead.sv_done -1)
                #     print("Lead ID:", lead.id, "Site Visits Done:", lead.sv_done)

                #If need to go with sales created leads only 
                booking_count = total_leads.filter(projectinventory__status="Booked")
                print("booking in sales",booking_count)
                booking_count = booking_count.count()
                print(sales_queryset.count())       

                # booking_count = sales_queryset.filter(projectinventory__status="Booked")
                # print("booking in sales",booking_count)
                # booking_count = booking_count.count()
                # print(sales_queryset.count())
               

   
                # call_center_users = Users.objects.filter(groups__name="CALL_CENTER_EXECUTIVE").values_list('id', flat=True)

                # call_center_user_arrays = [[user_id] for user_id in call_center_users]

                # presales_leads = sales_queryset.filter(followers__in=call_center_user_arrays)

                presales_leads = presales_queryset

                total_leads_sales_count = cp_count.count() + direct_leads + referral_count + revisit_count + presales_leads.count()
                total_leads_data = hot_leads.count() + warm_leads.count() + cold_leads.count() + lost_leads.count()
                total_leads_booked_revisit_count = revisit_count + booking_count
                

                data = {
                    'total_leads_referral_sales_count' : total_leads_sales_count,
                    'cp_count': cp_count.count(),
                    'cp_count_percentage' : round(cp_count.count()/total_leads_sales_count * 100 , 2) if total_leads_sales_count > 0 else 0,
                    'direct_leads': direct_leads,
                    "direct_leads_percentage": round(direct_leads/total_leads_sales_count * 100 , 2) if total_leads_sales_count > 0 else 0,
                    'referral': referral_count,
                    "referral_leads_percentage": round(referral_count/total_leads_sales_count * 100 , 2) if total_leads_sales_count > 0 else 0,
                    'presales': presales_leads.count(),
                    "presales_percentage": round(presales_leads.count()/total_leads_sales_count * 100 , 2) if total_leads_sales_count > 0 else 0,
                    'total_leads_hot_warm_count' : total_leads_data,
                    'hot_leads': hot_leads.count(),
                    'hot_leads_percentage' : round(hot_leads.count()/total_leads_data * 100 , 2) if total_leads_data > 0 else 0,
                    'warm_leads': warm_leads.count(),
                    'warm_leads_percentage' : round(warm_leads.count()/total_leads_data * 100 , 2) if total_leads_data > 0 else 0,
                    'cold_leads': cold_leads.count(),
                    'cold_leads_percentage' : round(cold_leads.count()/total_leads_data * 100 , 2) if total_leads_data > 0 else 0,
                    'lost_leads': lost_leads.count(),
                    'lost_leads_percentage' : round(lost_leads.count()/total_leads_data * 100 , 2) if total_leads_data > 0 else 0,
                    'total_leads_booked_revisit_count' : total_leads_booked_revisit_count,
                    'no_of_leads_revisits': revisit_count,
                    'no_of_leads_revisits_percentage' : round(revisit_count/total_leads_booked_revisit_count * 100 , 2) if total_leads_booked_revisit_count > 0 else 0,
                    'no_leads_booked': booking_count,
                    'no_of_leads_booked_percentage' : round(booking_count/total_leads_booked_revisit_count * 100 , 2) if total_leads_booked_revisit_count > 0 else 0
                }

                return ResponseHandler(False, "Summary data for Closing DashBoard", data,200) 
        
            elif module_param == "MONTHLY":
                current_month = timezone.now().month
                current_year = timezone.now().year
                months_data = []

                for i in range(6):
                    month = current_month - i
                    year = current_year
                    if month <= 0:
                        month += 12
                        year -= 1
                    start_date = datetime(year, month, 1)
                    end_date = start_date + timedelta(days=32)  
                    end_date = datetime(end_date.year, end_date.month, 1) - timedelta(days=1) 
                    month_name = start_date.strftime('%B')
                    stage = Stage.objects.filter(name='Sales').first()
                    sales_queryset = Lead.objects.filter(
                        created_on__range=[start_date, end_date],
                        workflow__current_stage=stage.order,
                        creation_stage = "Sales"
                    )
                   
                    # num_leads_with_revisits = 0

                    # for lead in sales_queryset:
                    #     site_visits = lead.sitevisit_set.filter(site_visit_status='Site Visit Done')

                    #     if not site_visits.exists():
                    #         continue

                    #     min_visit_date = site_visits.aggregate(min_visit_date=Min('visit_date'))['min_visit_date']

                    #     if site_visits.filter(visit_date__gt=min_visit_date).exists():
                    #         num_leads_with_revisits += 1

                    sales_queryset = sales_queryset.annotate(sv_done=Count('sitevisit', filter=Q(sitevisit__site_visit_status="Site Visit Done")))
                    print(sales_queryset.count())
                    sv_data = sales_queryset.filter(sv_done__gt=1)
                    num_leads_with_revisits = 0
                    for lead in sv_data:
                        num_leads_with_revisits += (lead.sv_done -1)
                        print("Lead ID:", lead.id, "Site Visits Done:", lead.sv_done) 

                    
                    # direct_leads = sales_queryset.filter(creator__groups__name__in=["INQUIRY_FORM"])   
                    direct_leads = sales_queryset.count()

                    booked_queryset = sales_queryset.filter(projectinventory__status="Booked").order_by('-id')
                    month_data = {
                        'month': month_name,
                        'start_date': start_date.date(),
                        'end_date': end_date.date(),
                        'visits': direct_leads,
                        'revisits': num_leads_with_revisits,
                        'bookings': booked_queryset.count()
                    }
                    months_data.append(month_data)

                return ResponseHandler(False, "Monthly Data", months_data, 200)      
            elif module_param == "BAR_GRAPH":
                result_dict = {}
                
                # some change needed
                # Brokerage section
                payment_done_count = Payment.objects.filter(payment_to='Sales', status='Payment Done').count()
                approval_pending_count = Payment.objects.filter(payment_to='Sales', status='Approval Pending').count()
                total_sales_count = Payment.objects.filter(payment_to='Sales').count()
                #total_sales_count = Payment.objects.filter(payment_to='Sales' , payment_type = "Standard").count()
                bill_overdue_count = Payment.objects.exclude(status='Payment Done').filter(payment_to='Sales',due_date__lt=timezone.now())
                print("payment_overdue_queryset",bill_overdue_count)
                bill_overdue_count = bill_overdue_count.count()
                print("bill_overdue_count",bill_overdue_count)
                interval = 2
                max_value = max(payment_done_count, approval_pending_count, total_sales_count)
                rounded_max_value = math.ceil(max_value / interval) * interval

                brokerage_counts = {
                    "payment_done_count": payment_done_count,
                    "approval_pending_count": approval_pending_count,
                    "total_submitted_count": total_sales_count,
                    "bill_overdue_count" : bill_overdue_count,
                    "interval" : interval,
                    "max_count": rounded_max_value
                }
                result_dict['Brokerage'] = brokerage_counts

                # Inventory section
                all_statuses = ["Yet to book", "Risk", "Hold Refuge", "Booked"]
                status_counts = {status: 0 for status in all_statuses}
                summary = ProjectInventory.objects.values('status').annotate(status_count=Count('status'))
                total_records_count = sum(entry['status_count'] for entry in summary)
                
                max_count = 0
                max_status = ""
                for entry in summary:
                    status_counts[entry['status']] = entry['status_count']
                    if entry['status_count'] > max_count:
                        max_count = entry['status_count']
                        max_status = entry['status']
                                
                interval = 100
                rounded_max_count = math.ceil(max_count / interval) * interval
                print(rounded_max_count) 
                status_counts['interval'] = 100
               # status_counts['max_status'] = max_status
                status_counts['max_count'] = rounded_max_count
                status_counts['Total'] = total_records_count
                result_dict['Inventory'] = status_counts

                # Sales followups section
                closing_managers = Users.objects.filter(groups__name="CLOSING_MANAGER")
                sales_stage = Stage.objects.filter(name='Sales').first()
                sales_leads = Lead.objects.filter(workflow__current_stage=sales_stage.order)
                sales_site_visits = SiteVisit.objects.filter(lead__in=sales_leads)
                sales_followups = []
                interval = 5
                max_follow_up_count = 0
                for manager in closing_managers:
                    lead_ids = sales_site_visits.filter(closing_manager=manager).values_list('lead', flat=True).distinct()
                    leads_with_followup_task_not_completed_count = 0
                    for lead_id in lead_ids:
                        lead_obj = Lead.objects.get(id=lead_id)
                        workflow = lead_obj.workflow.get()
                        followup_task = workflow.tasks.filter(name='Follow Up', completed=False).order_by('-time').first()
                        if followup_task:
                            leads_with_followup_task_not_completed_count += 1
                    sales_followups.append({
                            "name": manager.name,
                            "follow_up_count": leads_with_followup_task_not_completed_count
                        })# Update the maximum follow-up count
                    if leads_with_followup_task_not_completed_count > max_follow_up_count:
                        max_follow_up_count = leads_with_followup_task_not_completed_count
                
                # Calculate the rounded max count according to the interval
                rounded_max_follow_up_count = math.ceil(max_follow_up_count / interval) * interval

                result_dict['sales_followups'] = sales_followups
                sales_interval = {
                    "interval": interval,
                    "max_count": rounded_max_follow_up_count
                }
                result_dict['sales_follow_up_interval'] = sales_interval
                # Presales followups section
                call_center_executives = Users.objects.filter(groups__name='CALL_CENTER_EXECUTIVE')
                presales_stage = Stage.objects.filter(name='PreSales').first()
                presales_leads = Lead.objects.filter(workflow__current_stage=presales_stage.order)
                presales_followups = []
                interval = 5

                # To find the maximum follow-up count
                max_follow_up_count = 0
                current_time = timezone.now()
                for user in call_center_executives:
                    leads_assigned = presales_leads.filter(followers__contains=[user.id])
                    leads_with_followup_task_not_completed_count = 0
                    for lead in leads_assigned:
                        workflow = lead.workflow.get()
                        followup_task = workflow.tasks.filter(name='Follow Up', completed=False, time__gte=current_time).order_by('-time').first()
                        if followup_task:
                            leads_with_followup_task_not_completed_count += 1
                    presales_followups.append({
                        "name": user.name,
                        "follow_up_count": leads_with_followup_task_not_completed_count
                    })
                    # Update the maximum follow-up count
                    if leads_with_followup_task_not_completed_count > max_follow_up_count:
                        max_follow_up_count = leads_with_followup_task_not_completed_count

                # Calculate the rounded max count according to the interval
                rounded_max_follow_up_count = math.ceil(max_follow_up_count / interval) * interval

                result_dict['presales_followups'] = presales_followups
                presales_interval = {
                    "interval": interval,
                    "max_count": rounded_max_follow_up_count
                }
                result_dict['presales_follow_up_interval'] = presales_interval 
                
                return ResponseHandler(False, "Summary data for Bargraph", result_dict,200) 
        except Exception as e:
            return ResponseHandler(error=True, message=str(e), body=None, status_code=500)



#Brokerage ladder code
class ChannelPartnerBrokerageListView(APIView):
    def get(self, request):
        channel_partners = ChannelPartner.objects.all()
        serializer = ChannelPartnerSerializer(channel_partners, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

class SendNotificationView(APIView):
    def post(self, request, *args, **kwargs):
        print("Hree")
        # Fetch the Lead object based on the provided ID
        lead_id = request.data.get('lead_id')
        lead = Lead.objects.filter(id=lead_id).first()

        if not lead:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        
        print("Lead" , lead)

        updates_record, created = Updates.objects.get_or_create(lead=lead)
        print("updated_record: ", updates_record, lead)
        inventory_instance = InventoryCostSheet.objects.filter(lead=lead).first()
        print(inventory_instance)
        if inventory_instance:
            email_id = lead.primary_email
            lead_name = f"{lead.first_name} {lead.last_name}"
            company_name = lead.organization.name

            print(f"Sending reminder email to {email_id} for lead {lead_name}")

            # if updates_record and updates_record.slab:
            #     if updates_record.slab.event_order <= project_cost_sheet.event_order:
            #         send_demand_letter = False
                    

            if email_id  :
                
                response = requests.post(
                    'http://3.111.78.151:81/api/email/sendmail/',
                    headers={
                        'Authorization': 'token 43fb69c07ff4d2ec5b75bfa16638588a8606e199',
                        'Content-Type': 'application/json'
                    },
                    json={
                        "template_id": 27,
                        "email": email_id,
                        "parameters": {
                            "username": lead_name,
                            "company_name": company_name
                             
                        }
                    }
                )

                if response.status_code == 200:
                    print("Notification logic for notification count")
                    notification_count, created = NotificationCount.objects.get_or_create(
                        lead=lead,
                        defaults={'count': 1, 'last_notified': timezone.now()}
                    )
                    if not created:
                        notification_count.count += 1
                        notification_count.last_notified = timezone.now()
                        notification_count.save()
                else:
                    print(f"Failed to send demand letter. HTTP status code: {response.status_code}")
   
        return ResponseHandler(False,"Reminder sent successfully", None ,status.HTTP_200_OK)            

        # Assuming get_aging is a method within Lead or can be called from here
        # aging = LeadPostSalesSerializer().get_aging(lead)
        # print("aging",aging)

        # if aging is None:
        #     NotificationCount.objects.filter(lead=lead).update(count=0)
        #     return Response({"error": "Aging is none for this lead and count set 0"}, status=status.HTTP_404_NOT_FOUND)
        # # aging = ">30"
        # # Define users
        # crm_head_user = Users.objects.filter(groups__name="CRM_HEAD").first()
        # ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
        # vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()

        # # Define title and body for the notification
        # title = f"Aging Notification for Lead {lead.id}"
        # body = f"The aging for lead {lead.id} is currently {aging}."

        # # Notification data
        # data = {'notification_type': 'aging_notification'}

        # def handle_notification(user):
        #     if user:
        #         # Create notification
        #         Notifications.objects.create(
        #             notification_id=f"lead-{lead.id}-{user.id}",
        #             user_id=user,
        #             created=timezone.now(),
        #             notification_message=body,
        #             notification_url=f'/leads/details/{lead.id}'
        #         )
        #         # Send push notification
        #         send_push_notification(user.fcm_token, title, body, data)
                
        #         # # Update NotificationCount table
        #         # notification_count, created = NotificationCount.objects.get_or_create(
        #         #     lead=lead,
        #         #     # user=user,
        #         #     defaults={'count': 1, 'last_notified': timezone.now()}
        #         # )
        #         # if not created:
        #         #     notification_count.count += 1
        #         #     notification_count.last_notified = timezone.now()
        #         #     notification_count.save()

        # # Send notifications based on aging
        # if  aging == ">30 Days" :
        #     print("Inside this")
        #     handle_notification(crm_head_user)
        #     handle_notification(ah_user)
        #     # Update NotificationCount table only once for both CRM and AH users
        #     notification_count, created = NotificationCount.objects.get_or_create(
        #         lead=lead,
        #         defaults={'count': 1, 'last_notified': timezone.now()}
        #     )
        #     if not created:
        #         notification_count.count += 1
        #         notification_count.last_notified = timezone.now()
        #         notification_count.save()

        # elif aging == ">60 Days" :
        #     print("Inside this >60")
        #     handle_notification(vp_user)
            
        #     # Handle NotificationCount for VP user
        #     notification_count, created = NotificationCount.objects.get_or_create(
        #         lead=lead,
        #         defaults={'count': 1, 'last_notified': timezone.now()}
        #     )
        #     if not created:
        #         notification_count.count += 1
        #         notification_count.last_notified = timezone.now()
        #         notification_count.save()

        # return Response({"message": "Notifications sent successfully"}, status=status.HTTP_200_OK)




class NotificationCountView(generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        lead_id = request.query_params.get('lead_id')

        if not lead_id:
            return Response({"error": "lead_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        # Aggregate notification count for the lead
        total_count = NotificationCount.objects.filter(lead=lead).aggregate(total_count=Sum('count'))['total_count'] or 0

        return Response({"lead_id": lead_id, "total_notifications": total_count}, status=status.HTTP_200_OK)



class CanceledBookingLeadsView(APIView):
    pagination_class = CustomLimitOffsetPagination

    def filter_by_refund_initiated_on(self, leads, filter_value, from_date, to_date):
        """Filter leads based on the 'refund_initiated_on' criteria."""
        today = datetime.now().date()

        if filter_value == 'Today':
            return [
                lead for lead in leads 
                if (refund_date := LeadRefundSerializer().get_refund_initiated_on(lead)) and refund_date == today
            ]
        
        elif filter_value == 'Next_7_days':
            next_7_days = today + timedelta(days=7)
            return [
                lead for lead in leads 
                if (refund_date := LeadRefundSerializer().get_refund_initiated_on(lead)) and today <= refund_date <= next_7_days
            ]

        elif filter_value == 'Next_1_month':
            next_1_month = today + timedelta(days=30)
            return [
                lead for lead in leads 
                if (refund_date := LeadRefundSerializer().get_refund_initiated_on(lead)) and today <= refund_date <= next_1_month
            ]

        elif filter_value == 'Custom' and from_date and to_date:
            try:
                # Convert custom from and to dates into aware datetime objects
                from_date_obj = make_aware(datetime.strptime(from_date, "%Y-%m-%d")).date()
                to_date_obj = make_aware(datetime.strptime(to_date, "%Y-%m-%d")).date()
                return [
                    lead for lead in leads 
                    if (refund_date := LeadRefundSerializer().get_refund_initiated_on(lead)) and from_date_obj <= refund_date <= to_date_obj
                ]
            except ValueError:
                return []  # Return an empty list if date conversion fails

        return leads  # Return original list if no valid filter is applied
    
    def get(self, request):
        refund_status_filter = request.query_params.get('refund_status', None)
        tower_filter = request.query_params.get('tower', None)
        refund_initiated_on_filter = request.query_params.get('refund_initiated_on', None)
        custom_from_date = request.query_params.get('from', None)
        custom_to_date = request.query_params.get('to', None)
        search = request.query_params.get('search', None)

        # Fetch leads with canceled booking
        leads_with_canceled_booking = Lead.objects.filter(property_owner__booking_status="cancel")
        print(leads_with_canceled_booking)
        

        if search:
            if search.isdigit():
                # Search by ID
                leads_with_canceled_booking = leads_with_canceled_booking.filter(id=search)
            else:
                # Search by name (partial or full match)
                leads_with_canceled_booking = leads_with_canceled_booking.filter(
                    Q(first_name__icontains=search) | Q(last_name__icontains=search)
                )

        if refund_status_filter in ['Pending', 'Refunded']:
            leads_with_canceled_booking = [
                lead for lead in leads_with_canceled_booking 
                if LeadRefundSerializer().get_refund_status(lead) == refund_status_filter
            ]

        # Apply tower filter if provided
        if tower_filter:
            tower_list = [tower.strip() for tower in tower_filter.split(',')]
            leads_with_canceled_booking = [
                lead for lead in leads_with_canceled_booking
                if LeadRefundSerializer().get_inventory_unit(lead) and
                any(tower in LeadRefundSerializer().get_inventory_unit(lead) for tower in tower_list)
            ]


         # Apply refund_initiated_on filter if provided
        if refund_initiated_on_filter:
            leads_with_canceled_booking = self.filter_by_refund_initiated_on(
                leads_with_canceled_booking, refund_initiated_on_filter, custom_from_date, custom_to_date
            )  


        # Apply pagination
        paginator = self.pagination_class()
        result_page = paginator.paginate_queryset(leads_with_canceled_booking, request)
        serializer = LeadRefundSerializer(result_page, many=True)
        
        total_count = len(leads_with_canceled_booking)

        # Prepare the paginated response
        response_data = {
            'count': total_count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'results': serializer.data
        }
         
        
        # Serialize the data
        # serializer = LeadRefundSerializer(leads_with_canceled_booking, many=True)
        
        # Return the serialized data as JSON response
        return ResponseHandler(False,"Cancel Booking Leads Data",response_data,status.HTTP_200_OK)
    


class PostSalesDocumentBulkUploadView(generics.CreateAPIView):
    queryset = PostSalesDocumentSection.objects.all()
    serializer_class = PostSalesDocumentSectionSerializer

    def create(self, request, *args, **kwargs):
        lead_id = request.data.get('lead')
        uploaded_files = request.FILES.getlist('files')
        document_type_ids = request.data.get('document_type_ids', '')
        print("document_type_ids:", document_type_ids)

        if not lead_id:
            return ResponseHandler(True, "Lead ID is required.", None, status.HTTP_400_BAD_REQUEST)
        
        lead = get_object_or_404(Lead, pk=lead_id)

        document_type_ids_list = [int(id.strip()) for id in document_type_ids.split(',') if id.strip()]
        print("document_type_ids_list:", document_type_ids_list)
        document_types = PostSalesDocumentType.objects.filter(id__in=document_type_ids_list)
        print("document_types:", document_types)
        mandatory_document_types = document_types.filter(is_mandatory=True)
        print("mandatory_document_types:", mandatory_document_types)
        mandatory_type_ids = mandatory_document_types.values_list('id', flat=True)
        print("mandatory_type_ids:", mandatory_type_ids)

        document_data_list = []
        missing_mandatory_docs = []

        # Ensure each file has a corresponding document type
        for file, doc_type_id in zip(uploaded_files, document_type_ids_list):
            print("file:", file)
            print("doc_type_id:", doc_type_id)
            document_type = get_object_or_404(PostSalesDocumentType, pk=doc_type_id)
            print("document_type:", document_type)
            
            if document_type.is_mandatory and doc_type_id not in mandatory_type_ids:
                missing_mandatory_docs.append(document_type.name)

            # Prepare document data
            document_data = {
                'lead': lead_id,
                'document_type': doc_type_id,
                'file': file,
            }
            print("document_data:", document_data)
            document_data_list.append(document_data)
            print("document_data_list:", document_data_list)

        if missing_mandatory_docs:
            print("missing_mandatory_docs:", missing_mandatory_docs)
            return ResponseHandler(True, f"Missing mandatory documents: {', '.join(missing_mandatory_docs)}", None, status.HTTP_400_BAD_REQUEST)

        if not document_data_list:
            return ResponseHandler(True, "No valid documents to upload.", None, status.HTTP_400_BAD_REQUEST)

        # Serialize and save documents
        serializer = self.get_serializer(data=document_data_list, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return ResponseHandler(False, "Documents uploaded successfully.", None, status.HTTP_201_CREATED)
class PostSalesDocumentsListView(generics.ListAPIView):
    serializer_class = PostSalesDocumentSectionSerializer

    def get_queryset(self):
        lead_id = self.kwargs.get('lead_id')

        lead = get_object_or_404(Lead, pk=lead_id)

        queryset = PostSalesDocumentSection.objects.filter(lead=lead)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        if not queryset.exists():
            return ResponseHandler(True, "No documents found for the given lead.", None, status.HTTP_404_NOT_FOUND)
        
        serializer = self.get_serializer(queryset, many=True)
        return ResponseHandler(False, "Documents retrieved successfully.", serializer.data, status.HTTP_200_OK)    

class PostSalesDocumentTypeMetadataView(generics.ListAPIView):

    def get(self, request):
        document_types = PostSalesDocumentType.objects.values('id', 'name', 'is_mandatory')
        data = list(document_types)
        return ResponseHandler(False, "Document type metadata retrieved successfully.", data, status.HTTP_200_OK)


class LeadSignatureView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, lead_id):
        """Retrieve the signatures of a specific Lead"""
        lead = get_object_or_404(Lead, id=lead_id)
        serializer = LeadSignatureSerializer(lead)
        return ResponseHandler(False,"Signatures Reterieved successfully",serializer.data,status.HTTP_200_OK)

    def post(self, request, lead_id):
        """Add signatures to a specific Lead"""
        lead = get_object_or_404(Lead, id=lead_id)
        serializer = LeadSignatureSerializer(lead, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False,"Signature Saved successfully",serializer.data,status.HTTP_201_CREATED)
        return ResponseHandler(True,"Bad Request",serializer.errors,status.HTTP_400_BAD_REQUEST)

    def put(self, request, lead_id):
        """Update signatures of a specific Lead"""
        lead = get_object_or_404(Lead, id=lead_id)
        serializer = LeadSignatureSerializer(lead, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(False, "Signature updated successfully",serializer.data,status.HTTP_200_OK)
        return ResponseHandler(True,"Bad Request",serializer.errors, status.HTTP_400_BAD_REQUEST)

    def delete(self, request, lead_id):
        """Delete signatures of a specific Lead"""
        lead = get_object_or_404(Lead, id=lead_id)
        lead.sh_signature.delete(save=True)
        lead.co_owner_signature.delete(save=True)
        lead.customer_signature.delete(save=True)
        lead.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

 
class SignatureAPIView(APIView):
    def get(self,request,lead_id):
        lead = get_object_or_404(Lead, id=lead_id)

        def get_signature_url(field):
            return field.url if field else None
        res={}
        if lead:
            res["booking_form_signatures"] = {
                "sh_signature": get_signature_url(lead.sh_signature),
                "co_owner1_signature": get_signature_url(lead.co_owner1_signature),
                "co_owner2_signature": get_signature_url(lead.co_owner2_signature),
                "co_owner3_signature": get_signature_url(lead.co_owner3_signature),
                "co_owner4_signature": get_signature_url(lead.co_owner4_signature),
                "co_owner5_signature": get_signature_url(lead.co_owner5_signature),
                "customer_signature": get_signature_url(lead.customer_signature),
            }

            res["cost_sheet_signatures"] = {
                "client_signature": get_signature_url(lead.client_signature),
                "cm_signature": get_signature_url(lead.cm_signature),
                "vp_signature": get_signature_url(lead.vp_signature),
                "cost_sheet_co_owner_signature": get_signature_url(lead.cost_sheet_co_owner_signature),
                "cost_sheet_co_owner2_signature": get_signature_url(lead.cost_sheet_co_owner2_signature),
                "cost_sheet_co_owner3_signature": get_signature_url(lead.cost_sheet_co_owner3_signature),
                "cost_sheet_co_owner4_signature": get_signature_url(lead.cost_sheet_co_owner4_signature),
                "cost_sheet_co_owner5_signature": get_signature_url(lead.cost_sheet_co_owner5_signature),
            }

            # res = [booking_form_signatures, cost_sheet_signatures]
            return ResponseHandler(False, "Signature retrieved successfully", res, status.HTTP_200_OK)
        
        return ResponseHandler(True, "Lead not found", [], status.HTTP_404_NOT_FOUND)

class CCEViewList(APIView):
    def get(self, request):
        call_center_executives = Users.objects.filter(groups__name='CALL_CENTER_EXECUTIVE')
         
        data = []

        for cce in call_center_executives:
            cce_dict = {
                'id': cce.id,
                'cce_name' : cce.name
            }

            data.append(cce_dict)

        return ResponseHandler(False, 'CCE list',data,status.HTTP_200_OK)    


class CMViewList(APIView):
    def get(self, request):
        closing_manager = Users.objects.filter(groups__name='CLOSING_MANAGER')
         
        data = []

        for cm in closing_manager:
            cce_dict = {
                'id': cm.id,
                'cce_name' : cm.name
            }

            data.append(cce_dict)

        return ResponseHandler(False, 'Closing manager list',data,status.HTTP_200_OK)  


class SMViewList(APIView):
    def get(self, request):
        sourcing_manager = Users.objects.filter(groups__name='SOURCING_MANAGER')
         
        data = []

        for sm in sourcing_manager:
            cce_dict = {
                'id': sm.id,
                'cce_name' : sm.name
            }

            data.append(cce_dict)

        return ResponseHandler(False, 'Sourcing manager list',data,status.HTTP_200_OK) 


class CPViewList(APIView):
    def get(self, request):
        cp_list=ChannelPartner.objects.filter(full_name__isnull=False,firm__isnull=False)

        data=[
             {
                'id': cp.id,
                'cp_name': cp.full_name,
            }
            for cp in cp_list
        ]
        # for cp in cp_list:
        #     cp_list = {
        #         'id' : cp.id,
        #         'cp_name':cp.full_name
        #     }
        #     data.append(cp)
        return ResponseHandler(False,'Channel Partner list',data,status.HTTP_200_OK)    

