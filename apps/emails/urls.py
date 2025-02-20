from django.urls import path
from .views import EmailTemplateListCreateView, EmailTemplateRetrieveUpdateView, EmailSendView, send_email_with_template

urlpatterns = [
    path('email-templates/', EmailTemplateListCreateView.as_view(), name='email-template-list-create'),
    path('email-templates/<int:pk>/', EmailTemplateRetrieveUpdateView.as_view(), name='email-template-detail'),
    path('send-email/', EmailSendView.as_view(), name='send-email'),
    path('send-email/<int:template_id>/send/', send_email_with_template, name='send-email-with-template')
]
