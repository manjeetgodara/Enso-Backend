import hashlib
from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from activity.models import SiteVisit
from comms.utils import send_push_notification
from auth.utils import ResponseHandler
from .models import *
from .serializers import *
from django.db.models import F
from auth.models import Users
from rest_framework.response import Response
from .pagination import CustomLimitOffsetPagination
from django.http import Http404
import os
from rest_framework.pagination import PageNumberPagination
from django.http import HttpResponse
from django.conf import settings
from reportlab.pdfgen import canvas
import os
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.db import transaction
from datetime import datetime
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from django.db.models import Q
import boto3
from lead.decorator import *
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from django.db.models import Count
from django.db.models import Sum
from django.conf import settings
from accounts.models import Payment
from django.core.files import File
import pandas as pd


class CustomPageNumberPagination(PageNumberPagination):
    page_size = 2
    page_size_query_param = "page_size"
    max_page_size = 5


class CampaignCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CampaignSerializer
    pagination_class = CustomLimitOffsetPagination

    def get_queryset(self):
        queryset = Campaign.objects.all()

        agency_type_param = self.request.GET.getlist("agency_type")
        if agency_type_param:
            queryset = queryset.filter(agency_type__name__in=agency_type_param)

        sort_order = self.request.query_params.get("sort_order", "asc")
        sort_field = self.request.query_params.get("sort_field", None)
        if sort_field in ["budget", "spend"]:
            if sort_order.lower() == "desc":
                sort_field = F(sort_field).desc()
            queryset = queryset.order_by(sort_field)
        else:
            queryset = queryset.order_by("-id")

        search_query = self.request.query_params.get("search", None)
        if search_query is not None:
            try:
                number_query = int(search_query)
                queryset = queryset.filter(sourceid__icontains=number_query).distinct()
                return queryset
            except ValueError:
                queryset = queryset.filter(campaign_name__icontains=search_query).distinct()
                agency_queryset = queryset.filter(
                    agency_type__name__icontains=search_query
                )
                queryset = queryset | agency_queryset
                return queryset
        return queryset

    def upload_document(self, instance, document_file):
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
        aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

        s3 = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_s3_region_name,
        )

        try:
            s3.upload_fileobj(
                document_file,
                aws_storage_bucket_name,
                f"marketing_documents/{instance.id}/{document_file.name}",
            )

            instance.document = (
                f"marketing_documents/{instance.id}/{document_file.name}"
            )
            instance.save()

        except Exception as e:
            return ResponseHandler(
                True,
                f"Error uploading document to S3: {e}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                campaign_data = serializer.save()
                print("campaign_data", campaign_data)

                document_files = request.FILES.getlist("new_documents")
                if document_files:
                    for document_file in document_files:
                        upload_response = self.upload_document(
                            campaign_data, document_file
                        )
                        if upload_response:
                            return upload_response

                title = "A New Campaign Created"
                body = (
                    f"A new campaign '{campaign_data.campaign_name}' has been created."
                )
                print(body)
                data = {
                    "notification_type": "marketing_campaign",
                    "redirect_url": f"/marketing/agencies_campaigns/campaign/{campaign_data.id}",
                }
                print(data)
                marketing_head_users = Users.objects.filter(
                    groups__name="MARKETING_HEAD"
                )
                print(marketing_head_users)
                for marketing_head_user in marketing_head_users:
                    marketing_head_fcm_token = marketing_head_user.fcm_token

                    print("marketing_head_fcm_token", marketing_head_fcm_token)
                    Notifications.objects.create(
                        notification_id=f"campaign-{campaign_data.id}-{marketing_head_user.id}",
                        user_id=marketing_head_user,
                        created=timezone.now(),
                        notification_message=body,
                        notification_url=f"/marketing/agencies_campaigns/campaign/{campaign_data.id}",
                    )

                    send_push_notification(marketing_head_fcm_token, title, body, data)

                return ResponseHandler(
                    False,
                    "Campaign created successfully.",
                    serializer.data,
                    status.HTTP_201_CREATED,
                )
            else:
                return ResponseHandler(
                    True, serializer.errors, None, status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error creating Campaign: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request, *args, **kwargs):
        paginated_class = CustomLimitOffsetPagination
        try:
            campaigns = self.get_queryset()
             # Apply budget filtering based on query parameters
            budget_min = request.query_params.get("budget_min")
            budget_max = request.query_params.get("budget_max")
            
            if budget_min is not None or budget_max is not None:
                budget_filter = Q()
                if budget_min is not None:
                    budget_filter &= Q(budget__gte=float(budget_min))
                if budget_max is not None:
                    budget_filter &= Q(budget__lte=float(budget_max))
                campaigns = campaigns.filter(budget_filter)

            if campaigns.exists():
                dashboard_type = request.query_params.get("dashboard_type", None)
                print(dashboard_type)
                if dashboard_type == "BudgetAndCampaigns":
                    serializer = BudgetCampaignSerializer(campaigns, many=True)
                elif dashboard_type == "Performance":
                    serializer = CampaignPerformanceSerializer(campaigns, many=True)
                    print(serializer)
                else:
                    return ResponseHandler(
                        True,
                        "Provide correct info in query params",
                        None,
                        status.HTTP_400_BAD_REQUEST,
                    )

                data = serializer.data
                print("data:", serializer.data)
                sort_field = self.request.query_params.get("sort_field", None)
                sort_order = self.request.query_params.get("sort_order", "asc")
                reverse_order = sort_order.lower() == "desc"
                duration_param = self.request.query_params.get("duration")

                filtered_data = []

                if duration_param:
                    for item in data:
                        if duration_param == "7_days" and item["duration"] <= 7:
                            filtered_data.append(item)
                        elif duration_param == "14_days" and item["duration"] <= 14:
                            filtered_data.append(item)
                        elif duration_param == "21_days" and item["duration"] <= 21:
                            filtered_data.append(item)
                        elif duration_param == "last_month" and item["duration"] <= 30:
                            filtered_data.append(item)    
                        elif (
                            duration_param == "greater_than_21_days"
                            and item["duration"] > 21
                        ):
                            filtered_data.append(item)
                        elif duration_param == "today" and item["duration"] == 0:
                            filtered_data.append(item)
                        elif duration_param == "custom":
                            min_duration = request.query_params.get("min_duration")
                            max_duration = request.query_params.get("max_duration")
                            if min_duration is not None and max_duration is not None:
                                min_duration = int(min_duration)
                                max_duration = int(max_duration)
                                if min_duration <= item["duration"] <= max_duration:
                                    filtered_data.append(item)
                        # elif duration_param == "custom":
                        #     from_date_str = request.query_params.get("from_date")
                        #     to_date_str = request.query_params.get("to_date")
                        #     if from_date_str and to_date_str:
                        #             # Parse the dates from query parameters
                        #             from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
                        #             to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
                                    
                        #             # Calculate the duration based on from_date and to_date
                        #             duration = (to_date - from_date).days
                        #             if item["duration"] == duration:
                        #                 filtered_data.append(item)            
                    data = filtered_data

                field_mapping = {
                    "duration": "duration",
                    "team_members": "team_members",
                    "roas": "roas",
                    "marketing_leads": "marketing_leads",
                    "marketing_to_site_visit": "marketing_to_site_visit",
                    "marketing_to_closure": "marketing_to_closure",
                    "leads_to_walkin": "leads_to_walkin",
                    "leads_to_closure": "leads_to_closure",
                }
                selected_sort_field = field_mapping.get(sort_field, None)
                if selected_sort_field is not None:
                    data = sorted(
                        data,
                        key=lambda x: x[selected_sort_field],
                        reverse=reverse_order,
                    )

                offset = int(request.query_params.get("offset", 0))
                limit = int(request.query_params.get("limit", 10))
                total_count = len(data)
                print("total_count :", total_count)
                paginated_data = data[offset : offset + limit]

                response_data = {
                    "count": total_count,
                    "next": paginated_class.get_next_link(
                        self, request, offset, limit, total_count
                    ),
                    "previous": paginated_class.get_previous_link(
                        self, request, offset, limit
                    ),
                    "results": paginated_data,
                }

                return ResponseHandler(
                    False,
                    "Campaigns retrieved successfully.",
                    response_data,
                    status.HTTP_200_OK,
                )
            else:
                dummy_data = {"count": 0, "next": None, "previous": None, "results": []}
                return ResponseHandler(
                    False, "No data is present", dummy_data, status.HTTP_200_OK
                )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error retrieving Campaigns: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CampaignSummaryAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    @check_access(
        required_groups=["ADMIN", "PROMOTER", "VICE_PRESIDENT", "MARKETING_HEAD"]
    )
    def get(self, request, *args, **kwargs):
        try:
            module_param = self.request.GET.get("module", None)
            campaign_param = self.request.GET.get("campaign_id", None)
            campaign_data = None  # Initialize here

            if module_param == "dashboard":
                current_campaigns = Campaign.objects.all().count()
                budget = (
                    Campaign.objects.all().aggregate(Sum("budget"))["budget__sum"] or 0
                )
                payments = (
                    Campaign.objects.all().aggregate(Sum("spend"))["spend__sum"] or 0
                )

                campaign_data = {
                    "current_campaigns": current_campaigns,
                    "budget": budget,
                    "payments": payments,
                    "sales_achievements": None,  # Placeholder
                }
            elif module_param == "overview":
                total_lead_count = 0
                total_leads_booked = 0
                site_visit_done = 0
                total_campaigns = Campaign.objects.all().count()

                campaigns = Campaign.objects.all()
                for campaign in campaigns:
                    source_model = Source.objects.filter(source_id=campaign.sourceid)

                    if source_model.exists():
                        source_id = source_model.first().id
                        query_set = Lead.objects.filter(source_id=source_id)
                        print("leads source wise",query_set)
                        leads_count = query_set.count()
                        print("lead count",leads_count)
                        no_of_leads_booked = query_set.filter(
                            projectinventory__status="Booked"
                        ).count()
                        total_lead_count += leads_count
                        total_leads_booked += no_of_leads_booked

                        #site_visit_done = SiteVisit.objects.filter(lead__in=query_set , site_visit_status = "Site Visit Done").count()
                        site_visits = SiteVisit.objects.filter(lead__in=query_set , site_visit_status = "Site Visit Done")
                        for site_visit in site_visits:
                            print("site_visit_id",site_visit.id,"site_visit",site_visit.lead,"site_visit_lead_source",site_visit.lead.source)
                        print("lead", site_visits )
                        count=site_visits.count()
                        site_visit_done += count
                        print("site_visit_done_count",count)

                total_budget = Campaign.objects.aggregate(total_budget=Sum("budget"))[
                    "total_budget"
                ]
                total_spend = Campaign.objects.aggregate(total_spend=Sum("spend"))[
                    "total_spend"
                ]
                # roas = f"{total_leads_booked} / {total_spend}"
                roas = total_leads_booked / total_spend if total_spend else 0
                current_date = date.today()
                upcoming_payments = Payment.objects.filter(due_date__gt=current_date,payment_to="Marketing",status="Approval Pending")
                print("upcoming_payment",upcoming_payments)
                upcoming_payments_count = upcoming_payments.aggregate(
                    total_amount=Sum("amount")
                )["total_amount"]
                print("payment_sum",upcoming_payments_count)
                if upcoming_payments_count is None:
                    upcoming_payments_count = 0
                total_booking_and_leads_count = total_leads_booked + total_lead_count
                campaign_data = {
                    "total_compaigns": total_campaigns,
                    "total_leads": total_lead_count,
                    "total_booking_and_leads_count": total_booking_and_leads_count,
                    "upcoming_payments": upcoming_payments_count,
                    "total_budget": total_budget,
                    "total_leads_booked": total_leads_booked,
                    "total_spend": total_spend,
                    "roas_spend": roas,
                    "no_of_leads": total_lead_count,
                    "site_visit_done" : site_visit_done,
                    "no_of_leads_percentage": (
                        round(total_lead_count / total_booking_and_leads_count * 100, 2)
                        if total_booking_and_leads_count > 0
                        else 0
                    ),
                    "no_of_bookings": total_leads_booked,
                    "no_of_bookings_percentage": (
                        round(
                            total_leads_booked / total_booking_and_leads_count * 100, 2
                        )
                        if total_booking_and_leads_count > 0
                        else 0
                    ),
                }
            elif module_param == "live_campaigns" and campaign_param:
                no_of_leads_booked = 0
                site_visit_done = 0
                leads_count = 0
                campaign = Campaign.objects.get(id=campaign_param)

                source_model = Source.objects.filter(source_id=campaign.sourceid)

                if source_model.exists():
                    source_id = source_model.first().id
                    query_set = Lead.objects.filter(source_id=source_id)
                    leads_count = query_set.count()
                    no_of_leads_booked = query_set.filter(
                        projectinventory__status="Booked"
                    ).count()

                    site_visit_done = SiteVisit.objects.filter(lead__in=query_set , site_visit_status = "Site Visit Done")
                    for site_visit in site_visit_done:
                        print("site_visit_id",site_visit.id,"site_visit",site_visit.lead,"site_visit_lead_source",site_visit.lead.source)
                    print("lead", site_visit_done )
                    site_visit_done=site_visit_done.count()
                    print("site_visit_done_count",site_visit_done)



                total_budget = campaign.budget
                total_spend = campaign.spend
                roas = no_of_leads_booked / total_spend if total_spend else 0
                current_date = date.today()
                upcoming_payments = Payment.objects.filter(due_date__gt=current_date , campaign = campaign,payment_to="Marketing",status="Approval Pending")
                print("upcoming_payment",upcoming_payments)
                upcoming_payments_count = upcoming_payments.aggregate(
                    total_amount=Sum("amount")
                )["total_amount"]
                print("payment_sum",upcoming_payments_count)
                if upcoming_payments_count is None:
                    upcoming_payments_count = 0

                total_booking_and_leads_count = no_of_leads_booked + leads_count
                campaign_data = {
                    "total_leads": leads_count,
                    "upcoming_payments": upcoming_payments_count,
                    "total_budget": total_budget,
                    "total_leads_booked": no_of_leads_booked,
                    "total_spend": total_spend,
                    "roas_spend": roas,
                    "site_visit_done" : site_visit_done,
                    "no_of_leads": leads_count,
                    "no_of_leads_percentage": (
                        round(leads_count / total_booking_and_leads_count * 100, 2)
                        if total_booking_and_leads_count > 0
                        else 0
                    ),
                    "no_of_bookings": no_of_leads_booked,
                    "no_of_bookings_percentage": (
                        round(
                            no_of_leads_booked / total_booking_and_leads_count * 100, 2
                        )
                        if total_booking_and_leads_count > 0
                        else 0
                    ),
                }
            else:
                agency_types = [
                    "Creative",
                    "Digital",
                    "Production",
                    "PR",
                    "Printing",
                    "Event",
                    "Other",
                ]
                campaign_data = []

                for agency_type in agency_types:
                    campaigns = Campaign.objects.filter(agency_type=agency_type)
                    overall_agency_count = 0

                    for campaign in campaigns:
                        source_model = Source.objects.filter(
                            source_id=campaign.sourceid
                        ).first()
                        if source_model:
                            leads = Lead.objects.filter(source_id=source_model.id)
                            no_of_leads_marketing = leads.count()
                            overall_agency_count += no_of_leads_marketing

                    agency_data = {
                        "agency_type": agency_type,
                        "campaign_count": overall_agency_count,
                    }

                    campaign_data.append(agency_data)

            return ResponseHandler(
                False,
                "Campaign summary retrieved successfully.",
                campaign_data,
                status.HTTP_200_OK,
            )

        except Exception as e:
            return ResponseHandler(
                True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignBreakdownSummaryAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    @staticmethod
    def generate_color(name):
        # Generate a hash of the name
        hash_object = hashlib.md5(name.encode())
        hex_dig = hash_object.hexdigest()
        # Use the first 6 characters of the hash as the color code
        color = f"{hex_dig[:6].upper()}"
        return color

    @check_access(
        required_groups=["ADMIN", "PROMOTER", "VICE_PRESIDENT", "MARKETING_HEAD"]
    )
    def get(self, request, *args, **kwargs):
        try:
            module_param = self.request.GET.get("module", None)
            campaign_param = self.request.GET.get("campaign_id", None)

            if module_param == "direct" and campaign_param is None:

                source_leads = {}
                payments = Payment.objects.filter(payment_type="Direct")
                total_budget = payments.aggregate(total_budget=Sum("amount"))[
                    "total_budget"
                ]
                print("Total budget:", total_budget)
                campaigns = Campaign.objects.all()
                for campaign in campaigns:
                    total_payment = 0
                    source_model = Source.objects.filter(source_id=campaign.sourceid)
                    print("Source model:", source_model, "Campaign:", campaign)
                    if source_model.exists():
                        source_name = source_model.first().name
                        campaign_payments = payments.filter(campaign=campaign)
                        print("Campaign payments:", campaign_payments)
                        for payment in campaign_payments:
                            total_payment += payment.amount
                        source_leads[source_name] = total_payment

                source_percentages = []
                if total_budget is not None:
                    for source_name, total_payment in source_leads.items():
                        percentage = (
                            (total_payment / total_budget) * 100
                            if total_budget > 0
                            else 0
                        )
                        source_percentages.append(
                            {
                                "compaign_name": source_name,
                                "spent_amount": total_payment,
                                "percentage": percentage,
                                "color": self.generate_color(source_name),
                            }
                        )
                result_list = {
                    "total_budget_spend": total_budget,
                    "source_breakdown": source_percentages,
                }
            elif module_param == "direct" and campaign_param:
                print("HERE")
                source_leads = {}
                source_percentages = []
                payments = Payment.objects.filter(
                    payment_type="Direct", campaign=campaign_param
                )

                total_budget = payments.aggregate(total_budget=Sum("amount"))[
                    "total_budget"
                ]
                if total_budget is None:
                    total_budget = 0

                for payment in payments:
                    expense_head = payment.campaign.campaign_name
                    print(expense_head)
                    amount = payment.amount
                    if expense_head not in source_leads:
                        source_leads[expense_head] = 0
                    source_leads[expense_head] += amount

                for expense_head, amount in source_leads.items():
                    percentage = (
                        (amount / total_budget) * 100 if total_budget != 0 else 0
                    )
                    source_percentages.append(
                        {
                            "compaign_name": expense_head,
                            "amount": amount,
                            "percentage": percentage,
                            "color": self.generate_color(expense_head),
                        }
                    )

                result_list = {"source_breakdown": source_percentages}

            else:

                # total_lead_count = 0
                # total_leads_booked = 0
                # source_leads = {}
                # source_booked_leads = {}
                # sources = Source.objects.all()
                # for source in sources:
                #     source_name = source.name
                #     leads_count = Lead.objects.filter(source_id=source.id).count()
                #     booked_leads_count = Lead.objects.filter(source_id=source.id, projectinventory__status="Booked").count()
                #     total_lead_count += leads_count
                #     total_leads_booked += booked_leads_count
                #     source_leads[source_name] = leads_count
                #     source_booked_leads[source_name] = booked_leads_count

                # source_percentages = {}
                # source_booked_percentages = {}
                # for source_name, leads_count in source_leads.items():
                #     booked_leads_count = source_booked_leads[source_name]
                #     percentage = (leads_count / total_lead_count) * 100 if total_lead_count != 0 else 0
                #     booked_leads_percentage = (booked_leads_count / total_leads_booked) * 100 if leads_count != 0 else 0
                #     source_percentages[source_name] = {'leads_count': leads_count, 'percentage': percentage}
                #     source_booked_percentages[source_name] = {'booked_leads_count': booked_leads_count, 'booked_leads_percentage': booked_leads_percentage}

                # lead_source_breakdown= {'lead_source_breakdown': source_percentages}
                # booking_source_breakdown= {'booking_source_breakdown': source_booked_percentages}
                # result_list = [lead_source_breakdown, booking_source_breakdown]

                total_lead_count = 0
                total_leads_booked = 0
                source_leads = {}
                source_booked_leads = {}
                sources = Source.objects.all()

                # Calculate leads and booked leads counts for each source
                for source in sources:
                    source_name = source.name
                    leads_count = Lead.objects.filter(source_id=source.id).count()
                    booked_leads_count = Lead.objects.filter(
                        source_id=source.id, projectinventory__status="Booked"
                    ).count()
                    total_lead_count += leads_count
                    total_leads_booked += booked_leads_count
                    source_leads[source_name] = leads_count
                    source_booked_leads[source_name] = booked_leads_count

                # Calculate percentages and create the response format
                lead_source_breakdown = []
                booking_source_breakdown = []

                for source_name, leads_count in source_leads.items():
                    booked_leads_count = source_booked_leads[source_name]
                    percentage = (
                        (leads_count / total_lead_count) * 100
                        if total_lead_count != 0
                        else 0
                    )
                    booked_leads_percentage = (
                        (booked_leads_count / total_leads_booked) * 100
                        if leads_count != 0
                        else 0
                    )
                    color = self.generate_color(source_name)
                    lead_source_breakdown.append(
                        {
                            "compaign_name": source_name,
                            "leads_count": leads_count,
                            "percentage": percentage,
                            "color": color,
                            "total_leads_count": total_lead_count,
                        }
                    )
                    booking_source_breakdown.append(
                        {
                            "compaign_name": source_name,
                            "leads_count": booked_leads_count,
                            "percentage": booked_leads_percentage,
                            "color": color,
                            "total_leads_booked": total_leads_booked,
                        }
                    )

                result_list = {
                    "lead_source_breakdown": lead_source_breakdown,
                    "booking_source_breakdown": booking_source_breakdown,
                }

            return ResponseHandler(
                False,
                "Campaign summary retrieved successfully.",
                result_list,
                status.HTTP_200_OK,
            )
        except Exception as e:
            return ResponseHandler(
                True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CampaignDetailApiView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CampaignSerializer
    permission_classes = (IsAuthenticated,)

    queryset = Campaign.objects.all()

    def get(self, request, *args, **kwargs):
        Campaign_id = self.kwargs.get("pk")
        try:
            instance = Campaign.objects.get(pk=Campaign_id)
            dashboard_type = request.query_params.get("dashboard_type", None)
            if dashboard_type == "BudgetAndCampaigns":
                serializer = CampaignReportbyIdSerializer(instance)
            else:
                serializer = self.get_serializer(instance)
                print(serializer)

            if request.query_params.get("export") == "pdf":
                pdf_response = self.generate_pdf(serializer.data, instance)
                return pdf_response

            return ResponseHandler(
                False,
                "Campaign retrieved successfully",
                serializer.data,
                status.HTTP_200_OK,
            )
        except Campaign.DoesNotExist:
            return ResponseHandler(
                True, "Campaign not found", None, status.HTTP_404_NOT_FOUND
            )
        
    def upload_document(self, instance, document_file):
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
        aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

        s3 = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_s3_region_name,
        )

        print(instance.id, document_file.name)
        try:
            s3.upload_fileobj(
                document_file,
                aws_storage_bucket_name,
                f"marketing_documents/{instance.id}/{document_file.name}",
            )
            print("here")

            instance.document = (
                f"marketing_documents/{instance.id}/{document_file.name}"
            )
            instance.save()

            return instance.document

        except Exception as e:
            return None   

    def generate_pdf(self, campaign_data, instance):
        try:
            # Create a PDF document using reportlab
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            pdf_filename = f"campaign_report_{timestamp}.pdf"
            pdf_file_path = os.path.join(settings.MEDIA_ROOT, pdf_filename)
            # excel_file_path = os.path.join(settings.MEDIA_ROOT, f'leadsexported_{timestamp}.xlsx')
            # Create a canvas and draw the content
            p = canvas.Canvas(pdf_file_path)
            print(campaign_data)
            p.drawString(100, 800, f"Campaign Name: {campaign_data['campaign_name']}")
            p.drawString(100, 780, f"Agency Type: {', '.join(campaign_data['agency_types_list'])}")
            p.drawString(100, 760, f"Agency_Name: {', '.join(campaign_data['agency_names_list'])}")
            p.drawString(100, 740, f"Budget: {campaign_data['budget']}")
            p.drawString(100, 720, f"Spend: {campaign_data['spend']}")
            p.drawString(100, 700, f"duration: {campaign_data['duration']}")
            p.drawString(100, 680, f"members_number: {len(campaign_data['team_members_list'])}")
            p.drawString(100, 660, f"members_name: {', '.join(campaign_data['team_members_list'])}")
            p.showPage()
            p.save()
            if os.path.exists(pdf_file_path):
                with open(pdf_file_path, "rb") as pdf_file:
                    response = self.upload_document(instance, pdf_file)
                    print(f"response:{response}")
                    if response:
                        file_url = f"https://{os.getenv('AWS_STORAGE_BUCKET_NAME')}.{os.getenv('STORAGE_DESTINATION')}.amazonaws.com/{response}"
                        os.remove(pdf_file_path)
                        return ResponseHandler(
                            False,
                            "PDF generated successfully.",
                            {"file_url": file_url},
                            status.HTTP_200_OK,
                        )
                    else:
                        return ResponseHandler(
                            True,
                            "Error exporting to PDF",
                            None,
                            status.HTTP_500_INTERNAL_SERVER_ERROR,
                        )
            else:
                return ResponseHandler(
                    True,
                    "Error exporting to PDF",
                    None,
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            # return pdf_file_path
            # return response

        except Exception as e:
            return ResponseHandler(
                True,
                "Unexpected Error: ",
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, *args, **kwargs):
        Campaign_id = self.kwargs.get("pk")
        update_type = request.query_params.get("update_type", None)

        try:
            instance = self.queryset.get(pk=Campaign_id)
        except Campaign.DoesNotExist:
            return ResponseHandler(
                True, "Campaign not found", None, status.HTTP_404_NOT_FOUND
            )

        if update_type == "end_campaign":
            end_date = request.data.get("end_date")
            if end_date:
                try:
                    instance.end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
                    instance.save()

                    if instance.end_date >= timezone.now().date():
                        # Send push notification to Marketing Head
                        title = "Campaign Ended"
                        body = f"The campaign '{instance.campaign_name}' has ended."
                        data = {
                            "notification_type": "campaign_ended",
                            "redirect_url": f"/marketing/agencies_campaigns/campaign/{instance.id}",
                        }

                        # Fetch the Marketing Head's FCM token
                        marketing_head_users = Users.objects.filter(
                            groups__name="MARKETING_HEAD"
                        )
                        for marketing_head_user in marketing_head_users:
                            marketing_head_fcm_token = marketing_head_user.fcm_token
                            Notifications.objects.create(
                                notification_id=f"campaign-{instance.id}-{marketing_head_user.id}",
                                user_id=marketing_head_user,
                                created=timezone.now(),
                                notification_message=body,
                                notification_url=f"/marketing/agencies_campaigns/campaign/{instance.id}",
                            )
                            send_push_notification(
                                marketing_head_fcm_token, title, body, data
                            )

                    return ResponseHandler(
                        False, "Campaign ended successfully", None, status.HTTP_200_OK
                    )
                except ValueError:
                    return ResponseHandler(
                        True, "Invalid date format", None, status.HTTP_400_BAD_REQUEST
                    )
            else:
                return ResponseHandler(
                    True,
                    "End date is required for ending the campaign",
                    None,
                    status.HTTP_400_BAD_REQUEST,
                )
        else:
            serializer = self.get_serializer(instance, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return ResponseHandler(
                    False,
                    "Data updated successfully",
                    serializer.data,
                    status.HTTP_200_OK,
                )
            else:
                return ResponseHandler(
                    True, serializer.errors, None, status.HTTP_400_BAD_REQUEST
                )

    @check_access(
        required_groups=["ADMIN", "MARKETING_HEAD", "VICE_PRESIDENT", "PROMOTER"]
    )
    def delete(self, request, *args, **kwargs):
        Campaign_id = self.kwargs.get("pk")
        try:
            instance = Campaign.objects.get(pk=Campaign_id)
            instance_id = instance.id
            campaign_name = (
                instance.campaign_name
            )  # Retrieve campaign name for notification message

            self.perform_destroy(instance)

            # Send push notification to Marketing Head
            title = "Campaign Deleted"
            body = f"The campaign '{campaign_name}' has been deleted."
            data = {"notification_type": "marketing_campaign", "redirect_url": None}

            # Fetch the Marketing Head's FCM token
            marketing_head_users = Users.objects.filter(groups__name="MARKETING_HEAD")
            # marketing_head_user = Users.objects.get(id=get_marketing_head_user.id)
            for marketing_head_user in marketing_head_users:

                marketing_head_fcm_token = marketing_head_user.fcm_token

                print("marketing_head_fcm_token", marketing_head_fcm_token)
                Notifications.objects.create(
                    notification_id=f"campaign-{instance_id}-{marketing_head_user.id}",
                    user_id=marketing_head_user,
                    created=timezone.now(),
                    notification_message=body,
                    notification_url=None,
                )

                send_push_notification(marketing_head_fcm_token, title, body, data)

            return ResponseHandler(
                False, "Campaign deleted successfully", None, status.HTTP_204_NO_CONTENT
            )
        except Campaign.DoesNotExist:
            return ResponseHandler(
                True,
                "No matching data present in models",
                None,
                status.HTTP_404_NOT_FOUND,
            )


class CampaignSearchView(generics.ListAPIView):
    serializer_class = CampaignSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):

        search_query = self.request.query_params.get("search", "")
        search_scope = self.request.GET.get("scope", "all")

        queryset = Campaign.objects.none()
        try:

            number_query = int(search_query)

            queryset = Campaign.objects.filter(sourceid__icontains=number_query)
            # if search_scope in ["source", "all"]:
            #     source_queryset = Lead.objects.filter(source=number_query)
            #     queryset = queryset | source_queryset

            return queryset

        except ValueError:

            if search_scope in ["campaign", "all"]:
                queryset = Campaign.objects.filter(
                    campaign_name__icontains=search_query
                )

            if search_scope in ["agency", "all"]:
                agency_queryset = Campaign.objects.filter(
                    agency_type__icontains=search_query
                )
                queryset = queryset | agency_queryset

        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())

            if not queryset.exists():
                return ResponseHandler(
                    True, "No matching results", None, status.HTTP_404_NOT_FOUND
                )

            serializer = CampaignSerializer(queryset, many=True)
            return ResponseHandler(
                False, "Results", serializer.data, status.HTTP_200_OK
            )
        except Exception as e:
            return ResponseHandler(
                True,
                "Unexpected Error: ",
                str(e),
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserAllocationView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserAllocationSerializer

    def create(self, request, *args, **kwargs):
        try:
            source_id_param = request.data.get("source_id")
            team_members = request.data.get("team_members", [])

            campaign = Campaign.objects.get(sourceid=source_id_param)

            valid_team_members = []
            for user_id in team_members:
                try:
                    user = Users.objects.get(id=user_id)
                    valid_team_members.append(user.id)
                except Users.DoesNotExist:
                    return Response(
                        {
                            "error": True,
                            "message": f"User with ID {user_id} not found.",
                        },
                        status=400,
                    )

            unique_team_members = set(campaign.team_members + valid_team_members)
            campaign.team_members = list(unique_team_members)
            campaign.save()

            return ResponseHandler(
                False,
                "Users allocated to the campaign successfully.",
                None,
                status.HTTP_201_CREATED,
            )

        except Campaign.DoesNotExist:
            return ResponseHandler(
                True,
                f"Campaign with source id {source_id_param} not found.",
                None,
                status.HTTP_404_NOT_FOUND,
            )

        except Exception as e:
            return ResponseHandler(
                True,
                f"Error allocating users to the campaign: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FolderCreateView(generics.ListCreateAPIView):
    queryset = Folder.objects.all()
    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Folder.objects.all()
        return queryset.order_by("-id")

    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                # serializer.save(created_by=request.user)
                return ResponseHandler(
                    False, "Folder Created", serializer.data, status.HTTP_201_CREATED
                )
            else:
                return ResponseHandler(
                    True, serializer.errors, None, status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error creating Campaign: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request, *args, **kwargs):
        try:
            folders = self.get_queryset()
            if folders.exists():
                serializer = FolderSerializer(folders, many=True)
                return ResponseHandler(
                    False,
                    "Folders retrieved successfully.",
                    serializer.data,
                    status.HTTP_200_OK,
                )
            else:
                return ResponseHandler(
                    True, "No data is present", None, status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error retrieving Folders: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class FolderDetailApiView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FolderSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Folder.objects.all()

    def get(self, request, *args, **kwargs):
        Folder_id = self.kwargs.get("pk")
        try:
            instance = Folder.objects.get(pk=Folder_id)
            serializer = self.get_serializer(instance)
            return ResponseHandler(
                False,
                "Folder retrieved successfully",
                serializer.data,
                status.HTTP_200_OK,
            )
        except Folder.DoesNotExist:
            return ResponseHandler(
                True, "Folder not found", None, status.HTTP_404_NOT_FOUND
            )

    def put(self, request, *args, **kwargs):
        Folder_id = self.kwargs.get("pk")
        try:
            instance = self.queryset.get(pk=Folder_id)
        except Folder.DoesNotExist:
            return ResponseHandler(
                True, "Folder not found", None, status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(
                False, "Data updated successfully", serializer.data, status.HTTP_200_OK
            )
        else:
            return ResponseHandler(
                True, serializer.errors, None, status.HTTP_400_BAD_REQUEST
            )

    @check_access(
        required_groups=["ADMIN", "MARKETING_HEAD", "VICE_PRESIDENT", "PROMOTER"]
    )
    def delete(self, request, *args, **kwargs):
        folder_id = self.kwargs.get("pk")

        try:

            folder_instance = Folder.objects.get(pk=folder_id)

            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
            aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

            s3 = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_s3_region_name,
            )

            folder_prefix = f"uploads/{folder_id}/"

            objects_to_delete = s3.list_objects(
                Bucket=aws_storage_bucket_name, Prefix=folder_prefix
            ).get("Contents", [])

            for obj in objects_to_delete:
                s3.delete_object(Bucket=aws_storage_bucket_name, Key=obj["Key"])

            self.perform_destroy(folder_instance)

            return ResponseHandler(
                False,
                "Folder and associated documents deleted successfully",
                None,
                status.HTTP_204_NO_CONTENT,
            )
        except Folder.DoesNotExist:
            return ResponseHandler(
                True,
                "No matching data present in models",
                None,
                status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"An error occurred: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentDetailApiView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DocumentSerializer
    permission_classes = (IsAuthenticated,)
    queryset = Document.objects.all()

    def get(self, request, *args, **kwargs):
        document_id = self.kwargs.get("pk")
        try:
            instance = Document.objects.get(pk=document_id)
            serializer = self.get_serializer(instance)
            return ResponseHandler(
                False,
                "Document retrieved successfully",
                serializer.data,
                status.HTTP_200_OK,
            )
        except Document.DoesNotExist:
            return ResponseHandler(
                True, "Document not found", None, status.HTTP_404_NOT_FOUND
            )

    def put(self, request, *args, **kwargs):

        document_id = self.kwargs.get("pk")
        print("DOCID", document_id)
        try:
            instance = self.queryset.get(pk=document_id)
            print(instance)
        except Document.DoesNotExist:
            return ResponseHandler(
                True, "Document not found", None, status.HTTP_404_NOT_FOUND
            )

        serializer = self.get_serializer(instance, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(
                False, "Data updated successfully", serializer.data, status.HTTP_200_OK
            )
        else:
            return ResponseHandler(
                True, serializer.errors, None, status.HTTP_400_BAD_REQUEST
            )

    @check_access(
        required_groups=["ADMIN", "MARKETING_HEAD", "VICE_PRESIDENT", "PROMOTER"]
    )
    def delete(self, request, *args, **kwargs):
        doc_id = self.kwargs.get("pk")
        try:
            document = Document.objects.get(id=doc_id)

            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
            aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

            s3 = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_s3_region_name,
            )

            file_key = str(document.file)

            s3.delete_object(Bucket=aws_storage_bucket_name, Key=file_key)

            document.delete()

            return ResponseHandler(
                False,
                "Document deleted successfully.",
                None,
                status.HTTP_204_NO_CONTENT,
            )
        except Document.DoesNotExist:
            return ResponseHandler(
                True, "Document not found.", None, status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"An error occurred: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DocumentCreateView(generics.ListCreateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        try:
            document_data_list = []
            files_uploaded = request.FILES.getlist("file")
            folder_id = request.data.get("folder")

            for single_file in files_uploaded:
                content_type = single_file.content_type
                data = {
                    "file": single_file,
                    "content_type": content_type,
                    "folder": folder_id,
                }
                document_data_list.append(data)

            serializer = self.get_serializer(data=document_data_list, many=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return ResponseHandler(
                    True, serializer.errors, None, status.HTTP_400_BAD_REQUEST
                )

            return ResponseHandler(
                False, "Documents Created", serializer.data, status.HTTP_201_CREATED
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error creating Documents: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request, *args, **kwargs):
        try:
            documents = self.get_queryset()
            if documents.exists():
                serializer = self.get_serializer(documents, many=True)
                return ResponseHandler(
                    False,
                    "Docs retrieved successfully.",
                    serializer.data,
                    status.HTTP_200_OK,
                )
            else:
                return ResponseHandler(
                    True, "No data is present", None, status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error retrieving Folders: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get_queryset(self):
        return Document.objects.all()
        # return Document.objects.filter(folder__created_by=self.request.user)


class GetAllDocsView(generics.ListAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Document.objects.all()
        return queryset

    def get(self, request, *args, **kwargs):
        folder_id = self.kwargs.get("pk")
        try:
            instance = Document.objects.filter(folder=folder_id)

            # instance = instance.order_by(sort_field)
            serializer = self.get_serializer(instance, many=True)
            return ResponseHandler(
                False,
                "All Docs retrieved successfully",
                serializer.data,
                status.HTTP_200_OK,
            )
        except Folder.DoesNotExist:
            return ResponseHandler(
                True, "Folder not found", None, status.HTTP_404_NOT_FOUND
            )


class DocumentRenameView(generics.UpdateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer

    def update(self, request, *args, **kwargs):
        doc_id = self.kwargs.get("pk")
        try:
            new_doc_name = request.data.get("new_doc_name", "")
            document = Document.objects.get(id=doc_id)

            if not new_doc_name:
                return ResponseHandler(
                    True,
                    "New document name is required.",
                    None,
                    status.HTTP_400_BAD_REQUEST,
                )

            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
            aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

            s3 = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_s3_region_name,
            )

            current_file_key = str(document.file)
            print("current_file_key: ", current_file_key)
            new_file_key = f"{os.path.dirname(current_file_key)}/{new_doc_name}"
            print("new_file_key: ", new_file_key)
            s3.copy_object(
                Bucket=aws_storage_bucket_name,
                CopySource=f"{aws_storage_bucket_name}/{current_file_key}",
                Key=new_file_key,
            )
            s3.delete_object(Bucket=aws_storage_bucket_name, Key=current_file_key)

            document.file.name = new_file_key
            document.save()

            return ResponseHandler(
                False, "Document renamed successfully.", None, status.HTTP_200_OK
            )
        except Document.DoesNotExist:
            return ResponseHandler(
                True, "Document not found.", None, status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"An error occurred: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GanttViewList(generics.ListAPIView):
    serializer_class = CampaignCalenderSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        try:

            month_name = self.request.query_params.get("month_name")
            frequency = self.request.query_params.get("frequency", "monthly")

            if month_name is not None:
                if frequency == "monthly":
                    return self.filter_monthly(month_name)
                elif frequency == "weekly":
                    return self.filter_weekly()
            print("ERROR4")
            raise ValueError("Please provide valid parameters.")

        except ValueError as e:
            return ResponseHandler(True, str(e), None, 400)

    def filter_monthly(self, month_name):
        try:
            datetime_object = datetime.strptime(month_name, "%B")
            month_number = datetime_object.month

            # Campaigns with start_date in the given month
            start_date_filter = Q(start_date__month=month_number)

            # Campaigns with no end_date (continuing campaigns)
            no_end_date_filter = Q(end_date__isnull=True)

            # Campaigns with end_date in the specified month
            end_date_filter = Q(end_date__month=month_number)

            combined_filter = start_date_filter | (no_end_date_filter & end_date_filter)

            return Campaign.objects.filter(combined_filter)

        except ValueError:
            return ResponseHandler(True, "Invalid month name provided.", None, 404)

    def filter_weekly(self):
        start_date_param = self.request.query_params.get("start_date")
        end_date_param = self.request.query_params.get("end_date")

        try:
            if start_date_param and end_date_param:
                start_date = datetime.strptime(start_date_param, "%Y-%m-%d")
                end_date = datetime.strptime(end_date_param, "%Y-%m-%d")
            else:
                current_date = datetime.now().date()
                start_date = current_date - timedelta(days=current_date.weekday())
                end_date = start_date + timedelta(days=6)

            # Campaigns with start_date in the given week
            start_date_filter = Q(start_date__range=[start_date, end_date])

            # Campaigns with no end_date
            no_end_date_filter = Q(end_date__isnull=True)

            # Campaigns with end_date in the given week
            end_date_filter = Q(end_date__range=[start_date, end_date])

            combined_filter = start_date_filter | (no_end_date_filter & end_date_filter)

            return Campaign.objects.filter(combined_filter)

        except ValueError:
            return ResponseHandler(True, "Invalid date format provided.", None, 404)


# class PaymentCreateView(generics.CreateAPIView):
#     serializer_class = PaymentSerializer
#     def get_queryset(self):
#         queryset = Payment.objects.all()
#         return queryset


#     def get(self, request, *args, **kwargs):
#             try:
#                 payments = self.get_queryset()
#                 serializer = self.get_serializer(payments, many=True)
#                 return ResponseHandler(False, "Payments retrieved successfully.", serializer.data, status.HTTP_200_OK)
#             except Exception as e:
#                 return ResponseHandler(True, f"Error retrieving Campaigns: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

#     def create(self, request, *args, **kwargs):
#         try:
#             campaign_id = request.data.get('campaign')
#             campaign = get_object_or_404(Campaign, id=campaign_id)

#             payment_type = request.data.get('payment_type', 'single') # this can be checked using recurring field

#             if payment_type == 'single':

#                 serializer = self.get_serializer(data=request.data)
#                 serializer.is_valid(raise_exception=True)
#                 serializer.save()

#                 # Update spend in Campaign model for single payments
#                 if request.data['status'] == "Done":
#                     campaign.spend = campaign.spend or 0
#                     campaign.spend += request.data.get('amount', 0)
#                     campaign.save()
# Send push notification to Marketing Head
#   title = "Payment Request Created"
#   body = f"A payment request has been made for the campaign '{campaign.campaign_name}'."
#   data = {'campaign_id': campaign_id}

#   # Fetch the FCM tokens associated with the Marketing Head
#   marketing_head_user = self.request.user
#   user = Users.objects.get(id=marketing_head_user.id)
#   fcm_token = user.fcm_token

#   # Send push notification
#   send_push_notification(fcm_token, title, body, data)
#             # elif payment_type == 'recurring':

#             else:
#                 return Response({"error": "Invalid payment type"}, status=status.HTTP_400_BAD_REQUEST)

#             return Response({"success": "Payment(s) created successfully"}, status=status.HTTP_201_CREATED)

#         except Exception as e:
#             return Response({"error": f"Error creating payment: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VendorCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorSerializer

    @check_access(
        required_groups=["ADMIN", "MARKETING_HEAD", "VICE_PRESIDENT", "PROMOTER"]
    )
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHandler(
                    False,
                    "Vendor created successfully.",
                    serializer.data,
                    status.HTTP_201_CREATED,
                )
            else:
                return ResponseHandler(
                    True, serializer.errors, None, status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error creating Vendor: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get_queryset(self):
        queryset = Vendor.objects.all()
        return queryset.order_by("-id")

    def get(self, request, *args, **kwargs):
        try:
            vendors = self.get_queryset()
            if vendors.exists():
                serializer = self.get_serializer(vendors, many=True)
                return ResponseHandler(
                    False,
                    "Vendors retrieved successfully.",
                    serializer.data,
                    status.HTTP_200_OK,
                )
            else:
                return ResponseHandler(
                    False, "No data is present", [], status.HTTP_200_OK
                )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error retrieving Vendors: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


def delete_files_from_s3(vendor):

    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_storage_bucket_name = os.getenv("AWS_STORAGE_BUCKET_NAME")
    aws_s3_region_name = os.getenv("AWS_S3_REGION_NAME")

    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=aws_s3_region_name,
    )

    if vendor.gst_certificate:
        file_path = str(vendor.gst_certificate)
        print("It is working inside: ")
        s3.delete_object(Bucket=aws_storage_bucket_name, Key=file_path)

    if vendor.rera_certificate:
        file_path = str(vendor.rera_certificate)

        s3.delete_object(Bucket=aws_storage_bucket_name, Key=file_path)


class VendorDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return ResponseHandler(
                False,
                "Vendor retrieved successfully",
                serializer.data,
                status.HTTP_200_OK,
            )
        except Exception as e:
            return ResponseHandler(
                True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, *args, **kwargs):
        try:
            vendor = self.get_object()
            serializer = self.get_serializer(vendor, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return ResponseHandler(
                    False,
                    "Vendor updated successfully",
                    serializer.data,
                    status.HTTP_200_OK,
                )
            else:
                return ResponseHandler(
                    True, serializer.errors, None, status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return ResponseHandler(
                True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @check_access(
        required_groups=["ADMIN", "MARKETING_HEAD", "VICE_PRESIDENT", "PROMOTER"]
    )
    def delete(self, request, *args, **kwargs):
        try:
            vendor = self.get_object()
            delete_files_from_s3(vendor)
            vendor.delete()
            return ResponseHandler(
                False, "Vendor deleted successfully.", None, status.HTTP_200_OK
            )
        except Exception as e:
            return ResponseHandler(
                True, f"Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HistoryRetrievalView(APIView):
    def get(self, request, campaign_id):
        try:
            campaign = get_object_or_404(Campaign, id=campaign_id)
            Campaign_history = campaign.history.all()
            campaign_history_data = CampaignHistorySerializer(
                Campaign_history, many=True
            ).data
            sorted_history = sorted(
                campaign_history_data, key=lambda x: x["history_date"], reverse=True
            )
            for record in sorted_history:
                if record["history_type"] == "+":
                    pass
                if record["history_type"] == "~":
                    previous_record = None
                    if record["activity_type"] == "Campaign":
                        previous_record = next(
                            (
                                prev
                                for prev in sorted_history
                                if prev["history_date"] < record["history_date"]
                                and prev["activity_type"] == "Campaign"
                            ),
                            None,
                        )
                    if previous_record:

                        changed_fields = self.find_changed_fields(
                            previous_record, record
                        )
                        if changed_fields:
                            record["changed_fields"] = changed_fields

                            if record["activity_type"] == "Campaign":
                                messages = []
                                if (
                                    "campaign_name" in changed_fields
                                    and changed_fields["campaign_name"]["new_value"]
                                    is not None
                                ):
                                    old_campaign_name = changed_fields["campaign_name"][
                                        "old_value"
                                    ]
                                    new_campaign_name = changed_fields["campaign_name"][
                                        "new_value"
                                    ]
                                    # record['message'] = f'Campaign Name  Changed from {old_campaign_name} to {new_campaign_name}'
                                    messages.append(
                                        f"Campaign Name Changed from {old_campaign_name} to {new_campaign_name}."
                                    )
                                if (
                                    "agency_types_iist" in changed_fields
                                    and changed_fields["agency_types_list"]["new_value"]
                                    is not None
                                ):
                                    old_agency_type = changed_fields["agency_types_list"][
                                        "old_value"
                                    ]
                                    old_agency_type = f"{', '.join(old_agency_type)}"
                                    new_agency_type = changed_fields["agency_types_list"][
                                        "new_value"
                                    ]
                                    new_agency_type = f"{', '.join(new_agency_type)}"
                                    # record['message'] = f'Campaign Agency Type Changed from {old_agency_type} to {new_agency_type}'
                                    messages.append(
                                        f"Campaign Agency Type Changed from {old_agency_type} to {new_agency_type}"
                                    )
                                if (
                                    "agency_names_list" in changed_fields
                                    and changed_fields["agency_names_list"]["new_value"]
                                    is not None
                                    and changed_fields["agency_names_list"]["old_value"]
                                    is not None
                                ):
                                    old_vendor = changed_fields["agency_names_list"]["old_value"]
                                    old_vendor = f"{', '.join(old_vendor)}"
                                    new_vendor = changed_fields["agency_names_list"]["new_value"]
                                    new_vendor = f"{', '.join(new_vendor)}"
                                    # old_vendor_instance = Agency.objects.get(
                                    #     id=old_vendor
                                    # )
                                    # old_vendor_name = old_vendor_instance.name
                                    # new_vendor_instance = Agency.objects.get(
                                    #     id=new_vendor
                                    # )
                                    # new_vendor_name = new_vendor_instance.name
                                    # # record['message'] = f'Vendor Changed from {old_vendor} to {new_vendor}'
                                    messages.append(
                                        f"Agency name Changed from {old_vendor} to {new_vendor}"
                                    )
                                if (
                                    "budget" in changed_fields
                                    and changed_fields["budget"]["new_value"]
                                    is not None
                                ):
                                    old_budget = changed_fields["budget"]["old_value"]
                                    new_budget = changed_fields["budget"]["new_value"]
                                    # record['message'] = f'Campaign Budget Changed from {old_budget} to {new_budget}'
                                    messages.append(
                                        f"Campaign Budget Changed from {old_budget} to {new_budget}"
                                    )
                                if (
                                    "spend" in changed_fields
                                    and changed_fields["spend"]["new_value"] is not None
                                ):
                                    old_spend = changed_fields["spend"]["old_value"]
                                    new_spend = changed_fields["spend"]["new_value"]
                                    messages.append(
                                        f"Campaign Spend Changed from {old_spend} to {new_spend}"
                                    )
                                    # record['message'] = f'Campaign Spend Changed from {old_spend} to {new_spend}'
                                if (
                                    "end_date" in changed_fields
                                    and changed_fields["end_date"]["new_value"]
                                    is not None
                                ):
                                    new_end_date = changed_fields["end_date"][
                                        "new_value"
                                    ]
                                    messages.append(f"Campaign ended at {new_end_date}")
                                    # record['message'] = f'Campaign ended at {new_end_date}'
                                if (
                                    "team_members" in changed_fields
                                    and changed_fields["team_members"]["new_value"]
                                    is not None
                                ):
                                    old_team_members = set(
                                        changed_fields["team_members"]["old_value"]
                                    )
                                    new_team_members = set(
                                        changed_fields["team_members"]["new_value"]
                                    )

                                    added_team_members_ids = list(
                                        new_team_members - old_team_members
                                    )

                                    removed_team_members_ids = list(
                                        old_team_members - new_team_members
                                    )

                                    added_team_members_names = []
                                    for member_id in added_team_members_ids:
                                        try:
                                            member_instance = Users.objects.get(
                                                id=member_id
                                            )
                                            member_name = member_instance.name
                                            added_team_members_names.append(member_name)
                                        except Users.DoesNotExist:
                                            pass

                                    removed_team_members_names = []
                                    for member_id in removed_team_members_ids:
                                        try:
                                            member_instance = Users.objects.get(
                                                id=member_id
                                            )
                                            member_name = member_instance.name
                                            removed_team_members_names.append(
                                                member_name
                                            )
                                        except Users.DoesNotExist:
                                            pass

                                    if added_team_members_names:
                                        messages.append(
                                            f'Team Members added: {", ".join(added_team_members_names)}'
                                        )
                                    if removed_team_members_names:
                                        messages.append(
                                            f'Team Members removed: {", ".join(removed_team_members_names)}'
                                        )

                                    # record['message'] = f'Team Members added {new_team_members}'
                                if messages:
                                    record["message"] = ", ".join(messages)
            sorted_history = [
                record
                for record in sorted_history
                if record["message"] not in ["Campaign Details Edited"]
            ]
            response_data = {
                "activity_history": sorted_history,
            }
            return ResponseHandler(
                False, "Data retrieved successfully", response_data, 200
            )

        except Exception as e:
            return ResponseHandler(True, "Error retrieving activity data", str(e), 500)

    def find_changed_fields(self, previous_record, current_record):
        return {
            key: {
                "old_value": previous_record.get(key),
                "new_value": value,
            }
            for key, value in current_record.items()
            if (
                key
                not in (
                    "changed_fields",
                    "history_date",
                    "history_type",
                    "history_user",
                    "message",
                    "activity_type",
                )
                and previous_record.get(key) != value
            )
        }


class GetMetaDataAPIView(APIView):
    def get(self, request, *args, **kwargs):
        try:

            search_query = request.GET.get("search", "")

            if search_query:
                campaigns = Campaign.objects.filter(
                    Q(campaign_name__icontains=search_query)
                )

                campaigns_dict = [
                    {"id": campaign.id, "value": campaign.campaign_name}
                    for campaign in campaigns
                ]
            else:
                campaigns = Campaign.objects.values("id", "campaign_name")

                campaigns_dict = [
                    {"id": campaign["id"], "value": f"{campaign['campaign_name']} "}
                    for campaign in campaigns
                ]

            agency_types = [
                "Creative",
                "Digital",
                "Production",
                "PR",
                "Printing",
                "Event",
                "Other",
            ]

            agencies = Agency.objects.values("id", "agency_name")

            agencies_dict = [
                {"id": agency["id"], "value": agency["agency_name"]}
                for agency in agencies
            ]

            meta_data = {
                "campaigns": campaigns_dict,
                "agency_type": agency_types,
                "agencies": agencies_dict,
            }

            return ResponseHandler(
                False,
                "Meta data retrieved successfully.",
                meta_data,
                status.HTTP_200_OK,
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error retrieving meta data: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class WeeklyLeadsView(APIView):
    def get(self, request, campaign_id):
        try:

            campaign = Campaign.objects.get(id=campaign_id)

            end_date = campaign.end_date if campaign.end_date else datetime.now().date()

            source_model = Source.objects.filter(source_id=campaign.sourceid)
            if source_model.exists():
                source_id = source_model.first().id

                start_date = campaign.start_date
                date_range = end_date - start_date
                no_of_weeks = date_range.days // 7 + 1

                weekly_results = []

                for week in range(no_of_weeks):

                    current_start_date = start_date + timedelta(weeks=week)
                    current_end_date = current_start_date + timedelta(days=6)

                    leads_count = Lead.objects.filter(
                        source_id=source_id,
                        created_on__range=(current_start_date, current_end_date),
                    ).count()

                    day_wise_data = []
                    for day in range(7):
                        current_day = current_start_date + timedelta(days=day)
                        day_leads_count = Lead.objects.filter(
                            source_id=source_id, created_on__date=current_day
                        ).count()
                        day_wise_data.append(
                            {
                                "date": current_day.strftime("%Y-%m-%d"),
                                "leads_count": day_leads_count,
                            }
                        )

                    weekly_results.append(
                        {
                            "week_number": week + 1,
                            "start_date": current_start_date.strftime("%Y-%m-%d"),
                            "end_date": current_end_date.strftime("%Y-%m-%d"),
                            "leads_count": leads_count,
                            "day_wise_data": day_wise_data,
                        }
                    )

                response_data = {
                    "campaign_id": campaign_id,
                    "weekly_leads": weekly_results,
                }

                return ResponseHandler(
                    False,
                    "Weekly leads data retrieved successfully",
                    response_data,
                    200,
                )

            else:
                return ResponseHandler(
                    True, "Source not found for the given source_id", None, 404
                )

        except Campaign.DoesNotExist:
            return ResponseHandler(True, "Campaign not found", None, 404)
        except Exception as e:
            return ResponseHandler(True, f"An error occurred: {str(e)}", None, 500)


class CampaignSpecificBudgetView(APIView):
    @staticmethod
    def generate_color(name):
        # Generate a hash of the name
        hash_object = hashlib.md5(name.encode())
        hex_dig = hash_object.hexdigest()
        # Use the first 6 characters of the hash as the color code
        color = f"{hex_dig[:6].upper()}"
        return color

    def get_object(self, pk):
        try:
            return CampaignSpecificBudget.objects.get(pk=pk)
        except CampaignSpecificBudget.DoesNotExist:
            raise Http404

    def get(self, request):
        try:
            module = request.query_params.get("module", None)
            pk = request.query_params.get("campaign_id", None)
            if module == "live-campaign" and pk:
                campaign = Campaign.objects.get(id=pk)
                budgets = CampaignSpecificBudget.objects.filter(
                    campaign=campaign, expense_head__isnull=False
                )
                total_amount = sum(budget.amount for budget in budgets)
                print(total_amount)
                data = []
                for budget_data in budgets:
                    output = {
                        "expense_head": budget_data.expense_head,
                        "amount": budget_data.amount,
                        "percentage": (
                            round(budget_data.amount / total_amount * 100, 2)
                            if total_amount > 0
                            else 0.0
                        ),
                        "color": self.generate_color(budget_data.expense_head),
                        "total_amount_of_all_heads": total_amount,
                    }
                    data.append(output)
                # serializer = CampaignSpecificBudgetSerializer(data, many=True)
                return ResponseHandler(
                    False, "Data reterieved for live campaign", data, 200
                )
            elif module == "overview" and pk is None:
                budgets = CampaignSpecificBudget.objects.filter(
                    expense_head__isnull=False
                )
                total_amount = sum(budget.amount for budget in budgets)
                print(total_amount)
                expense_budgets = (
                    CampaignSpecificBudget.objects.filter(expense_head__isnull=False)
                    .values("expense_head")
                    .annotate(total_amount=Sum("amount"))
                )
                data = [
                    {
                        "expense_head": budget["expense_head"],
                        "amount": budget["total_amount"],
                        "percentage": (
                            round(budget["total_amount"] / total_amount * 100, 2)
                            if total_amount > 0
                            else 0.0
                        ),
                        "color": self.generate_color(budget["expense_head"]),
                        "total_amount_of_all_heads": total_amount,
                    }
                    for budget in expense_budgets
                ]

                return ResponseHandler(False, "Data reterieved for overview", data, 200)
            elif module == "live-graph" and pk:
                campaign = Campaign.objects.get(id=pk)
                if campaign:
                    print("campaign",campaign)
                    campaign_total_budget = campaign.budget
                    print("budget",campaign_total_budget)
                    budgets = CampaignSpecificBudget.objects.filter(campaign=campaign)
                    #total_amount_spend = sum(budget.amount for budget in budgets)
                    total_amount_spend = campaign.spend
                    print("spend",total_amount_spend)
                    interval = 20000
                    max_value = campaign_total_budget + interval
                    data = {
                        "name": campaign.campaign_name,
                        "total_budget": campaign_total_budget,
                        "total_spend": total_amount_spend,
                        "interval": interval,
                        "max_value": max_value,
                    }
                    return ResponseHandler(False, "Live campaign graph data", data, 200)
                else:
                    return ResponseHandler(
                        True, "Campaign not exists with given id", None, 500
                    )
            elif module == "overview-graph":
                campaigns = Campaign.objects.all()
                data = {}
                graph_data = []
                max_val = 0

                for campaign in campaigns:
                    print("camapign",campaign)
                    campaign_total_budget = campaign.budget
                    print("budget",campaign_total_budget)
                    budgets = CampaignSpecificBudget.objects.filter(
                        campaign=campaign.id
                    )
                    # total_amount_spend = sum(budget.amount for budget in budgets)

                    total_amount_spend = campaign.spend
                    print("spend",total_amount_spend)

                    if campaign_total_budget > max_val:
                        max_val = campaign_total_budget

                    campaign_data = {
                        "name": campaign.campaign_name,
                        "total_budget": campaign_total_budget,
                        "total_spend": total_amount_spend,
                    }
                    graph_data.append(campaign_data)

                data["graph_data"] = graph_data
                data["interval_data"] = {
                    "interval": 20000,
                    "max_value": max_val + 20000,
                }
                return ResponseHandler(False, "Graph data for overview", data, 200)
            elif module == "live-view" and pk:
                campaign = Campaign.objects.get(id=pk)
                if campaign:
                    all_spends = CampaignSpecificBudget.objects.filter(
                        campaign=campaign.id, expense_head__isnull=False
                    )
                    serializer = CampaignSpecificBudgetSerializer(all_spends, many=True)
                else:
                    return ResponseHandler(
                        True, "Campaign not exists with given id", None, 500
                    )
                return Response(
                    data={
                        "error": False,
                        "message": "Data retrieved successfully for live campaign",
                        "body": serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                all_spends = CampaignSpecificBudget.objects.filter(
                    expense_head__isnull=True
                )
                print(all_spends)
                data = []
                for spend in all_spends:
                    print(spend.id)
                    res = {
                        "id": spend.id,
                        "campaign": spend.campaign.id,
                        "campaign_name": (
                            spend.campaign.campaign_name
                            if spend.campaign and spend.campaign.campaign_name
                            else None
                        ),
                        # "vendor_name": spend.campaign.agency_name.agency_name if spend.campaign.agency_name and spend.campaign else None,
                        # "agency_type": spend.campaign.agency_type if spend.campaign and spend.campaign.agency_type else None ,
                        "amount": spend.amount,
                        "paid_date": spend.paid_date,
                    }
                    data.append(res)
                # serializer = CampaignSpecificBudgetSerializer(all_spends, many=True)
                return Response(
                    data={
                        "error": False,
                        "message": "Data retrieved successfully for overview",
                        "body": data,
                    },
                    status=status.HTTP_200_OK,
                )
        except Campaign.DoesNotExist:
            return Response(
                {"error": "Error in data"}, status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request, format=None):
        if not isinstance(request.data, list):
            return Response(
                {
                    "error": True,
                    "message": "Expected a list of items but got type 'dict'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = []
        errors = []

        for budget_data in request.data:
            campaign_id = budget_data.get("campaign")
            amount = budget_data.get("amount", 0)

            try:
                campaign = Campaign.objects.get(id=campaign_id)
            except Campaign.DoesNotExist:
                errors.append({"campaign": "Campaign does not exist."})
                continue

            # # Validate total spend amount against campaign budget
            # total_spend = CampaignSpecificBudget.objects.filter(campaign=campaign).aggregate(Sum('amount'))['amount__sum'] or 0
            # if total_spend + amount > campaign.budget:
            #     #errors.append({"campaign": f"Total spend amount exceeds campaign budget for campaign ID {campaign_id}."})
            #     return ResponseHandler(True,f"Total spend amount exceeds campaign budget for campaign ID {campaign_id}.", None, 400)

            serializer = CampaignSpecificBudgetSerializer(data=budget_data)
            if serializer.is_valid():
                serializer.save()
                response_data.append(serializer.data)
            else:
                errors.append(serializer.errors)

        if errors:
            return ResponseHandler(True, errors, None, 400)
        else:
            return ResponseHandler(
                False, "Spend created successfully", response_data, 201
            )

    def put(self, request, pk, format=None):
        budget = self.get_object(pk)
        serializer = CampaignSpecificBudgetSerializer(budget, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(
                False, "data updated successfully", serializer.data, 200
            )
        return ResponseHandler(True, serializer.errors, None, 400)

    def delete(self, request, pk, format=None):
        budget = self.get_object(pk)
        if budget:
            budget.delete()
            return ResponseHandler(False, "Deleted Successfully", None, 200)
        else:
            return ResponseHandler(True, "Not found spend with given id", None, 400)


# class PaymentDetailApiView(generics.RetrieveUpdateDestroyAPIView):
#     serializer_class = PaymentSerializer
#     permission_classes = (IsAuthenticated,)

#     queryset = Payment.objects.all()

#     def get(self, request, *args, **kwargs):
#        Payment_id = self.kwargs.get('pk')
#        try:
#             instance = Payment.objects.get(pk=Payment_id)
#             serializer = self.get_serializer(instance)

#             return ResponseHandler(False, 'Payment retrieved successfully', serializer.data, status.HTTP_200_OK)
#        except Payment.DoesNotExist:
#             return ResponseHandler(True, 'Payment not found', None, status.HTTP_404_NOT_FOUND)


#     def put(self, request, *args, **kwargs):
#         Payment_id = self.kwargs.get('pk')
#         try:
#             instance = self.queryset.get(pk=Payment_id)
#         except Payment.DoesNotExist:
#             return ResponseHandler(True, 'Payment not found', None, status.HTTP_404_NOT_FOUND)

#         serializer = self.get_serializer(instance, data=request.data, partial=True)

#         if serializer.is_valid():
#             serializer.save()

#             if request.data.get('status') == "Done" and not instance.recurring:
#                 campaign = instance.campaign
#                 campaign.spend = campaign.spend or 0
#                 campaign.spend += instance.amount
#                 campaign.save()

#             return ResponseHandler(False, 'Data updated successfully', serializer.data, status.HTTP_200_OK)
#         else:
#             return ResponseHandler(True, 'Validation error.', serializer.errors, status.HTTP_400_BAD_REQUEST)


#     def delete(self, request, *args, **kwargs):
#         Payment_id = self.kwargs.get('pk')
#         try:
#             instance = Payment.objects.get(pk=Payment_id)
#             self.perform_destroy(instance)
#             return ResponseHandler(False, 'Payment deleted successfully' , None,status.HTTP_204_NO_CONTENT)
#         except Payment.DoesNotExist:
#             return ResponseHandler(True , 'No matching data present in models', None ,status.HTTP_404_NOT_FOUND)


class AgencyView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomLimitOffsetPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AgencyCreateSerializer
        return AgencyListSerializer

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return ResponseHandler(
                    False,
                    "Agency created successfully.",
                    serializer.data,
                    status.HTTP_201_CREATED,
                )
            return ResponseHandler(
                True,
                serializer.errors,
                None,
                status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error creating Agency: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get_queryset(self):
        queryset = Agency.objects.all().order_by("-id")
        search = self.request.query_params.get("search", None)
        agency_type = self.request.query_params.get("agency_type", None)

        if search:
            queryset = queryset.filter(
                Q(agency_name__icontains=search)
                | Q(vendors_full_name__icontains=search)
            )
        if agency_type:
            agency_type_list = [atype.strip() for atype in agency_type.split(",")]
            queryset = queryset.filter(agency_type__name__in=agency_type_list)

        return queryset

    def get(self, request, *args, **kwargs):
        try:
            agencies = self.get_queryset()
            serializer = self.get_serializer(agencies, many=True)
            if agencies.exists():
                # Apply pagination
                paginated_class = self.pagination_class
                offset = int(request.query_params.get("offset", 0))
                limit = int(request.query_params.get("limit", 10))
                total_count = len(serializer.data)
                paginated_data = serializer.data[offset : offset + limit]

                response_data = {
                    "count": total_count,
                    "next": paginated_class.get_next_link(
                        self, request, offset, limit, total_count
                    ),
                    "previous": paginated_class.get_previous_link(
                        self, request, offset, limit
                    ),
                    "results": paginated_data,
                }

                return ResponseHandler(
                    False,
                    "Agencies retrieved successfully.",
                    response_data,
                    status.HTTP_200_OK,
                )
            return ResponseHandler(
                False,
                "No data is present",
                {"count": 0, "next": None, "previous": None, "results": []},
                status.HTTP_200_OK,
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error retrieving Agencies: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AgencyDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "PUT":
            return AgencyCreateSerializer
        return AgencyDetailSerializer

    def get_object(self):
        return get_object_or_404(Agency, id=self.kwargs.get("pk"))

    def get(self, request, *args, **kwargs):
        try:
            agency = self.get_object()
            serializer = self.get_serializer(agency)
            return ResponseHandler(
                False,
                "Agency retrieved successfully.",
                serializer.data,
                status.HTTP_200_OK,
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error retrieving Agency: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, *args, **kwargs):
        try:
            agency = self.get_object()
            serializer = self.get_serializer(agency, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return ResponseHandler(
                    False,
                    "Agency updated successfully.",
                    serializer.data,
                    status.HTTP_200_OK,
                )
            return ResponseHandler(
                True,
                serializer.errors,
                None,
                status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error updating Agency: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ExportView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def export_to_excel(self, data):
        try:
            if not data:
                raise ValueError("No data to export.")

            df = pd.DataFrame(data)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            excel_file_path = os.path.join(
                settings.MEDIA_ROOT, f"leadsexported_{timestamp}.xlsx"
            )

            df.to_excel(excel_file_path, index=False)

            with open(excel_file_path, "rb") as file:
                export_file = ExportFile(file=File(file))
                export_file.save()

            os.remove(excel_file_path)
            return export_file.file.url
        except Exception as e:
            if os.path.exists(excel_file_path):
                os.remove(excel_file_path)
            raise e

    def post(self, request, *args, **kwargs):
        data = request.data.get("data", [])
        try:
            file_url = self.export_to_excel(data)
            return ResponseHandler(
                False,
                "Export successful",
                {"file_url": file_url},
                status.HTTP_200_OK,
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error exporting data: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AgencyRemarkCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AgencyRemarkSerializer

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        print(request.user)
        data["created_by"] = str(request.user)
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return ResponseHandler(
                False,
                "Remark created successfully.",
                serializer.data,
                status.HTTP_201_CREATED,
            )
        return ResponseHandler(
            True, serializer.errors, None, status.HTTP_400_BAD_REQUEST
        )

class AgencyRemarkListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AgencyRemarkSerializer

    def get_queryset(self):
        agency_id = self.kwargs.get("agency_id")
        return AgencyRemark.objects.filter(agency__id=agency_id).order_by("-created_at")

    def get(self, request, *args, **kwargs):
        try:
            remarks = self.get_queryset()
            serializer = self.get_serializer(remarks, many=True)
            return ResponseHandler(
                False,
                "Remarks retrieved successfully.",
                serializer.data,
                status.HTTP_200_OK
            )
        except Exception as e:
            return ResponseHandler(
                True,
                f"Error retrieving remarks: {str(e)}",
                None,
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )