from rest_framework import generics
from .models import EmailTemplate, Email
from .serializers import EmailTemplateSerializer, EmailSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, mixins, status
from rest_framework.response import Response
from django.core.mail import send_mail
from .serializers import EmailSerializer
from auth.utils import ResponseHandler
from django.views.decorators.csrf import csrf_exempt
from .utils import get_user_from_email
from auth.decorator import role_check
from lead.decorator import check_access
from rest_framework.authentication import TokenAuthentication
from django.contrib.auth.decorators import permission_required

class EmailTemplateListCreateView(generics.ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = (IsAuthenticated,)


    @check_access(required_permissions=["emails.add_emailtemplate"]) 
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            error = False
            message = 'Email Template created successfully.'
            body = serializer.data
            return ResponseHandler(error,message,body,status.HTTP_201_CREATED)
        else:
            error = True
            message = 'Validation error.'
            body = serializer.errors
            return ResponseHandler(error,message,body,status.HTTP_400_BAD_REQUEST)


class EmailTemplateRetrieveUpdateView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, generics.GenericAPIView):
    authentication_classes = [TokenAuthentication]
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer
    permission_classes = (IsAuthenticated,)


    @check_access(required_permissions=["emails.view_emailtemplate"]) 
    def get(self, request, *args, **kwargs):
        template_id = self.kwargs.get('pk') 

        try:
            instance = EmailTemplate.objects.get(pk=template_id)
            serializer = self.get_serializer(instance)
            error  = False
            message = 'Email template retrieved successfully'
            body = serializer.data
            return ResponseHandler(error,message,body,status.HTTP_200_OK)
        
        except EmailTemplate.DoesNotExist:
            error = True
            message =  'No record present'
            body = None,
            return ResponseHandler(error, message, body, status.HTTP_404_NOT_FOUND)

    #@role_check(required_roles=['ADMIN'])

    @check_access(required_permissions=["emails.change_emailtemplate"]) 
    def put(self, request, *args, **kwargs):
        template_id = self.kwargs.get('pk')

        try:
            instance = EmailTemplate.objects.get(pk=template_id)
            serializer = self.get_serializer(instance, data=request.data)

            if serializer.is_valid():

                serializer.save()
                error  = False
                message = 'Data updated successfully'
                body = serializer.data

                return ResponseHandler(error,message,body,status.HTTP_200_OK)
            else:
                error  = True
                message =  'Validation error.'
                body = serializer.errors

                return ResponseHandler(error,message,body,status.HTTP_400_BAD_REQUEST)

        except EmailTemplate.DoesNotExist:
            error = True
            message =  'No record present'
            body = None,
            return ResponseHandler(error, message, body, status.HTTP_404_NOT_FOUND)


    @check_access(required_permissions=["emails.delete_emailtemplate"])   
    def delete(self, request, *args, **kwargs):
        template_id = self.kwargs.get('pk')
        try:
            instance = EmailTemplate.objects.get(pk=template_id)
            self.perform_destroy(instance)
            error  = False
            message ='Email Template deleted successfully',
            body =  None

            return ResponseHandler(error,message,body,status.HTTP_204_NO_CONTENT)
        except EmailTemplate.DoesNotExist:
            error  = True
            message = 'No matching data present in models',
            body =  None

            return ResponseHandler(error,message,body,status.HTTP_404_NOT_FOUND)

@csrf_exempt
def send_email_with_template(request, template_id, to_email):
    try:
        template = EmailTemplate.objects.get(pk=template_id)
        
        if not template:
            error  = True
            message ="Email template not found",
            body =  None
            return ResponseHandler(error,message,body,status.HTTP_404_NOT_FOUND)
        
        user_id = request.user.id  
        from_email = get_user_from_email(user_id)

        if not from_email:
            error  = True
            message = "Invalid user or from_email not found",
            body =  None
            return ResponseHandler(error,message,body,status.HTTP_400_BAD_REQUEST)
    
        subject = template.subject
        message = template.message

        send_mail(subject, message, from_email, [to_email])
        error  = False
        message = "Email sent successfully",
        body =  None
        return ResponseHandler(error, message, body, status.HTTP_200_OK)
    
    except Exception as e:
        error  = True
        message = str(e),
        body =  None
        return ResponseHandler(error, message, body, status.HTTP_500_INTERNAL_SERVER_ERROR)

class EmailSendView(generics.CreateAPIView):
    queryset = Email.objects.all()
    serializer_class = EmailSerializer


    @check_access(required_permissions=["emails.add_email"])   
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():

            to_email = serializer.validated_data['to_email']
            subject = serializer.validated_data['subject']
            message = serializer.validated_data['message']
            user_id = request.user.id  
            from_email = get_user_from_email(user_id)
            

            if not from_email:
                return Response({"error": True, "message": "Invalid user or from_email not found"}, status=status.HTTP_400_BAD_REQUEST)
            try:
                send_mail(subject, message, from_email, [to_email])
                return Response({"error": False, "message": "Email sent successfully"}, status=status.HTTP_200_OK)
            except Exception as e:
                error  = True
                message = str(e),
                body =  None
                return ResponseHandler(error, message, body, status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            error  = True
            message = "Validation error",
            body =  serializer.errors
            return ResponseHandler(error,message,body,status.HTTP_400_BAD_REQUEST)
            





























'''
#W#let's assume there's a serializer called EmailSerializer

class EmailSendView():
    query_set = Email.objects.all()
    serializer_class = EmailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data = request.data)
'''



#def send_mail(from_mail, to_mail, message, subject ):

