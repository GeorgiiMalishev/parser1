import logging
from django.utils import timezone
from .models import Internship
from .hh_api_parser import fetch_hh_internships
from .habr_parser import fetch_habr_career_internships
from .superjob_parser import fetch_superjob_internships, SuperJobParser
from .models import Website
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger('parser')

def run_all_parsers():
    """Заглушка функции запуска всех парсеров"""
    logger.info("Функция запуска всех парсеров отключена")
    return False

def run_hh_api_parser():
    """Заглушка функции запуска парсера HeadHunter через API"""
    logger.info("Функция парсера HeadHunter API отключена")
    return False

def cleanup_old_internships():
    """Заглушка функции перемещения устаревших стажировок в архив"""
    logger.info("Функция архивации устаревших стажировок отключена")
    return 0

def parse_hh_internships(keywords=None, area=None, city=None, max_pages=20):
    """Функция для получения стажировок с HeadHunter
    
    Args:
        keywords (str, optional): Ключевые слова для поиска
        area (str, optional): ID региона
        city (str, optional): Название города (имеет приоритет над area)
        max_pages (int, optional): Максимальное количество страниц для загрузки. По умолчанию 20.
    """
    try:
        hh_website, created = Website.objects.get_or_create(
            name="HeadHunter",
            defaults={"url": "https://hh.ru/"}
        )
        
        from .hh_api_parser import HeadHunterAPI
        
        internships = fetch_hh_internships(
            keywords=keywords, 
            area=area, 
            city=city, 
            max_pages=max_pages,
            website_obj=hh_website
        )
        
        count_created = 0
        count_updated = 0
        
        for internship in internships:
            if isinstance(internship, Internship):
                if internship.id is None:
                    count_created += 1
                else:
                    count_updated += 1
        
        result_msg = f"Успешно обработано {len(internships)} стажировок с HeadHunter. Создано: {count_created}, обновлено: {count_updated}"
        logger.info(result_msg)
        return result_msg
    
    except Exception as e:
        error_msg = f"Ошибка при выполнении задачи парсинга стажировок с HeadHunter: {str(e)}"
        logger.error(error_msg)
        return error_msg

def parse_habr_internships(location_id=None, city=None, keywords=None, max_pages=10):
    """Функция для получения стажировок с Habr Career
    
    Args:
        location_id (str, optional): ID локации для поиска (передается в fetch_habr_career_internships)
        city (str, optional): Название города для поиска (имеет приоритет над location_id)
        keywords (str, optional): Ключевые слова для поиска вакансий
        max_pages (int, optional): Максимальное количество страниц для загрузки. По умолчанию 10.
    """
    try:
        habr_website, created = Website.objects.get_or_create(
            name="Habr Career",
            defaults={"url": "https://career.habr.com/"}
        )
        
    
        processed_internships = fetch_habr_career_internships(
            keywords_query=keywords, 
            city_name=city, 
            max_pages=max_pages, 
            location_id=location_id,
            website_obj=habr_website 
        )
        
        num_processed = len(processed_internships)
        
        result_msg = f"Успешно обработано {num_processed} стажировок с Habr Career. Детали создания/обновления см. в логах парсера."
        logger.info(result_msg)
        return result_msg
    
    except Exception as e:
        error_msg = f"Ошибка при выполнении задачи парсинга стажировок с Habr Career: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg

def parse_superjob_internships(town=None, city=None, keywords=None, max_pages=10):
    """Функция для получения стажировок с SuperJob
    
    Args:
        town (int, optional): ID города
        city (str, optional): Название города (имеет приоритет над town)
        keywords (str, optional): Ключевые слова для поиска
        max_pages (int, optional): Максимальное количество страниц для загрузки. По умолчанию 10.
    """
    try:
        superjob_website, created = Website.objects.get_or_create(
            name="SuperJob",
            defaults={"url": "https://www.superjob.ru/"}
        )
        
        internships = fetch_superjob_internships(city=city, keywords=keywords, max_pages=max_pages, website_obj=superjob_website)
        
        count_created = 0
        count_updated = 0
        
        client = SuperJobParser() 
        for internship_data_dict in internships: 
            if isinstance(internship_data_dict, Internship):
                internship_obj = internship_data_dict
                action = "Обновлена (уже объект)" 
                is_created = False 
                
                existing_internship = Internship.objects.filter(external_id=internship_obj.external_id, source_website=superjob_website).first()
                if existing_internship:
                    pass
                else:
                    is_created = True 
            
            elif isinstance(internship_data_dict, dict):
                internship_obj, is_created = client.create_internship(internship_data_dict, superjob_website)
            else:
                logger.warning(f"Неизвестный тип данных для стажировки SuperJob: {type(internship_data_dict)}")
                continue

            if internship_obj:
                if is_created:
                    count_created += 1
                else:
                    count_updated += 1
            
        result_msg = f"Успешно обработано {len(internships)} стажировок с SuperJob. Создано: {count_created}, обновлено: {count_updated}"
        logger.info(result_msg)
        return result_msg
    
    except Exception as e:
        error_msg = f"Ошибка при выполнении задачи парсинга стажировок с SuperJob: {str(e)}"
        logger.error(error_msg)
        return error_msg

def parse_all_internships(city=None, keywords=None, max_pages=10):
    """Функция для параллельного получения стажировок со всех источников
    
    Args:
        city (str, optional): Название города для поиска
        keywords (str, optional): Ключевые слова для поиска
        max_pages (int, optional): Максимальное количество страниц для загрузки. По умолчанию 10.
    """
    logger.info(f"Запуск многопоточного парсинга стажировок")
    
    hh_params = {'city': city, 'keywords': keywords, 'max_pages': max_pages}
    habr_params = {'city': city, 'keywords': keywords, 'max_pages': max_pages}
    superjob_params = {'city': city, 'keywords': keywords, 'max_pages': max_pages}
    
    import concurrent.futures
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_hh = executor.submit(parse_hh_internships, **hh_params)
        future_habr = executor.submit(parse_habr_internships, **habr_params)
        future_superjob = executor.submit(parse_superjob_internships, **superjob_params)
        
        results['hh'] = future_hh.result()
        results['habr'] = future_habr.result()
        results['superjob'] = future_superjob.result()
    
    return results

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
    
    params = {'city': city, 'keywords': keywords, 'max_pages': max_pages}
    
    import threading
    
    threads = []
    
    t1 = threading.Thread(target=parse_hh_internships, kwargs=params)
    t2 = threading.Thread(target=parse_habr_internships, kwargs=params)
    t3 = threading.Thread(target=parse_superjob_internships, kwargs=params)
    
    t1.start()
    t2.start()
    t3.start()
    
    threads.append(t1)
    threads.append(t2)
    threads.append(t3)
    
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