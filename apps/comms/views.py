import base64
from django.shortcuts import render
# Create your views here.
from rest_framework import status
from auth.utils import ResponseHandler, ResponseHandlerAsync
from rest_framework.parsers import MultiPartParser
from rest_framework.views import APIView
import requests
from rest_framework.response import Response
from comms.utils import send_push_notification
from auth.models import *
from django.http import HttpResponseRedirect
from lead.models import Lead,Updates
import urllib.parse
from inventory.models import ProjectDetail,ProjectCostSheet,InventoryCostSheet
from workflow.models import *
from rest_framework.permissions import IsAuthenticated
from lead.decorator import  check_group_access
from .tasks import send_demand_letters
from datetime import timedelta
class EmailTemplateAPI(APIView):
    def get(self, request, *args, **kwargs):
        try:
            comms_api_url = 'http://3.111.78.151:81/api/email/templates/{}/'.format(kwargs['template_id'])
            headers = {'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade'}
            
            response = requests.get(comms_api_url, headers=headers)

            if response.status_code == 200:
                return Response(response.json())
                #return ResponseHandler(False, "Email template retrieved successfully.", response.json(), status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Failed to retrieve email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, *args, **kwargs):
        try:
            comms_api_url = 'http://3.111.78.151:81/api/email/templates/{}/'.format(kwargs['template_id'])
            headers = {'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade'}

            response = requests.put(comms_api_url, json=request.data, headers=headers)

            if response.status_code == 200:
                return Response(response.json())
                # return ResponseHandler(False, "Email template updated successfully.", response.json(), status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Failed to update email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, *args, **kwargs):
        try:          
            comms_api_url = 'http://3.111.78.151:81/api/email/templates/{}/'.format(kwargs['template_id'])
            print("comms_api_url: ",comms_api_url)
            response = requests.delete(comms_api_url)

            if response.status_code == 204:
                return ResponseHandler(False, "Email template deleted successfully.", None, status.HTTP_204_NO_CONTENT)
            else:
                return ResponseHandler(True, "Failed to delete email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)



class WhatsAppMessageTemplateRetrieveUpdateDeleteView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            comms_api_url = 'http://3.111.78.151:81/api/whatsapp/templates/{}/'.format(kwargs['template_id'])
            headers = {'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade'}
            
            response = requests.get(comms_api_url, headers=headers)

            if response.status_code == 200:
                return Response(response.json())
                #return ResponseHandler(False, "Email template retrieved successfully.", response.json(), status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Failed to retrieve email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, *args, **kwargs):
        try:
            comms_api_url = 'http://3.111.78.151:81/api/whatsapp/templates/{}/'.format(kwargs['template_id'])
            headers = {'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade'}

            response = requests.put(comms_api_url, json=request.data, headers=headers)

            if response.status_code == 200:
                return Response(response.json())
                # return ResponseHandler(False, "Email template updated successfully.", response.json(), status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Failed to update email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, *args, **kwargs):
        try:          
            comms_api_url = 'http://3.111.78.151:81/api/email/templates/{}/'.format(kwargs['template_id'])
            headers = {'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade'}
            print("comms_api_url: ",comms_api_url)
            response = requests.delete(comms_api_url, headers=headers)

            if response.status_code == 204:
                return ResponseHandler(False, "Email template deleted successfully.", None, status.HTTP_204_NO_CONTENT)
            else:
                return ResponseHandler(True, "Failed to delete email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class CreateEmailTemplate(APIView):
    def post(self, request, *args, **kwargs):
        try:
            comms_api_url = 'http://3.111.78.151:81/api/email/templates/'
            headers = {'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade'}
            response = requests.post(comms_api_url, json=request.data, headers=headers)

            if response.status_code == 201:
                return Response(response.json())
                # return ResponseHandler(False, "Email template created successfully.", response.json(), status.HTTP_201_CREATED)
            else:
                return ResponseHandler(True, "Failed to create email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            
    def get(self, request, *args, **kwargs):
        try:
            comms_api_url = 'http://3.111.78.151:81/api/email/templates/'
            headers = {'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade'}
            
            response = requests.get(comms_api_url, headers=headers)

            if response.status_code == 200:
                return Response(response.json())
                #return ResponseHandler(False, "Email template retrieved successfully.", response.json(), status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Failed to retrieve email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

class WhatsAppMessageTemplateListCreateView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            comms_api_url = 'http://3.111.78.151:81/api/whatsapp/templates/'
            headers = {'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade'}
            response = requests.post(comms_api_url, json=request.data, headers=headers)

            if response.status_code == 201:
                return Response(response.json())
                # return ResponseHandler(False, "Email template created successfully.", response.json(), status.HTTP_201_CREATED)
            else:
                return ResponseHandler(True, "Failed to create email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
                
            
    def get(self, request, *args, **kwargs):
        try:
            comms_api_url = 'http://3.111.78.151:81/api/email/templates/'
            headers = {'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade'}
            
            response = requests.get(comms_api_url, headers=headers)

            if response.status_code == 200:
                return Response(response.json())
                #return ResponseHandler(False, "Email template retrieved successfully.", response.json(), status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Failed to retrieve email template.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class AttachFilesToTemplate(APIView):
    parser_classes = (MultiPartParser,)

    def post(self, request, *args, **kwargs):
        try:
            template_id = request.data.get('template_id')
            print("template_id: ", template_id)
            if not template_id:
                return ResponseHandler(True, "template_id is required.", None, status.HTTP_400_BAD_REQUEST)

            uploaded_file = request.FILES.get('upload_files')

            if not uploaded_file:
                return ResponseHandler(True, "upload_files is required.", None, status.HTTP_400_BAD_REQUEST)

            comms_api_url = 'http://3.111.78.151:81/api/email/templates/attach-files/'
            files = {'upload_files': uploaded_file}
            data = {'template_id': template_id}
            response = requests.post(comms_api_url, data=data, files=files)

            print("response: ", response, response.status_code)
            if response.status_code == 201:
                email_templates = response.json()
                return ResponseHandler(False, "File attached to the template successfully.", None, status.HTTP_200_OK)
            else:
                return ResponseHandler(True, "Failed to fetch email templates.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

class SendMailAPI(APIView):
    def post(self, request, *args, **kwargs):
        try:
            sendmail_api_url = 'http://3.111.78.151:81/api/email/sendmail/'
            headers = {
                'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade',
                'Content-Type': 'application/json'
            }

            email_param = self.request.GET.get('email_param', None)
            
            if email_param == "custom":

                headers = {
                    'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade',
                }
                if 'email' not in request.data or request.data.get('email') == '' or request.data.get('email') is None:
                    return ResponseHandler(True, "Email is required.", None, status.HTTP_400_BAD_REQUEST)

                if 'subject' not in request.data or request.data.get('subject') == '' or request.data.get('subject') is None:
                    return ResponseHandler(True, "Subject is required.", None, status.HTTP_400_BAD_REQUEST)

                if 'message' not in request.data or request.data.get('message') == '' or request.data.get('message') is None:
                    return ResponseHandler(True, "Message is required.", None, status.HTTP_400_BAD_REQUEST)
                  
                form_data = {
                    'subject': request.data.get('subject', ''),
                    'email': request.data.get('email', ''),
                    'message': request.data.get('message', ''),
                }


                attachments = request.FILES.getlist('attachments')

                files = [('attachments', (attachment.name, attachment)) for attachment in attachments]

                response = requests.post(sendmail_api_url, data=form_data, headers=headers, files=files,params=self.request.query_params)

            else:   
                if 'email' not in request.data or request.data.get('email') == '' or request.data.get('email') is None:
                    return ResponseHandler(True, "Email is required.", None, status.HTTP_400_BAD_REQUEST)
                
                if 'template_id' not in request.data or request.data.get('template_id') == '' or request.data.get('template_id') is None:
                    return ResponseHandler(True, "Template id is required.", None, status.HTTP_400_BAD_REQUEST)
                
                response = requests.post(sendmail_api_url, json=request.data, headers=headers, params=self.request.query_params)

            if response.status_code == 200:
                return ResponseHandler(False, "'Email sent successfully.", None, status.HTTP_200_OK) 
            else:
                return ResponseHandler(True, "'Failed to send email.", response.text, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)



class SendWhatsAppMessageView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            sendwhatsapp_api_url = 'http://3.111.78.151:81/api/whatsapp/sendwhatsapp/'
            headers = {
                'Authorization': 'token 3ce7752202f68f1861478d26c500e99fc0a69ade',
                'Content-Type': 'application/json'
            }
            recipient_numbers = request.data.get('recipient_numbers', [])
            template_id = request.data.get('template_id')
            dynamic_data = request.data.get('dynamic_data', {})
            #attachments = request.data.get('attachments', [])
            service_name = request.data.get('service_name')
            src_name = request.data.get('src_name')  
            source_number = request.data.get('source_number')  
            
            if not all([recipient_numbers, template_id, dynamic_data, service_name, src_name, source_number]):
                return ResponseHandler(True, "All required fields are mandatory.", None, status.HTTP_400_BAD_REQUEST)


            response = requests.post(sendwhatsapp_api_url, json=request.data, headers=headers)

            if response.status_code == 200:
                return ResponseHandler(False, "'Whatsapp message sent successfully.", None, status.HTTP_200_OK) 
            else:
                return ResponseHandler(True, "'Failed to send whatsapp message.", None, status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

class WhatsAppRedirectView(APIView):
    def get(self, request, lead_id):
        try:
            lead = Lead.objects.get(id=lead_id)
            phone_number = f"91{lead.primary_phone_no}"
            
            message = ""

            query_param = request.query_params.get('param', None)
            if query_param == 'PRESALES':
                message = ""
            elif query_param == 'SALES':
                message = ""
            
            encoded_message = urllib.parse.quote(message)
            
            whatsapp_link = f"https://web.whatsapp.com/send?phone={phone_number}&text={encoded_message}"
            return HttpResponseRedirect(whatsapp_link)
        except Lead.DoesNotExist:
            return ResponseHandler(True,  "Lead not found", None, status.HTTP_404_NOT_FOUND) 
        
class SendDemandLetter(APIView):
    permission_classes = [IsAuthenticated]

    @check_group_access(required_groups=['CRM_HEAD'])
    def post(self, request):

        project_id = request.data.get('project_id')
        event_id = request.data.get('event_id')
        
        print(f"Project ID: {project_id}, Event ID: {event_id}")

        try:
            project = ProjectDetail.objects.get(id=project_id)
        except ProjectDetail.DoesNotExist:
            return ResponseHandler(True, 'Project does not exist', None, status.HTTP_400_BAD_REQUEST)
        
        try:
            project_cost_sheet = ProjectCostSheet.objects.get(project=project, id=event_id, event_status="Done")
            print("Project cost sheet: ", project_cost_sheet, project_cost_sheet.id)
            event_order = project_cost_sheet.event_order
            if not project_cost_sheet.due_date:
                return ResponseHandler(True, 'ProjectCostSheet Due Date is not marked', None, status.HTTP_400_BAD_REQUEST)
            #fetch documents from project cost sheet
            architect_certificate = project_cost_sheet.architect_certificate
            site_image = project_cost_sheet.site_image

            if not architect_certificate or not site_image:
                return ResponseHandler(
                    True,
                    'Both Architect\'s certificate and Site image are required to send the demand letter.',
                    None,
                    status.HTTP_400_BAD_REQUEST
                )
        except ProjectCostSheet.DoesNotExist:
            return ResponseHandler(True, 'Event not found or not marked as "Done" in ProjectCostSheet', None, status.HTTP_400_BAD_REQUEST)
        
        stage = Stage.objects.filter(name='PostSales').first()
        post_sales_leads = Lead.objects.filter(
            workflow__current_stage=stage.order,
            inventorycostsheet__event_order=event_order,
            inventorycostsheet__payment_in_percentage__gt=0,
            primary_email__isnull=False
        ).distinct()
        
        print(f"Total leads to send demand letters: {post_sales_leads.count()}")

        for lead in post_sales_leads:
            print(f"Processing demand letter for lead: {lead}")
            updates_record, created = Updates.objects.get_or_create(lead=lead)
            print("updated_record: ", updates_record, lead, event_order)
            inventory_instance = InventoryCostSheet.objects.filter(lead=lead, event_order=event_order).first()
            if inventory_instance:
                email_id = lead.primary_email
                lead_name = f"{lead.first_name} {lead.last_name}"
                company_name = lead.organization.name
                due_date = str((project_cost_sheet.due_date + timedelta(days=1)).date())
                amount = int(inventory_instance.total_amount)
   
                print(f"Sending demand letter to {email_id} for lead {lead_name}")
                print(f"Due date:{due_date}")

                send_demand_letter = True

                # if updates_record and updates_record.slab:
                #     if updates_record.slab.event_order <= project_cost_sheet.event_order:
                #         send_demand_letter = False
                        

                if email_id and due_date and amount and send_demand_letter :
                    architect_certificate.open('rb')
                    site_image.open('rb')
                    cert_file_content = base64.b64encode(architect_certificate.read()).decode('utf-8')
                    image_file_content = base64.b64encode(site_image.read()).decode('utf-8')
                    try:
                        response = requests.post(
                            'http://3.111.78.151:81/api/email/sendmail/',
                            headers={
                                'Authorization': 'token 43fb69c07ff4d2ec5b75bfa16638588a8606e199',
                                'Content-Type': 'application/json'
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
                                    "apartment_name": inventory_instance.inventory.apartment_no
                                },
                                "attachments": {
                                    "architect_certificate": cert_file_content,
                                    "site_image": image_file_content
                                }
                            }
                        )

                        if response.status_code == 200:
                            if not updates_record.slab or updates_record.slab.event_order < project_cost_sheet.event_order: 
                                updates_record.demand_letter_status = "Sent"
                                updates_record.slab = project_cost_sheet
                                updates_record.save() 
                        else:
                            print(f"Failed to send demand letter. HTTP status code: {response.status_code}")
                    finally:
                        architect_certificate.close()
                        site_image.close()
                else:
                    print("Email is Not Sent: ",lead,due_date,email_id,amount)


        return ResponseHandler(False, 'Demand letters sent successfully', None, status.HTTP_200_OK)

# class SendDemandLetter(APIView):
#     permission_classes = [IsAuthenticated]

#     @check_group_access(required_groups=['CRM_HEAD'])
#     def post(self, request):
#         project_id = request.data.get('project_id')
#         event_id = request.data.get('event_id')
        
#         print(f"Project ID: {project_id}, Event ID: {event_id}")

#         send_demand_letters.apply_async(args=[project_id, event_id])

#         return ResponseHandler(False, 'Demand letters sent successfully.', None, status.HTTP_200_OK)