from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .api_views import FetchInternshipsAPIView, InternshipAPIViewSet

app_name = 'parser'

router = DefaultRouter()
router.register(r'internships', InternshipAPIViewSet, basename='api-internships')

urlpatterns = [
    path('', views.index, name='home'),
    path('results/', views.ParserResultsView.as_view() if hasattr(views, 'ParserResultsView') else views.index, name='results'),
    path('results/<int:pk>/', views.DetailInternshipView.as_view() if hasattr(views, 'DetailInternshipView') else views.index, name='detail'),
    path('parse/', views.RunManualParsingView.as_view() if hasattr(views, 'RunManualParsingView') else views.run_hh_parser, name='run_parsing'),
    path('clear/', views.ClearParsingResultsView.as_view() if hasattr(views, 'ClearParsingResultsView') else views.index, name='clear_results'),
    path('search/', views.SearchResultsView.as_view() if hasattr(views, 'SearchResultsView') else views.index, name='search'),
    
    path('api/', include(router.urls)),
    path('api/fetch/', FetchInternshipsAPIView.as_view(), name='fetch_internships'),

    path('websites/', views.WebsiteListView.as_view(), name='website_list'),
    path('websites/add/', views.WebsiteCreateView.as_view(), name='website_add'),
    path('websites/parse-preview/', views.parse_website_preview, name='parse_preview'),
    path('websites/save-internship/', views.save_internship, name='save_internship'),
    path('websites/run-hh-parser/', views.run_hh_parser, name='run_hh_parser'),

    path('internships/', views.InternshipListView.as_view(), name='internship_list'),
    path('internships/archive/', views.ArchivedInternshipListView.as_view(), name='archived_internships'),
    path('internships/<int:pk>/archive/', views.archive_internship, name='archive_internship'),
] 