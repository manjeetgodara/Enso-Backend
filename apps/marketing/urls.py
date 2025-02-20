from django.urls import path, include
from .views import *

urlpatterns = [
    path('campaign/', CampaignCreateView.as_view(), name = "create-campaign"),
    path('campaign/<int:pk>/', CampaignDetailApiView.as_view(), name= 'get-update-delete-campaign'),
    path('campaign/weekly-leads/<int:campaign_id>/', WeeklyLeadsView.as_view(), name='weekly-leads-api'),
    path('search/', CampaignSearchView.as_view(), name= 'search'),
    path('user_allocation/', UserAllocationView.as_view(), name='user_allocation'),
    path('folder/', FolderCreateView.as_view(), name = 'create-folder'),
    path('folder/<int:pk>/', FolderDetailApiView.as_view(), name = 'detail-folder'),
    path('document/', DocumentCreateView.as_view(), name = 'create-folder'),
    path('document/<int:pk>/', DocumentDetailApiView.as_view(), name = 'detail-folder'),
    path('folder/document/<int:pk>/', GetAllDocsView.as_view(), name = 'get-all-docs'),
    path('documents/<int:pk>/rename/', DocumentRenameView.as_view(), name='document-rename'),
    path('gantt-view/', GanttViewList.as_view(), name='gantt-view-list'), # Calendar View
    path('vendors/', VendorCreateView.as_view(), name='vendor-create'),
    path('vendors/<int:pk>/', VendorDetailView.as_view(), name='vendor-detail'),
    path('get_meta_data/', GetMetaDataAPIView.as_view(), name='get_meta_data'),
    # path('payments/', PaymentCreateView.as_view(), name = 'payment-create'), 
    # path('payments/<int:pk>/', PaymentDetailApiView.as_view(), name= 'payment-detail'),
    path('campaign-summary/', CampaignSummaryAPIView.as_view(), name='campaign-summary'),
    path('campaign-breakdown/', CampaignBreakdownSummaryAPIView.as_view(), name='campaign-breakdown'),
    path('history-retrieval/<int:campaign_id>/', HistoryRetrievalView.as_view(), name='history_retrieval'), 
    path('campaign-specific-budgets/', CampaignSpecificBudgetView.as_view(), name='campaign-specific-budget-list'),
    path('campaign-specific-budgets/<int:pk>/', CampaignSpecificBudgetView.as_view(), name='campaign-specific-budget-detail'),
    path('agencies/', AgencyView.as_view(), name='agency-list-create'),
    path('agencies/<int:pk>/', AgencyDetailView.as_view(), name='agency-detail'),
    path('export/', ExportView.as_view(), name='file-export'),
    path('agencies/remarks/', AgencyRemarkCreateView.as_view(), name='agency-remarks-list-create'),
    path('agencies/remarks/<int:agency_id>/', AgencyRemarkListView.as_view(), name='agency-remarks-list-create'),
]
 
