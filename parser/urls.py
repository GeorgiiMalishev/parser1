from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views
from .api_views import FetchInternshipsAPIView, FetchHabrInternshipsAPIView, FetchSuperJobInternshipsAPIView, FetchAllInternshipsAPIView, ParseUniversalURLAPIView, PreviewInternshipAPIView
from .tasks import sync_webhook
from . import views
from .views import WebsiteListView, WebsiteCreateView, InternshipListView, ArchivedInternshipListView, MainPageView, SecondPageView, AddSiteModalView

app_name = 'parser'


urlpatterns = [
    path('api/fetch/hh/', FetchInternshipsAPIView.as_view(), name='fetch_internships'),
    path('api/fetch/habr/', FetchHabrInternshipsAPIView.as_view(), name='fetch_habr_internships'),
    path('api/fetch/superjob/', FetchSuperJobInternshipsAPIView.as_view(), name='fetch_superjob_internships'),
    path('api/fetch/all/', FetchAllInternshipsAPIView.as_view(), name='fetch_all_internships'),
    path('api/sync/', sync_webhook, name='sync_webhook'),
    path('parse-universal/', ParseUniversalURLAPIView.as_view(), name='parse_universal_url'),
    path('api/preview-internship/', PreviewInternshipAPIView.as_view(), name='preview_internship'),
    path('api/internships/', api_views.internship_list_api, name='internship_list_api'),
    path('api/internship/<int:pk>/', api_views.internship_detail_api, name='internship_detail_api'),
    
    path('', MainPageView.as_view(), name='main_page'),
    path('second/', SecondPageView.as_view(), name='second_page'),
    path('modal/add-site/', AddSiteModalView.as_view(), name='add_site_modal'),

    path('websites/', WebsiteListView.as_view(), name='website_list'),
    path('website/add/', WebsiteCreateView.as_view(), name='website_create'),
    path('website/delete/<int:pk>/', views.WebsiteDeleteView.as_view(), name='website_delete'),
    path('internships/', InternshipListView.as_view(), name='internship_list'),
    path('archived/', ArchivedInternshipListView.as_view(), name='archived_internship_list'),
    path('run-hh-parser/', views.run_hh_parser, name='run_hh_parser'),
    path('archive-internship/<int:pk>/', views.archive_internship, name='archive_internship'),
    path('delete_internship/<int:internship_id>/', views.delete_internship, name='delete_internship'),
    path('special_parsers/settings/get/', views.get_special_parsers_settings, name='get_special_parsers_settings'),
    path('special_parsers/settings/save/', views.save_special_parsers_settings, name='save_special_parsers_settings'),
] 