import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, filters
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .hh_api_parser import fetch_hh_internships, HeadHunterAPI
from .models import Website, Internship
from .serializers import InternshipSerializer

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    """Стандартная пагинация для API"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class InternshipAPIViewSet(viewsets.ReadOnlyModelViewSet):
    """API для просмотра стажировок"""
    serializer_class = InternshipSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'company', 'position', 'description', 'keywords', 'city']
    ordering_fields = ['created_at', 'title', 'company', 'selection_start_date']
    ordering = ['-created_at']
    
    @extend_schema(
        description="Получение списка стажировок с пагинацией и фильтрацией",
        parameters=[
            OpenApiParameter(
                name='search',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Поиск по всем текстовым полям'
            ),
            OpenApiParameter(
                name='is_archived',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Фильтрация по архивному статусу'
            ),
            OpenApiParameter(
                name='employment_type',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Фильтрация по типу занятости (remote, office, hybrid, full_time, part_time, flexible)'
            ),
            OpenApiParameter(
                name='ordering',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Сортировка (-created_at, title, company, selection_start_date)'
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    def get_queryset(self):
        """Получение списка стажировок с учетом фильтров"""
        queryset = Internship.objects.select_related('source_website').all()
        
        is_archived = self.request.query_params.get('is_archived')
        if is_archived is not None:
            is_archived = is_archived.lower() == 'true'
            queryset = queryset.filter(is_archived=is_archived)
        
        employment_type = self.request.query_params.get('employment_type')
        if employment_type:
            queryset = queryset.filter(employment_type=employment_type)
            
        city = self.request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)
            
        company = self.request.query_params.get('company')
        if company:
            queryset = queryset.filter(company__icontains=company)
            
        return queryset

class FetchInternshipsAPIView(APIView):
    """API endpoint для получения стажировок с HH.ru"""
    
    @extend_schema(
        description="Получить стажировки с HeadHunter по ключевым словам, региону и другим параметрам.",
        parameters=[
            OpenApiParameter('keywords', OpenApiTypes.STR, description="Ключевые слова для поиска"),
            OpenApiParameter('area', OpenApiTypes.STR, description="Регион поиска (код HH.ru)"),
            OpenApiParameter('max_pages', OpenApiTypes.INT, description="Максимальное количество страниц", default=20),
        ],
        responses={200: {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "count": {"type": "integer"},
                "internships": {"type": "array"}
            }
        }}
    )
    def get(self, request):
        """Получение списка стажировок"""
        params = self._prepare_params(request)
        
        try:
            internships = fetch_hh_internships(**params)
            logger.info(f"Получено {len(internships)} стажировок.")
            
            hh_website, created = Website.objects.get_or_create(
                name="HeadHunter",
                url="https://hh.ru",
            )
            
            if created:
                logger.info("Создан новый источник: HeadHunter")
            
            count_created = 0
            count_updated = 0
            client = HeadHunterAPI()
            
            for internship_data in internships:
                internship, is_created = client.create_internship(internship_data, hh_website)
                if is_created:
                    count_created += 1
                else:
                    count_updated += 1
            
            logger.info(f"Обработано стажировок: {len(internships)}, создано: {count_created}, обновлено: {count_updated}")
            
            return Response({
                'status': 'success', 
                'count': len(internships), 
                'saved': {'created': count_created, 'updated': count_updated},
                'internships': internships
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Ошибка при вызове fetch_hh_internships: {e}", exc_info=True)
            return Response({
                'status': 'error', 
                'message': 'Произошла внутренняя ошибка сервера при получении данных.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _prepare_params(self, request):
        """Подготовка параметров для API запроса"""
        keywords = request.GET.get('keywords', None)
        area = request.GET.get('area', None)
        max_pages = request.GET.get('max_pages', 20)
        
        try:
            max_pages = int(max_pages)
        except (ValueError, TypeError):
            max_pages = 20
            
        logger.info(f"Запрос на получение стажировок: keywords='{keywords}', area='{area}', max_pages={max_pages}")
        
        fetch_params = {
            'keywords': keywords,
            'area': area,
            'max_pages': max_pages,
        }
        
        return {k: v for k, v in fetch_params.items() if v is not None} 