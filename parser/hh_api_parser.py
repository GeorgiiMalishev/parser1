import requests
import logging
import os
import re
from datetime import datetime, timedelta
from django.conf import settings
import time
from .constants import TECH_KEYWORDS

logger = logging.getLogger('parser')

class HeadHunterAPI:
    """Класс для работы с API HeadHunter"""
    
    BASE_URL = 'https://api.hh.ru/vacancies'
    
    def __init__(self, token=None, host="hh.ru"):
        """Инициализация API клиента"""
        self.token = token or settings.HH_API_TOKEN or os.getenv('HH_API_TOKEN')
        self.host = host
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'HH-User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 malishev292@gmail.com'
        }
        
        if self.token:
            self.headers['Authorization'] = f'Bearer {self.token}'
            logger.info("Используется токен авторизации для HeadHunter API")
        else:
            logger.warning("Токен авторизации для HeadHunter API не найден. Возможны ограничения в количестве запросов.")
    
    def search_internships(self, keywords=None, area=None, page=0, per_page=100, 
                          date_from=None, date_to=None, schedule=None, metro=None, 
                          professional_role=None, industry=None, only_with_salary=False, 
                          salary=None, currency=None, experience=None, 
                          part_time=None, accept_temporary=True, employment=None):
        """Поиск стажировок через API HeadHunter"""
        if page > 19 and per_page == 100:
            logger.warning("Ограничение API HeadHunter: невозможно получить более 2000 вакансий.")
            return {'items': [], 'found': 0, 'pages': 0, 'per_page': per_page, 'page': page}
        
        search_text = 'стажировка'
        if keywords:
            search_text += f' {keywords}'
            
        params = {
            'text': search_text.strip(),
            'page': page,
            'per_page': per_page
        }
        
        self._add_optional_params(params, {
            'experience': experience,
            'employment': employment,
            'area': area,
            'date_from': date_from,
            'date_to': date_to,
            'schedule': schedule,
            'metro': metro,
            'professional_role': professional_role,
            'industry': industry,
            'salary': salary,
            'currency': currency
        })
        
        if only_with_salary:
            params['only_with_salary'] = 'true'
        
        try:
            logger.info(f"Отправка запроса к API HeadHunter с параметрами: {params}")
            response = requests.get(self.BASE_URL, params=params, headers=self.headers)
            
            logger.info(f"URL запроса: {response.url}")
            
            if response.status_code == 403:
                logger.warning("Получен код 403: API HeadHunter требует ввода капчи или ограничивает доступ")
                return {'items': [], 'found': 0, 'pages': 0, 'per_page': per_page, 'page': page}
            
            elif response.status_code == 400:
                logger.error(f"Неверный запрос (400): {response.text}")
                return {'items': [], 'found': 0, 'pages': 0, 'per_page': per_page, 'page': page}
            
            elif response.status_code != 200:
                error_msg = f"API вернул код ошибки {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {'items': [], 'found': 0, 'pages': 0, 'per_page': per_page, 'page': page}
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к API HeadHunter: {str(e)}")
            return {'items': [], 'found': 0, 'pages': 0, 'per_page': per_page, 'page': page}

    def _add_optional_params(self, params, options_dict):
        """Добавляет непустые параметры в словарь params"""
        for key, value in options_dict.items():
            if value:
                params[key] = value
    
    def get_all_internships(self, keywords=None, area=None, max_pages=20, **kwargs):
        """Получение всех доступных стажировок с учетом пагинации"""
        all_vacancies = []
        page = 0
        
        if max_pages > 20:
            logger.warning("API HeadHunter ограничивает глубину результатов до 2000. Максимум 20 страниц по 100 вакансий.")
            max_pages = 20
        
        while True:
            logger.info(f"Загрузка стажировок с HeadHunter: страница {page+1}")
            result = self.search_internships(keywords, area, page, per_page=100, **kwargs)
            
            if not result or not result.get('items'):
                logger.warning(f"Не удалось получить данные со страницы {page+1} или страница пуста")
                if page == 0:
                    logger.error("Не удалось получить ни одной стажировки с HeadHunter")
                break
                
            all_vacancies.extend(result['items'])
            logger.info(f"Получено {len(result['items'])} стажировок с страницы {page+1}")
            
            total_pages = result.get('pages', 0)
            logger.info(f"Всего доступно страниц: {total_pages}")
            
            if page >= total_pages - 1 or page >= max_pages - 1:
                logger.info(f"Достигнут конец данных или ограничение на количество страниц")
                break
            
            page += 1
            time.sleep(2)
        
        logger.info(f"Загружено {len(all_vacancies)} стажировок с HeadHunter")
        return all_vacancies
    
    def parse_vacancy_details(self, vacancy_id):
        """Получение подробной информации о вакансии по её ID"""
        try:
            response = requests.get(f'https://api.hh.ru/vacancies/{vacancy_id}', headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении деталей вакансии {vacancy_id}: {str(e)}")
            raise Exception(f"Ошибка при получении деталей вакансии: {str(e)}")
            
    def convert_to_internship_data(self, vacancy):
        """Преобразование данных вакансии из API в унифицированный формат"""
        try:
            employment_type = 'office'
            if 'удаленн' in vacancy.get('name', '').lower() or 'удаленн' in vacancy.get('description', '').lower():
                employment_type = 'remote'
            elif vacancy.get('schedule', {}).get('id') == 'remote':
                employment_type = 'remote'
            elif vacancy.get('schedule', {}).get('id') == 'flexible':
                employment_type = 'hybrid'
                
            keywords_list = []
            
            if vacancy.get('key_skills'):
                keywords_list = [skill.get('name') for skill in vacancy.get('key_skills', [])]
            
            if not keywords_list and vacancy.get('description'):
                description = vacancy.get('description', '')
                extracted_keywords = []
                for tech in TECH_KEYWORDS:
                    if tech.lower() in description.lower():
                        extracted_keywords.append(tech)
                keywords_list = extracted_keywords if extracted_keywords else ['стажировка']
                
            city = None
            if vacancy.get('area', {}).get('name'):
                city = vacancy.get('area', {}).get('name')
                
            selection_start_date = None
            selection_end_date = None
            
            if vacancy.get('published_at'):
                try:
                    published_date = datetime.fromisoformat(vacancy.get('published_at').replace('Z', '+00:00'))
                    selection_start_date = published_date.date()
                    selection_end_date = (published_date + timedelta(days=30)).date()
                except (ValueError, TypeError):
                    pass
            
            salary = None
            if vacancy.get('salary'):
                if vacancy.get('salary').get('from') and vacancy.get('salary').get('to'):
                    salary = f"{vacancy.get('salary').get('from')} - {vacancy.get('salary').get('to')} {vacancy.get('salary').get('currency', 'RUB')}"
                elif vacancy.get('salary').get('from'):
                    salary = f"от {vacancy.get('salary').get('from')} {vacancy.get('salary').get('currency', 'RUB')}"
                elif vacancy.get('salary').get('to'):
                    salary = f"до {vacancy.get('salary').get('to')} {vacancy.get('salary').get('currency', 'RUB')}"
                    
            result = {
                'external_id': vacancy.get('id'),
                'title': vacancy.get('name', 'Не указано'),
                'company': vacancy.get('employer', {}).get('name', 'Не указано'),
                'position': vacancy.get('professional_roles', [{}])[0].get('name', 'Стажер') if vacancy.get('professional_roles') else 'Стажер',
                'salary': salary,
                'description': self._clean_html_tags(vacancy.get('description', '')),
                'keywords': ', '.join(keywords_list),
                'employment_type': employment_type,
                'city': city,
                'url': vacancy.get('alternate_url', ''),
                'selection_start_date': selection_start_date,
                'selection_end_date': selection_end_date,
                'duration': None,
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при преобразовании данных вакансии: {str(e)}")
            return {
                'title': 'Ошибка обработки',
                'company': 'Неизвестно',
                'position': 'Ошибка обработки',
                'description': 'Произошла ошибка при обработке данных',
                'url': ''
            }
    
    def _clean_html_tags(self, html_text):
        """Удаляет HTML-теги из текста"""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', html_text)
        
    def create_internship(self, data, website):
        """Создание или обновление стажировки в базе данных"""
        from .models import Internship
        external_id = data.get('external_id')
        
        if external_id:
            internship = Internship.objects.filter(external_id=external_id).first()
            
            if internship:
                for key, value in data.items():
                    if hasattr(internship, key):
                        setattr(internship, key, value)
                internship.source_website = website
                internship.save()
                return internship, False
        
        internship = Internship(
            external_id=data.get('external_id'),
            title=data.get('title', 'Не указано'),
            company=data.get('company', 'Не указано'),
            position=data.get('position', 'Стажер'),
            salary=data.get('salary'),
            description=data.get('description', ''),
            keywords=data.get('keywords', ''),
            employment_type=data.get('employment_type', 'office'),
            city=data.get('city', ''),
            url=data.get('url', ''),
            source_website=website,
            selection_start_date=data.get('selection_start_date'),
            selection_end_date=data.get('selection_end_date'),
            duration=data.get('duration')
        )
        internship.save()
        return internship, True


def fetch_hh_internships(keywords=None, area=None, **kwargs):
    """Получение списка стажировок через API HeadHunter"""
    try:
        client = HeadHunterAPI()
        vacancies = client.get_all_internships(keywords, area, **kwargs)
        
        if not vacancies:
            logger.warning("Не найдено стажировок по заданным критериям")
            return []
        
        result = []
        
        for vacancy in vacancies:
            vacancy_name = vacancy.get('name', '').lower()
            try:
                vacancy_details = client.parse_vacancy_details(vacancy['id'])
                internship_data = client.convert_to_internship_data(vacancy_details)
            except Exception:
                internship_data = client.convert_to_internship_data(vacancy)
            
            result.append(internship_data)
            
        logger.info(f"Получено {len(result)} стажировок через API HeadHunter")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при получении стажировок: {str(e)}")
        return []
