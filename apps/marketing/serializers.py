from .models import *
from lead.models import Lead, Source
from rest_framework import serializers
from auth.models import Users
from datetime import datetime
from workflow.models import *
from auth.serializers import UserDataIdSerializer


class CampaignDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignDocument
        fields = ["document"]


class CampaignSerializer(serializers.ModelSerializer):
    agency_types = serializers.CharField(write_only=True)
    agency_types_list = serializers.SerializerMethodField(read_only=True)
    agency_names = serializers.CharField(write_only=True)
    agency_names_list = serializers.SerializerMethodField(read_only=True)
    documents = CampaignDocumentSerializer(many=True, read_only=True)
    new_documents = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )
    documents_list = serializers.SerializerMethodField(read_only=True)
    duration = serializers.SerializerMethodField(read_only=True)
    team_members_list = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Campaign
        fields = "__all__"
        extra_kwargs = {
            "campaign_name": {"required": True},
            "agency_types": {"required": True},
            "agency_names": {"required": True},
            "budget": {"required": True},
            "start_date": {"required": True},
        }

    def get_agency_types_list(self, obj):
        return [agency_type.name for agency_type in obj.agency_type.all()]

    def get_agency_names_list(self, obj):
        return [agency_name.agency_name for agency_name in obj.agency_name.all()]

    def get_documents_list(self, obj):
        aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
        storage_destination = os.getenv("STORAGE_DESTINATION")
        base_url = (
            f"https://{aws_storage_bucket_name}.{storage_destination}.amazonaws.com/"
        )

        documents = obj.documents.all()
        print([(str(base_url) + str(document.document)) for document in documents])
        return [(str(base_url) + str(document.document)) for document in documents]

    def validate_agency_types(self, value):
        agency_type_list = [atype.strip() for atype in value.split(",")]
        if not all(
            AgencyType.objects.filter(name=atype).exists() for atype in agency_type_list
        ):
            raise serializers.ValidationError("One or more agency types are not valid.")
        return agency_type_list

    def validate_agency_names(self, value):
        agency_name_list = [atype.strip() for atype in value.split(",")]
        if not all(
            Agency.objects.filter(agency_name=atype).exists()
            for atype in agency_name_list
        ):
            raise serializers.ValidationError("One or more agency names are not valid.")
        return agency_name_list

    def create(self, validated_data):
        agency_types = validated_data.pop("agency_types")
        agency_names = validated_data.pop("agency_names")
        new_documents = validated_data.pop("new_documents", [])
        print(agency_types)
        print(agency_names)
        validated_data.pop("agency_type")
        validated_data.pop("agency_name")
        print(validated_data)
        campaign = Campaign.objects.create(**validated_data)
        print(campaign)

        agency_types_objs = AgencyType.objects.filter(name__in=agency_types)
        if agency_types_objs:
            campaign.agency_type.set(agency_types_objs)

        agency_names_objs = Agency.objects.filter(agency_name__in=agency_names)
        if agency_names_objs:
            campaign.agency_name.set(agency_names_objs)
            print(f"campaign:{campaign}")

        for document in new_documents:
            CampaignDocument.objects.create(campaign=campaign, document=document)

        Source.objects.create(source_id=campaign.sourceid, name=campaign.campaign_name)

        return campaign

    def update(self, instance, validated_data):
        agency_types = validated_data.pop("agency_types")
        agency_names = validated_data.pop("agency_names")
        new_documents = validated_data.pop("new_documents", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if agency_types:
            agency_types_objs = AgencyType.objects.filter(name__in=agency_types)
            instance.agency_type.set(agency_types_objs)

        if agency_names:
            agency_names_objs = Agency.objects.filter(agency_name__in=agency_names)
            instance.agency_name.set(agency_names_objs)

        if new_documents:
            instance.documents.all().delete()
            for document in new_documents:
                CampaignDocument.objects.create(campaign=instance, document=document)

        instance.save()
        return instance
    
    def get_duration(self, obj):
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        if obj.end_date:
            return (obj.end_date - obj.start_date).days
        else:
            if obj.start_date < current_date:
                return (current_date - obj.start_date).days
            return 0
        
    def get_team_members_list(self, obj):
        team_list = []
        for user_id in obj.team_members:
            try:
                user = Users.objects.get(id=user_id)
                team_list.append(user.name)
            except Users.DoesNotExist:
                pass
        return team_list    

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["agency_types_list"] = list(
            instance.agency_type.values_list("name", flat=True)
        )
        representation["agency_names_list"] = list(
            instance.agency_name.values_list("agency_name", flat=True)
        )
        representation["documents"] = CampaignDocumentSerializer(
            instance.documents.all(), many=True
        ).data
        return representation


from datetime import date


class BudgetCampaignSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()
    team_members = serializers.SerializerMethodField()
    agency_types_list = serializers.SerializerMethodField()
    roas = serializers.SerializerMethodField()
    team_members_list = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Campaign
        fields = (
            "id",
            "sourceid",
            "campaign_name",
            "agency_types_list",
            "budget",
            "spend",
            "duration",
            "team_members",
            "roas",
            "end_date",
            "team_members_list"
        )

    def get_duration(self, obj):
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        if obj.end_date:
            return (obj.end_date - obj.start_date).days
        else:
            if obj.start_date < current_date:
                return (current_date - obj.start_date).days
            return 0

    def get_team_members(self, obj):
        return len(obj.team_members)

    def get_roas(self, obj):
        source_model = Source.objects.filter(source_id=obj.sourceid)
        if source_model.exists():
            query_set = Lead.objects.filter(source_id=source_model.first().id)
            no_of_leads_marketing = query_set.count()
            no_of_leads_booked = query_set.filter(
                projectinventory__status="Booked"
            ).count()
            campaign_spend = obj.spend
            if (
                campaign_spend is not None
                and campaign_spend > 0
                and no_of_leads_booked > 0
            ):
                roas = no_of_leads_booked / campaign_spend
                return round(roas)
            return 0
        return 0

    def get_agency_types_list(self, obj):
        return [atype.name for atype in obj.agency_type.all()]
    
    def get_team_members_list(self, obj):
        team_list = []
        for user_id in obj.team_members:
            try:
                user = Users.objects.get(id=user_id)
                team_list.append(user.name)
            except Users.DoesNotExist:
                pass
        return team_list


class CampaignPerformanceSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()
    marketing_leads = serializers.SerializerMethodField()
    roas = serializers.SerializerMethodField()
    agency_types_list = serializers.SerializerMethodField()
    agency_names_list = serializers.SerializerMethodField()
    marketing_to_site_visit = serializers.SerializerMethodField()
    marketing_to_site_visit_percentage = serializers.SerializerMethodField()
    marketing_to_closure = serializers.SerializerMethodField()
    marketing_to_closure_percentage = serializers.SerializerMethodField()
    leads_to_walkin = serializers.SerializerMethodField()
    leads_to_walkin_percentage = serializers.SerializerMethodField()
    leads_to_closure = serializers.SerializerMethodField()
    leads_to_closure_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = (
            "id",
            "sourceid",
            "campaign_name",
            "budget",
            "agency_types_list",
            "agency_names_list",
            "duration",
            "marketing_leads",
            "roas",
            "marketing_to_site_visit",
            "marketing_to_site_visit_percentage",
            "marketing_to_closure",
            "marketing_to_closure_percentage",
            "leads_to_walkin",
            "leads_to_walkin_percentage",
            "leads_to_closure",
            "leads_to_closure_percentage",
        )

    def get_duration(self, obj):
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        if obj.end_date:
            return (obj.end_date - obj.start_date).days
        else:
            if obj.start_date < current_date:
                return (current_date - obj.start_date).days
            return 0

    # def get_cost_per_lead(self, obj):
    #     source_model = Source.objects.filter(source_id=obj.sourceid)
    #     if source_model.exists():
    #         no_of_leads = Lead.objects.filter(source_id=source_model.first().id).count()  # Find number of leads records
    #         print(no_of_leads, obj.spend)
    #         if no_of_leads > 0 and obj.spend > 0:
    #             cost_per_lead = obj.spend / no_of_leads
    #             return cost_per_lead
    #         return None
    #     return None

    def get_marketing_to_sales(self, obj):
        source_model = Source.objects.filter(source_id=obj.sourceid)
        if source_model.exists():
            query_set = Lead.objects.filter(source_id=source_model.first().id)
            no_of_leads_marketing = (
                query_set.count()
            )  # Find number of leads records from marketing
            stage = Stage.objects.filter(name="Sales").first()
            post_stage = Stage.objects.filter(name="PostSales").first()
            no_of_leads_post_sales = query_set.filter(
                workflow__current_stage=post_stage.order
            ).count()
            no_of_leads_sales = query_set.filter(
                workflow__current_stage=stage.order
            ).count()
            no_of_leads_sales = no_of_leads_post_sales + no_of_leads_sales
            return int(no_of_leads_sales)
        return 0

    def get_marketing_to_sales_percentage(self, obj):
        source_model = Source.objects.filter(source_id=obj.sourceid)
        if source_model.exists():
            query_set = Lead.objects.filter(source_id=source_model.first().id)
            no_of_leads_marketing = (
                query_set.count()
            )  # Find number of leads records from marketing
            stage = Stage.objects.filter(name="Sales").first()
            post_stage = Stage.objects.filter(name="PostSales").first()
            no_of_leads_post_sales = query_set.filter(
                workflow__current_stage=post_stage.order
            ).count()
            no_of_leads_sales = query_set.filter(
                workflow__current_stage=stage.order
            ).count()
            no_of_leads_sales = no_of_leads_post_sales + no_of_leads_sales
            if no_of_leads_marketing > 0:
                marketing_to_sales_ratio = no_of_leads_sales / no_of_leads_marketing
                marketing_to_sales_percentage = marketing_to_sales_ratio * 100
                return int(marketing_to_sales_percentage)
            return 0
        return 0

    def get_marketing_to_closure(self, obj):
        source_model = Source.objects.filter(source_id=obj.sourceid)
        if source_model.exists():
            query_set = Lead.objects.filter(source_id=source_model.first().id)
            no_of_leads_marketing = (
                query_set.count()
            )  # Find number of leads records from marketing
            stage = Stage.objects.filter(name="PostSales").first()
            no_of_leads_post_sales = query_set.filter(
                workflow__current_stage=stage.order
            ).count()
            return int(no_of_leads_post_sales)
        return 0

    def get_marketing_to_closure_percentage(self, obj):
        source_model = Source.objects.filter(source_id=obj.sourceid)
        if source_model.exists():
            query_set = Lead.objects.filter(source_id=source_model.first().id)
            no_of_leads_marketing = (
                query_set.count()
            )  # Find number of leads records from marketing
            stage = Stage.objects.filter(name="PostSales").first()
            no_of_leads_post_sales = query_set.filter(
                workflow__current_stage=stage.order
            ).count()
            if no_of_leads_marketing > 0:
                marketing_to_post_sales = no_of_leads_post_sales / no_of_leads_marketing
                marketing_to_post_sales_percentage = marketing_to_post_sales * 100
                return int(marketing_to_post_sales_percentage)
            return 0
        return 0

    def get_converted_to_client(self, obj):
        # add key transfer logic when post sales is completed
        return 0

    def get_converted_to_client_percentage(self, obj):
        # add key transfer logic when post sales is completed
        return 0

    def get_marketing_leads(self, obj):
        source_model = Source.objects.filter(source_id=obj.sourceid)
        no_of_leads_marketing = 0
        if source_model.exists():
            query_set = Lead.objects.filter(source_id=source_model.first().id)
            no_of_leads_marketing = query_set.count()
        return no_of_leads_marketing

    def get_marketing_to_site_visit(self, obj):
        source_model = Source.objects.filter(source_id=obj.sourceid)
        marketing_to_sitevisit = 0
        if source_model.exists():
            query_set = Lead.objects.filter(source_id=source_model.first().id)
            marketing_to_sitevisit = (
                query_set.filter(sitevisit__isnull=False).distinct().count()
            )
        return marketing_to_sitevisit

    def get_marketing_to_site_visit_percentage(self, obj):
        source_model = Source.objects.filter(source_id=obj.sourceid)
        marketing_to_sitevisit = 0
        marketing_to_sitevisit_percentage = 0
        if source_model.exists():
            query_set = Lead.objects.filter(source_id=source_model.first().id)
            marketing_count = query_set.count()
            marketing_to_sitevisit = (
                query_set.filter(sitevisit__isnull=False).distinct().count()
            )
            if marketing_count > 0:
                marketing_to_sitevisit_percentage = (
                    marketing_to_sitevisit / marketing_count
                ) * 100
            else:
                marketing_to_sitevisit_percentage = 0
        return int(marketing_to_sitevisit_percentage)

    def get_leads_to_walkin(self, obj):
        query_set = Lead.objects.filter(sitevisit__isnull=False)
        agency_detail = [aname.id for aname in obj.agency_name.all()]
        all_source = Campaign.objects.filter(agency_name__in=agency_detail)
        all_source_ids = list(all_source.values_list("id", flat=True))
        leads_to_walkin = query_set.filter(source_id__in=all_source_ids).count()
        if leads_to_walkin > 0:
            print(leads_to_walkin)
            return int(leads_to_walkin)
        else:
            return 0

    def get_leads_to_walkin_percentage(self, obj):
        query_set = Lead.objects.filter(sitevisit__isnull=False)
        leads_to_walkin_percentage = 0
        all_leads_count = query_set.count()
        agency_detail = [aname.id for aname in obj.agency_name.all()]
        all_source = Campaign.objects.filter(agency_name__in=agency_detail)
        all_source_ids = list(all_source.values_list("id", flat=True))
        leads_to_walkin = query_set.filter(source_id__in=all_source_ids).count()
        if leads_to_walkin > 0:
            if all_leads_count > 0:
                leads_to_walkin_percentage = (leads_to_walkin / all_leads_count) * 100
                print(leads_to_walkin_percentage)
                return int(leads_to_walkin_percentage)
            else:
                return 0
        else:
            return 0

    def get_leads_to_closure(self, obj):
        query_set = Lead.objects.all()
        agency_detail = [aname.id for aname in obj.agency_name.all()]
        all_source = Campaign.objects.filter(agency_name__in=agency_detail)
        all_source_ids = list(all_source.values_list("id", flat=True))
        stage = Stage.objects.filter(name="PostSales").first()
        leads_to_closure = query_set.filter(
            workflow__current_stage=stage.order, source_id__in=all_source_ids
        ).count()
        if leads_to_closure > 0:
            print(leads_to_closure)
            return int(leads_to_closure)
        else:
            return 0

    def get_leads_to_closure_percentage(self, obj):
        leads_to_closure_percentage = 0
        query_set = Lead.objects.all()
        total_leads = query_set.count()
        agency_detail = [aname.id for aname in obj.agency_name.all()]
        all_source = Campaign.objects.filter(agency_name__in=agency_detail)
        all_source_ids = list(all_source.values_list("id", flat=True))
        stage = Stage.objects.filter(name="PostSales").first()
        leads_to_closure = query_set.filter(
            workflow__current_stage=stage.order, source_id__in=all_source_ids
        ).count()
        if total_leads > 0:
            leads_to_closure_percentage = (leads_to_closure / total_leads) * 100
            print(leads_to_closure_percentage)
            return int(leads_to_closure_percentage)
        else:
            return 0

    def get_roas(self, obj):
        source_model = Source.objects.filter(source_id=obj.sourceid)
        if source_model.exists():
            query_set = Lead.objects.filter(source_id=source_model.first().id)
            no_of_leads_marketing = query_set.count()
            no_of_leads_booked = query_set.filter(
                projectinventory__status="Booked"
            ).count()
            campaign_spend = obj.spend
            if (
                campaign_spend is not None
                and campaign_spend > 0
                and no_of_leads_booked > 0
            ):
                roas = no_of_leads_booked / campaign_spend
                return round(roas)
            return 0
        return 0

    def get_agency_types_list(self, obj):
        return [atype.name for atype in obj.agency_type.all()]

    def get_agency_names_list(self, obj):
        return [agency_name.agency_name for agency_name in obj.agency_name.all()]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["agency_types_list"] = list(
            instance.agency_type.values_list("name", flat=True)
        )
        representation["agency_names_list"] = list(
            instance.agency_name.values_list("agency_name", flat=True)
        )
        return representation


class CampaignBudgetSerializer(serializers.ModelSerializer):
    Campaign = serializers.CharField(source="campaign_name")

    class Meta:
        model = Campaign
        fields = (
            "id",
            "sourceid",
            "Campaign",
            "budget",
            "spend",
            "agency_type",
            "agency_name",
        )


class CampaignTeamsSerializer(serializers.ModelSerializer):
    teammembers = serializers.SerializerMethodField()
    Campaign = serializers.CharField(source="campaign_name")

    class Meta:
        model = Campaign
        fields = ("sourceid", "Campaign", "teammembers")

    def get_teammembers(self, obj):
        team_list = []
        for user_id in obj.team_members:
            try:
                user = Users.objects.get(id=user_id)
                team_list.append(user.name)
            except Users.DoesNotExist:
                pass
                # team_list.append(f"User with ID {user_id} not found")
        return team_list
        # return len(obj.team_members)


class CampaignReportSerializer(serializers.ModelSerializer):
    members_number = serializers.SerializerMethodField()
    units_sold = serializers.SerializerMethodField()

    # agency_type = serializers.ListField(
    #     child=serializers.ChoiceField(choices=Agency.AGENCY_TYPES)
    # )
    class Meta:
        model = Campaign
        fields = [
            "id",
            "sourceid",
            "campaign_name",
            "agency_type",
            "members_number",
            "spend",
            "units_sold",
        ]

    def get_members_number(self, obj):
        return f"{len(obj.team_members)}Member"

    def get_units_sold(self, obj):
        # source_model = Source.objects.filter(source_id=obj.sourceid)
        # if source_model.exists():
        #     query_set = Lead.objects.filter(source_id=source_model.first().id)
        #     no_of_leads_booked = query_set.filter(inventory__status="Booked").count()  # Number of leads converted to sales
        #     if no_of_leads_booked > 0:
        #         return no_of_leads_booked # Since one lead can buy only one unit
        #     return None
        return None


class CampaignReportbyIdSerializer(serializers.ModelSerializer):
    members_number = serializers.SerializerMethodField()
    members_name = serializers.SerializerMethodField()
    duration = serializers.SerializerMethodField()
    agency_names_list = serializers.SerializerMethodField(read_only=True)
    agency_types_list = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Campaign
        # fields = ['id','sourceid','created_at','campaign_name', 'agency_type', 'vendor', 'budget', 'spend', 'duration' ,'members_number', 'members_name','start_date','end_date']
        fields = "__all__"

    def get_agency_types_list(self, obj):
        return [agency_type.name for agency_type in obj.agency_type.all()]

    def get_agency_names_list(self, obj):
        return [agency_name.agency_name for agency_name in obj.agency_name.all()]

    def validate_agency_types(self, value):
        agency_type_list = [atype.strip() for atype in value.split(",")]
        if not all(
            AgencyType.objects.filter(name=atype).exists() for atype in agency_type_list
        ):
            raise serializers.ValidationError("One or more agency types are not valid.")
        return agency_type_list

    def validate_agency_names(self, value):
        agency_name_list = [atype.strip() for atype in value.split(",")]
        if not all(
            Agency.objects.filter(agency_name=atype).exists()
            for atype in agency_name_list
        ):
            raise serializers.ValidationError("One or more agency names are not valid.")
        return agency_name_list

    def get_duration(self, obj):
        current_date = datetime.now().date()
        if obj.end_date:
            return f"{obj.start_date.strftime('%d-%m-%Y')} - {obj.end_date.strftime('%d-%m-%Y')}"
        else:
            return f"{obj.start_date.strftime('%d-%m-%Y')} - Continuing"

    def get_members_number(self, obj):
        return len(obj.team_members)

    def get_agency_name(self, obj):
        return obj.agency_name if obj.agency_name else None

    def get_members_name(self, obj):
        team_list = []
        for user_id in obj.team_members:
            try:
                user = Users.objects.get(id=user_id)
                user_data = UserDataIdSerializer(user).data if user else None
                team_list.append(user_data)
            except Users.DoesNotExist:
                pass
                # team_list.append(f"User with ID {user_id} not found")
        return team_list

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["agency_types_list"] = list(
            instance.agency_type.values_list("name", flat=True)
        )
        representation["agency_names_list"] = list(
            instance.agency_name.values_list("agency_name", flat=True)
        )
        return representation


class CampaignPaymentSerializer(serializers.ModelSerializer):
    upcoming_payment = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    paid_on = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    # amount = serializers.CharField(source = 'payment.amount')
    # due_date = serializers.CharField(source = 'payment.due_date')
    # paid_on = serializers.CharField(source = 'payment.paid_on')
    # payment_status = serializers.CharField(source = 'payment.status')
    class Meta:
        model = Campaign
        fields = [
            "id",
            "sourceid",
            "campaign_name",
            "budget",
            "spend",
            "upcoming_payment",
            "amount",
            "due_date",
            "payment_status",
            "paid_on",
        ]

    def get_upcoming_payment(self, obj):
        return None

    def get_amount(self, obj):
        return None

    def get_due_date(self, obj):
        return None

    def get_paid_on(self, obj):
        return None

    def get_payment_status(self, obj):
        return None


class UserAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = ["id", "team_members"]


class FolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Folder
        fields = "__all__"


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = "__all__"

    def create(self, validated_data):

        file = validated_data.pop("file")

        document = Document.objects.create(**validated_data)

        document.file.save(file.name, file, save=True)

        return document


class CampaignCalenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = "__all__"


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = "__all__"
        extra_kwargs = {
            "name": {"required": True},
            "company_name": {"required": True},
            "brand_name": {"required": True},
            "gstin_number": {"required": True},
            "gst_certificate": {"required": True},
            "bank_name": {"required": True},
            "account_holder_name": {"required": True},
            "account_number": {"required": True},
            "ifsc_code": {"required": True},
        }


class HistorySerializer(serializers.ModelSerializer):
    history_date = serializers.DateTimeField()
    history_type = serializers.CharField()
    history_user_id = serializers.IntegerField()
    history_user = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    activity_type = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            "history_date",
            "history_type",
            "history_user",
            "message",
            "activity_type",
        ]

    def get_history_user(self, obj):
        user_id = obj.history_user_id
        user = Users.objects.filter(id=user_id).first()
        return user.name if user else None

    def get_message(self, obj):
        history_type = obj.history_type
        model_name = self.Meta.model.__name__ if self.Meta.model else "Model"

        if history_type == "+":
            return f"{model_name} Created"
        elif history_type == "~":
            return f"{model_name} Details Edited"
        elif history_type == "-":
            return f"{model_name} Deleted"
        return None

    def get_activity_type(self, obj):
        model_name = self.Meta.model.__name__ if self.Meta.model else None
        return model_name


class CampaignHistorySerializer(HistorySerializer):
    agency_types_list = serializers.SerializerMethodField(read_only=True)
    agency_names_list = serializers.SerializerMethodField(read_only=True)
    team_members_list = serializers.SerializerMethodField(read_only=True)

    class Meta(HistorySerializer.Meta):
        model = Campaign.history.model
        fields = HistorySerializer.Meta.fields + [
            "sourceid",
            "campaign_name",
            "agency_types_list",
            "agency_names_list",
            "budget",
            "spend",
            "end_date",
            "team_members_list",
        ]

    def get_agency_types_list(self, obj):
        campaign_instance = Campaign.objects.get(pk=obj.id)
        return [agency_type.name for agency_type in campaign_instance.agency_type.all()]

    def get_agency_names_list(self, obj):
        campaign_instance = Campaign.objects.get(pk=obj.id)
        return [aname.agency_name for aname in campaign_instance.agency_name.all()]

    def get_team_members_list(self, obj):
        campaign_instance = Campaign.objects.get(pk=obj.id)
        team_list = []
        for user_id in campaign_instance.team_members:
            try:
                user = Users.objects.get(id=user_id)
                team_list.append(user.name)
            except Users.DoesNotExist:
                pass
        return team_list

class CampaignSpecificBudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignSpecificBudget
        fields = ["id", "expense_head", "campaign", "amount", "paid_date"]
        extra_kwargs = {"expense_head": {"required": False}}


# class CampaignSpecificBudgetListSerializer(serializers.ListSerializer):
#     child = CampaignSpecificBudgetSerializer()

#     def create(self, validated_data):
#         budgets = [CampaignSpecificBudget(**item) for item in validated_data]
#         return CampaignSpecificBudget.objects.bulk_create(budgets)


class AgencyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgencyType
        fields = ["name"]


class AgencyCreateSerializer(serializers.ModelSerializer):
    agency_types = serializers.CharField(write_only=True)
    agency_types_list = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Agency
        fields = [
            "agency_number",
            "agency_name",
            "agency_types",
            "agency_types_list",
            "vendors_full_name",
            "brand_name",
            "address",
            "gstin_number",
            "pan_details",
            "aadhaar_details",
            "phone_number",
            "gst_certificate",
            "pan_card",
            "bank_name",
            "account_holder_name",
            "account_number",
            "ifsc_code",
        ]

    def get_agency_types_list(self, obj):
        return [atype.name for atype in obj.agency_type.all()]

    def validate_agency_types(self, value):
        agency_type_list = [atype.strip() for atype in value.split(",")]
        if not all(
            AgencyType.objects.filter(name=atype).exists() for atype in agency_type_list
        ):
            raise serializers.ValidationError("One or more agency types are not valid.")
        return agency_type_list

    def create(self, validated_data):
        agency_types = validated_data.pop("agency_types")
        agency = Agency.objects.create(**validated_data)
        agency_types_objs = AgencyType.objects.filter(name__in=agency_types)
        print(agency_types_objs)
        if agency_types_objs:
            agency.agency_type.set(agency_types_objs)
        return agency

    def update(self, instance, validated_data):
        agency_types = validated_data.pop("agency_types", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if agency_types:
            agency_types_objs = AgencyType.objects.filter(name__in=agency_types)
            instance.agency_type.set(agency_types_objs)
        instance.save()
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["agency_types_list"] = list(
            instance.agency_type.values_list("name", flat=True)
        )
        return representation


class AgencyListSerializer(serializers.ModelSerializer):
    agency_types_list = serializers.SerializerMethodField()

    class Meta:
        model = Agency
        fields = [
            "id",
            "agency_number",
            "agency_name",
            "agency_types_list",
            "vendors_full_name",
            "brand_name",
            "phone_number",
        ]

    def get_agency_types_list(self, obj):
        return [atype.name for atype in obj.agency_type.all()]


class AgencyDetailSerializer(serializers.ModelSerializer):
    agency_types_list = serializers.SerializerMethodField()

    class Meta:
        model = Agency
        fields = [
            "id",
            "agency_number",
            "agency_name",
            "agency_types_list",
            "vendors_full_name",
            "brand_name",
            "address",
            "gstin_number",
            "pan_details",
            "aadhaar_details",
            "phone_number",
            "gst_certificate",
            "pan_card",
            "bank_name",
            "account_holder_name",
            "account_number",
            "ifsc_code",
            "created_at"
        ]

    def get_agency_types_list(self, obj):
        return [atype.name for atype in obj.agency_type.all()]
    

class AgencyRemarkSerializer(serializers.ModelSerializer):
    agency_id = serializers.IntegerField(write_only=True, required=True)

    class Meta:
        model = AgencyRemark
        fields = ['id', 'remark', 'created_at', 'created_by', 'agency_id']

    def create(self, validated_data):
        agency_id = validated_data.pop('agency_id')
        agency = Agency.objects.get(id=agency_id)
        remark = AgencyRemark.objects.create(**validated_data)
        agency.remarks.add(remark)
        return remark    
