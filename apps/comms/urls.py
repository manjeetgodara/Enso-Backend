from django.urls import path
from .views import *

urlpatterns = [
    path('email/create-template/', CreateEmailTemplate.as_view(), name='create-email-template'),
    path('email/template/<int:template_id>/', EmailTemplateAPI.as_view(), name='email-template-list'),
    path('email/sendmail/', SendMailAPI.as_view(), name='sendmail'),
    path('email/templates/attach-files/', AttachFilesToTemplate.as_view(), name='attach-files-to-template'),
    path('email/send-demand-letter/', SendDemandLetter.as_view(), name='send_demand_letter'),
    path('whatsapp/create-template/', WhatsAppMessageTemplateListCreateView.as_view(), name='template-list-create'),
    path('whatsapp/templates/<int:template_id>/', WhatsAppMessageTemplateRetrieveUpdateDeleteView.as_view(), name='template-retrieve-update-delete'),
    path('sendwhatsapp/', SendWhatsAppMessageView.as_view(), name = 'send-whatsapp'),
    path('whatsapp/<int:lead_id>/', WhatsAppRedirectView.as_view(), name='whatsapp_redirect'),

]