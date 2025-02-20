from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from  . import models
import json,random,uuid
from datetime import timedelta
from django.http import JsonResponse
# Create your views here
from django.utils import timezone
from django.http import HttpResponse
from rest_framework.authtoken.models import Token
from django.views.decorators.csrf import csrf_exempt
from apps.auth.utils import ResponseHandler
from drf_yasg.utils import swagger_auto_schema
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from .serializers import *
from rest_framework.decorators import api_view
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.hashers import check_password, make_password
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import smart_bytes,force_bytes
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.urls import reverse
import requests
from environs import Env
env = Env()
env.read_env()

@swagger_auto_schema(
operation_summary = "Login api",
operation_description="It gets mobile number as input for logging",
responses={200: 'OK'},
)        
@csrf_exempt
def login(request):
    if request.method=="POST":
        
        body= json.loads(request.body)
        mobile_number= body.get('mobile')

        try:
            user=models.Users.objects.get(mobile=mobile_number)
            '''
            data_dict = {
                        "session_id":"123456"
                        }
                        '''
            data_dict= dict()
            data_dict['session_id']="123459"
            error=False
            message=""
            body=data_dict
            status=200
            
           # response_json = json.dumps(response_data)
            #response_status = status.HTTP_200_OK
            #return JsonResponse({'message':"User is registered"},status=200)
        
        except models.Users.DoesNotExist:
            error=True
            message="User is not registered"
            body=""
            status=401
            return ResponseHandler(error,message,body,status)
        
        #Generate OTP
        #set default otp to 123456
        otp= str(random.randint(1000,9999))

        #Generate SessionId
        #session_id = str(uuid.uuid4())

        #Store OTP session in the database
        #expires_at = timezone.now()+timedelta(minutes=2)
        #otp_session =models.OTPSession(otp=otp,expires_at=expires_at,session_id=session_id,identifier=mobile_number)
        #otp_session.save()

        #otp_response= send_otp(mobile_number,otp)
        #print('otp_response', otp_response,otp)

        #if otp_response.status_code==200:
           # return JsonResponse({'message':'OTP send successfully','session_id': session_id})
        #else:
            #return JsonResponse({'message': 'Failed to send OTP'},status=500)'''
        return ResponseHandler(error,message,body,status)
        #return JsonResponse(response_data,status=401)


def get_dashboard_metadata(user_groups):
    current_env = env("ENVIRONMENT")
   # current_env = "PROD"
    print("current_env",current_env)
    meta_structure = [
        {"title": "MIS Dashboard", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Dashboard.svg", "subMenu": None, "path": "/mis_dashboard"},
        {"title": "Marketing", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Marketing.svg", "subMenu": [
            {"title": "Dashboard", "path": "/marketing/dashboard"},
            {"title": "Agencies", "path": "/marketing/agencies_campaigns"},
            {"title": "Performance", "path": "/marketing/performance"},
            {"title": "Budget & Campaigns", "path": "/marketing/budget_campaign"},
	        {"title": "Downloads", "path": "/marketing/downloads"},
        ],"path": "/marketing"},
        {"title": "Pre Sales", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Pre+Sales.svg", "subMenu": [
            {"title": "Dashboard", "path": "/pre_sales/dashboard"},
            {"title": "All Leads", "path": "/pre_sales/all_leads"},
            {"title": "Follow Ups", "path": "/pre_sales/follow_ups"},
            {"title": "Converted Leads", "path": "/pre_sales/converted_leads"},
            {"title": "Site Visit", "path": "/pre_sales/site_visit"},
        ],"path": "/pre_sales"},
        {"title": "Sales", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Sales.svg", "subMenu": [
            {"title": "Dashboard", "path": "/sales/dashboard"},
            #{"title": "Calendar", "path": "/sales/calendar"},
            {"title": "My Visit", "path": "/sales/my_visit"},
            {"title": "Closed Deals", "path": "/sales/closure"},
            #{"title": "Brokerage Payments", "path": "/sales/brokerage_payment"},
            {"title": "Brokerage Ladder", "path": "/sales/brokerage_ladder"}
        ],"path": "/sales"},
        {"title": "Post Sales", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Post+Sales.svg", "subMenu": [
            {"title": "All Customers", "path": "/post_sales/all_customers"},
            {"title": "Construction Updates", "path": "/post_sales/events"},
            {"title": "Possession", "path": "/post_sales/possession"}
        ],"path": "/post_sales"},
        # {"title": "Accounts", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Accounts.svg", "subMenu": None,"path": "/accounts"},
        {"title": "Accounts", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Accounts.svg", "subMenu": [
            {"title": "Partner Payments", "path": "/accounts/partner_payments"},
            {"title": "Customer Payments", "path": "/accounts/customer_payments"},
            {"title": "Refunds", "path": "/accounts/refunds"}
        ],"path": "/accounts"},
        {"title": "Sourcing", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Pre+Sales.svg", "subMenu": [
            {"title": "Dashboard", "path": "/sourcing/dashboard"},
            {"title": "All Channel Partners", "path": "/sourcing/all_channel_partners"},
        ],"path": "/sourcing"},
        {"title": "Reset Password", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/reset_password_icon.png", "subMenu": None,"path": "/reset_password"},
        # {"title": "User", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/User.svg", "subMenu": None,"path": "/user"},
        #  {"title": "Research", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Accounts.svg", "subMenu": None,"path": "/research"},
    ]

    
    meta_structure_prod = [
        {"title": "MIS Dashboard", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Dashboard.svg", "subMenu": None, "path": "/mis_dashboard"},
        {"title": "Marketing", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Marketing.svg", "subMenu": [
            {"title": "Dashboard", "path": "/marketing/dashboard"},
            {"title": "Agencies", "path": "/marketing/agencies_campaigns"},
            {"title": "Performance", "path": "/marketing/performance"},
            {"title": "Budget & Campaigns", "path": "/marketing/budget_campaign"},
	        {"title": "Downloads", "path": "/marketing/downloads"},
        ],"path": "/marketing"},
        {"title": "Pre Sales", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Pre+Sales.svg", "subMenu": [
            {"title": "Dashboard", "path": "/pre_sales/dashboard"},
            {"title": "All Leads", "path": "/pre_sales/all_leads"},
            {"title": "Follow Ups", "path": "/pre_sales/follow_ups"},
            {"title": "Converted Leads", "path": "/pre_sales/converted_leads"},
            {"title": "Site Visit", "path": "/pre_sales/site_visit"},
        ],"path": "/pre_sales"},
        {"title": "Sales", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Sales.svg", "subMenu": [
            {"title": "Dashboard", "path": "/sales/dashboard"},
            #{"title": "Calendar", "path": "/sales/calendar"},
            {"title": "My Visit", "path": "/sales/my_visit"},
            {"title": "Closed Deals", "path": "/sales/closure"},
            #{"title": "Brokerage Payments", "path": "/sales/brokerage_payment"},
            {"title": "Brokerage Ladder", "path": "/sales/brokerage_ladder"}
        ],"path": "/sales"},
        # {"title": "Post Sales", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Post+Sales.svg", "subMenu": [
        #     {"title": "All Customers", "path": "/post_sales/all_clients"},
        #     {"title": "Construction Updates", "path": "/post_sales/events"},
        #     {"title": "Possession", "path": "/post_sales/possession"}
        # ],"path": "/post_sales"},
        {"title": "Accounts", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Accounts.svg", "subMenu": None,"path": "/accounts"},
        {"title": "Sourcing", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Pre+Sales.svg", "subMenu": [
            {"title": "Dashboard", "path": "/sourcing/dashboard"},
            {"title": "All Channel Partners", "path": "/sourcing/all_channel_partners"},
        ],"path": "/sourcing"},
        {"title": "Reset Password", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/reset_password_icon.png", "subMenu": None,"path": "/reset_password"},
        # {"title": "User", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/User.svg", "subMenu": None,"path": "/user"},
        #  {"title": "Research", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Accounts.svg", "subMenu": None,"path": "/research"},
    ]

    meta_structure = meta_structure_prod if current_env == "PROD" else meta_structure
       

    allowed_meta = []


    if 'ADMIN' in user_groups or 'PROMOTER' in user_groups or 'VICE_PRESIDENT' in user_groups or 'SUPER ADMIN' in user_groups :
        if current_env == "PROD":
           allowed_meta = [item for item in meta_structure if item["title"] in ["Marketing", "Pre Sales", "Sales", "Accounts", "Sourcing", "Reset Password"]]    
        else:  
           allowed_meta = meta_structure
           
    elif 'CRM_HEAD' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in ["Dashboard","Post Sales","Reset Password"]]    
    elif 'CALL_CENTER_EXECUTIVE' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in ["Pre Sales","Reset Password"]]
    elif 'RECEPTIONIST' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in ["Sales", "Reset Password"]]
        exclude_submenu_title = [ "Dashboard",'Closure',"Brokerage Payments","Closed Deals","Brokerage Ladder"]
        for item in allowed_meta:
            if "subMenu" in item and item["subMenu"] is not None:
                item["subMenu"] = [submenu for submenu in item["subMenu"] if submenu["title"] not in exclude_submenu_title]

    elif 'CLOSING_MANAGER' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in ["Sales", "Reset Password"]]
        exclude_submenu_title = 'Brokerage Payments' 
        exclude_submenu_title = ["Brokerage Ladder","Brokerage Payments"]  
        for item in allowed_meta:
            if "subMenu" in item and item['title']=="Sales" and item["subMenu"] is not None:
                item["subMenu"] = [submenu for submenu in item["subMenu"] if submenu["title"] not in exclude_submenu_title] 
        # for item in allowed_meta:
        #     if "subMenu" in item and item["subMenu"] is not None:
        #         item["subMenu"] = [submenu for submenu in item["subMenu"] if submenu["title"] != exclude_submenu_title]
    elif 'SITE_HEAD' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in [ "Dashboard","Pre Sales", "Sales", "Sourcing","Accounts" , "Reset Password"]]
    elif 'CRM_EXECUTIVE' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in ["Dashboard", "Post Sales", "Reset Password"]]
        exclude_submenu_title = ['Construction Updates'] 
        for item in allowed_meta:
            if "subMenu" in item and item["title"] == "Post Sales":
                item["subMenu"] = [submenu for submenu in item["subMenu"] if submenu["title"] not in exclude_submenu_title]
    elif 'MARKETING_HEAD' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in ["Dashboard","Marketing", "Accounts", "Reset Password"]]
    elif 'MARKETING_EXECUTIVE' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in ["Dashboard","Marketing", "Reset Password"]]
        exclude_submenu_title = ['Performance',"Budget & Payments"]  
        for item in allowed_meta:
            if "subMenu" in item and item['title']=="Marketing":
                item["subMenu"] = [submenu for submenu in item["subMenu"] if submenu["title"] not in exclude_submenu_title]
    elif 'ACCOUNTS_HEAD' in user_groups or 'ACCOUNTS_EXECUTIVE' in user_groups :
        allowed_meta = [item for item in meta_structure if item["title"] in ["Dashboard", "Accounts", "Reset Password" ]] 
    # elif 'SOURCING_MANAGER' in user_groups:
    #     allowed_meta = [{"title": "Sourcing", "image": "https://enso-dev-bucket.s3.ap-south-1.amazonaws.com/dashboard_icons/Pre+Sales.svg", "subMenu": [
    #         # {"title": "Dashboard", "path": "/sourcing/dashboard"},
    #         {"title": "All Channel Partners", "path": "/sourcing/all_channel_partners"},
    #     ],"path": "/sourcing"},{"title": "Reset Password", "image": "", "subMenu": None,"path": "/reset_password"}]
    elif 'SOURCING_MANAGER' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in ["Dashboard","Sales", "Sourcing", "Reset Password"]]
        exclude_submenu_title = ["Brokerage Ladder"]  
        for item in allowed_meta:
            if "subMenu" in item and item['title']=="Sales":
                item["subMenu"] = [submenu for submenu in item["subMenu"] if submenu["title"] not in exclude_submenu_title]
    elif 'MIS' in user_groups:
        allowed_meta = [item for item in meta_structure if item["title"] in ["MIS Dashboard", "Reset Password"]]
    elif 'INQUIRY_FORM' in user_groups:
        allowed_meta = [{"title": "Inquiry", "image": "", "subMenu": None,"path": "/inquiry"},{"title": "Reset Password", "image": "", "subMenu": None,"path": "/reset_password"}] 
    print("allowed_data",allowed_meta)    
    return allowed_meta


@swagger_auto_schema(
operation_summary = "Login api",
operation_description="It gets mobile number as input for logging",
responses={200: 'OK'},
)    
@csrf_exempt
def verify_otp(request):
    if request.method=='POST':
        body= json.loads(request.body)
        otp=body.get('otp')
        print('otp:',otp,type(otp))
        
        mobile_number = body.get('mobile')

        session_id = body.get('session_id')

        if otp=="1234":
            try:
                user=models.Users.objects.get(mobile=mobile_number)
                #print(user)
                token = Token.objects.get_or_create(user=user)
                token_value = str(token[0])
                groups = list(user.groups.values_list('name', flat=True))
                permissions = list(user.user_permissions.values_list('codename', flat=True))
                dashboard_items = get_dashboard_metadata(groups)
                #print(dashboard_items)
                data_dict = {
                    'id': user.id,
                    'name': user.name,
                    'mobile': user.mobile,
                    'email': user.email,
                    'gender': user.gender,
                    'profile_pic': '',
                    'token': token_value,
                    'groups': groups,
                    'permissions': permissions,
                    'dashboard': dashboard_items,
                }
                error=False
                message="OTP Verified Successfully"
                body=data_dict
                status=200
                return ResponseHandler(error,message,body,status)
            except models.Users.DoesNotExist:
                error=True
                message="User is not registered"
                body=""
                status=401
                return ResponseHandler(error,message,body,status)
        
            '''
            response_data={
                'message':"OTP Verified Successfully",
                'token':token_value,
                'user':{
                    'id':user.id,
                    'name':user.name,
                    'mobile':user.mobile,
                    'email':user.email,
                    'gender': user.gender,
                    'profile_pic':'',
                }
            }
            return JsonResponse(response_data, status=200)'''
        else:
            error=True
            message="Please Check the otp"
            body=""
            status=400
            return ResponseHandler(error,message,body,status)

        '''
        try:
            otp_session = models.OTPSession.objects.filter(session_id=session_id)
            #print('OTP SESSION:', otp_session, timezone.now())

        except models.OTPSession.DoesNotExist:
            return JsonResponse({'message':'Invalid session_id'},status=400)
        
        if len(otp_session)>0:
            otp_session = otp_session[0]
            otp_db = otp_session.otp
            exp_time=otp_session.expires_at
            print(exp_time)
            print(timezone.now())
            #print("otpsession: ",otp_session)
        else:
            return JsonResponse({'message': 'Invalid session id'},status=400)
        
        #expires_at=2 and datetime.now()<otp_session[0].expires_at
        if otp==otp_db and timezone.now()<exp_time:
            user = models.Users.objects.filter(mobile=otp_session.identifier)[0]
            token = Token.objects.get_or_create(user=user)[0]
            #print('token',token)
            return JsonResponse({'message': 'OTP verified successfully', 'session_id': session_id})
        else:
            return JsonResponse({'message': 'Invalid session id'},status=400)
        '''

@api_view(['POST'])
def login_email(request):
    if request.method == 'POST':
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = authenticate(request, email=serializer.validated_data['email'], password=serializer.validated_data['password'])
            # print("USER: ", user)
            if user:
                #auth_login(request, user)
                token, created = Token.objects.get_or_create(user=user)
                groups = list(user.groups.values_list('name', flat=True))
                permissions = list(user.user_permissions.values_list('codename', flat=True))
                dashboard_items = get_dashboard_metadata(groups)
                p_role = None
                promoter_users = Users.objects.filter(groups__name="PROMOTER").order_by('id')[:3]
                user_dict = {
                    'P1': promoter_users[0].id if len(promoter_users) > 0 else None,
                    'P2': promoter_users[1].id if len(promoter_users) > 1 else None,
                    'P3': promoter_users[2].id if len(promoter_users) > 2 else None,
                }
                if user.groups.filter(name ="PROMOTER").exists():
                    for key, value in user_dict.items():
                        if value == user.id:
                            p_role = key

                data_dict = {
                    'id': user.id,
                    'name': user.name,
                    'mobile': user.mobile,
                    'email': user.email,
                    'gender': user.gender,
                    'profile_pic': '',  # Add logic to fetch or generate profile picture URL
                    'token': str(token),
                    'groups': groups,
                    'promoter_role' : p_role,
                    'permissions': permissions,
                    'dashboard': dashboard_items,
                    'organization': user.organization.id if user.organization else None,
                }

                response_data = {
                    "error": False,
                    "message": "Login successful",
                    "body": data_dict,
                }

                return ResponseHandler(False, 'Login successful', data_dict, status.HTTP_200_OK)
            else:
                return ResponseHandler(True, 'Invalid credentials', None, status.HTTP_401_UNAUTHORIZED)
        else:    
            return ResponseHandler(True, serializer.errors, None, status.HTTP_400_BAD_REQUEST)
    
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def store_fcm_token(request, *args, **kwargs):
    user = request.user  
    fcm_token = request.data.get('fcm_token')

    if not fcm_token:
        return ResponseHandler(True, 'Missing fcm_token parameter', None, status.HTTP_400_BAD_REQUEST)

    user.fcm_token = fcm_token
    user.save()

    return ResponseHandler(False, 'FCM token stored successfully for user.', None, status.HTTP_200_OK)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            user = request.user
            old_password = serializer.data.get("old_password")
            new_password = serializer.data.get("new_password1")
            # hash_password = make_password(user.password)
            # Validate old password
            
            if not check_password(old_password, user.password):
                return ResponseHandler(True,f"{old_password} is wrong. Please Provide Correct Password", None, status.HTTP_404_NOT_FOUND)

            # Change password
            
            form_data = {
                'old_password': old_password,
                'new_password1': new_password,
                'new_password2': new_password
            }
            form = PasswordChangeForm(user, data=form_data)
            
            if form.is_valid():
                form.save()
                return ResponseHandler(False, "Password changed successfully.", None,status.HTTP_200_OK)
            else:
                error_pwd = form.errors.get("new_password2")
                return ResponseHandler(True, f"New Password Error: {error_pwd}", None, status.HTTP_400_BAD_REQUEST)
            
        return ResponseHandler(True, 'Error', serializer.errors, status.HTTP_400_BAD_REQUEST)
    

class SetNewPasswordAPIView(APIView):
    def post(self, request, uidb64, token):

        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = Users.objects.get(pk=uid)
            print("Users: ", user)
        except Exception as e:
            user = None
        
        if user is not None and Token.objects.filter(user=user, key=token).exists():
            new_password = request.data.get('password')

            user.set_password(new_password)
            user.save()
            return ResponseHandler(False, "Password updated successfully.", None,status.HTTP_200_OK)

        else:
            return ResponseHandler(True, 'Invalid user or token', None, status.HTTP_400_BAD_REQUEST)
        


class RequestPasswordResetEmail(APIView):

    def post(self, request):
        email = request.data.get('email', None)
        if email is None:
            return Response({'error': 'Email is required'}, status=400)

        if Users.objects.filter(email=email).exists():
            user = Users.objects.filter(email=email).first()
            print(user)
            if user:
                uuidb64 = urlsafe_base64_encode(force_bytes(user.id))
                token = Token.objects.get_or_create(user=user)[0]
                print(token)
                current_site = "https://dev.estogroup.in/"  # update with FE url
                relative_link = reverse('password-reset-complete', kwargs={"token": token.key, "uidb64": uuidb64})
                print(relative_link)
                abs_link = f"{current_site}app/#/email_reset_password?token={token}"
               # abs_link = f"{current_site.strip('/')}{relative_link}"
                # email_body = f"Hi {user.name},\nPlease click on the link below to reset your password.\n{abs_link}\nRegards,\nEsto Team"
                # email_subject = "Esto - Password Reset"
                # email_template_id = 24
                headers = {
                    'Authorization': 'token 561e8af25f5eea21d27a65fd129603fad6fcdc0a',
                    'Content-Type': 'application/json'
                }

                form_data = {
                    "template_id": 24,  # Use the correct template ID
                    "email": email,
                    "parameters": {
                        "username": user.name,
                        "abs_link": abs_link
                    }
                }

                sendmail_api_url = 'http://3.111.78.151:81/api/email/sendmail/'
                json_data = json.dumps(form_data)
                response = requests.post(sendmail_api_url, data=json_data, headers=headers)
                print(response.text)
                if response.status_code == 200:
                    return ResponseHandler(False, 'Email sent successfully', None, status.HTTP_200_OK)
                else:
                    print('Failed to send email:', response)
                    return ResponseHandler(True, 'Failed to send email', None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return ResponseHandler(True, 'User with this email does not exists', None, status.HTTP_404_NOT_FOUND)

        return  ResponseHandler(True, 'Something went wrong', None, status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetPasswordView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            token_key = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']

            try:
                token = Token.objects.get(key=token_key)
            except Token.DoesNotExist:
                return Response({"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)

            user = token.user
            user.password = make_password(new_password)
            user.save()


            return Response({"detail": "Password reset successful."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    