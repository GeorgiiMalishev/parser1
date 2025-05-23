import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets, filters
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
import threading
import concurrent.futures
from django.db.models import Q

from .hh_api_parser import fetch_hh_internships, HeadHunterAPI
from .habr_parser import fetch_habr_career_internships, HabrCareerParser
from .superjob_parser import fetch_superjob_internships, SuperJobParser
from .universal_parser import UniversalParser
from .models import Website, Internship, SearchQuery
from .serializers import InternshipSerializer
from .tasks import parse_hh_internships, parse_habr_internships, parse_superjob_internships

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    """Стандартная пагинация для API"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class FetchInternshipsAPIView(APIView):
    """API endpoint для получения стажировок с HH.ru"""
    
    @extend_schema(
        description="Запуск задачи для получения стажировок с HeadHunter по ключевым словам, региону и другим параметрам.",
        parameters=[
            OpenApiParameter('keywords', OpenApiTypes.STR, description="Ключевые слова для поиска"),
            OpenApiParameter('city', OpenApiTypes.STR, description="Название города для поиска (например, 'Москва', 'Санкт-Петербург')"),
            OpenApiParameter('area', OpenApiTypes.STR, description="Регион поиска (код HH.ru). Используется, если не указан параметр city"),
            OpenApiParameter('max_pages', OpenApiTypes.INT, description="Максимальное количество страниц", default=20),
        ],
        responses={202: {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "message": {"type": "string"}
            }
        }}
    )
    def get(self, request):
        """Запуск задачи получения списка стажировок с HeadHunter"""
        params = self._prepare_params(request)
        
        try:
            logger.info(f"Выполнение получения стажировок с HeadHunter в многопоточном режиме")
            
            hh_website, created = Website.objects.get_or_create(
                name="HeadHunter",
                url="https://hh.ru",
            )
            
            import threading
            thread = threading.Thread(target=self._run_hh_parser, args=(params,))
            thread.daemon = True
            thread.start()
            
            return Response({
                'status': 'success', 
                'message': 'Задача запущена. Стажировки будут загружены и добавлены в базу данных.'
            }, status=status.HTTP_202_ACCEPTED)
                
        except Exception as e:
            logger.error(f"Ошибка при получении стажировок с HeadHunter: {e}", exc_info=True)
            return Response({
                'status': 'error', 
                'message': 'Произошла внутренняя ошибка сервера при получении данных.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _run_hh_parser(self, params):
        """Выполнение получения стажировок с HeadHunter"""
        try:
            from .tasks import parse_hh_internships
            result = parse_hh_internships(**params)
            logger.info(f"Результат получения стажировок с HeadHunter: {result}")
        except Exception as e:
            logger.error(f"Ошибка при выполнении задачи получения стажировок с HeadHunter: {e}", exc_info=True)
    
    def _prepare_params(self, request):
        """Подготовка параметров для API запроса"""
        keywords = request.GET.get('keywords', None)
        city = request.GET.get('city', None)
        area = request.GET.get('area', None)
        max_pages = request.GET.get('max_pages', 20)
        
        try:
            max_pages = int(max_pages)
        except (ValueError, TypeError):
            max_pages = 20
            
        logger.info(f"Запрос на получение стажировок: keywords='{keywords}', city='{city}', area='{area}', max_pages={max_pages}")
        
        fetch_params = {
            'keywords': keywords,
            'city': city,
            'area': area,
            'max_pages': max_pages
        }
        
        return {k: v for k, v in fetch_params.items() if v is not None}


class FetchHabrInternshipsAPIView(APIView):
    """API endpoint для получения стажировок с Habr Career"""
    
    @extend_schema(
        description="Запуск задачи для получения стажировок с Habr Career по городу/локации и другим параметрам.",
        parameters=[
            OpenApiParameter('city', OpenApiTypes.STR, description="Название города для поиска (например, 'Москва', 'Санкт-Петербург')"),
            OpenApiParameter('keywords', OpenApiTypes.STR, description="Ключевые слова для поиска вакансий (например, 'java', 'python')"),
            OpenApiParameter('location_id', OpenApiTypes.STR, description="ID локации (например, 'c_678' для Москвы). Используется, если не указан параметр city"),
            OpenApiParameter('max_pages', OpenApiTypes.INT, description="Максимальное количество страниц", default=10),
        ],
        responses={202: {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "message": {"type": "string"}
            }
        }}
    )
    def get(self, request):
        """Запуск задачи получения списка стажировок с Habr Career"""
        params = self._prepare_params(request)
        
        try:
            logger.info(f"Выполнение получения стажировок с Habr Career в многопоточном режиме")
            
            habr_website, created = Website.objects.get_or_create(
                name="Habr Career",
                url="https://career.habr.com/",
            )
            
            import threading
            thread = threading.Thread(target=self._run_habr_parser, args=(params,))
            thread.daemon = True
            thread.start()
            
            return Response({
                'status': 'success', 
                'message': 'Задача запущена. Стажировки будут загружены и добавлены в базу данных.'
            }, status=status.HTTP_202_ACCEPTED)
                
        except Exception as e:
            logger.error(f"Ошибка при получении стажировок с Habr Career: {e}", exc_info=True)
            return Response({
                'status': 'error', 
                'message': 'Произошла внутренняя ошибка сервера при получении данных.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _run_habr_parser(self, params):
        """Выполнение получения стажировок с Habr Career"""
        try:
            from .tasks import parse_habr_internships
            result = parse_habr_internships(**params)
            logger.info(f"Результат получения стажировок с Habr Career: {result}")
        except Exception as e:
            logger.error(f"Ошибка при выполнении задачи получения стажировок с Habr Career: {e}", exc_info=True)
    
    def _prepare_params(self, request):
        """Подготовка параметров для API запроса"""
        keywords = request.GET.get('keywords', None)
        city = request.GET.get('city', None)
        location_id = request.GET.get('location_id', None)
        max_pages = request.GET.get('max_pages', 10)
        
        try:
            max_pages = int(max_pages)
        except (ValueError, TypeError):
            max_pages = 10
            
        logger.info(f"Запрос на получение стажировок с Habr: keywords='{keywords}', city='{city}', location_id='{location_id}', max_pages={max_pages}")
        
        fetch_params = {
            'keywords': keywords,
            'city': city,
            'location_id': location_id,
            'max_pages': max_pages
        }
        
        return {k: v for k, v in fetch_params.items() if v is not None}


@api_view(['GET'])
def parse_hh_api(request):
    """API endpoint для запуска задачи парсинга стажировок с HeadHunter"""
    keywords = request.GET.get('keywords')
    area = request.GET.get('area')
    
    import threading
    params = {'keywords': keywords, 'area': area}
    params = {k: v for k, v in params.items() if v is not None}
    
    thread = threading.Thread(target=_run_hh_parser_thread, args=(params,))
    thread.daemon = True
    thread.start()
    
    return Response({
        'status': 'success', 
        'message': 'Задача запущена. Стажировки с HeadHunter будут загружены и добавлены в базу данных.'
    }, status=status.HTTP_202_ACCEPTED)

def _run_hh_parser_thread(params):
    """Выполнение парсинга HeadHunter в отдельном потоке"""
    try:
        from .tasks import parse_hh_internships
        result = parse_hh_internships(**params)
        logger.info(f"Результат получения стажировок с HeadHunter: {result}")
    except Exception as e:
        logger.error(f"Ошибка при выполнении задачи получения стажировок с HeadHunter: {e}", exc_info=True)


@api_view(['GET'])
def parse_habr_api(request):
    """API endpoint для запуска задачи парсинга стажировок с Habr Career"""
    city = request.GET.get('city')
    location_id = request.GET.get('location_id')
    
    import threading
    params = {'city': city, 'location_id': location_id}
    params = {k: v for k, v in params.items() if v is not None}
    
    thread = threading.Thread(target=_run_habr_parser_thread, args=(params,))
    thread.daemon = True
    thread.start()
    
    return Response({
        'status': 'success', 
        'message': 'Задача запущена. Стажировки с Habr Career будут загружены и добавлены в базу данных.'
    }, status=status.HTTP_202_ACCEPTED)

def _run_habr_parser_thread(params):
    """Выполнение парсинга Habr Career в отдельном потоке"""
    try:
        from .tasks import parse_habr_internships
        result = parse_habr_internships(**params)
        logger.info(f"Результат получения стажировок с Habr Career: {result}")
    except Exception as e:
        logger.error(f"Ошибка при выполнении задачи получения стажировок с Habr Career: {e}", exc_info=True)


@api_view(['GET'])
def internship_list_api(request):
    """Получение списка стажировок"""
    queryset = Internship.objects.all()
    serializer = InternshipSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def internship_detail_api(request, pk):
    """Получение деталей стажировки по ID"""
    try:
        internship = Internship.objects.get(pk=pk)
    except Internship.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    
    serializer = InternshipSerializer(internship)
    return Response(serializer.data)


@api_view(['GET'])
def search_internships(request):
    """API для поиска стажировок"""
    city = request.query_params.get('city')
    keywords = request.query_params.get('keywords')
    
    if city or keywords:
        SearchQuery.record_search(city=city, keywords=keywords)
    
    queryset = Internship.objects.filter(is_archived=False)
    
    if city:
        queryset = queryset.filter(city__icontains=city)
    
    if keywords:
        queryset = queryset.filter(
            Q(title__icontains=keywords) | 
            Q(position__icontains=keywords) | 
            Q(description__icontains=keywords) |
            Q(keywords__icontains=keywords)
        )
    
    serializer = InternshipSerializer(queryset, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def get_stats_api(request):
    """Получение статистики по стажировкам"""
    total_count = Internship.objects.count()
    active_count = Internship.objects.filter(is_archived=False).count()
    archived_count = Internship.objects.filter(is_archived=True).count()
    
    by_website = {}
    websites = Website.objects.all()
    for website in websites:
        count = Internship.objects.filter(source_website=website).count()
        by_website[website.name] = count
    
    return Response({
        'total': total_count,
        'active': active_count,
        'archived': archived_count,
        'by_website': by_website
    })


class FetchSuperJobInternshipsAPIView(APIView):
    """API endpoint для получения стажировок с SuperJob"""
    
    @extend_schema(
        description="Запуск задачи для получения стажировок с SuperJob по ключевым словам, городу и другим параметрам.",
        parameters=[
            OpenApiParameter('keywords', OpenApiTypes.STR, description="Ключевые слова для поиска"),
            OpenApiParameter('city', OpenApiTypes.STR, description="Название города для поиска (например, 'Москва', 'Санкт-Петербург')"),
            OpenApiParameter('town', OpenApiTypes.INT, description="ID города (используется, если не указан параметр city)"),
            OpenApiParameter('max_pages', OpenApiTypes.INT, description="Максимальное количество страниц", default=10),
        ],
        responses={202: {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "message": {"type": "string"}
            }
        }}
    )
    def get(self, request):
        """Запуск задачи получения списка стажировок с SuperJob"""
        params = self._prepare_params(request)
        
        try:
            logger.info(f"Выполнение получения стажировок с SuperJob в многопоточном режиме")
            
            superjob_website, created = Website.objects.get_or_create(
                name="SuperJob",
                url="https://www.superjob.ru/",
            )
            
            import threading
            thread = threading.Thread(target=self._run_superjob_parser, args=(params,))
            thread.daemon = True
            thread.start()
            
            return Response({
                'status': 'success', 
                'message': 'Задача запущена. Стажировки будут загружены и добавлены в базу данных.'
            }, status=status.HTTP_202_ACCEPTED)
                
        except Exception as e:
            logger.error(f"Ошибка при получении стажировок с SuperJob: {e}", exc_info=True)
            return Response({
                'status': 'error', 
                'message': 'Произошла внутренняя ошибка сервера при получении данных.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _run_superjob_parser(self, params):
        """Выполнение получения стажировок с SuperJob"""
        try:
            from .tasks import parse_superjob_internships
            result = parse_superjob_internships(**params)
            logger.info(f"Результат получения стажировок с SuperJob: {result}")
        except Exception as e:
            logger.error(f"Ошибка при выполнении задачи получения стажировок с SuperJob: {e}", exc_info=True)
    
    def _prepare_params(self, request):
        """Подготовка параметров для API запроса"""
        keywords = request.GET.get('keywords', None)
        city = request.GET.get('city', None)
        town = request.GET.get('town', None)
        max_pages = request.GET.get('max_pages', 10)
        
        try:
            max_pages = int(max_pages)
        except (ValueError, TypeError):
            max_pages = 10
            
        logger.info(f"Запрос на получение стажировок с SuperJob: keywords='{keywords}', city='{city}', town='{town}', max_pages={max_pages}")
        
        fetch_params = {
            'keywords': keywords,
            'city': city,
            'town': town,
            'max_pages': max_pages
        }
        
        return {k: v for k, v in fetch_params.items() if v is not None}


class FetchAllInternshipsAPIView(APIView):
    """API endpoint для получения стажировок со всех источников"""
    
    @extend_schema(
        description="Запуск задачи для одновременного получения стажировок с HeadHunter, Habr Career и SuperJob.",
        parameters=[
            OpenApiParameter('city', OpenApiTypes.STR, description="Название города для поиска (например, 'Москва', 'Санкт-Петербург')"),
            OpenApiParameter('keywords', OpenApiTypes.STR, description="Ключевые слова для поиска (используется для всех источников)"),
            OpenApiParameter('max_pages', OpenApiTypes.INT, description="Максимальное количество страниц", default=10),
        ],
        responses={202: {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "message": {"type": "string"}
            }
        }}
    )
    def get(self, request):
        """Запуск задачи параллельного получения стажировок со всех источников"""
        params = self._prepare_params(request)
        
        try:
            logger.info(f"Выполнение получения стажировок со всех источников в многопоточном режиме")
            
            city = params.get('city')
            keywords = params.get('keywords')
            max_pages = params.get('max_pages', 10)
            
            if city or keywords:
                SearchQuery.record_search(city=city, keywords=keywords, max_pages=max_pages)
            
            import threading
            thread = threading.Thread(target=self._run_all_parsers, args=(params,))
            thread.daemon = True
            thread.start()
            
            return Response({
                'status': 'success',
                'message': 'Задача запущена. Стажировки будут загружены и добавлены в базу данных.'
            }, status=status.HTTP_202_ACCEPTED)
                
        except Exception as e:
            logger.error(f"Ошибка при запуске задачи парсинга: {e}", exc_info=True)
            return Response({
                'status': 'error', 
                'message': 'Произошла внутренняя ошибка сервера при запуске задачи.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _run_all_parsers(self, params):
        """Выполнение получения стажировок со всех источников"""
        try:
            city = params.get('city')
            keywords = params.get('keywords')
            max_pages = params.get('max_pages')
            
            results = {'hh': None, 'habr': None, 'superjob': None}
            
            hh_website, _ = Website.objects.get_or_create(
                name="HeadHunter",
                defaults={"url": "https://hh.ru/"}
            )
            habr_website, _ = Website.objects.get_or_create(
                name="Habr Career",
                defaults={"url": "https://career.habr.com/"}
            )
            superjob_website_obj, _ = Website.objects.get_or_create(
                name="SuperJob",
                defaults={"url": "https://www.superjob.ru/"}
            )
            
            def fetch_hh():
                try:
                    internships = fetch_hh_internships(city=city, keywords=keywords, max_pages=max_pages)
                    logger.info(f"Получено {len(internships)} словарей стажировок с HeadHunter.")
                    results['hh'] = internships
                except Exception as e:
                    logger.error(f"Ошибка при получении стажировок с HeadHunter: {str(e)}")
                    results['hh'] = []
            
            def fetch_habr():
                try:
                    internships = fetch_habr_career_internships(city=city, keywords=keywords, max_pages=max_pages)
                    logger.info(f"Получено {len(internships)} словарей стажировок с Habr Career.")
                    results['habr'] = internships
                except Exception as e:
                    logger.error(f"Ошибка при получении стажировок с Habr Career: {str(e)}")
                    results['habr'] = []
                    
            def fetch_superjob_task():
                try:
                    processed_internship_objects = fetch_superjob_internships(city=city, keywords=keywords, max_pages=max_pages, website_obj=superjob_website_obj)
                    logger.info(f"Получено {len(processed_internship_objects)} объектов стажировок с SuperJob.")
                    results['superjob'] = processed_internship_objects
                except Exception as e:
                    logger.error(f"Ошибка при получении стажировок с SuperJob: {str(e)}")
                    results['superjob'] = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                hh_future = executor.submit(fetch_hh)
                habr_future = executor.submit(fetch_habr)
                superjob_future = executor.submit(fetch_superjob_task)
                
                concurrent.futures.wait([hh_future, habr_future, superjob_future])
            
            hh_internships_data = results['hh'] or []
            habr_internships_data = results['habr'] or []
            superjob_internship_objects = results['superjob'] or []
            
            hh_client = HeadHunterAPI()
            habr_client = HabrCareerParser()
            
            stats = {
                'hh': {'total': len(hh_internships_data), 'created': 0, 'updated': 0, 'errors': 0},
                'habr': {'total': len(habr_internships_data), 'created': 0, 'updated': 0, 'errors': 0},
                'superjob': {'total': len(superjob_internship_objects), 'created': 0, 'updated': 0, 'errors': 0}
            }
            
            for internship_data in hh_internships_data:
                obj, is_created = hh_client.create_internship(internship_data, hh_website)
                if obj:
                    if is_created:
                        stats['hh']['created'] += 1
                    else:
                        stats['hh']['updated'] += 1
                else:
                    stats['hh']['errors'] +=1
            
            for internship_data in habr_internships_data:
                if isinstance(internship_data, Internship):
                    if internship_data.id is None:  
                        stats['habr']['created'] += 1
                    else:
                        stats['habr']['updated'] += 1
                else:
                    obj, is_created = habr_client.create_internship(internship_data, habr_website)
                    if obj:
                        if is_created:
                            stats['habr']['created'] += 1
                        else:
                            stats['habr']['updated'] += 1
                    else:
                        stats['habr']['errors'] +=1
                    
            for internship_obj in superjob_internship_objects:
                if isinstance(internship_obj, Internship):
                    if internship_obj.id is None:
                        stats['superjob']['created'] += 1
                    else:
                        stats['superjob']['updated'] += 1
                else:
                    try:
                        sj_client = SuperJobParser()
                        obj, is_created = sj_client.create_internship(internship_obj, superjob_website_obj)
                        if obj:
                            if is_created:
                                stats['superjob']['created'] += 1
                            else:
                                stats['superjob']['updated'] += 1
                        else:
                            stats['superjob']['errors'] += 1
                    except Exception as e:
                        logger.error(f"Ошибка при создании/обновлении стажировки SuperJob: {str(e)}")
                        stats['superjob']['errors'] += 1
            
            total_processed = stats['hh']['created'] + stats['hh']['updated'] + \
                              stats['habr']['created'] + stats['habr']['updated'] + \
                              stats['superjob']['created'] + stats['superjob']['updated']
            logger.info(f"Параллельно обработано стажировок: HH (создано {stats['hh']['created']}, обновлено {stats['hh']['updated']}), "
                        f"Habr (создано {stats['habr']['created']}, обновлено {stats['habr']['updated']}), "
                        f"SuperJob (создано {stats['superjob']['created']}, обновлено {stats['superjob']['updated']}). "
                        f"Всего обработано: {total_processed}")
        except Exception as e:
            logger.error(f"Ошибка при выполнении задачи получения стажировок со всех источников: {e}", exc_info=True)
    
    def _prepare_params(self, request):
        """Подготовка параметров для API запроса"""
        city = request.GET.get('city', None)
        keywords = request.GET.get('keywords', None)
        max_pages = request.GET.get('max_pages', 10)
        
        try:
            max_pages = int(max_pages)
        except (ValueError, TypeError):
            max_pages = 10
            
        logger.info(f"Запрос на получение стажировок со всех источников: city='{city}', keywords='{keywords}', max_pages={max_pages}")
        
        fetch_params = {
            'city': city,
            'keywords': keywords,
            'max_pages': max_pages,
        }
        
        return {k: v for k, v in fetch_params.items() if v is not None}


class ParseUniversalURLAPIView(APIView):
    """API endpoint для запуска задачи парсинга по URL."""
    
    @extend_schema(
        description="Запуск задачи парсинга стажировки по указанному URL.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'format': 'url'}
                },
                'required': ['url']
            }
        },
        examples=[
            OpenApiExample(
                'Пример запроса',
                summary='Запрос на парсинг стажировки с example.com',
                value={'url': 'https://example.com/internship-details'}
            ),
        ],
        responses={
            202: {
                "description": "Задача парсинга успешно запущена.",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string", "example": "success"},
                                "message": {"type": "string", "example": "Задача парсинга URL запущена."}
                            }
                        }
                    }
                }
            },
            400: {"description": "Неверный запрос (например, отсутствует URL)"},
            500: {"description": "Внутренняя ошибка сервера"}
        }
    )
    def post(self, request):
        """Запуск задачи парсинга URL."""
        url = request.data.get('url')
        if not url:
            return Response({'error': 'URL is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info(f"Выполнение парсинга URL {url} в многопоточном режиме")
            
            thread = threading.Thread(target=self._run_universal_parser, args=(url,))
            thread.daemon = True
            thread.start()
            
            return Response({
                'status': 'success', 
                'message': 'Задача парсинга URL запущена.'
            }, status=status.HTTP_202_ACCEPTED)
                
        except Exception as e:
            logger.error(f"Ошибка при парсинге URL {url}: {e}", exc_info=True)
            return Response({
                'status': 'error', 
                'message': 'Произошла внутренняя ошибка сервера при парсинге URL.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _run_universal_parser(self, url):
        """Выполнение парсинга URL в отдельном потоке."""
        try:
            parser = UniversalParser(url)
            parser.parse()
            logger.info(f"Успешно спарсен и сохранен URL: {url}")
        except Exception as e:
            logger.error(f"Ошибка при выполнении парсинга URL {url}: {e}", exc_info=True)


class PreviewInternshipAPIView(APIView):
    """
    API endpoint для предварительного парсинга URL и получения данных стажировки.
    Не сохраняет данные в базу, а только возвращает их.
    """
    @extend_schema(
        description="Предварительный парсинг URL для извлечения данных стажировки.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string', 'format': 'url'}
                },
                'required': ['url']
            }
        },
        examples=[
            OpenApiExample(
                'Пример запроса',
                summary='Запрос на предварительный парсинг стажировки с example.com',
                value={'url': 'https://example.com/internship-details'}
            ),
        ],
        responses={
            200: InternshipSerializer,
            400: {
                "description": "Неверный запрос (например, отсутствует URL или URL некорректен)",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {"type": "string"}
                            }
                        }
                    }
                }
            },
            500: {
                "description": "Внутренняя ошибка сервера или ошибка парсинга",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {"type": "string"},
                                "details": {"type": "string", "nullable": True}
                            }
                        }
                    }
                }
            }
        }
    )
    def post(self, request):
        """
        Обрабатывает POST-запрос с URL, парсит его и возвращает данные стажировки.
        """
        url = request.data.get('url')
        if not url:
            return Response({'error': 'URL is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info(f"Запрос на предварительный парсинг URL: {url}")
            parser = UniversalParser(url)
            internship_data = parser.extract_data()

            if not internship_data:
                logger.warning(f"Не удалось извлечь данные для URL: {url}")
                return Response(
                    {'error': 'Не удалось извлечь данные по указанному URL.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(internship_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Ошибка при предварительном парсинge URL {url}: {e}", exc_info=True)
            return Response(
                {'error': 'Произошла ошибка при парсинге URL.', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
def sync_webhook(request):
    """Вебхук для синхронизации стажировок"""
    city = request.data.get('city')
    keywords = request.data.get('keywords')
    max_pages = request.data.get('max_pages')
    
    if max_pages:
        try:
            max_pages = int(max_pages)
        except (ValueError, TypeError):
            max_pages = None
    
    logger.info(f"Запуск многопоточной синхронизации стажировок: city='{city}', keywords='{keywords}', max_pages={max_pages}")
    
    params = {
        'city': city, 
        'keywords': keywords, 
        'max_pages': max_pages
    }
    params = {k: v for k, v in params.items() if v is not None}
    
    import threading
    thread = threading.Thread(target=_run_parsers_in_thread, args=(params,))
    thread.daemon = True
    thread.start()
    
    message_parts = []
    if city:
        message_parts.append(f"для города {city}")
    if keywords:
        message_parts.append(f"по запросу '{keywords}'")
    if max_pages:
        message_parts.append(f"с лимитом {max_pages} страниц")
    
    message_suffix = f" {', '.join(message_parts)}" if message_parts else ""
    
    return Response({
        'status': 'success', 
        'message': f'Запущена многопоточная синхронизация стажировок{message_suffix}'
    }, status=status.HTTP_202_ACCEPTED)

def _run_parsers_in_thread(params):
    """Выполнение парсинга в отдельном потоке"""
    try:
        results = {'hh': None, 'habr': None, 'superjob': None}
        
        def fetch_hh():
            try:
                internships = fetch_hh_internships(**params)
                logger.info(f"Получено {len(internships)} стажировок с HeadHunter.")
                results['hh'] = internships
            except Exception as e:
                logger.error(f"Ошибка при получении стажировок с HeadHunter: {str(e)}")
                results['hh'] = []
        
        def fetch_habr():
            try:
                internships = fetch_habr_career_internships(**params)
                logger.info(f"Получено {len(internships)} стажировок с Habr Career.")
                results['habr'] = internships
            except Exception as e:
                logger.error(f"Ошибка при получении стажировок с Habr Career: {str(e)}")
                results['habr'] = []
                
        def fetch_superjob():
            try:
                internships = fetch_superjob_internships(**params)
                logger.info(f"Получено {len(internships)} стажировок с SuperJob.")
                results['superjob'] = internships
            except Exception as e:
                logger.error(f"Ошибка при получении стажировок с SuperJob: {str(e)}")
                results['superjob'] = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            hh_future = executor.submit(fetch_hh)
            habr_future = executor.submit(fetch_habr)
            superjob_future = executor.submit(fetch_superjob)
            
            concurrent.futures.wait([hh_future, habr_future, superjob_future])
        
        hh_internships = results['hh'] or []
        habr_internships = results['habr'] or []
        superjob_internships = results['superjob'] or []
        
        hh_website, _ = Website.objects.get_or_create(
            name="HeadHunter",
            url="https://hh.ru",
        )
        
        habr_website, _ = Website.objects.get_or_create(
            name="Habr Career",
            url="https://career.habr.com/",
        )
        
        superjob_website, _ = Website.objects.get_or_create(
            name="SuperJob",
            url="https://www.superjob.ru/",
        )
        
        hh_client = HeadHunterAPI()
        habr_client = HabrCareerParser()
        superjob_client = SuperJobParser()
        
        stats = {
            'hh': {'total': len(hh_internships), 'created': 0, 'updated': 0},
            'habr': {'total': len(habr_internships), 'created': 0, 'updated': 0},
            'superjob': {'total': len(superjob_internships), 'created': 0, 'updated': 0}
        }
        
        for internship_data in hh_internships:
            _, is_created = hh_client.create_internship(internship_data, hh_website)
            if is_created:
                stats['hh']['created'] += 1
            else:
                stats['hh']['updated'] += 1
        
        for internship_data in habr_internships:
            if isinstance(internship_data, Internship):
                if internship_data.id is None:  
                    stats['habr']['created'] += 1
                else:
                    stats['habr']['updated'] += 1
            else:
                obj, is_created = habr_client.create_internship(internship_data, habr_website)
                if obj:
                    if is_created:
                        stats['habr']['created'] += 1
                    else:
                        stats['habr']['updated'] += 1
                else:
                    stats['habr']['errors'] +=1
                    
        for internship_data in superjob_internships:
            if isinstance(internship_data, Internship):
                if internship_data.id is None:  
                    stats['superjob']['created'] += 1
                else:
                    stats['superjob']['updated'] += 1
            else:
                try:
                    _, is_created = superjob_client.create_internship(internship_data, superjob_website)
                    if is_created:
                        stats['superjob']['created'] += 1
                    else:
                        stats['superjob']['updated'] += 1
                except Exception as e:
                    logger.error(f"Ошибка при создании/обновлении стажировки SuperJob: {str(e)}")
        
        total_count = len(hh_internships) + len(habr_internships) + len(superjob_internships)
        logger.info(f"Параллельно обработано {total_count} стажировок через webhook")
    except Exception as e:
        logger.error(f"Ошибка при выполнении параллельного парсинга через webhook: {str(e)}") 