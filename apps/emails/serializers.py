from rest_framework import serializers
from .models import EmailTemplate, Email

class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = '__all__'

class EmailSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Email
        fields = '__all__'
