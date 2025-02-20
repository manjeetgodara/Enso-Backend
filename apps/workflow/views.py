from django.shortcuts import render
from rest_framework import viewsets
from .serializers import TaskSerializer, WorkflowSerializer, NotificationsSerializer
from .models import Task, Notifications
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.db.models import Max
from django.urls import reverse
from django.http.response import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from river.models import State, Workflow, TransitionApprovalMeta, TransitionMeta, Transition
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Group
from .serializers import ApprovalSerializer
from rest_framework.permissions import IsAuthenticated
from lead.decorator import check_group_access
from river.models import State
from auth.utils import ResponseHandler
from workflow.models import Task
from .tasks import process_task
from inventory.models import PropertyOwner,ProjectInventory, BookingForm, SalesActivity
from auth.models import Users
from lead.models import Lead
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from accounts.models import Payment
from marketing.models import Campaign
from comms.utils import send_push_notification
from datetime import datetime,timedelta
from django.utils import timezone
from workflow.utils import reset_task_approval_status
from inventory.utils import create_property_owner_and_inventory_cost_sheets
class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    queryset = Task.objects.all()
    permission_classes = (IsAuthenticated, )

    def list(self, request, *args, **kwargs):
        print('request:', request.user.id)
        time_lte=request.GET.get('time_lte', None)
        time_gte=request.GET.get('time_gte', None)
        date=request.GET.get('date', None)
        # Todo get tasks based on stage__assigned_to, showing task with task_type = 'appointment'
        # task_list = Task.objects.filter((Q(workflow__assigned_to=request.user)|Q (workflow__lead__creator=request.user)|Q(workflow__lead__followers__contains=[request.user.id])), completed= False, task_type__in=['appointment'])
        task_list = Task.objects.filter((Q(workflow__assigned_to=request.user)|Q (workflow__lead__creator=request.user)|Q(workflow__lead__followers__contains=[request.user.id])), completed= False)
        # task_list = Task.objects.filter((Q(workflow__assigned_to=request.user)|Q (workflow__lead__creator=request.user)), completed= False)

        if time_lte:
            task_list=task_list.filter(time__lte=time_lte)
        if time_gte:
            task_list=task_list.filter(time__gte=time_gte)
        if date:
            task_list=task_list.filter(time__date=date)
        
        print('task_list:', task_list)
        task_list=task_list.order_by("-id")
        serializer = self.get_serializer(task_list, many = True)
        return ResponseHandler(False, "Tasks retrieved successfully." , serializer.data,status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        print('request:', request.data)
        serializer = self.get_serializer(data = request.data)
        serializer.is_valid(raise_exception = True)
        stage = serializer.validated_data['stage']
        max_order_dict = stage.tasks.aggregate(Max('order'))
        max_order_yet = max_order_dict.get('order__max', None)
        task = serializer.save()
        if max_order_yet:
            task.order = max_order_yet+1
        else:
            task.order = 1

        task.groups.set(request.data['groups'])
        task.users.set(request.data['users'])
        if 'status' in request.data:
            state = get_object_or_404(State, label=request.data['status'])
            task.status = state
            
        task.save()

        if task.task_type == 'automation' and task.action == 'send_mail':
            template_id = request.data.get('template', None)
            if template_id:
                # task = workflow_email_update(task, request, template_id)
                pass
            else:
                return ResponseHandler(True, "Email Template not Found!" , None,status.HTTP_404_NOT_FOUND)


        return ResponseHandler(False, "Task created successfully." , TaskSerializer(task).data,status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except Exception as e:
            return ResponseHandler(True, str(e) , None,status.HTTP_404_NOT_FOUND)

        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance = instance, data = request.data, partial = partial)
        # serializer.is_valid(raise_exception = True)

        try:
            serializer.is_valid(raise_exception = True)
        except Exception as e:
            return ResponseHandler(True, str(e) , None,status.HTTP_400_BAD_REQUEST)
        
        task = serializer.save()
        if 'status' in request.data:
            state = get_object_or_404(State, label=request.data['status'])
            task.status = state
            task.save()

        if task.task_type == 'automation' and task.action == 'send_mail':
            template_id = request.data.get('template', None)
            if template_id:
                # task = workflow_email_update(task, request, template_id)
                pass

        return ResponseHandler(False, "Task updated successfully." , WorkflowSerializer(task.workflow).data,status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        print('delete instance:', instance)
        if instance.due_flag and instance.dependent_due.all().exists() or instance.reminder_flag and instance.dependent_reminder.all().exists():
            return ResponseHandler(True,"Triggers are attached to it so can't delete the task, remove the triggers to delete task", None, status.HTTP_400_BAD_REQUEST)
        workflow = instance.workflow
        order = instance.order
        self.perform_destroy(instance)
        task_list = workflow.tasks.filter(order__gt = order).order_by('order')
        for task in task_list:
            task.order = order
            task.save()
            order+=1
            
        return ResponseHandler(False, "Task deleted successfully." , WorkflowSerializer(workflow).data,status.HTTP_200_OK)


class RequestApproval(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        task_id, pre_deal_amount, deal_amount, lead_id,car_parking = request.data.get("task_id", None), request.data.get("pre_deal_amount", None), request.data.get("deal_amount", None), request.data.get("lead_id", None), request.data.get("car_parking", None)
        apartment_no, tower , amount_per_car_parking= request.data.get("apartment_no", None), request.data.get("tower", None), request.data.get("amount_per_car_parking",None)
        token_amount , token_percentage = request.data.get("token_amount", None) , request.data.get("token_percentage", None)

        if not task_id and not pre_deal_amount and not deal_amount and not lead_id and not apartment_no and not tower:
            return ResponseHandler(True,'Missing parameters!, task_id, lead_id, apartment_no, tower, pre_deal_amount & deal_amount are required.','', 400)

        try:

            lead = get_object_or_404(Lead, pk=lead_id)

            property_owner = PropertyOwner.objects.filter(lead=lead_id).first()
            print('property_owner:', property_owner)

            if not property_owner:
                print('create property_owner & cost_sheets triggered')
                data = create_property_owner_and_inventory_cost_sheets(apartment_no, tower, lead)
                property_owner = PropertyOwner.objects.filter(lead=lead_id).first()
                print('property_owner:', property_owner)

            # project_inventory = ProjectInventory.objects.get(lead=lead_id)
            project_inventory = property_owner.property
            min_deal_amount_cm = project_inventory.min_deal_amount_cm
            min_deal_amount_sh = project_inventory.min_deal_amount_sh
            min_deal_amount_vp = project_inventory.min_deal_amount_vp

            if deal_amount < min_deal_amount_vp:
               return ResponseHandler(True,'Deal amount cannot be less than minimum deal amount!',None, 400)
            if not property_owner:
                return ResponseHandler(True,'Property owner not found!','', 404)
            if car_parking:
                print("Car_parking: ",car_parking)
                if not project_inventory:
                    return ResponseHandler(True,"ProjectInventory not found for the given data", None, status.HTTP_400_BAD_REQUEST)
                project_inventory.car_parking = car_parking
                project_inventory.amount_per_car_parking = amount_per_car_parking 
                project_inventory.token_percentage = token_percentage
                project_inventory.token_amount = token_amount
                project_inventory.save()
            property_owner.deal_amount = deal_amount
            property_owner.save()
            
            task = get_object_or_404(Task, pk=task_id)
            print('task:', task)
            state = get_object_or_404(State, label='In Progress')
            print('state:', state)
            task.status = state
            task.save()


            if deal_amount < min_deal_amount_cm and deal_amount >= min_deal_amount_sh:
                # Setting default VP's approval as accepted
                next_state = get_object_or_404(State, label='Accept')
                group = Group.objects.get(name='VICE_PRESIDENT')
                user_vp = Users.objects.filter(groups=group).first()

                group = Group.objects.get(name='SITE_HEAD')
                user_sh = Users.objects.filter(groups=group).first()#add project

                # marking 'VICE_PRESIDENT' approval 'Accept' and sending approval to 'SITE_HEAD'
                task.river.status.approve(as_user=user_vp, next_state=next_state, task=task)

                title = "Deal amount approval required"
                body = f"{self.request.user.name} has requested approval for {project_inventory.tower.project.name} - {project_inventory.apartment_no}"
                data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/sales/my_visit/lead_details/{lead_id}/0'}

                fcm_token = user_sh.fcm_token
                SalesActivity.objects.create(
                    history_date=datetime.now(),
                    history_type="+",
                    history_user=self.request.user.name,
                    sent_to =user_sh.name,
                    message=f"{self.request.user.name} has requested approval for {project_inventory.tower.project.name} - {project_inventory.apartment_no}",
                    activity_type="SalesActivity",
                    lead= lead
                )
                Notifications.objects.create(notification_id=f"task-{task.id}-{user_sh.id}", user_id=user_sh,created=timezone.now(), notification_message=body,notification_url=f'/sales/my_visit/lead_details/{lead_id}/0')

                send_push_notification(fcm_token, title, body, data)               
            elif deal_amount < min_deal_amount_sh and deal_amount >= min_deal_amount_vp:
                next_state = get_object_or_404(State, label='Accept')
                group = Group.objects.get(name='SITE_HEAD')
                user_sh = Users.objects.filter(groups=group).first()

                group = Group.objects.get(name='VICE_PRESIDENT')
                user_vp = Users.objects.filter(groups=group).first()

                # marking 'SITE_HEAD' approval 'Accept' and sending approval to 'VICE_PRESIDENT'
                task.river.status.approve(as_user=user_sh, next_state=next_state, task=task)
                title = "Deal amount approval required"
                body = f"{self.request.user.name} has requested approval for {project_inventory.tower.project.name} - {project_inventory.apartment_no}"
                data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/sales/my_visit/lead_details/{lead_id}/0'}

                fcm_token = user_vp.fcm_token
                SalesActivity.objects.create(
                    lead= lead,
                    history_date=datetime.now(),
                    history_type="+",
                    history_user=self.request.user.name,
                    sent_to =user_vp.name,
                    message=f"{self.request.user.name} has requested approval for {project_inventory.tower.project.name} - {project_inventory.apartment_no}",
                    activity_type="SalesActivity"
                )
                Notifications.objects.create(notification_id=f"task-{task.id}-{user_vp.id}", user_id=user_vp,created=timezone.now(), notification_message=body,notification_url=f'/sales/my_visit/lead_details/{lead_id}/0')

                send_push_notification(fcm_token, title, body, data) 
            elif deal_amount >= min_deal_amount_cm:
                state = get_object_or_404(State, label='Accept')
                print('state:', state)
                task.status = state
                task.save()# promoter and vp
                # project_inventory.status = 'Booked'
                # project_inventory.save()

                # user_cm = self.request.user
                # title = "Deal amount approved"
                # body = f"{self.request.user.name} has approved deal amount for {project_inventory.tower.project.name} - {project_inventory.apartment_no}"
                # data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/sales/my_visit/lead_details/{lead_id}/0'}

                # fcm_token = user_cm.fcm_token

                
                vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                promoter_users = Users.objects.filter(groups__name="PROMOTER")[:3]

                title = "Deal amount approved"
                body = f"{self.request.user.name} has approved deal amount {deal_amount} for {project_inventory.tower.project.name} - {project_inventory.apartment_no}"
                data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/sales/my_visit/lead_details/{lead_id}/0'}
                SalesActivity.objects.create(
                    lead= lead,
                    history_date=datetime.now(),
                    history_type="+",
                    history_user=self.request.user.name,
                    message=f"{self.request.user.name} has approved deal amount {deal_amount} for {project_inventory.tower.project.name} - {project_inventory.apartment_no}",
                    activity_type="SalesActivity"
                )
                if vp_user and not vp_user == self.request.user:
                    fcm_token_vp = vp_user.fcm_token
                    Notifications.objects.create(notification_id=f"task-{task.id}-{vp_user.id}", user_id=vp_user,created=timezone.now(), notification_message=body,notification_url=f'/sales/my_visit/lead_details/{lead_id}/0')
                    send_push_notification(fcm_token_vp, title, body, data)

                for promoter_user in promoter_users:
                    if promoter_user and not promoter_user ==self.request.user:
                        fcm_token_promoter = promoter_user.fcm_token
                        Notifications.objects.create(notification_id=f"task-{task.id}-{promoter_user.id}", user_id=promoter_user,created=timezone.now(), notification_message=body,notification_url=f'/sales/my_visit/lead_details/{lead_id}/0')
                        send_push_notification(fcm_token_promoter, title, body, data)

                users = []
                sh_user = Users.objects.filter(groups__name="SITE_HEAD").first()
                if sh_user:
                    users.append(sh_user)
    
                # vp_user = Users.objects.filter(groups__name="VICE_PRESIDENT").first()
                # if vp_user:
                #     users.append(vp_user)

                title = "Deal amount approved."
                body = f"{self.request.user.name} has approved deal amount {deal_amount} for {project_inventory.tower.project.name} - {project_inventory.apartment_no}"
                data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/sales/my_visit/lead_details/{lead_id}/0'}

                for user in users:
                    fcm_token = user.fcm_token
    
                    Notifications.objects.create(notification_id=f"task-{task.id}-{user.id}", user_id=user,    created=timezone.now(), notification_message=body,notification_url=f'/sales/my_visit/lead_details/{lead_id}/0')
    
                    send_push_notification(fcm_token, title, body, data) 

            return ResponseHandler(False,'Approval request sent!','', status.HTTP_200_OK)
           
        except Exception as e:
            return ResponseHandler(True,f"Error: {str(e)}",None, status.HTTP_500_INTERNAL_SERVER_ERROR)
            # return ResponseHandler(True,'Approval task not found!','', 404)


class ApprovalListView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        try:
            module_param = self.request.GET.get('module')
            tasks = Task.objects.filter(completed=False).order_by("-id") if module_param=='payment' else Task.objects.filter(name='Collect Token',completed=False,workflow__current_stage=1).order_by("-id")
            print('tasks:', request.user.groups.all())
            ret_value = []
            for task in tasks:
                workflow = dict()
                approvals = task.river.status.get_available_approvals(as_user=request.user)

                # test = task.river.status.next_approvals
                # print('approvals:', approvals)
                # print('approvals:', test)
                workflow["task_id"] = task.pk
                workflow["task_name"] = task.name
                workflow["approvals"] = []
                temp_list_src_dest = []

                #Todo - check approval_history for accept & deny must be same get approval must not show approvals if accepted or denied
                approval_history = []
                if approvals.count()>0:
                    for approval in approvals:
                        if not approval_history:
                            approval_history = approval.history.filter(transactioner_id=request.user.id, object_id=approval.object_id, meta_id=approval.meta_id)
                            print('approval_history:', approval_history, approval.object_id, request.user.id,approval.meta_id)

                        if not (approval.transition.source_state.label + approval.transition.destination_state.label) in     temp_list_src_dest :
                            temp_list_src_dest.append(approval.transition.source_state.label + approval.transition.    destination_state.label)
                            workflow["approvals"].append(
                                {
                                    "source": approval.transition.source_state.label,
                                    "destination": approval.transition.destination_state.label,
                                    "destination_id": approval.transition.destination_state.pk
                                }
                            )

                # for approval in approvals:
                #     print('transition:',temp_list_src_dest, vars(approval.transition))

                #     if not (approval.transition.source_state.label + approval.transition.destination_state.label) in     temp_list_src_dest :
                #         temp_list_src_dest.append(approval.transition.source_state.label + approval.transition.destination_state.label)
                #         workflow["approvals"].append(
                #             {
                #                 "source": approval.transition.source_state.label,
                #                 "destination": approval.transition.destination_state.label,
                #                 "destination_id": approval.transition.destination_state.pk
                #             }
                #         )
                            
                # if approval_history exist will show approvals as empty
                if approval_history:
                    workflow['approvals'] = []
                ret_value.append(workflow)
            return ResponseHandler(False,'',ret_value, 200)
        except Exception as e:
            print('e:', e)
            return ResponseHandler(True,'Approval list not found!','', 404)


class SubmitApproval(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        # print('request:', vars(request))
        task_id, next_state_id,deal_amount,lead_id,payment_id,refund_payment_id,reject_reason = request.data.get("task_id", None), request.data.get("next_state_id", None),request.data.get("deal_amount", None),request.data.get("lead_id", None),request.data.get("payment_id", None),request.data.get("refund_payment_id",None),request.data.get("reject_reason", None)
        # costsheet_events_data = request.data.get("costsheet_events_data", None)
        apartment_no = request.data.get("apartment_no", None)
        project_id = request.data.get("project_id", None)
        total_value = request.data.get("total_value", None)
        cost_sheet_deny_reason = request.data.get("cost_sheet_deny_reason", None)

        if not task_id and not next_state_id:
            return HttpResponse(status=status.HTTP_400_BAD_REQUEST)

        task = get_object_or_404(Task, pk=task_id)
        approval_task = task
        next_state = get_object_or_404(State, pk=next_state_id)
        print('next_state:', next_state, next_state_id)

        try:
            module_param = self.request.GET.get('module')
            # if module_param == "payment":
            #     if next_state.label=='Accept':
            #         if payment_id:
            #             payment = Payment.objects.filter(id=payment_id).first()
            #             if payment:
            #                 payment.status="Done"
            #                 payment.invoice_overview="Approved by Account"
            #                 payment.denied_reason = ""
            #                 payment.save()
            #                 if payment.campaign:
            #                     campaign = Campaign.objects.filter(id=payment.campaign.id).first()
            #                     campaign.spend = campaign.spend + payment.amount
            #                     campaign.save()
            #                 task.skip_history_when_saving = True
            #                 task.river.status.approve(as_user=request.user, next_state=next_state, task=task)
            #                 del task.skip_history_when_saving
            #         else:
            #             return ResponseHandler(False,'Provide payment_id','', 200)         
            #         return ResponseHandler(False,'Approval approved successfully','', 200)
            #     elif next_state.label=='In Progress':
            #         task.skip_history_when_saving = True
            #         task.river.status.approve(as_user=request.user, next_state=next_state, task=task)
            #         del task.skip_history_when_saving
            #         return ResponseHandler(False,'Requested for approval successfully','', 200)
            #     elif next_state.label=='Deny':# update payment object status here
            #         if reject_reason and payment_id:
            #             payment = Payment.objects.filter(id=payment_id).first()
            #             if payment:
            #                 payment.status="Reject"
            #                 payment.invoice_overview="Denied by Account"
            #                 payment.denied_reason=reject_reason
            #                 payment.save()
            #                 task.skip_history_when_saving = True
            #                 task.river.status.approve(as_user=request.user, next_state=next_state, task=task)
            #                 del task.skip_history_when_saving
            #         else:
            #             return ResponseHandler(False,'Provide Reject Reason and payment_id','', 200)    
            #         return ResponseHandler(False,'Approval rejected successfully','', 200)
            #     return HttpResponse(status=status.HTTP_200_OK)
            # else:
            task.skip_history_when_saving = True
            task.river.status.approve(as_user=request.user, next_state=next_state, task=task)
            if payment_id:
                task.completed = True
                task.completed_at = datetime.now()
                task.save()
            elif refund_payment_id:
                print("inside refund task approval")
                task.completed = True
                task.completed_at = datetime.now()
                task.save()    
            del task.skip_history_when_saving

            if next_state.label=='Accept':
                if payment_id:
                    payment_instance = Payment.objects.get(id=payment_id)
                    if payment_instance and payment_instance.status == 'On Hold':
                        payment_instance.status = 'Approval Pending'
                        payment_instance.denied_reason = ""
                        payment_instance.save()
                    payment = Payment.objects.filter(id=payment_id).first()
                    first_stage = payment.payment_workflow.get().stages.first()
                    state = get_object_or_404(State, label='In Progress')
                    if self.request.user.groups.filter(name="VICE_PRESIDENT").exists():
  
                        tasks = first_stage.tasks.filter(completed=False).order_by('order')[:3]
                        for task in tasks:
       
                            if task is not None:
                                task.status = state
                                task.save()

                    first_task = first_stage.tasks.filter(completed=False).order_by('order').first()
                    ah_state = get_object_or_404(State, label='Request')
                    if first_task and first_task.status == ah_state:
                        first_task.status = state
                        first_task.save()

                    # updating approval in payment list :
                    print('task_name:', approval_task.name)
                    promoter_approval_count = 0
                    for entry in payment.invoice_overview_list:
                        if entry["role"] == "AE" and approval_task.name == "Payment Approval AE":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "VP" and approval_task.name == "Payment Approval VP":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P1" and approval_task.name == "Payment Approval P1":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P2" and approval_task.name == "Payment Approval P2":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P3" and approval_task.name == "Payment Approval P3":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "AH" and approval_task.name == "Payment Approval AH":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 

                        if entry["status"] == "Approve":
                            if entry["role"] == "P1" or entry["role"] == "P2" or entry["role"] == "P3":
                                promoter_approval_count += 1
                    payment.save()

                    # if any 2 promoter approved 
                    if promoter_approval_count >= 2:
                        remaining_tasks = first_stage.tasks.filter(completed=False).order_by('order')
                        for task_instance in remaining_tasks:
                            if task_instance.name == "Payment Approval P1" or task_instance.name == "Payment Approval P2" or task_instance.name == "Payment Approval P3":
                                task_instance.completed = True
                                task_instance.completed_at = datetime.now()
                                task_instance.save()
                
                elif refund_payment_id:
                    payment_instance = Payment.objects.get(id=refund_payment_id)
                    print("payment_instance",payment_instance)
                    if payment_instance and payment_instance.status == 'On Hold':
                        payment_instance.status = 'Approval Pending'
                        payment_instance.denied_reason = ""
                        payment_instance.save()
                    payment = Payment.objects.filter(id=refund_payment_id).first()
                    print("payment",payment)
                    first_stage = payment.payment_workflow.get().stages.first()
                    print("first_stage",first_stage)
                    state = get_object_or_404(State, label='In Progress')
                    print("state",state)
                    print("user",self.request.user)
                    if self.request.user.groups.filter(name="ACCOUNTS_EXECUTIVE").exists():
                        print("inside account executive")
                        tasks = first_stage.tasks.filter(completed=False).order_by('order')[:1]
                        print("tasks",tasks)
                        for task in tasks:
                            if task is not None:
                                task.status = state
                                task.save()

                    if self.request.user.groups.filter(name="VICE_PRESIDENT").exists():
                        print("inside Vp")
                        tasks = first_stage.tasks.filter(completed=False).order_by('order')[:3]
                        print("tasks",tasks)
                        for task in tasks:
                            if task is not None:
                                task.status = state
                                task.save()


                    first_task = first_stage.tasks.filter(completed=False).order_by('order').first()
                    print('first_task',first_task)
                    ah_state = get_object_or_404(State, label='Request')
                    print('ah_state',ah_state)
                    if first_task and first_task.status == ah_state:
                        first_task.status = state
                        first_task.save()

                    # updating approval in payment list :
                    print('task_name:', approval_task.name)
                    promoter_approval_count = 0
                    for entry in payment.invoice_overview_list:
                        if entry["role"] == "AE" and approval_task.name == "Refund Approval AE":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "VP" and approval_task.name == "Refund Approval VP":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P1" and approval_task.name == "Refund Approval P1":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P2" and approval_task.name == "Refund Approval P2":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P3" and approval_task.name == "Refund Approval P3":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "AH" and approval_task.name == "Refund Approval AH":
                            entry["status"] = "Approve"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 

                        if entry["status"] == "Approve":
                            if entry["role"] == "P1" or entry["role"] == "P2" or entry["role"] == "P3":
                                promoter_approval_count += 1
                    payment.save()

                    if self.request.user.groups.filter(name="ACCOUNTS_HEAD").exists():
                        print("inside Accounts Head")
                        payment.status = 'Payment Done'
                        payment.invoice_overview="Paid by Account"
                        payment.save()
                    
                    # state_accept = get_object_or_404(State, label='Accept')
                    # if any 2 promoter approved 
                    if promoter_approval_count >= 2:
                        remaining_tasks = first_stage.tasks.filter(completed=False).order_by('order')
                        for task_instance in remaining_tasks:
                            if task_instance.name == "Refund Approval P1" or task_instance.name == "Refund Approval P2" or task_instance.name == "Refund Approval P3":
                                task_instance.completed = True
                                task_instance.completed_at = datetime.now()
                                # task_instance.status = state_accept
                                task_instance.save()
                            if task_instance.name == "Refund Approval AH":
                                    task_instance.status = state
                                    task_instance.save() 

                        # for entry in payment.invoice_overview_list:
                        #     print(entry['role'])
                        #     if entry["role"] == "P1" or entry["role"] == "P2" or entry["role"] == "P3":
                        #         print(entry["status"])
                        #         if entry["status"] == "Approval Pending":
                        #             entry["status"] = "Approve"
                        #             entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        payment.save()        
                           

                    # print("first task:",first_task)
                else:
                    if project_id and apartment_no and task:
                        print('cost_sheet accept:', project_id, apartment_no, lead_id)
                        from inventory.views import update_cost_sheet_and_notify
                        res = update_cost_sheet_and_notify(self.request,lead_id, apartment_no, project_id,total_value)
                    elif task:
                        task_data = TaskSerializer(task).data
                        lead_id_task = task_data.get('lead_id', None)
                        property_owner = PropertyOwner.objects.filter(lead=lead_id_task).first()
                        project_inventory = property_owner.property
                        print('project_inventory:', project_inventory)
                        # project_inventory.status = 'Booked'
                        # project_inventory.save()
                        request_record = SalesActivity.objects.filter(lead=lead_id_task, message__icontains="requested").order_by('-history_date').first()
                        # booking_form = BookingForm.objects.filter(lead_id__id=lead_id_task).first()
                        if request_record:
                            user_record = Users.objects.filter(name=request_record.history_user,groups__name="CLOSING_MANAGER").first()
                            user_cm = user_record
                            title = "Deal amount approved"
                            body = f"{self.request.user.name} has approved deal amount for {project_inventory.tower.project.name} - {project_inventory.apartment_no}"
                            data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/sales/my_visit/lead_details/{lead_id_task}/0'}
                            SalesActivity.objects.create(
                                history_date=datetime.now(),
                                history_type="+",
                                history_user=self.request.user.name,
                                message=f"{self.request.user.name} has approved deal amount for {project_inventory.tower.project.name} - {project_inventory.apartment_no}",
                                activity_type="SalesActivity",
                                lead_id= lead_id_task,
                            )
                            fcm_token = user_cm.fcm_token
                            send_push_notification(fcm_token, title, body, data)
                            Notifications.objects.create(notification_id=f"task-{task.id}-{user_cm.id}", user_id=user_cm,created=timezone.now(), notification_message=body,notification_url=f'/sales/my_visit/lead_details/{lead_id_task}/0')

                return ResponseHandler(False,'Approval approved successfully',None, 200)
            elif next_state.label=='In Progress':
                return ResponseHandler(False,'Requested for approval successfully',None, 200)
            elif next_state.label=='Deny':
                if deal_amount:
                    property_owner = PropertyOwner.objects.filter(lead=lead_id).first()
                    if property_owner:
                        property_owner.deal_amount = deal_amount
                        property_owner.save()

                if reject_reason and payment_id:
                    payment = Payment.objects.filter(id=payment_id).first()
                    if payment:
                        payment.status="Reject"
                        payment.invoice_overview="Denied by Account"
                        payment.denied_reason=reject_reason
                        payment.save()

                        first_stage = payment.payment_workflow.get().stages.first()
                        all_tasks = first_stage.tasks.all().order_by('order')
                        state = get_object_or_404(State, label='Request')
                        if all_tasks:
                            for task in all_tasks:
                                print()
                                reset_task_approval_status(task.id)
                                task.completed = False
                                task.completed_at = None
                                task.status = state
                                task.save()
                            # add workflow = current
                        # updating approval in payment list :
                    print('task_name:', approval_task.name)
                    for entry in payment.invoice_overview_list:
                        if entry["role"] == "AE" and approval_task.name == "Payment Approval AE":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "VP" and approval_task.name == "Payment Approval VP":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P1" and approval_task.name == "Payment Approval P1":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P2" and approval_task.name == "Payment Approval P2":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P3" and approval_task.name == "Payment Approval P3":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "AH" and approval_task.name == "Payment Approval AH":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                    payment.save()

                elif reject_reason and refund_payment_id:
                    payment = Payment.objects.filter(id=refund_payment_id).first()
                    if payment:
                        payment.status="Reject"
                        payment.invoice_overview="Denied by Account"
                        payment.denied_reason=reject_reason
                        payment.save()

                        first_stage = payment.payment_workflow.get().stages.first()
                        all_tasks = first_stage.tasks.all().order_by('order')
                        state = get_object_or_404(State, label='Request')
                        if all_tasks:
                            for task in all_tasks:
                                print()
                                reset_task_approval_status(task.id)
                                task.completed = False
                                task.completed_at = None
                                task.status = state
                                task.save()
                            # add workflow = current
                        # updating approval in payment list :
                    print('task_name:', approval_task.name)
                    for entry in payment.invoice_overview_list:
                        if entry["role"] == "AE" and approval_task.name == "Refund Approval AE":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "VP" and approval_task.name == "Refund Approval VP":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P1" and approval_task.name == "Refund Approval P1":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P2" and approval_task.name == "Refund Approval P2":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "P3" and approval_task.name == "Refund Approval P3":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                        if entry["role"] == "AH" and approval_task.name == "Refund Approval AH":
                            entry["status"] = "Reject"
                            entry["time"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S') 
                    payment.save() 
                       
                elif cost_sheet_deny_reason and lead_id:
                    from inventory.models import InventoryCostSheet
                    print('cost_sheet deny:', cost_sheet_deny_reason)
                    property_owner = PropertyOwner.objects.filter(lead__id=lead_id).first()
                    property_owner.cost_sheet_deny_reason = cost_sheet_deny_reason
                    property_owner.save()

                    existing_sheets = InventoryCostSheet.objects.filter(lead=lead_id, inventory__apartment_no=apartment_no, inventory__tower__project=project_id,is_changed=True).order_by('event_order')

                    for existing_sheet in existing_sheets:
                        existing_sheet.is_changed = False
                        existing_sheet.save()

                    # for cost_sheet in costsheet_events_data:
                    #     if cost_sheet["is_changed"]:
                    #         event = InventoryCostSheet.objects.filter(id=cost_sheet["id"]).first()
                    #         event.is_changed = False
                    #         event.save()

                    sh_user = Users.objects.filter(groups__name="SITE_HEAD").first()
                    title = "Cost sheet approval denied"
                    body = f"{self.request.user.name} has denied cost sheet for {property_owner.property.tower.project.name} - {property_owner.property.apartment_no}"
                    data = {'notification_type': 'request_cost_sheet', 'redirect_url': f'/sales/my_visit/lead_details/{lead_id}/0'}
                    SalesActivity.objects.create(
                        lead_id =lead_id,
                        history_date=datetime.now(),
                        history_type="+",
                        history_user=self.request.user.name,
                        message=f"{self.request.user.name} has denied cost sheet for {property_owner.property.tower.project.name} - {property_owner.property.apartment_no}",
                        activity_type="SalesActivity"
                    )
                    if sh_user and sh_user.fcm_token:
                        fcm_token = sh_user.fcm_token
                        send_push_notification(fcm_token, title, body, data)
                    Notifications.objects.create(notification_id=f"task-{task.id}-{sh_user.id}", user_id=sh_user,created=timezone.now(), notification_message=body,notification_url=f'/sales/my_visit/lead_details/{lead_id}/0')
                else:
                    if task:
                        task_data = TaskSerializer(task).data
                        lead_id_task = task_data.get('lead_id', None)
                        project_owner = PropertyOwner.objects.filter(lead__id=lead_id_task).first()
                        request_record = SalesActivity.objects.filter(lead=lead_id_task, message__icontains="requested").order_by('-history_date').first()
                        # booking_form = BookingForm.objects.filter(lead_id__id=lead_id_task).first()
                        if request_record:
                            user_record = Users.objects.filter(name=request_record.history_user,groups__name="CLOSING_MANAGER").first()
                            user_cm = user_record
                            title = "Deal amount denied"
                            body = f"{self.request.user.name} has denied deal amount for {project_owner.property.tower.project.name} - {project_owner.property.apartment_no}"
                            data = {'notification_type': 'request_deal_amount', 'redirect_url': f'/sales/my_visit/lead_details/{lead_id_task}/0'}
                            SalesActivity.objects.create(
                                lead_id =lead_id_task,
                                history_date=datetime.now(),
                                history_type="+",
                                history_user=self.request.user.name,
                                message=f"{self.request.user.name} has denied deal amount for {project_owner.property.tower.project.name} - {project_owner.property.apartment_no}",
                                activity_type="SalesActivity"
                            )
                            fcm_token = user_cm.fcm_token
                            send_push_notification(fcm_token, title, body, data)
                            Notifications.objects.create(notification_id=f"task-{task.id}-{user_cm.id}", user_id=user_cm,created=timezone.now(), notification_message=body,notification_url=f'/sales/my_visit/lead_details/{lead_id_task}/0')
            
                return ResponseHandler(False,'Approval rejected successfully',None, 200)
            return HttpResponse(status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return ResponseHandler(True,'Approval request not found!',str(e), 404)


class NotificationsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        try:
            print('request:', request.user)
            notifications_obj = Notifications.objects.filter(user_id=request.user).order_by('-id')
            serializer = NotificationsSerializer(notifications_obj, many=True)
            return ResponseHandler(False,'Notifications retrieved successfully',serializer.data, 200)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            error_message = 'An error occurred while processing the request'
            return ResponseHandler(True, error_message, None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request):
        try:
            notifications_obj = Notifications.objects.filter(user_id=request.user)
            for notification in notifications_obj:
                notification.read = True
                notification.save()
            return ResponseHandler(False,'Notifications marked as read successfully','',status.HTTP_200_OK)
        except Notifications.DoesNotExist:
            return ResponseHandler(True,'No notifications found for the user','',status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            error_message = 'An error occurred while processing the request'
            return ResponseHandler(True, error_message, str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class NotificationsRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationsSerializer

    def get_queryset(self):
        return Notifications.objects.filter(user_id=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            print('instance:', instance)
            serializer = self.get_serializer(instance)
            return ResponseHandler(False, 'Notification retrieved successfully', serializer.data, status.HTTP_200_OK)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            error_message = 'An error occurred while processing the request'
            return ResponseHandler(True, error_message, None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return ResponseHandler(False, 'Notification updated successfully', serializer.data, status.HTTP_200_OK)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            error_message = 'An error occurred while processing the request'
            return ResponseHandler(True, error_message, None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return ResponseHandler(False, 'Notification deleted successfully', '', status.HTTP_204_NO_CONTENT)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            error_message = 'An error occurred while processing the request'
            return ResponseHandler(True, error_message, None, status.HTTP_500_INTERNAL_SERVER_ERROR)