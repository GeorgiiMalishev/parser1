from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views
from .api_views import FetchInternshipsAPIView, FetchHabrInternshipsAPIView, FetchSuperJobInternshipsAPIView, FetchAllInternshipsAPIView
from .tasks import sync_webhook
from . import views

app_name = 'parser'


urlpatterns = [
    path('api/fetch/hh/', FetchInternshipsAPIView.as_view(), name='fetch_internships'),
    path('api/fetch/habr/', FetchHabrInternshipsAPIView.as_view(), name='fetch_habr_internships'),
    path('api/fetch/superjob/', FetchSuperJobInternshipsAPIView.as_view(), name='fetch_superjob_internships'),
    path('api/fetch/all/', FetchAllInternshipsAPIView.as_view(), name='fetch_all_internships'),
    path('api/sync/', sync_webhook, name='sync_webhook'),
    path('', views.index, name='index'),
    path('api/internships/', api_views.internship_list_api, name='internship_list_api'),
    path('api/internship/<int:pk>/', api_views.internship_detail_api, name='internship_detail_api'),
] 