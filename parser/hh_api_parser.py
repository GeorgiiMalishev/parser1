import requests
import logging
import os
import re
import json
import random
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
import time
from .constants import TECH_KEYWORDS
from .base_parser import BaseParser
from .models import Internship, Website
from .internship_service import InternshipService
from django.db import transaction

logger = logging.getLogger('parser')

class HeadHunterAPI(BaseParser):
    BASE_URL = 'https://api.hh.ru/vacancies'

    def __init__(self, token=None, host="hh.ru"):
        super().__init__()
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

    def handle_auth_error(self, response, retry_count=0, max_retries=2):
        if retry_count >= max_retries:
            logger.warning(f"Достигнуто максимальное количество попыток ({max_retries}) обновления токена")
            return False
        if response.status_code in (401, 403):
            error_text = response.text
            error_json = {}
            try:
                error_json = response.json()
            except:
                pass
            token_related_error = False
            if error_json.get('error') in ('invalid_token', 'expired_token'):
                token_related_error = True
            elif 'token' in error_text.lower() and ('expired' in error_text.lower() or 'invalid' in error_text.lower()):
                token_related_error = True
            if token_related_error or response.status_code == 401:
                logger.info(f"Обнаружена ошибка авторизации: {response.status_code} - {error_text}")
                return False
            elif response.status_code == 403:
                logger.warning(f"Получена ошибка доступа 403: {error_text}")
                return False
        return False

    def make_authenticated_request(self, url, params=None, method='get', data=None, max_retries=2):
        retry_count = 0

        while retry_count <= max_retries:
            try:
                if method.lower() == 'get':
                    response = requests.get(url, params=params, headers=self.headers)
                elif method.lower() == 'post':
                    response = requests.post(url, params=params, data=data, headers=self.headers)
                else:
                    logger.error(f"Неподдерживаемый метод запроса: {method}")
                    return None
                if response.status_code in (401, 403):
                    if self.handle_auth_error(response, retry_count, max_retries):
                        retry_count += 1
                        logger.info(f"Повторная попытка запроса #{retry_count}")
                        continue
                return response
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка при выполнении запроса: {str(e)}")
                retry_count += 1
                if retry_count <= max_retries:
                    logger.info(f"Повторная попытка запроса #{retry_count}")
                    time.sleep(2)
                else:
                    logger.error(f"Превышено максимальное количество попыток ({max_retries})")
                    return None
        return None

    def search_internships(self, keywords=None, area=None, page=0, per_page=100,
                          date_from=None, date_to=None, schedule=None, metro=None,
                          professional_role=None, industry=None, only_with_salary=False,
                          salary=None, currency=None, experience=None,
                          part_time=None, accept_temporary=True, employment=None):
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
            response = self.make_authenticated_request(self.BASE_URL, params=params)
            if not response:
                return {'items': [], 'found': 0, 'pages': 0, 'per_page': per_page, 'page': page}
            logger.info(f"URL запроса: {response.url}")
            if response.status_code == 403:
                logger.warning("Получен код 403: API HeadHunter требует ввода капчи или ограничивает доступ")
                return {'items': [], 'found': 0, 'pages': 0, 'per_page': per_page, 'page': page, 'error_403': True}
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
        for key, value in options_dict.items():
            if value:
                params[key] = value

    def get_area_id_by_city(self, city_name):
        if not city_name:
            logger.warning("Название города не указано")
            return None
        try:
            logger.info(f"Поиск ID региона для города: {city_name}")
            response = self.make_authenticated_request('https://api.hh.ru/areas')
            if not response or response.status_code != 200:
                logger.error(f"Ошибка при получении списка регионов: {response.status_code if response else 'Нет ответа'}")
                return None
            areas_data = response.json()
            def search_area_by_name(areas, search_name):
                for area in areas:
                    if area.get('name', '').lower() == search_name.lower():
                        return area.get('id')
                    if area.get('areas'):
                        result = search_area_by_name(area.get('areas'), search_name)
                        if result:
                            return result
                return None
            area_id = search_area_by_name(areas_data, city_name)
            if area_id:
                logger.info(f"Найден ID региона для города {city_name}: {area_id}")
                return area_id
            else:
                logger.warning(f"Не удалось найти ID региона для города '{city_name}'")
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении ID региона по названию города '{city_name}': {str(e)}")
            return None

    def get_all_internships(self, keywords=None, area=None, max_pages=20, website_obj=None, **kwargs):
        all_vacancies = []
        page = 0
        if max_pages > 20:
            logger.warning("API HeadHunter ограничивает глубину результатов до 2000. Максимум 20 страниц по 100 вакансий.")
            max_pages = 20
        base_delay = 5
        max_retries = 3

        vacancies_to_process = []

        while True:
            retries = 0
            success = False
            while not success and retries <= max_retries:
                logger.info(f"Загрузка стажировок с HeadHunter: страница {page+1}")
                result = self.search_internships(keywords, area, page, per_page=100, **kwargs)
                if result.get('error_403'):
                    if retries < max_retries:
                        retries += 1
                        retry_delay = base_delay * (2 ** retries)
                        jitter = random.uniform(0.7, 1.3)
                        actual_delay = retry_delay * jitter
                        logger.warning(f"Получен код 403 при запросе страницы {page+1}. Повторная попытка через {actual_delay:.2f} секунд...")
                        time.sleep(actual_delay)
                    else:
                        logger.error(f"Не удалось получить данные со страницы {page+1} после {max_retries} попыток из-за ошибки 403")
                        success = True
                elif not result or not result.get('items'):
                    logger.warning(f"Не удалось получить данные со страницы {page+1} или страница пуста")
                    success = True
                else:
                    success = True
            if result.get('error_403') or not result or not result.get('items'):
                if page == 0:
                    logger.error("Не удалось получить ни одной стажировки с HeadHunter")
                break

            for vacancy in result['items']:
                basic_info = {
                    'external_id': vacancy.get('id'),
                    'title': vacancy.get('name', 'Не указано'),
                    'company': vacancy.get('employer', {}).get('name', 'Не указано'),
                    'url': vacancy.get('alternate_url', f"https://hh.ru/vacancy/{vacancy.get('id')}")
                }

                existing = None
                current_external_id = basic_info.get('external_id')

                logger.debug(f"[Check ID: {current_external_id}] Поиск существующей записи для ID: {current_external_id} (тип: {type(current_external_id)}), сайт: {website_obj.name if website_obj else 'None'}")

                if website_obj and current_external_id:
                    existing = InternshipService.get_existing_by_external_id(str(current_external_id), website_obj)

                logger.debug(f"[Check ID: {current_external_id}] Результат поиска: {'Найден объект Internship' if existing else 'None'}")

                should_process = False
                if not existing:
                    logger.debug(f"[Check ID: {current_external_id}] Причина обработки: Стажировка не найдена в БД (existing is None).")
                    should_process = True
                elif website_obj:
                    needs_update = InternshipService.should_update_internship(existing)
                    if needs_update:
                        logger.debug(f"[Check ID: {current_external_id}] Причина обработки: Требуется обновление (should_update_internship вернуло True).")
                        last_updated = existing.updated_at.strftime('%Y-%m-%d %H:%M:%S') if existing.updated_at else 'None'
                        seven_days_ago = (timezone.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                        logger.debug(f"[Check ID: {current_external_id}] Дата последнего обновления: {last_updated}, порог: {seven_days_ago}")
                        should_process = True
                    else:
                         logger.debug(f"[Check ID: {current_external_id}] Пропуск: Не требуется обновление (should_update_internship вернуло False).")
                         last_updated = existing.updated_at.strftime('%Y-%m-%d %H:%M:%S') if existing.updated_at else 'None'
                         logger.debug(f"[Check ID: {current_external_id}] Дата последнего обновления: {last_updated}, обновление не требуется.")
                else:
                    logger.warning(f"[Check ID: {current_external_id}] Пропуск: Не передан website_obj для проверки should_update_internship.")

                if should_process:
                    vacancies_to_process.append(vacancy)
                else:
                    logger.info(f"Пропуск обновления для вакансии {basic_info.get('title')} (ID: {current_external_id}) - обновлена недавно или не требует обновления")

            logger.info(f"Обработано {len(result['items'])} стажировок с страницы {page+1}, из них для детального парсинга отобрано {len(vacancies_to_process) - len(all_vacancies)}")

            total_pages = result.get('pages', 0)
            logger.info(f"Всего доступно страниц: {total_pages}")
            if page >= total_pages - 1 or page >= max_pages - 1:
                logger.info(f"Достигнут конец данных или ограничение на количество страниц")
                break
            page += 1
            jitter = random.uniform(0.8, 1.2)
            delay = base_delay * jitter
            logger.info(f"Ожидание {delay:.2f} секунд перед следующим запросом...")
            time.sleep(delay)

        logger.info(f"Всего отобрано {len(vacancies_to_process)} стажировок для детального парсинга")

        detailed_vacancies = []
        for i, vacancy in enumerate(vacancies_to_process):
            try:
                logger.info(f"Получение деталей вакансии {i+1}/{len(vacancies_to_process)}: {vacancy.get('id')}")
                vacancy_details = self.parse_vacancy_details(vacancy.get('id'))
                internship_data = self.convert_to_internship_data(vacancy_details)
                if internship_data:
                    detailed_vacancies.append(internship_data)

                if i < len(vacancies_to_process) - 1:
                    delay = random.uniform(1.0, 2.0)
                    time.sleep(delay)
            except Exception as e:
                logger.error(f"Ошибка при обработке вакансии {vacancy.get('id')}: {str(e)}")

        logger.info(f"Успешно получены детали {len(detailed_vacancies)} стажировок из {len(vacancies_to_process)} отобранных")
        return detailed_vacancies

    def parse_vacancy_details(self, vacancy_id):
        try:
            logger.info(f"Запрос детальной информации о вакансии {vacancy_id}")
            url = f'https://api.hh.ru/vacancies/{vacancy_id}'
            response = self.make_authenticated_request(url)
            if not response:
                logger.error(f"Ошибка при получении деталей вакансии {vacancy_id}: нет ответа")
                raise Exception(f"Ошибка при получении деталей вакансии: нет ответа")
            if response.status_code != 200:
                logger.error(f"Ошибка при получении деталей вакансии {vacancy_id}: {response.status_code} - {response.text}")
                raise Exception(f"Ошибка при получении деталей вакансии: {response.status_code}")
            return response.json()
        except Exception as e:
            logger.error(f"Ошибка при получении деталей вакансии {vacancy_id}: {str(e)}")
            raise

    def convert_to_internship_data(self, vacancy):
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
                'description': self.clean_description(vacancy.get('description', '')),
                'selection_status': 'open',
                'employment_type': employment_type,
                'url': vacancy.get('alternate_url', f"https://hh.ru/vacancy/{vacancy.get('id')}") ,
                'source': 'HeadHunter',
                'salary': salary,
                'city': city,
                'keywords': ', '.join(keywords_list) if keywords_list else 'стажировка',
                'selection_start_date': selection_start_date,
                'selection_end_date': selection_end_date,
            }
            return result
        except Exception as e:
            logger.error(f"Ошибка при преобразовании данных вакансии {vacancy.get('id', 'unknown')}: {str(e)}")
            return None

    def create_internship(self, data, website_obj):
        if not data:
            logger.warning("Попытка создать/обновить стажировку с пустыми данными.")
            return None, False

        if isinstance(data, Internship):
            logger.info(f"Возвращаем существующий объект Internship: {data.title} (ID: {data.id})")
            return data, False

        valid_keys = {f.name for f in Internship._meta.get_fields()}
        internship_data = {k: v for k, v in data.items() if k in valid_keys}

        return InternshipService.create_or_update(internship_data, website_obj)

def fetch_hh_internships(keywords=None, area=None, city=None, **kwargs):
    client = HeadHunterAPI()
    logger.info(f"Запуск парсинга стажировок с HeadHunter с параметрами: keywords={keywords}, city={city}")

    website_obj = kwargs.pop('website_obj', None)
    if not website_obj:
        website_obj, _ = Website.objects.get_or_create(
            name="HeadHunter",
            defaults={"url": "https://hh.ru/"}
        )

    if city and not area:
        area = client.get_area_id_by_city(city)
        if not area:
            logger.warning(f"Не удалось найти ID региона для города '{city}'. Поиск будет выполнен без фильтрации по региону.")

    vacancies = client.get_all_internships(keywords=keywords, area=area, website_obj=website_obj, **kwargs)
    logger.info(f"Получено {len(vacancies)} стажировок с HeadHunter")

    processed_internships = []
    for internship_data in vacancies:
        try:
            with transaction.atomic():
                internship, created = client.create_internship(internship_data, website_obj)
                if internship:
                    processed_internships.append(internship)
        except Exception as e:
            logger.error(f"Ошибка при обработке данных стажировки (данные: {str(internship_data)[:200]}...): {e}", exc_info=True)

    logger.info(f"Завершено получение стажировок с HeadHunter. Обработано {len(processed_internships)} стажировок.")
    return processed_internships
