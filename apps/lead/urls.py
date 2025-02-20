from django.urls import path
from .views import *#, LeadHistoryView
#from .views import LeadListCreateAPIView,LeadCreateAPIView, LeadRequirementListCreateAPIView,LeadRetrieveUpdateDeleteAPIView,DownloadLeadsView,LeadRequirementsRetrieveUpdateDeleteAPIView
# from .views import InventoryCreateView, InventoryDetailApiView, BookingFormCreateView,BookingFormDetailApiView,\
#    CollectTokenCreateView, CollectTokenDetailApiView 
from rest_framework import permissions
from django.urls import path
from .views import HistoryRetrievalView
#from .views import LeadSearchAPIView
# Add followers to lead models json fields. Push users from api
urlpatterns = [
    path('', LeadCreateAPIView.as_view(), name='lead-create'),
    path('<int:pk>/', LeadRetrieveUpdateDeleteAPIView.as_view(), name='lead-retrieve-update-destroy'),
    path('details/', LeadDetailsByPhone.as_view(), name='lead_details_by_phone'),
    path('bulk-upload/', BulkLeadUploadView.as_view(), name='bulk-lead-upload'),
    path('bulk-cp-upload/', BulkChannelPartnerUploadView.as_view(), name='bulk-cp-upload'),
    #path('download-leads/', DownloadLeadsView.as_view(), name='download-leads'),
    path('createcp/', ChannelPartnerCreateView.as_view(), name='create-channel-partner'),
    path('cp-unique-check/', CheckCPuniqueness.as_view(), name='check-uniqueness-cp'),
    path('cp/<int:pk>/', ChannelPartnerUpdateView.as_view(), name='update-retrieve-update-destroy-channel-partner'),
    path('lead-search/', LeadSearchAPIView.as_view(), name='lead-search'),
    path('users/', UsersList.as_view(), name='users-list'),
    path('allocate-user/', UserAllocationView.as_view(), name='user-allocation'),
    path('user-reallocation/', UserReallocationView.as_view(), name='user_reallocation'),
    path('get_meta_data/', GetMetaDataAPIView.as_view(), name='get_meta_data'),
    path('export-leads/',ExportLeadsView.as_view(), name='export-leads'),
    path('export-cps/',ExportChannelPartnerView.as_view(), name='export-cps'),
    path('documents/', DocumentSectionAPIView.as_view(), name='document-section-list-create'),
    path('documents/bulk-upload/', DocumentSectionBulkUploadView.as_view(), name='document-bulk-upload'),
    path('documents/lead/<int:lead_id>/', DocumentSectionRetrieveByLeadAndTagView.as_view(), name='document-section-retrieve-by-lead'),
    path('history-retrieval/<int:lead_id>/', HistoryRetrievalView.as_view(), name='history_retrieval'),
    path('updates/<int:lead_id>/', UpdatesListApi.as_view(), name='updates-list'),
    path('send_updates/', CommunicationAPI.as_view(), name='send_updates'),
    path('documents/<int:doc_id>/', DocumentActions.as_view(), name='document-actions'),
    path('meetings/', CreateMeetingAPIView.as_view(), name='create-meeting'),
    path('meetings/<int:meeting_id>/', MeetingDetailAPIView.as_view(), name='meeting-detail'),
    path('meetings/cp/<int:pk>/',MeetingDetailsbyId.as_view(), name='get-site-visit-id' ),
    path('lead-summary/', LeadSummaryAPIView.as_view(), name='lead_summary'),
    path('sales-summary/', SalesSummaryAPIView.as_view(), name='sales_summary'),
    path('top-performance/', TopPerformanceAPIView.as_view(), name='top-performance'),
    path('leads-overview/', LeadsOverviewAPIView.as_view(), name='leads-overview'),
    path('check-lead/', CheckLeadExists.as_view(), name='check_lead_exists'),
    # path('inventory/', InventoryCreateView.as_view(), name='inventory-create'),
    # path('inventory/<int:pk>/', InventoryDetailApiView.as_view(), name='inventory-detail'),
    # path('bookingform/', BookingFormCreateView.as_view(), name= "bookingform-create"),
    # path('bookingform/<int:pk>/', BookingFormDetailApiView.as_view(), name='bookingform-detail'),
    # path('collecttoken/', CollectTokenCreateView.as_view(), name= "collecttoken-create"),
    # path('collecttoken/<int:pk>/', CollectTokenDetailApiView.as_view(), name='collecttoken-detail'),
    #path('lead/<int:lead_id>/history/', LeadHistoryView.as_view(), name='lead_history'),
    #path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    #path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('location/<str:pincode>/', LocationByPincodeView.as_view(), name='location_by_pincode'),
    path('brokerage-categories/', BrokerageCategoryList.as_view(), name='brokerage-category-list'),
    path('brokerage-categories/<int:pk>/', BrokerageCategoryDetail.as_view(), name='brokerage-category-detail'),
    path('brokerage-deals/', BrokerageDealList.as_view(), name='brokerage-deal-list'),
    path('brokerage-deals/<int:pk>/', BrokerageDealDetail.as_view(), name='brokerage-deal-detail'),
    path('brokerage-channel-partners/', ChannelPartnerBrokerageListView.as_view(), name='channel-partner-list'),
    path('channel-partner-brokerages/', ChannelPartnerBrokerageView.as_view(), name='channel-partner-brokerage-list'),
    path('channel-partner-brokerages/<int:pk>/', ChannelPartnerBrokerageView.as_view(), name='channel-partner-brokerage-detail'),
    path('brokerage-meta-data/', BrokerageMetaDataAPIView.as_view(),name="brokerage-meta-data"),
    path('send-reminder/', SendNotificationView.as_view(), name='send_reminder'),
    path('notification-count/', NotificationCountView.as_view(), name='notification-count'),
    path('post-sales/documents/bulk-upload/', PostSalesDocumentBulkUploadView.as_view(), name='post-sales-document-bulk-upload'),
    path('post-sales/documents/lead/<int:lead_id>/', PostSalesDocumentsListView.as_view(), name='postsales-documents-list'),
    path('canceled-bookings-leads/', CanceledBookingLeadsView.as_view(), name='canceled-bookings'),
    path('post-sales/document-type-metadata/', PostSalesDocumentTypeMetadataView.as_view(), name='post-sales-document-type-metadata'),
    path('export/postsales/', ExportPostSalesDataView.as_view(), name='export_postsales'),
    path('signatures/<int:lead_id>/', LeadSignatureView.as_view(), name='lead-signatures'),
    path('get_signatures/<int:lead_id>/',SignatureAPIView.as_view(),name="get all signatures"),
    path('cce-list/',CCEViewList.as_view(),name='cce-list'),
    path('cm-list/',CMViewList.as_view(),name='cm_list'),
    path('sm-list/',SMViewList.as_view(),name='sm-list-view'),
    path('channel-partner-list/', CPViewList.as_view(),name='cp_view_list')
]




