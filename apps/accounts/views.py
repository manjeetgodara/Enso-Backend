from django.shortcuts import render
from rest_framework import generics,status
from rest_framework.permissions import IsAuthenticated
from inventory.models import InventoryCostSheet, PropertyOwner
from comms.utils import send_push_notification
from auth.utils import ResponseHandler 
from .models import *
from .serializers import *
from lead.decorator import *
from river.models import *
from workflow.serializers import *
from django.shortcuts import get_object_or_404, redirect
from lead.pagination import CustomLimitOffsetPagination
from datetime import datetime,timedelta
from rest_framework.views import APIView
from workflow.utils import reset_task_approval_status
from lead.serializers import ChannelPartnerId
from django.db.models import Q
from django.utils.timezone import now
from decimal import Decimal
from django.utils.dateparse import parse_datetime
from django.db.models import Sum

# Create your views here.
class PaymentCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentSerializer
    pagination_class = CustomLimitOffsetPagination

    @check_access(required_groups=["ADMIN","MARKETING_HEAD","ACCOUNTS_HEAD","PROMOTER","VICE_PRESIDENT","SITE_HEAD"])
    def post(self, request, *args, **kwargs):
        try:
            module_param =  self.request.GET.get('module',None)

            if module_param and module_param == "Direct":
                if isinstance(request.data, list):
                    response_data = []
                    errors = []

                    for payment_data in request.data:
                        serializer = PaymentDirectSerializer(data=payment_data)
                        if serializer.is_valid():
                            payment = serializer.save()
                            response_data.append(serializer.data)
                        else:
                            errors.append(serializer.errors)

                    if errors:
                        return ResponseHandler(True, errors, None, status.HTTP_400_BAD_REQUEST)
                    else:
                        return ResponseHandler(False, "Payment Requests created successfully.", response_data, status.HTTP_201_CREATED)
                else:
                    return ResponseHandler(True, "Expected a list of payment data objects.", None, status.HTTP_400_BAD_REQUEST)

            else:    
                serializer = self.get_serializer(data=request.data)
                if serializer.is_valid():
                    payment=serializer.save()   

                    # Handle agency_names and agency_types
                    agency_names = request.data.get('agency_names', '').split(',')
                    agency_types = request.data.get('agency_types', '').split(',')
                    print(agency_names)
                    print(agency_types)


                    # Update payment instance with related agencies and types
                    if agency_names:
                        agencies = Agency.objects.filter(agency_name__in=agency_names)
                        print(agencies)
                        payment.agency_name.set(agencies)

                    if agency_types:
                        types = AgencyType.objects.filter(name__in=agency_types)
                        print(types)
                        payment.agency_type.set(types)   

                    definition=WorkflowDefinition.objects.filter(organization=self.request.user.organization,workflow_type='accounts').last()
                
                    if definition:
                    # if not payment.workflow.exists(): check this line
                        workflow_data = {
                            "payment": payment.id,
                            "definition": definition.id,
                            "name": definition.name,
                            "workflow_type": definition.workflow_type,
                            "organization": self.request.user.organization.id if self.request.user.organization else None,
                        }
                        workflow_ser = PaymentWorkflowCreateSerializer(data=workflow_data)
                        workflow_ser.is_valid(raise_exception=True)
                        workflow=workflow_ser.save()
                        print("Workflow created")
                        first_stage = payment.payment_workflow.get().stages.first()
                        first_task = first_stage.tasks.filter(completed=False).order_by('order').first()
                        state = get_object_or_404(State, label='In Progress')
                        first_task.status = state
                        first_task.save()
                        print("first task:",first_task)
                    
                        vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                        promoter_users = Users.objects.filter(groups__name="PROMOTER")[:3]
                        ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
                        ae_user = Users.objects.filter(groups__name="ACCOUNTS_EXECUTIVE").first()
                        # add type of marketing
                        source_variable = payment.payment_to
                        title = f"New Payment Request received from {source_variable}."
                        body = f"New Payment Request received from {source_variable}."
                        data = {'notification_type': 'request_deal_amount'}

                        if ae_user:
                            fcm_token_ae = ae_user.fcm_token
                            Notifications.objects.create(notification_id=f"task-{first_task.id}-{ae_user.id}", user_id=ae_user,created=timezone.now(), notification_message=body, notification_url=f'/accounts/payment_details/{payment.id}')
                            send_push_notification(fcm_token_ae, title, body, data)                           
                        if vp_user:
                            fcm_token_vp = vp_user.fcm_token
                            Notifications.objects.create(notification_id=f"task-{first_task.id}-{vp_user.id}", user_id=vp_user,created=timezone.now(), notification_message=body, notification_url=f'/accounts/payment_details/{payment.id}')
                            send_push_notification(fcm_token_vp, title, body, data)

                        for promoter_user in promoter_users:
                            if promoter_user:
                                fcm_token_promoter = promoter_user.fcm_token
                                Notifications.objects.create(notification_id=f"task-{first_task.id}-{promoter_user.id}", user_id=promoter_user,created=timezone.now(),  notification_message=body, notification_url=f'/accounts/payment_details/{payment.id}')
                                send_push_notification(fcm_token_promoter, title, body, data)

                        if ah_user:
                            fcm_token_ah = ah_user.fcm_token
                            Notifications.objects.create(notification_id=f"task-{first_task.id}-{ah_user.id}", user_id=ah_user,created=timezone.now(), notification_message=body, notification_url=f'/accounts/payment_details/{payment.id}')
                            send_push_notification(fcm_token_ah, title, body, data)
               
                    return ResponseHandler(False, "Payment Request created successfully.", serializer.data, status.HTTP_201_CREATED)
                else:
                    return ResponseHandler(True, serializer.errors,None, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHandler(True, f"Error creating Payment: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)    



class PaymentReterivalView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentReterivalSerializer
    pagination_class = CustomLimitOffsetPagination

    def get_queryset(self):
        queryset = Payment.objects.all()
        user = self.request.user
        if user.groups.filter(name__in=["ADMIN","ACCOUNTS_HEAD","ACCOUNTS_EXECUTIVE","PROMOTER","VICE_PRESIDENT"]).exists():
            print('here')
            return queryset.order_by('-id')

        elif user.groups.filter(name="MARKETING_HEAD").exists():
            queryset = queryset.filter(payment_type = 'Standard', payment_to="Marketing")
            return queryset.order_by('-id')
        
        elif user.groups.filter(name="SITE_HEAD").exists():
            queryset = queryset.filter(payment_type = 'Standard', payment_to="Sales")
            return queryset.order_by('-id')
        
    def get(self, request, *args, **kwargs):
        try:
            module_param = self.request.GET.get('module', None)
            campaign_param = self.request.GET.get('campaign_id',None)
            if module_param == "Marketing":
                payment = self.get_queryset()
                payment = payment.filter(payment_type = 'Standard', payment_to="Marketing")
                search_query = self.request.query_params.get('search', None)
                approval_param = self.request.query_params.get('approval_status', None)
                vendor_param = self.request.query_params.get('vendor_id', None)
                request_type_param = self.request.query_params.get('request_type', None)
                amount_from_param = self.request.query_params.get('amount_from', None)
                amount_to_param = self.request.query_params.get('amount_to', None)
                if vendor_param is not None:
                    payment = payment.filter(vendor=vendor_param)

                if search_query is not None:
                    try:
                        number_query = int(search_query)
                        payment = payment.filter(Q(id__icontains = number_query)| Q(vendor__name__icontains = search_query) )

                    except ValueError:
                        payment = payment.filter(vendor__name__icontains=search_query) 

                if approval_param is not None:
                    print('approval_param:', approval_param)
                    approval_param = approval_param.split(",")
                    payment = payment.filter(status__in=approval_param)

                if request_type_param is not None:
                    payment = payment.filter(request_type=request_type_param)

                if amount_from_param is not None and amount_to_param is not None:
                    payment = payment.filter(amount__gte=amount_from_param, amount__lte=amount_to_param)
                    
                date_range_param = request.GET.get('date_range', None)
                start_date_param =  request.GET.get('start_date', None)
                end_date_param =  request.GET.get('end_date', None)

                if date_range_param == 'next_7_days':
                    next_seven_days = datetime.now() + timedelta(days=7)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_seven_days)
                elif date_range_param == 'next_14_days':
                    next_fourteen_days = datetime.now() + timedelta(days=14)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_fourteen_days)
                elif date_range_param == 'next_1_month':
                    next_one_month = datetime.now() + timedelta(days=30)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_one_month)
                elif date_range_param == 'next_2_months':
                    next_two_months = datetime.now() + timedelta(days=60)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_two_months)
                elif date_range_param == 'custom_range' and start_date_param and end_date_param:
                    start_date = datetime.strptime(start_date_param, '%Y-%m-%d')
                    end_date = datetime.strptime(end_date_param, '%Y-%m-%d')
                    payment = payment.filter(due_date__gte=start_date, due_date__lte=end_date) 

                if payment.exists():
                    payments = self.paginate_queryset(payment)
                    serializer = MarketingPaymentSerializer(payments, many=True  , context={'request': request})
                    data = self.get_paginated_response(serializer.data).data                 
                    return ResponseHandler(False,"Marketing Payments retrieved successfully.", data, status.HTTP_200_OK)
                else:
                    page = self.paginate_queryset(payment)
                    dummy_data= self.get_paginated_response(page)
                    return ResponseHandler(False,"No data is present", dummy_data.data, status.HTTP_200_OK) 
            elif module_param == "Sales":
                payment = self.get_queryset()
                payment = payment.filter(payment_type = 'Standard', payment_to="Sales")
                search_query = self.request.query_params.get('search', None)
                approval_param = self.request.query_params.get('approval_status', None)
                channel_partner_id = self.request.query_params.get('channel_partner_id', None)
                request_type_param = self.request.query_params.get('request_type', None)
                amount_from_param = self.request.query_params.get('amount_from', None)
                amount_to_param = self.request.query_params.get('amount_to', None)
                if channel_partner_id is not None:
                    payment = payment.filter(channel_partner=channel_partner_id)

                if search_query is not None:
                    try:
                        number_query = int(search_query)
                        payment = payment.filter(id__icontains = number_query)

                    except ValueError:
                        payment = payment.filter(Q(channel_partner__full_name__icontains = search_query) | Q(channel_partner__firm__icontains = search_query)) 

                if approval_param is not None:
                    print('approval_param:', approval_param)
                    approval_param = approval_param.split(",")
                    payment = payment.filter(status__in=approval_param)

                if request_type_param is not None:
                    payment = payment.filter(request_type=request_type_param)

                if amount_from_param is not None and amount_to_param is not None:
                    payment = payment.filter(amount__gte=amount_from_param, amount__lte=amount_to_param)
                    
                date_range_param = request.GET.get('date_range', None)
                start_date_param =  request.GET.get('start_date', None)
                end_date_param =  request.GET.get('end_date', None)

                if date_range_param == 'next_7_days':
                    next_seven_days = datetime.now() + timedelta(days=7)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_seven_days)
                elif date_range_param == 'next_14_days':
                    next_fourteen_days = datetime.now() + timedelta(days=14)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_fourteen_days)
                elif date_range_param == 'next_1_month':
                    next_one_month = datetime.now() + timedelta(days=30)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_one_month)
                elif date_range_param == 'next_2_months':
                    next_two_months = datetime.now() + timedelta(days=60)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_two_months)
                elif date_range_param == 'custom_range' and start_date_param and end_date_param:
                    start_date = datetime.strptime(start_date_param, '%Y-%m-%d')
                    end_date = datetime.strptime(end_date_param, '%Y-%m-%d')
                    payment = payment.filter(due_date__gte=start_date, due_date__lte=end_date) 

                if payment.exists():
                    payments = self.paginate_queryset(payment)
                    serializer = SalesPaymentSerializer(payments, many=True , context={'request': request})
                    data = self.get_paginated_response(serializer.data).data                 
                    return ResponseHandler(False,"Marketing Payments retrieved successfully.", data, status.HTTP_200_OK)
                else:
                    page = self.paginate_queryset(payment)
                    dummy_data= self.get_paginated_response(page)
                    return ResponseHandler(False,"No data is present", dummy_data.data, status.HTTP_200_OK) 
            elif module_param == "Accounts":
                payment = self.get_queryset()
                payment = payment.filter(payment_type = 'Standard')
                search_query = self.request.query_params.get('search', None)
                approval_param = self.request.query_params.get('approval_status', None)
                # approval_details_param = self.request.query_params.get('approval_details', None)
                vendor_param = self.request.query_params.get('vendor_id', None)
                channel_partner_id = self.request.query_params.get('channel_partner_id', None)
                request_type_param = self.request.query_params.get('request_type', None)
                amount_from_param = self.request.query_params.get('amount_from', None)
                amount_to_param = self.request.query_params.get('amount_to', None)
                payment_filter_param = self.request.query_params.get('payment_to',None)
                # invoice_status_param = self.request.query_params.get("invoice_status", None)

                if payment_filter_param == 'all_pending':
                    payment = payment.filter(Q(status='Approval Pending') | Q(status='On Hold'))
                if vendor_param is not None:
                    payment = payment.filter(vendor=vendor_param)
                    
                if channel_partner_id is not None:
                    payment = payment.filter(channel_partner=channel_partner_id)

                if search_query is not None:
                    try:
                        number_query = int(search_query)
                        payment = payment.filter(id__icontains = number_query)

                    except ValueError:
                        payment = payment.filter(Q(vendor__name__icontains = search_query)| Q(channel_partner__full_name__icontains = search_query) | Q(channel_partner__firm__icontains = search_query)) 

                if approval_param is not None:
                    approval_param = approval_param.split(",")
                    payment = payment.filter(status__in=approval_param)

                if payment_filter_param:
                    payment = payment.filter(payment_to=payment_filter_param)
    

                if request_type_param is not None:
                    payment = payment.filter(request_type=request_type_param)

                if amount_from_param is not None and amount_to_param is not None:
                    payment = payment.filter(amount__gte=amount_from_param, amount__lte=amount_to_param)
                    
                date_range_param = request.GET.get('date_range', None)
                start_date_param =  request.GET.get('start_date', None)
                end_date_param =  request.GET.get('end_date', None)
                
                if date_range_param == 'today':
                    today = datetime.now().date()
                    payment = payment.filter(due_date=today)
                elif date_range_param == 'next_7_days':
                    next_seven_days = datetime.now() + timedelta(days=7)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_seven_days)
                elif date_range_param == 'next_2_weeks':
                    next_fourteen_days = datetime.now() + timedelta(days=14)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_fourteen_days)
                elif date_range_param == 'next_3_weeks':
                    next_three_weeks = datetime.now().date() + timedelta(days=21)
                    payment = payment.filter(due_date__gte=datetime.now().date(), due_date__lte=next_three_weeks)
                elif date_range_param == 'next_1_month':
                    next_one_month = datetime.now() + timedelta(days=30)
                    payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_one_month)
                # elif date_range_param == 'next_2_months':
                #     next_two_months = datetime.now() + timedelta(days=60)
                #     payment = payment.filter(due_date__gte=datetime.now(), due_date__lte=next_two_months)
                elif date_range_param == 'custom_range' and start_date_param and end_date_param:
                    start_date = datetime.strptime(start_date_param, '%Y-%m-%d')
                    end_date = datetime.strptime(end_date_param, '%Y-%m-%d')
                    payment = payment.filter(due_date__gte=start_date, due_date__lte=end_date) 
                
                
                # payments = payment.filter(status="Approval Pending")

                # # Retrieve the filtered queryset and apply the JSON-specific filtering in Python
                # filtered_payments = []

                # if invoice_status_param == "pending_from_vp":
                #     for p in payments:
                #         # Check if 'VP' is in the invoice_overview_list with status "Approval Pending"
                #         if any(entry.get("role") == "VP" and entry.get("status") == "Approval Pending" for entry in p.invoice_overview_list):
                #             filtered_payments.append(p)

                # elif invoice_status_param == "pending_from_promoter":
                #     for p in payments:
                #         # Check for any promoter roles (P1, P2, P3) with status "Approval Pending"
                #         if any(entry.get("role") in ["P1", "P2", "P3"] and entry.get("status") == "Approval Pending" for entry in p.invoice_overview_list):
                #             filtered_payments.append(p)

                if payment.exists():
                    payments = self.paginate_queryset(payment)
                    serializer = AccountsPaymentSerializer(payments, many=True , context={'request': request})
                    data = self.get_paginated_response(serializer.data).data                 
                    return ResponseHandler(False,"Payments retrieved successfully.", data, status.HTTP_200_OK)    
                else:
                    page = self.paginate_queryset(payment)
                    dummy_data= self.get_paginated_response(page)
                    return ResponseHandler(False,"No data is present", dummy_data.data, status.HTTP_200_OK) 
                
            elif module_param == 'Direct' and campaign_param is None:
                payment = self.get_queryset()
                payment = payment.filter(payment_type = 'Direct')
                if payment.exists():
                    payments = self.paginate_queryset(payment)
                    serializer = PaymentDirectSerializer(payments, many=True)
                    data = self.get_paginated_response(serializer.data).data       
                    return ResponseHandler(False,"Payment retrieved successfully.",data, status.HTTP_200_OK)
                else:
                    page = self.paginate_queryset(payment)
                    dummy_data= self.get_paginated_response(page)  
                    return ResponseHandler(False, "No data is present",  dummy_data.data,  status.HTTP_200_OK)  
            elif module_param == 'Direct' and campaign_param:
                payment = self.get_queryset()
                payment = payment.filter(payment_type = 'Direct', campaign=campaign_param)
                if payment.exists():
                    payments = self.paginate_queryset(payment)
                    serializer = PaymentDirectSerializer(payments, many=True)
                    data = self.get_paginated_response(serializer.data).data  
                    return ResponseHandler(False,"Payment retrieved successfully.", data, status.HTTP_200_OK)
                else:
                    page = self.paginate_queryset(payment)
                    dummy_data= self.get_paginated_response(page) 
                    return ResponseHandler(False, "No data is present",  dummy_data.data,  status.HTTP_200_OK)  
            else:
                payment = self.get_queryset()
                if payment.exists():
                    serializer = self.get_serializer(payment, many=True)
                    return ResponseHandler(False,"Payment retrieved successfully.", serializer.data, status.HTTP_200_OK)
                else:
                    page = self.paginate_queryset(payment)
                    dummy_data= self.get_paginated_response(page) 
                    return ResponseHandler(False, "No data is present",  dummy_data.data,  status.HTTP_200_OK)                        
        except Exception as e:
            return ResponseHandler(True, f"Error retrieving Payment: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            module_param = self.request.GET.get('module')
            if module_param == "direct":
                serializer = PaymentDirectSerializer(instance, context={'request': self.request})
            else:
                serializer = PaymentbyIdSerializer(instance, context={'request': self.request})
            return ResponseHandler(False, "Payment retrieved successfully", serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, *args, **kwargs):
        try:
            payment = self.get_object()
            module_param = self.request.GET.get('module')

            if module_param != "direct":
                first_stage = payment.payment_workflow.get().stages.first()
                first_task = first_stage.tasks.filter(completed=False).order_by('order').first()
                due_date_changed = False
          
            if 'due_date' in request.data:
                request_due_date = datetime.strptime(request.data['due_date'], '%Y-%m-%d').date()

                if request_due_date != payment.due_date:
                    due_date_changed = True
                    old_due_date = payment.due_date
                    old_due_date_format =  old_due_date.strftime('%d-%m-%Y')
                    new_due_date_format = request_due_date.strftime('%d-%m-%Y')
            if module_param == "direct":
                serializer = self.get_serializer(payment, data=request.data, partial=True)
                if serializer.is_valid():
                    serializer.save()
                    return ResponseHandler(False, "Payment updated successfully", serializer.data, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, serializer.errors,None, status.HTTP_400_BAD_REQUEST)   
            elif module_param == "payment":

                if first_task and first_task.status=='Accept':
                    return ResponseHandler(True, 'Payment is already approved',None, status.HTTP_400_BAD_REQUEST)

                state = get_object_or_404(State, label='In Progress')
                if first_task:
                    first_task.status = state
                    first_task.save()
                payment.status='Approval Pending'
                payment.denied_reason = ""
                payment.invoice_overview = ""
                # updating approval in payment list :
                for entry in payment.invoice_overview_list:
                    entry["status"] = "Approval Pending"
                payment.save()
            elif module_param == "on_hold_payment":
                print('module_param:', module_param)
                
                payment.status='Approval Pending'
                payment.denied_reason = ""
                payment.invoice_overview = ""

                # To continue from last approval
                # for entry in payment.invoice_overview_list:
                #     if entry["status"] == "On Hold":
                #         print('entry:', entry["status"])
                #         entry["status"] = "Approval Pending"

                # To start approval from beginning, reste the approval
                all_tasks = first_stage.tasks.all().order_by('order')
                request_state = get_object_or_404(State, label='Request')
                in_progress_state = get_object_or_404(State, label='In Progress')
                if all_tasks:
                    for task in all_tasks:
                        reset_task_approval_status(task.id)
                        task.completed = False
                        task.completed_at = None
                        task.status = in_progress_state if task.order == 0 else request_state
                        task.save()

                for entry in payment.invoice_overview_list:
                    entry["status"] = "Approval Pending"
                        
                payment.save()    
            elif module_param == "record_payment":
                payment.status='Payment Done'
                payment.transaction_id = request.data.get('transaction_id')
                payment.payment_mode = request.data.get('payment_mode')
                for entry in payment.invoice_overview_list:
                    if entry["status"] == "Approval Pending":
                        print('entry:', entry["status"])
                        entry["status"] = "Approve"
                payment.save()

                state = get_object_or_404(State, label='Accept')
                if first_task is not None:
                    first_task.status = state
                    first_task.completed = True
                    first_task.completed_at = datetime.now()
                    first_task.save()

                print("first task:",first_task)
                if payment.campaign:
                    campaign = Campaign.objects.filter(id=payment.campaign.id).first()
                    campaign.spend = campaign.spend + payment.amount
                    campaign.save()
            serializer = self.get_serializer(payment, data=request.data, partial=True)
            if serializer.is_valid():
                if request.data.get('status', None) == 'On Hold':
                    promoter_users = Users.objects.filter(groups__name="PROMOTER").order_by('id')[:3]
                    for entry in payment.invoice_overview_list:
                        if entry["role"] == "AE" and request.user.groups.filter(name="ACCOUNTS_EXECUTIVE").exists():
                            entry["status"] = "On Hold"
                        if entry["role"] == "VP" and request.user.groups.filter(name="VICE_PRESIDENT").exists():
                            entry["status"] = "On Hold"
                        if entry["role"] == "P1" and request.user == promoter_users[0]:
                            entry["status"] = "On Hold"
                        if entry["role"] == "P2" and request.user == promoter_users[1]:
                            entry["status"] = "On Hold"
                        if entry["role"] == "P3" and request.user == promoter_users[2]:
                            entry["status"] = "On Hold"
                        if entry["role"] == "AH" and request.user.groups.filter(name="ACCOUNTS_HEAD").exists():
                            entry["status"] = "On Hold"

                serializer.save()
        
                vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                promoter_users = Users.objects.filter(groups__name="PROMOTER")[:3]
                ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
                ae_user = Users.objects.filter(groups__name="ACCOUNTS_EXECUTIVE").first()
                # body = f"Payment request has been updated by {self.request.user.name}."
                if due_date_changed:
                    title = "Payment request has been updated."
                    body = f"Due date has been changed from {old_due_date_format} to {new_due_date_format} by {self.request.user.name}."
                    data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/marketing/budget_payments/payment/{payment.id}/0'}
                elif module_param == "record_payment":
            
                    ah_user = Users.objects.filter(groups__name="ACCOUNTS_HEAD").first()
                    sh_user = Users.objects.filter(groups__name ="SITE_HEAD").first()
                    title = f"Payment of {payment.amount} has been made"
                    
                    data = {'notification_type': 'payment_done', 'redirect_url': f'/marketing/budget_payments/payment/{payment.id}/0'}
                    
                    if payment.payment_to == 'Marketing' and ah_user:
                        body = f"Payment of {payment.amount} has been made by {ah_user.name} on {payment.paid_date} {payment.paid_time}"
                        fcm_token_promoter = ah_user.fcm_token
                        Notifications.objects.create(notification_id=f"task-{payment.id}-{ah_user.id}", user_id=ah_user,created=timezone.now(), notification_message=body, notification_url=f'/marketing/budget_payments/payment/{payment.id}/0')
                        send_push_notification(fcm_token_promoter, title, body, data)  
                        
                    elif payment.payment_to == 'Sales' and sh_user:
                        body = f"Payment of {payment.amount} has been made by {sh_user.name} on {payment.paid_date} {payment.paid_time}"
                        fcm_token_promoter = sh_user.fcm_token
                        Notifications.objects.create(notification_id=f"task-{payment.id}-{sh_user.id}", user_id=sh_user,created=timezone.now(), notification_message=body, notification_url=f'/marketing/budget_payments/payment/{payment.id}/0')
                        send_push_notification(fcm_token_promoter, title, body, data)  

                else:
                    title = "Payment request has been updated."
                    body = f"Payment request has been updated by {self.request.user.name}."
                    data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/marketing/budget_payments/payment/{payment.id}/0'}
                    
                first_task_id = first_task.id if first_task else None
                if vp_user and not vp_user == self.request.user:
                    fcm_token_vp = vp_user.fcm_token
                    Notifications.objects.create(notification_id=f"task-{first_task_id}-{vp_user.id}", user_id=vp_user,created=timezone.now(), notification_message=body, notification_url=f'/marketing/budget_payments/payment/{payment.id}/0')
                    send_push_notification(fcm_token_vp, title, body, data)

                for promoter_user in promoter_users:
                    if promoter_user and not promoter_user ==self.request.user:
                        fcm_token_promoter = promoter_user.fcm_token
                        Notifications.objects.create(notification_id=f"task-{first_task_id}-{promoter_user.id}", user_id=promoter_user,created=timezone.now(), notification_message=body, notification_url=f'/marketing/budget_payments/payment/{payment.id}/0')
                        send_push_notification(fcm_token_promoter, title, body, data)

                if ae_user and not ae_user == self.request.user:
                    fcm_token_ae = ae_user.fcm_token
                    Notifications.objects.create(notification_id=f"task-{first_task_id}-{ae_user.id}", user_id=ae_user,created=timezone.now(), notification_message=body, notification_url=f'/marketing/budget_payments/payment/{payment.id}/0')
                    send_push_notification(fcm_token_ae, title, body, data)
                #  AH notification commented because AH dont have access to Marketing Module 
                # if ah_user and not ah_user ==self.request.user:
                #     fcm_token_ah = ah_user.fcm_token
                #     Notifications.objects.create(notification_id=f"task-{first_task_id}-{ah_user.id}", user_id=ah_user,created=timezone.now(), notification_message=body,  notification_url=f'/marketing/budget_payments/payment/{payment.id}/0')
                #     send_push_notification(fcm_token_ah, title, body, data)

                return ResponseHandler(False, "Payment updated successfully", serializer.data, status.HTTP_200_OK)
            else:
                return ResponseHandler(True, serializer.errors,None, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return ResponseHandler(True, f"Error: {str(e)}", None,status.HTTP_500_INTERNAL_SERVER_ERROR)
     
    def delete(self, request, *args, **kwargs):
        try:
            payment = self.get_object()
            payment.delete()
            return ResponseHandler(False, "Payment deleted successfully.", None, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class GetMetaDataAPIView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            campaigns = Campaign.objects.values('id', 'campaign_name')
            
            campaigns_dict =[{'id': campaign['id'], 'value': f"{campaign['campaign_name']} "} for campaign in campaigns]

            vendors =  Vendor.objects.values('id', 'name')

            vendors_dict =[{'id': vendor['id'], 'value': vendor['name']} for vendor in vendors]

            payment_choices = ["Cash", "Paytm", "Phone Pe", "UPI", "Razorpay", "Bank transfer"]

            meta_data = {'campaigns': campaigns_dict, 'vendors': vendors_dict, 'payment_mode':payment_choices}


            return ResponseHandler(False, "Meta data retrieved successfully.", meta_data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, f"Error retrieving meta data: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class HistoryRetrievalView(APIView):
    def get(self, request, payment_id):
        try:
            payment = get_object_or_404(Payment, id=payment_id)
            payment_history = payment.history.all()
            payment_history_data = PaymentHistorySerializer(payment_history, many=True).data  
            payment_history_list = []
            payment_history_list.extend(payment_history_data)
            first_stage = payment.payment_workflow.get().stages.first()
            all_tasks = first_stage.tasks.all().order_by('order')
            ids = all_tasks.values_list('id', flat=True)
            print("ids: ", ids)


            query = '''
                SELECT * FROM public.river_historicaltransitionapproval
                WHERE object_id = %s
                ORDER BY history_id ASC;
            '''
            transitionapproval_data = []
            for id in ids:
                print("id: ", id)
                history_records = TransitionApproval.objects.raw(query, [str(id)])
                if history_records:
                    history_data = TransitionApprovalHistorySerializer(history_records, many=True).data 
                    transitionapproval_data.append(history_data)
            all_history_data = [item for sublist in transitionapproval_data for item in sublist]

            # Sort the flattened list based on the 'history_date'
            # sorted_transitionapproval_data = sorted(all_history_data, key=lambda x: x['history_date'], reverse=True)
            # print("data:",transitionapproval_data  )
            all_data = payment_history_data + all_history_data
            sorted_history = sorted(all_data, key=lambda x: x['history_date'], reverse=True)
                                

            for record in sorted_history:
                if record['history_type'] == "~":
                    if record['activity_type'] == "TransitionApproval" and record['status'] == "approved" :
                        history_user = record['history_user']
                        record['message'] = f'Payment Approved by  {history_user}'
                    if record['activity_type'] == "TransitionApproval" and record['status'] == "cancelled" :
                            history_user = record['history_user']
                            record['message'] = f'Payment Denied by  {history_user}'

                    previous_record = None

                    if record['activity_type'] == "Payment":
                        previous_record = next(
                            (prev for prev in sorted_history if prev['history_date'] < record['history_date'] and prev['activity_type'] == "Payment"),
                            None
                        )                                                 
                    if previous_record:

                        changed_fields = self.find_changed_fields(previous_record, record)
                        if changed_fields:
                            record['changed_fields'] = changed_fields
                                        
                            if record['activity_type'] == "Payment":
                                messages = []     
                                if 'amount' in changed_fields and changed_fields.get("amount").get("new_value") is not None:
                                    old_amount = changed_fields.get("amount").get("old_value")
                                    new_amount = changed_fields.get("amount").get("new_value")
                                    if old_amount is None:
                                        messages.append(f'Payment Amount added {new_amount}')
                                    else:
                                        #record['message'] = f'Amount Changed from {old_amount} to {new_amount}.'
                                        messages.append(f'Payment Amount Changed from {old_amount} to {new_amount}.')
                                if 'transaction_id' in changed_fields and changed_fields.get("transaction_id").get("new_value") is not None:
                                    old_transaction_id = changed_fields.get("transaction_id").get("old_value")
                                    new_transaction_id = changed_fields.get("transaction_id").get("new_value")
                                    if old_transaction_id is None:
                                        messages.append(f'Payment Transaction Id added {new_transaction_id}')
                                    else:
                                        messages.append(f'Payment Transaction Id Changed from {old_transaction_id} to {new_transaction_id}')
                                if 'vendor' in changed_fields and changed_fields.get("vendor").get("new_value") is not None and changed_fields.get("vendor").get("old_value") is not None:
                                    old_vendor = changed_fields.get("vendor").get("old_value")
                                    new_vendor = changed_fields.get("vendor").get("new_value")
                                    old_vendor_instance = Vendor.objects.get(id=old_vendor)
                                    old_vendor_name = old_vendor_instance.name
                                    new_vendor_instance = Vendor.objects.get(id=new_vendor)
                                    new_vendor_name = new_vendor_instance.name     
                                    #record['message'] = f'Vendor Changed from {old_vendor} to {new_vendor}' 
                                    messages.append(f'Vendor Changed from {old_vendor_name} to {new_vendor_name}')

                                if 'status' in changed_fields and changed_fields.get("status").get("new_value") is not None:
                                    old_status = changed_fields.get("status").get("old_value")
                                    new_status = changed_fields.get("status").get("new_value")

                                    if old_status is None:
                                        messages.append(f'Payment status added {new_status}')
                                    elif new_status == 'Payment Done':
                                        approved_by = record.get("history_user")
                                        messages.append(f'Payment Approved by {approved_by}' ) 
                                    elif new_status == 'Reject':
                                        rejected_by = record.get("history_user")
                                        messages.append(f'Payment Rejected by {rejected_by}' ) 
                                    else:
                                        messages.append(f'Payment status Changed from {old_status} to {new_status}' ) 

                                if 'payment_mode' in changed_fields and changed_fields.get("payment_mode").get("new_value") is not None:
                                    old_payment_mode = changed_fields.get("payment_mode").get("old_value")
                                    new_payment_mode = changed_fields.get("payment_mode").get("new_value")
                                    if old_payment_mode is None:
                                        messages.append(f'Payment status added {new_payment_mode}')
                                    else:
                                        messages.append(f'Payment Mode Changed from {old_payment_mode} to {new_payment_mode}')

                                if 'due_date' in changed_fields and changed_fields.get("due_date").get("new_value") is not None:
                                    old_due_date = changed_fields.get("due_date").get("old_value")
                                    new_due_date = changed_fields.get("due_date").get("new_value")  
                                    
                                    if old_due_date is None:
                                        messages.append(f'Payment Duedate added {new_due_date}')
                                    else:
                                        messages.append(f'Payment Duedate Changed from {old_due_date} to {new_due_date}')  

                                if 'paid_date' in changed_fields and changed_fields.get("paid_date").get("new_value") is not None:
                                    old_paid_date = changed_fields.get("paid_date").get("old_value")
                                    new_paid_date = changed_fields.get("paid_date").get("new_value")

                                    if old_paid_date is None:
                                        messages.append(f'Payment paid date added {new_paid_date}')
                                    else:
                                        messages.append(f'Payment paid date Changed from {old_paid_date} to {new_paid_date}')

  
                                if 'paid_time' in changed_fields and changed_fields.get("paid_time").get("new_value") is not None:
                                    old_paid_time = changed_fields.get("paid_time").get("old_value")
                                    new_paid_time = changed_fields.get("paid_time").get("new_value") 

                                    if old_paid_time is None:
                                        messages.append(f'Payment paid time added {new_paid_time}')
                                    else: 
                                        messages.append(f'Payment paid time Changed from {old_paid_time} to {new_paid_time}')  

                                if 'payment_to' in changed_fields and changed_fields.get("payment_to").get("new_value") is not None:
                                    old_payment_to = changed_fields.get("payment_to").get("old_value")
                                    new_payment_to = changed_fields.get("payment_to").get("new_value") 

                                    if old_payment_to is None:
                                        messages.append(f'Payment paid to {new_payment_to}')
                                    else:  
                                        messages.append(f'Payment paid to Changed from {old_payment_to} to {new_payment_to}') 

                                if 'payment_for' in changed_fields and changed_fields.get("payment_for").get("new_value") is not None:
                                    old_payment_for = changed_fields.get("payment_for").get("old_value")
                                    new_payment_for = changed_fields.get("payment_for").get("new_value")
                                                                                            
                                    if old_payment_for is None:
                                        messages.append(f'Payment paid for  {new_payment_for}')
                                    else:                                                             
                                        messages.append(f'Payment paid for Changed from {old_payment_for} to {new_payment_for}') 

                                if 'denied_reason' in changed_fields and changed_fields.get("denied_reason").get("new_value") is not None:
                                    old_denied_reason = changed_fields.get("denied_reason").get("old_value")
                                    new_denied_reason = changed_fields.get("denied_reason").get("new_value") 

                                    if old_denied_reason is None and not new_denied_reason == '' or old_denied_reason == '' and new_denied_reason is not None:
                                        if record.get('status') == 'On Hold':
                                            messages.append(f'Payment is put On Hold due to {new_denied_reason}')  
                                        else:                                         
                                            messages.append(f'Payment is denied due to {new_denied_reason}')
                                    elif new_denied_reason is None or new_denied_reason == "":
                                        pass
                                    else:                                                             
                                        messages.append(f'Payment denied due to {new_denied_reason}') 

                                if 'attached_documents' in changed_fields and changed_fields.get("attached_documents").get("new_value") is not None:
                                    old_attached_documents = changed_fields.get("attached_documents").get("old_value")
                                    new_attached_documents = changed_fields.get("attached_documents").get("new_value")    
                                   
                                    if old_attached_documents is None:
                                        messages.append(f'Payment documents added')
                                    else:                                                             
                                        messages.append(f'Payment documents have been updated')     
                                
                                if 'request_type' in changed_fields and changed_fields.get("request_type").get("new_value") is not None:
                                    old_request_type = changed_fields.get("request_type").get("old_value")
                                    new_request_type = changed_fields.get("request_type").get("new_value")
                                   
                                    if old_request_type is None:
                                        messages.append(f'Payment request added {new_request_type}')
                                    else:                                                                 
                                        messages.append(f'Payment request Changed from {old_request_type} to {new_request_type}')  

                                if 'campaign' in changed_fields and changed_fields.get("campaign").get("new_value") is not None:
                                    old_campaign = changed_fields.get("campaign").get("old_value")
                                    new_campaign = changed_fields.get("campaign").get("new_value")    
                                    if old_campaign is None:
                                        messages.append(f'Payment campaign added {new_campaign}')
                                    else:                                                                 
                                        messages.append(f'Payment campaign Changed from {old_campaign} to {new_campaign}')  

                                if 'agency_type' in changed_fields and changed_fields.get("agency_type").get("new_value") is not None:
                                    old_agency_type = changed_fields.get("agency_type").get("old_value")
                                    new_agency_type = changed_fields.get("agency_type").get("new_value")    

                                    if old_agency_type is None:
                                        messages.append(f'Payment agency type added {new_agency_type}')
                                    else:                                                                 
                                        messages.append(f'Payment agency type Changed from {old_agency_type} to {new_agency_type}') 

                                if 'source_id' in changed_fields and changed_fields.get("source_id").get("new_value") is not None:
                                    old_source_id = changed_fields.get("source_id").get("old_value")
                                    new_source_id = changed_fields.get("source_id").get("new_value") 

                                    if old_source_id is None:
                                        messages.append(f'Payment source id added {new_source_id}')
                                    else:                                                                 
                                        messages.append(f'Payment source id Changed from {old_source_id} to {new_source_id}') 

                                if 'campaign_type' in changed_fields and changed_fields.get("campaign_type").get("new_value") is not None:
                                    old_campaign_type = changed_fields.get("campaign_type").get("old_value")
                                    new_campaign_type = changed_fields.get("campaign_type").get("new_value")   

                                    if old_campaign_type is None:
                                        messages.append(f'Payment Campaign type added {new_campaign_type}')
                                    else:                                                                   
                                        messages.append(f'Payment Campaign type Changed from {old_campaign_type} to {new_campaign_type}')

                                # if 'invoice_overview' in changed_fields and changed_fields.get("invoice_overview").get("new_value") is not None:
                                #     old_invoice_overview = changed_fields.get("invoice_overview").get("old_value")
                                #     new_invoice_overview = changed_fields.get("invoice_overview").get("new_value")    

                                #     if old_invoice_overview is None:
                                #         messages.append(f'Payment invoice overview added {new_invoice_overview}')
                                #     elif new_invoice_overview is None or new_invoice_overview == "":
                                #         pass    
                                #     else:                                                                   
                                #         messages.append(f'Payment invoice overview Changed from {old_invoice_overview} to {new_invoice_overview}')    
                      
                                if messages:
                                    record['message'] = ', '.join(messages)      
            sorted_history = [record for record in sorted_history if record['message'] not in ["Payment Details Edited","TransitionApproval Created","TransitionApproval Deleted"]]  

            response_data = {
                        'activity_history': sorted_history,  
                    }
            return ResponseHandler(False, 'Data retrieved successfully', response_data, 200)

        except Exception as e:
            return ResponseHandler(True, 'Error retrieving activity data', str(e), 500)
        
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

class NotesListCreateView(generics.ListCreateAPIView):
    queryset = Notes.objects.all()
    serializer_class = NotesSerializer
    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        request.data["created_by"] = request.user.id

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)

            return ResponseHandler(False , 'Note created successfully.', serializer.data ,status.HTTP_201_CREATED)
        else:
            return ResponseHandler(True , serializer.errors , None, status.HTTP_400_BAD_REQUEST)
        

class NotesListView(generics.ListAPIView):
    serializer_class = NotesSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        payment_id = self.kwargs.get('payment_id')
        
        try:
            payment = Payment.objects.get(id=payment_id)
            queryset = Notes.objects.filter(payment=payment).order_by('-id')
            return queryset
        
        except Payment.DoesNotExist:
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
            return ResponseHandler(False, "Notes retrieved successfully." , serializer.data,status.HTTP_200_OK)
        else:
            return ResponseHandler(False, "Notes are not present.", [], status.HTTP_200_OK)


class UpdateOrDeleteNoteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Notes.objects.all()
    serializer_class = NotesSerializer
    permission_classes = (IsAuthenticated,)
    lookup_field = 'id'

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return ResponseHandler(False, 'Notes retrieved successfully', serializer.data, status.HTTP_200_OK)
        except Notes.DoesNotExist:
            return ResponseHandler(True, 'Notes ID not found', None, status.HTTP_404_NOT_FOUND)
        
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)

            if serializer.is_valid():
                queryset = Notes.objects.get(pk=kwargs['id'])
                if queryset.created_by == self.request.user:
                    serializer.save()
                    return ResponseHandler(False, "Notes updated successfully.", serializer.data, status.HTTP_200_OK)
                else:
                    return ResponseHandler(True, 'Access Denied',None, status.HTTP_400_BAD_REQUEST)
            else:
                return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
        except Notes.DoesNotExist:
            return ResponseHandler(True, "Note not found.", "Note not found.", status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHandler(True, "An error occurred.", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance:
                instance.delete()
                return ResponseHandler(False, "Note deleted successfully.", None, status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Note not found.", "Note not found.", status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return ResponseHandler(True, "An error occurred.", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class SalesPaymentMetadataAPI(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        try:
            from inventory.models import ProjectDetail, ProjectInventory
            from inventory.serializers import ProjectInventorySerializer, ProjectDetailSerializer

            project_details = ProjectDetail.objects.all()

            project_details_with_inventories = []
            for project_detail in project_details:

                data = dict()

                project = ProjectDetailSerializer(project_detail, many=False).data
                # print('project:', project)

                project_inventories = ProjectInventory.objects.filter(tower__project_id=project_detail.id,status="Booked").order_by("apartment_no")

                project_inventories = ProjectInventorySerializer(project_inventories, many=True).data

                # data['project'] = project
                project['inventories'] = project_inventories

                project_details_with_inventories.append(project)


            channel_partners = ChannelPartner.objects.all()
            channel_partners = ChannelPartnerId(channel_partners, many=True).data
            metadata = {
                'project_details': project_details_with_inventories,
                'channel_partners': channel_partners
            }

            return ResponseHandler(False, "Sales payment meta data retrieved successfully.", metadata, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, f"Error retrieving meta data: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)


class CustomerPaymentCreateView(APIView):
    """
    View to create a new CustomerPayment.
    """
    def post(self, request, lead_id):
        # Fetch the lead object based on the lead_id passed in the URL
        lead = get_object_or_404(Lead, id=lead_id)

        # Combine lead_id with other data
        payment_data = request.data.copy()
        payment_data['lead'] = lead.id

         # Initialize TDS variables
        total_tds_amount = Decimal('0.0')
        payment_data['tds_status'] = "Pending"
        
        payment_type = payment_data.get('payment_type', 'Payment')

        # Get event names
        event_names = payment_data.get('event_name', '').split(',')

        for event_name in event_names:
            event_name = event_name.strip()  # Clean whitespace
            inventory_cost_sheet = InventoryCostSheet.objects.filter(
                lead=lead,
                event=event_name
            ).first()

            # Accumulate TDS amount if an entry is found
            if inventory_cost_sheet and inventory_cost_sheet.tds:
                total_tds_amount += inventory_cost_sheet.tds

        # Add TDS amount to payment data
        payment_data['tds_amount'] = total_tds_amount
        payment_data['tds_date'] = None
        payment_data['tds_time'] = None

        # Serialize and save the payment record
        serializer = CustomerPaymentSerializer(data=payment_data)
        if serializer.is_valid():
            payment = serializer.save()

            if payment_type != "Refund":

                # Get event_name from payment data
                event_names = payment_data.get('event_name', '').split(',')

                payment_amount = Decimal(payment_data.get('amount', '0'))

                payment_date = payment_data.get('date')  
                payment_time = payment_data.get('time')  

                # Combine date and time into a DateTime object
                if payment_date and payment_time:
                    paid_date_str = f"{payment_date} {payment_time}"
                    paid_date = parse_datetime(paid_date_str)
                else:
                    paid_date = None

                # Update InventoryCostSheet entries for each event_name
                for event_name in event_names:
                    
                    event_name = event_name.strip()  # Remove leading/trailing whitespace
                    inventory_cost_sheet = InventoryCostSheet.objects.filter(
                        lead=lead,
                        event=event_name
                    ).first()

                    print("inventory_cost_sheet" , inventory_cost_sheet)

                    # Update paid status and paid_date if an entry is found
                    if inventory_cost_sheet:
                        # Get total_amount and amount, setting defaults if None
                        total_amount = inventory_cost_sheet.total_amount or Decimal('0')
                        amount = inventory_cost_sheet.amount_paid or Decimal('0')
                        
                        # Calculate remaining amount for this event
                        remaining_amount = total_amount - amount

                        print("total amount:", total_amount)
                        print("amount:", amount)
                        print("remaining_amount:", remaining_amount)

                        # Determine how much of the payment amount should be applied to this event
                        if payment_amount > remaining_amount:
                            # If the payment amount is greater than the remaining amount
                            inventory_cost_sheet.amount_paid = total_amount
                            # inventory_cost_sheet.completed = True
                            # inventory_cost_sheet.completed_at = timezone.now()  
                            payment_amount -= remaining_amount
                        else:
                            # If the payment amount is less than or equal to the remaining amount
                            inventory_cost_sheet.amount_paid += payment_amount
                            payment_amount = Decimal('0')

                        print("payment amount:", payment_amount)

                        # Check if the remaining difference between total and current amount is zero
                        diff_amount = total_amount - inventory_cost_sheet.amount_paid
                        if diff_amount == 0:
                            inventory_cost_sheet.completed = True
                            inventory_cost_sheet.completed_at = timezone.now()

                        # Update paid status and paid_date
                        inventory_cost_sheet.paid = True
                        inventory_cost_sheet.paid_date = paid_date
                        inventory_cost_sheet.save()

                        # Break out of the loop if payment amount is exhausted
                        if payment_amount <= 0:
                            break

            elif payment_type == "Refund":
                refund_total_dict = CustomerPayment.objects.filter(
                    lead_id=lead_id,
                    payment_type='Refund'
                ).aggregate(total_refund=Sum('amount'))
                refund_total = refund_total_dict.get('total_refund', Decimal('0'))
                inventory_owner = PropertyOwner.objects.filter(lead = lead_id).first()
                print("inventory owner",inventory_owner)

                if inventory_owner:

                    refund_amount = inventory_owner.refund_amount
                    print(refund_amount)

                    if refund_total >= refund_amount :
                        print("inside")
                        inventory_owner.refund_status = True
                        inventory_owner.save()
                      

            return ResponseHandler(False, "Payment recorded successfully and Inventory Cost Sheets updated.", serializer.data, status.HTTP_201_CREATED)
        
        return ResponseHandler(True, "Error in recording payment", serializer.errors, status.HTTP_400_BAD_REQUEST)



class CustomerPaymentListView(APIView):
    """
    View to fetch CustomerPayments by lead_id.
    """
    def get(self, request, lead_id):
        payments = CustomerPayment.objects.filter(lead_id=lead_id , payment_type__in = ["Payment","TDS"]).order_by('-created_date')
        if not payments.exists():
            return ResponseHandler(False, "No records found for the specified lead_id.", [], status.HTTP_200_OK)
        
        serializer = CustomerPaymentSerializer(payments, many=True)
        return ResponseHandler(False,"Transaction updates reterieve successfully",serializer.data,status.HTTP_200_OK)



class LatestRefundPaymentView(generics.GenericAPIView):
    serializer_class = CustomerPaymentSerializer

    def get(self, request, lead_id):
        # Get the lead object; if it does not exist, raise a 404 error
        lead = get_object_or_404(Lead, id=lead_id)
        
        # Query the latest refund payment for the lead
        latest_refund = CustomerPayment.objects.filter(lead=lead, payment_type="Refund").order_by('-date', '-time').first()
        
        # If no refund payment is found, return a 404 response
        if not latest_refund:
            return ResponseHandler(True, "No refund payment found for this lead.",None,status.HTTP_404_NOT_FOUND)
        
        # Serialize the latest refund payment
        serializer = self.get_serializer(latest_refund)
        return ResponseHandler(False,"Refund data reterieved successfully",serializer.data,status.HTTP_200_OK)


class RecordTDSPaymentView(APIView):
    def post(self, request, lead_id):
        lead = get_object_or_404(Lead, id=lead_id)
        event_names = request.data.get('event_name')  # Comma-separated string
        tds_transaction_id = request.data.get('tds_transaction_id')
        tds_date = request.data.get('tds_date', now().date())
        tds_time = request.data.get('tds_time', now().time())
        tds_amount = request.data.get('tds_amount')

        if not lead_id or not event_names:
            return ResponseHandler( True, 
                "Both 'lead_id' and 'event_name' are required.", None,
                status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return ResponseHandler( True,
                "Lead with the given ID does not exist.", None,
                status.HTTP_404_NOT_FOUND,
            )
        
        event_names_list = [name.strip() for name in event_names.split(',')]
        print(event_names_list)

        existing_payments = CustomerPayment.objects.filter(lead=lead)
        print(existing_payments)
        
        if not existing_payments.exists():
            return ResponseHandler( True,
                "No existing payments found for the given lead.", None,
                status.HTTP_404_NOT_FOUND,
            )

        # Match events and identify the most recent relevant payment
        matching_payment = None
        for payment in existing_payments.order_by('-created_date'):  # Assuming created_date exists
            if payment.event_name:
                event_names_in_payment = [name.strip() for name in payment.event_name.split(',')]
                print(event_names_in_payment)
                if any(event in event_names_list for event in event_names_in_payment):
                    matching_payment = payment
                    print(matching_payment)
                    break  # Stop at the most recent match

        if matching_payment:
            print("Matching Payment Found:", matching_payment)

            CustomerPayment.objects.create(lead=lead,transaction_id=matching_payment.transaction_id,
                                           date=matching_payment.date,
                                           time=matching_payment.time, amount= matching_payment.amount,
                                            event_name= event_names, tds_transaction_id=tds_transaction_id,tds_date=tds_date,tds_time=tds_time,
                                            tds_status="Paid", payment_type="TDS", payment_mode=matching_payment.payment_mode,tds_amount=tds_amount)
            
            for event in event_names_list:
            
                inventory_cost_sheet = InventoryCostSheet.objects.filter(
                        lead=lead,
                        event=event
                    ).first()

                print("inventory_cost_sheet" , inventory_cost_sheet)

                # Update paid status and paid_date if an entry is found
                if inventory_cost_sheet:
                    inventory_cost_sheet.tds_paid=True
                    inventory_cost_sheet.tds_paid_date=tds_date
                    inventory_cost_sheet.save()
                
        else:
            return ResponseHandler( True, "None"
                "No matching payment events found.",
                status.HTTP_404_NOT_FOUND
            )            

        return ResponseHandler( False, 
            "TDS payment recorded successfully.", None,
            status.HTTP_200_OK,
        )



def update_invoice_overview_list():
    # Get all Payment instances
    payments = Payment.objects.all()

    # Update invoice_overview_list for each Payment instance
    for payment in payments:
        updated = False  # Flag to track if any updates were made
        
        for entry in payment.invoice_overview_list:
            # Check if status is "Approve" or "Reject"
            if entry.get('status') in ["Approve", "Reject"]:
                # Set approval_time to the current time using strftime
                entry['time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                updated = True  # Mark as updated

        if updated:
            # Save the updated Payment instance only if changes were made
            payment.save()
    
    print("Done")       
