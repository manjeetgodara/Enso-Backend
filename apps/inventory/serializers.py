from decimal import Decimal
from rest_framework import serializers
from .models import *
from river.models import Workflow
from workflow.serializers import TaskSerializer
from auth.serializers import UserSerializer
from lead.serializers import SourceSerializer

class ProjectDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectDetail
        fields = '__all__'

class PropertyOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyOwner
        fields = '__all__'

class ProjectDetailPreviewSerializer(serializers.ModelSerializer):
    total_towers = serializers.SerializerMethodField()
    total_events = serializers.SerializerMethodField()
    class Meta:
        model = ProjectDetail
        fields = '__all__'

    def get_total_towers(self,obj):#ProjectTower
        return obj.projecttower_set.count()
    
    def get_total_events(self,obj):
        return obj.projectcostsheet_set.count()
class ConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Configuration
        fields = '__all__'



class ProjectInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectInventory
        fields = '__all__'

class ProjectCostSheetSerializer(serializers.ModelSerializer):
    event_status_list = serializers.SerializerMethodField()
    class Meta:
        model = ProjectCostSheet
        fields = '__all__'
    
    def get_event_status_list(self,obj):
        EVENT_STATUS_CHOICES = ["Pending", "Done"]
        current_status = obj.event_status
        return [ {"status": status, "selected": status == current_status} for status in EVENT_STATUS_CHOICES]

class InventoryCostSheetSerializer(serializers.ModelSerializer):
    remaining_amount = serializers.ReadOnlyField()
    payment_status = serializers.ReadOnlyField()
    co_owner_number = serializers.SerializerMethodField()


    class Meta:
        model = InventoryCostSheet
        fields = '__all__'

    def get_co_owner_number(self, obj):
        from lead.models import Lead
        
        # Fetch the specific lead instance
        lead = Lead.objects.filter(id=obj.lead.id).first()
        
        if lead:
            # Count the non-None co-owner signature fields
            co_owner_count = sum([
                bool(lead.co_owner1_signature),
                bool(lead.co_owner2_signature),
                bool(lead.co_owner3_signature),
                bool(lead.co_owner4_signature),
                bool(lead.co_owner5_signature)
            ])
            return co_owner_count
        
        return None
        
       


class ProjectTowerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectTower
        fields = ['name']


class BookingFormSerializer(serializers.ModelSerializer):

    # project = ProjectDetailPreviewSerializer(read_only=True)
    # sales_manager_name = UserSerializer(read_only=True)
    # configuration = ConfigurationSerializer(read_only=True)
    # tower = ProjectTowerSerializer(read_only=True)

    class Meta:
        model = BookingForm
        fields = '__all__'
        # extra_kwargs = {
        #     'customer_name': {'required': True},
        #     'nationality': {'required': True},
        #     'pan_no': {'required': True},
        #     # 'residence_phone_no': {'required': True},
        #     'residence_address': {'required': True},
        #     'permanent_address': {'required': True},
        #     'correspondance_address': {'required': True},
        #     'aadhaar_details': {'required': True},
        #     'contact_person_name': {'required': True},
        #     'contact_person_number': {'required': True},
        #     'sales_manager_name': {'required': True},
        #     'booking_source': {'required': True},
        #     'date_of_booking': {'required': True},
        #     'apartment_no': {'required': True},
        #     'tower': {'required': True},
        #     'floor': {'required': True},
        #     'configuration': {'required': True},
        #     'project': {'required': True},
        #     'marital_status': {'required': True},
        #     # 'family_configuration': {'required': True},         
        # }


class BookingFormSignatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingForm
        fields = ['client_signature', 'cm_signature', 'vp_signature', 'co_owner_signature']


class ClosureStepSerializer(serializers.ModelSerializer):
    current_closure_step = serializers.SerializerMethodField()
    current_task = serializers.SerializerMethodField()
    inventory = serializers.SerializerMethodField()
    tower = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    cost_sheet_status = serializers.SerializerMethodField()
    booking_form_id = serializers.SerializerMethodField()

    class Meta:
        model = Workflow 
        fields = [ 'current_closure_step', 'current_task', 'inventory', 'tower', 'project', 'cost_sheet_status', 'booking_form_id']

    def get_current_closure_step(self, obj):
        lead_workflow = Workflow.objects.filter(lead=obj).first()
        # return lead_workflow.current_task + 1 if lead_workflow and lead_workflow.current_stage==1 else None
        current_task = lead_workflow.tasks.filter(completed=False, stage__name='Sales').order_by('order').first()
        current_task_order = None
        if current_task and current_task.order >=3:
            current_task_order = current_task.order
        elif current_task:
            current_task_order = current_task.order + 1
        else:
            current_task_order = None
        return current_task_order

    def get_current_task(self, obj):
        lead_workflow = obj.workflow.get()
        current_task = lead_workflow.tasks.filter(completed=False, stage__name='Sales').order_by('order').first()
        if current_task:
            data = TaskSerializer(current_task).data
            return data
        return None
    
    def get_inventory(self, obj):
        inventory = PropertyOwner.objects.filter(lead=obj).first()
        # current_task = lead_workflow.tasks.filter(completed=False, stage__name='Sales').order_by('order').first()
        if inventory:
            data = ProjectInventorySerializer(inventory.property).data
            return data
        return None
    
    def get_tower(self, obj):
        inventory = PropertyOwner.objects.filter(lead=obj).first()
        # current_task = lead_workflow.tasks.filter(completed=False, stage__name='Sales').order_by('order').first()
        if inventory:
            data = ProjectTowerSerializer(inventory.property.tower).data
            return data
        return None
    
    def get_project(self, obj):
        inventory = PropertyOwner.objects.filter(lead=obj).first()
        # current_task = lead_workflow.tasks.filter(completed=False, stage__name='Sales').order_by('order').first()
        if inventory:
            data = ProjectDetailPreviewSerializer(inventory.property.tower.project).data
            return data
        return None
    
    def get_cost_sheet_status(self, obj):
        lead_workflow = Workflow.objects.filter(lead=obj).first()
        cost_sheet_task = lead_workflow.tasks.filter(name='Cost Sheet').first()
        if cost_sheet_task:
            return cost_sheet_task.completed
        return False
    
    def get_booking_form_id(self, obj):
        booking_form = BookingForm.objects.filter(lead_id=obj).first()
        if booking_form:
            return BookingFormSerializer(booking_form).data
        return None
    
class CollectTokenInfoSerializer(serializers.ModelSerializer):
    booking_form = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    occupation = serializers.SerializerMethodField()
    configuration = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    current_task = serializers.SerializerMethodField()
    tower = serializers.SerializerMethodField()
    pre_deal_amount = serializers.SerializerMethodField()
    car_parking_amount = serializers.SerializerMethodField()
    deal_amount = serializers.SerializerMethodField()
    inventory = serializers.SerializerMethodField()
    booking_source = serializers.SerializerMethodField()
    final_amount = serializers.SerializerMethodField()
    rera_number = serializers.SerializerMethodField()
    sales_manager_name = serializers.SerializerMethodField()
    class Meta:
        model = Workflow 
        fields = [ 'booking_form','full_name', 'occupation', 'configuration', 'area', 'current_task', 'project','tower', 'rera_number','sales_manager_name','pre_deal_amount', 'car_parking_amount','deal_amount', 'final_amount', 'inventory', 'booking_source']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def get_occupation(self, obj):
        return obj.occupation if obj.occupation else None
    
    def get_configuration(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return property_owner.property.configuration.name if property_owner and property_owner.property and property_owner.property.configuration else None
    
    def get_area(self, obj):
        AREA_CHOICES=[
            ('<1000 Sqft', '<1000 Sqft'),
            ('1000-1500 Sqft', '1000-1500 Sqft'),
            ('>1500 Sqft', '<1500 Sqft')
        ]
            
        property_area_choices = dict(AREA_CHOICES)
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        print('property_owner:', property_owner)

        property_area_selected = property_owner.property.area if property_owner and property_owner.property else None
        print('property_area_selected:', property_area_selected)

        lead_status_list = [
           {"area": status, "selected": status == property_area_selected}
           for status in property_area_choices.keys()
        ]
        return lead_status_list
    
    def get_booking_form(self, obj):
        booking_form = BookingForm.objects.filter(lead_id=obj).first()
        return booking_form.id if booking_form else None
    
    def get_sales_manager_name(self, obj):
        booking_form = BookingForm.objects.filter(lead_id=obj).first()
        return booking_form.sales_manager_name.name if booking_form else None

    def get_rera_number(self,obj):
        project_inventory = ProjectInventory.objects.filter(lead=obj).first()
        if project_inventory and project_inventory.tower:
            rera_number = project_inventory.tower.project.rera_number
        else:
            None    

    def get_booking_source(self, obj):
        # booking_form = BookingForm.objects.filter(lead_id=obj).first()
        return SourceSerializer(obj.source).data if obj.source else None

    def get_project(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return ProjectDetailSerializer(property_owner.property.tower.project).data if property_owner else None
    
    def get_tower(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return property_owner.property.tower.name if property_owner and property_owner.property and property_owner.property.tower else None
    
    def get_pre_deal_amount(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return float(property_owner.property.pre_deal_amount) if property_owner and property_owner.property else None
    
    def get_car_parking_amount(self , obj):

        project_inventory=ProjectInventory.objects.filter(lead = obj).first()
        return project_inventory.amount_per_car_parking if project_inventory else 0
    
    def get_deal_amount(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return float(property_owner.deal_amount) if property_owner and property_owner.deal_amount else 0
    
    def get_final_amount(self, obj):
        car_parking_amount = Decimal(self.get_car_parking_amount(obj) or 0)
        deal_amount = Decimal(self.get_deal_amount(obj) or 0)
        return car_parking_amount + deal_amount

    def get_current_task(self, obj):
        lead_workflow = obj.workflow.get()
        current_task = lead_workflow.tasks.filter(completed=False, stage__name='Sales').order_by('order').first()
        if current_task:
            data = TaskSerializer(current_task).data
            return data
        return None
    
    def get_inventory(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return ProjectInventorySerializer(property_owner.property).data if property_owner and property_owner.property else None
    
class BookingFormMetaDataSerializer(serializers.ModelSerializer):
    booking_form = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    occupation = serializers.SerializerMethodField()
    configuration = serializers.SerializerMethodField()
    area = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    current_task = serializers.SerializerMethodField()
    tower = serializers.SerializerMethodField()
    pre_deal_amount = serializers.SerializerMethodField()
    deal_amount = serializers.SerializerMethodField()
    inventory = serializers.SerializerMethodField()
    booking_source = serializers.SerializerMethodField()
    
    class Meta:
        model = Workflow 
        fields = [ 'booking_form','full_name', 'occupation', 'configuration', 'area', 'current_task', 'project','tower', 'pre_deal_amount', 'deal_amount', 'inventory', 'booking_source']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    
    def get_occupation(self, obj):
        return obj.occupation if obj.occupation else None
    
    def get_configuration(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return property_owner.property.configuration.name if property_owner and property_owner.property and property_owner.property.configuration else None
    
    def get_area(self, obj):
        # AREA_CHOICES=[
        #     ('<1000 Sqft', '<1000 Sqft'),
        #     ('1000-1500 Sqft', '1000-1500 Sqft'),
        #     ('>1500 Sqft', '<1500 Sqft')
        # ]
        AREA_CHOICES=[
        ('<400 Sqft', '<400 Sqft'),
        ('400 - 500 Sqft', '400 - 500 Sqft'),
        ('>500 Sqft', '>500 Sqft'),
        ('<600 Sqft', '<600 Sqft'),
        ('600 - 700 Sqft', '600 - 700 Sqft'),
        ('>700 Sqft', '>700 Sqft'),
        ('<1000 Sqft', '<1000 Sqft'),
        ('1000 - 1300 Sqft', '1000 - 1300 Sqft'),
        ('>1300 Sqft', '>1300 Sqft'),
        ('1000 - 1500 Sqft', '1000 - 1500 Sqft'),
        ('>1500 Sqft', '>1500 Sqft'),
    ]
            
        property_area_choices = dict(AREA_CHOICES)
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        print('property_owner:', property_owner)

        property_area_selected = property_owner.property.area if property_owner and property_owner.property else None
        print('property_area_selected:', property_area_selected)

        lead_status_list = [
           {"area": status, "selected": status == property_area_selected}
           for status in property_area_choices.keys()
        ]
        return lead_status_list
    
    def get_booking_form(self, obj):
        booking_form = BookingForm.objects.filter(lead_id=obj).first()
        return booking_form.id if booking_form else None

    def get_booking_source(self, obj):
        # booking_form = BookingForm.objects.filter(lead_id=obj).first()
        return SourceSerializer(obj.source).data if obj.source else None

    def get_project(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return ProjectDetailSerializer(property_owner.property.tower.project).data if property_owner else None
    
    def get_tower(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return property_owner.property.tower.name if property_owner and property_owner.property and property_owner.property.tower else None
    
    def get_pre_deal_amount(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return float(property_owner.property.pre_deal_amount) if property_owner and property_owner.property else None
    
    def get_deal_amount(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return float(property_owner.deal_amount) if property_owner and property_owner.deal_amount else 0

    def get_current_task(self, obj):
        lead_workflow = obj.workflow.get()
        current_task = lead_workflow.tasks.filter(completed=False, stage__name='Sales').order_by('order').first()
        if current_task:
            data = TaskSerializer(current_task).data
            return data
        return None
    
    def get_inventory(self, obj):
        property_owner = PropertyOwner.objects.filter(lead=obj).first()
        return ProjectInventorySerializer(property_owner.property).data if property_owner and property_owner.property else None


class ProjectInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectInventory
        fields = '__all__'

class SalesActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesActivity
        fields = '__all__'