from rest_framework import serializers
from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
	connections_count = serializers.ReadOnlyField()
	lead_received_count = serializers.ReadOnlyField()
	lead_shared_count = serializers.ReadOnlyField()
	public_link = serializers.SerializerMethodField()
	category_name = serializers.SerializerMethodField()
	
	def to_representation(self, instance):
		representation = super().to_representation(instance)
		if instance.company_logo_url.strip():
			return representation
		category = instance.categories.all().first()
		if category is None:
			return representation
		
		if category.icon:
			representation['company_logo_url'] = category.icon.url
		
		return representation

	def get_category_name(self,obj):
		category = obj.categories.all().first()
		if category is None:
			return None
		
		return category.name	

	def get_public_link(self,obj):
		name = obj.name.lower().replace(" ", "-")
		return f'/in/{name}/'
	class Meta:
		model = Organization
		fields = '__all__'


        
		