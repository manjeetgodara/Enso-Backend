from django.shortcuts import render
from rest_framework import generics, mixins,status,serializers

from .serializers import *
from .models import LeadCallsMcube
from rest_framework.response import Response
from auth.models import Users
import requests
from environs import Env
import firebase_admin
from firebase_admin import db, firestore
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
import uuid
from auth.utils import ResponseHandler
from django.conf import settings
from django.db.models import Q
from lead.models import Lead, Source
from marketing.models import Campaign
from datetime import datetime
from rest_framework.views import APIView
env = Env()
env.read_env()

# Create your views here.
class McubeCreateAPIView(mixins.ListModelMixin, mixins.CreateModelMixin, generics.GenericAPIView):
    queryset = LeadCallsMcube.objects.all().order_by('-created_at')
    serializer_class = LeadCallsMcube
    
    def get(self):
        return super().get_queryset()
    
    def filter_queryset(self, queryset):
        return super().filter_queryset(queryset)

    def post(self, request, *args, **kwargs):
        data = request.data
        caller_number = data.get("callto")
        try:
            print(f'incoming call data {data}')
            call_id = data.get("callid")
            executive_number = data.get("emp_phone")
            dialstatus = data.get("dialstatus")
            call_direction = data.get("direction")
            print('call_direction:', call_direction.lower())
            if call_direction.lower() == 'inbound':
                call_type = 'INCOMING'
            else:
                call_type = 'OUTGOING'
            executive = Users.objects.filter(mobile=executive_number).first()
            print(f'executive {executive}')
            # is_caller_present = LeadCallsMcube.objects.filter(lead_phone=caller_number)
            is_caller_present = Lead.objects.filter(Q(primary_phone_no=caller_number)|Q(secondary_phone_no=caller_number))
            print(f'caller present {is_caller_present}')

            if is_caller_present.exists():
                if not executive:
                    return ResponseHandler(True, "Executive not found.", None, status.HTTP_404_NOT_FOUND)
                

                is_lead_call_present = LeadCallsMcube.objects.filter(callid=call_id)
                if not is_lead_call_present:
                    lead_call = LeadCallsMcube.objects.create(
                            lead_phone=data.get("callto"),
                            callid=call_id,
                            executive=executive,
                            call_status=dialstatus,
                            call_type=call_type,
                            start_time=data.get("starttime"),
                            end_time=data.get("endtime"),
                            request_body=data
                        )
                
                    lead_id = is_caller_present[0].id
                    print('lead_id:', lead_id)
                    
                    fr_data={
                            "show_lead_form":False,
                            "data":{
                                "redirect_url": f"/pre_sales/all_leads/lead_details/{lead_id}/0"
                            }
                        }
                    
                    if call_type == 'INCOMING':
                        db = firestore.client(app=settings.FIREBASE_APPS['mcube'])
                        fr_data_ref = db.collection('mcubeLeadForm').document(str(executive.id)).set(fr_data)
                else:
                    # current_request_bodies = is_lead_call_present.values_list('request_body', flat=True)
                    # print('current_request_bodies:', current_request_bodies)
                    # call_data = is_lead_call_present.first()
                    # print('call_data:', call_data.request_body)
                    # updated_request_bodies = call_data.request_body.append(data)
                    # print('updated_request_bodies:', updated_request_bodies)

                    starttime = datetime.strptime(data["starttime"], "%Y-%m-%d %H:%M:%S")
                    endtime = datetime.strptime(data["endtime"], "%Y-%m-%d %H:%M:%S")
                    
                    call_duration_seconds = (endtime - starttime).total_seconds()
                    
                    call_duration_minutes = call_duration_seconds / 60

                    update_lead_call = {
                        'call_duration': round(call_duration_minutes, 2),
                        'call_status': dialstatus,
                        'end_time': data.get('endtime'),
                        'request_body': data
                    }
                    is_lead_call_present.update(**update_lead_call)

                    # after call ends update firbase
                    fr_data={
                        "show_lead_form":False,
                        "data":None
                        }
            
                    db = firestore.client(app=settings.FIREBASE_APPS['mcube'])
                    fr_data_ref = db.collection('mcubeLeadForm').document(str(executive.id)).set(fr_data)

                return ResponseHandler(False, "Lead already present.", None, status.HTTP_200_OK)
            else:
                
                if not executive:
                    return ResponseHandler(True, "Executive not found.", None, status.HTTP_404_NOT_FOUND)
                else:

                    source = None
                    campaign = Campaign.objects.filter(virtual_number=data.get("clicktocalldid")).first()

                    if campaign:
                        source_data = Source.objects.filter(source_id=campaign.sourceid).first()
                        if source_data:
                            source = {
                                "source_id": source_data.source_id,
                                "name": source_data.name
                            }
                            print('source:', source)

                    fr_data={
                        "show_lead_form":True,
                        "data":{
                            "lead_phone":data.get("callto"),
                            "source": source
                        }
                    }
                    
                    
                    is_lead_call_present = LeadCallsMcube.objects.filter(callid=call_id)
                    if not is_lead_call_present:
                        lead_call = LeadCallsMcube.objects.create(
                            lead_phone=data.get("callto"),
                            callid=call_id,
                            executive=executive,
                            call_status=dialstatus,
                            start_time=data.get("starttime"),
                            end_time=data.get("endtime"),
                            call_type=call_type,
                            request_body=data
                        )
                        #update value in firebase
                        db = firestore.client(app=settings.FIREBASE_APPS['mcube'])
                        fr_data_ref = db.collection('mcubeLeadForm').document(str(executive.id)).set(fr_data)
                    else:
                        # current_request_bodies = is_lead_call_present.values_list('request_body', flat=True)
                        # updated_request_bodies = current_request_bodies.append(data)

                        starttime = datetime.strptime(data["starttime"], "%Y-%m-%d %H:%M:%S")
                        endtime = datetime.strptime(data["endtime"], "%Y-%m-%d %H:%M:%S")
                        
                        call_duration_seconds = (endtime - starttime).total_seconds()
                        
                        call_duration_minutes = call_duration_seconds / 60

                        update_lead_call = {
                            'call_duration': round(call_duration_minutes, 2),
                            'call_status': dialstatus,
                            'end_time': data.get('endtime'),
                            'request_body': data
                        }
                        is_lead_call_present.update(**update_lead_call)

                        # after call ends update firbase
                        fr_data={
                            "show_lead_form":False,
                            "data":None
                            }
                
                        db = firestore.client(app=settings.FIREBASE_APPS['mcube'])
                        fr_data_ref = db.collection('mcubeLeadForm').document(str(executive.id)).set(fr_data)

                    return ResponseHandler(False, "Lead added.", None, status.HTTP_201_CREATED)
        except Exception as e:
            print(f'Exception {e}')
            return ResponseHandler(True, f"Internal server error. {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        



class MCubeRetrieveUpdateAPIView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, generics.GenericAPIView):
    queryset=LeadCallsMcube.objects.all()
    serializer_class=LeadCallsMcube

    def put(self, request, *args, **kwargs):
        call_id = self.kwargs.get('pk')

        try:
            instance = LeadCallsMcube.objects.get(pk=call_id)
            serializer = self.get_serializer(instance, data=request.data, partial=True)

            if serializer.is_valid():
            # Perform the update
                serializer.save()
                return ResponseHandler(False, "Lead call details updated.", None, status.HTTP_200_OK)
        except Exception as e:
            print(f'Exception {e} occured')
            return ResponseHandler(True, f"Internal server error. {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)



@permission_classes(IsAuthenticated)
@api_view(['POST'])
def make_outbound_call(request):
    try:
        data = request.data
        print('data:', data)
        url = env("MCUBE_OUTGOING_URL")
        token = env("MCUBE_TOKEN")
        executive_number = data.get("executive_number")
        print('executive_number:', executive_number)
        lead_number = data.get("lead_number")
        print('lead_number:', lead_number)

        # print('creds:', url, token)

        executive_instance = Users.objects.filter(mobile=executive_number).first()

        if not executive_instance:
            return ResponseHandler(True, f"Executive not found", None, status.HTTP_404_NOT_FOUND)

        base_url='https://dev.estogroup.in'
        incoming_url=f'{base_url}/api/mcube/lead-calls/'
        refId=generate_random_id()
        print('refId:', refId)


        headers = {
            'Content-Type': 'application/json',
        }
        data = {
            'HTTP_AUTHORIZATION': token,
            "exenumber": executive_number,
            "custnumber": lead_number,
            "refurl":incoming_url,
            "refId": refId
        }


        print('data:', data)
        response = requests.post(url, headers=headers, json=data)
        # print('response:', vars(response))
        # Check if the request was successful
        if response.status_code == 200:
            print('response:', response.json())
            lead_call = LeadCallsMcube.objects.create(
                                        lead_phone=lead_number,
                                        callid=refId,
                                        executive=executive_instance,
                                        call_status='INITIATED',
                                        call_type='OUTGOING'
                                    )
            return ResponseHandler(False, f"Outbound call successful", response.json(), status.HTTP_200_OK)
        else:
            return ResponseHandler(True, f"Failed to make the request to external API", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        print(f'Exception {e} occured')
        return ResponseHandler(True, f"Internal server error. {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
    

class CustomPagination(PageNumberPagination):
    page_size = 10  # Set the number of items per page
    page_size_query_param = '10'
    max_page_size = 100

@api_view(['POST'])
# @permission_classes(IsAuthenticated)
def get_calls_list(request):
    try:
        print(f'request.data {request.data}')
        filter = request.data.get('filter')
        print(f'filter {filter}')
        if filter:
            calls_list = LeadCallsMcube.objects.filter(**filter).order_by('-created_at')
        else:
            calls_list = LeadCallsMcube.objects.filter().order_by('-created_at')
        print(f'calls list {calls_list}')

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(calls_list, request)

        print(f'result {result_page}')
        calls_list_serialized = McubeSerializer(result_page, many=True)
        # print(f'calls_list is {calls_list_serialized}')
        
        return ResponseHandler(False, f"Call list retrieved successfully.", calls_list_serialized.data, status.HTTP_200_OK)
    except Exception as e:
        print(f'Exception {e} occured')
        return ResponseHandler(True, f"Internal server error. {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)  


def generate_random_id():
    return uuid.uuid4().hex    

class ActivityView(APIView):
    def get(self, request, lead_phone, format=None):
        try:
            queryset = LeadCallsMcube.objects.filter(lead_phone=lead_phone).order_by('-created_at')
            if not queryset.exists():
                return ResponseHandler(True, f"No records found for lead phone {lead_phone}", [], status.HTTP_404_NOT_FOUND)
            
            serializer = LeadCallsMcubeSerializer(queryset, many=True)
            return ResponseHandler(False, "Records retrieved successfully", serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return ResponseHandler(True, str(e), {}, status.HTTP_500_INTERNAL_SERVER_ERROR)



