import logging
logger = logging.getLogger(__name__)
logger.debug(f"ЗАПУСК МОДУЛЯ {__name__} С УРОВНEM DEBUG")

import requests
import os
import time
import random
from datetime import datetime, timedelta
from .base_parser import BaseParser
from .models import Internship, Website
from django.db.utils import IntegrityError
from .internship_service import InternshipService

class SuperJobParser(BaseParser):
    BASE_URL = 'https://api.superjob.ru/2.0'
    API_KEY = 'v3.r.139049002.f1b9adb6e0967c7e7bd25dd81f637165584e18f9.84bed1fa451f8b443b34afcbd5f60e49a3314491'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = {
            'X-Api-App-Id': self.API_KEY,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        if not self.API_KEY:
            logger.error("API ключ для SuperJob не найден. Парсинг невозможен.")
            raise ValueError("API ключ для SuperJob не сконфигурирован")

    def make_request(self, endpoint, params=None, method='get', data=None, max_retries=3):
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        retry_count = 0

        while retry_count <= max_retries:
            try:
                if method.lower() == 'get':
                    response = requests.get(url, params=params, headers=self.headers)
                elif method.lower() == 'post':
                    response = requests.post(url, json=data, headers=self.headers, params=params)
                else:
                    logger.error(f"Неподдерживаемый метод запроса: {method}")
                    return None

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 400:
                    logger.error(f"Ошибка 400 Bad Request для {url} с параметрами {params}: {response.text}")
                    return None
                elif response.status_code == 401 or response.status_code == 403:
                     logger.error(f"Ошибка авторизации/доступа ({response.status_code}) для {url}: {response.text}. Проверьте API ключ.")
                     return None
                elif response.status_code >= 500:
                    logger.warning(f"Серверная ошибка ({response.status_code}) для {url}. Попытка {retry_count + 1}/{max_retries + 1}")
                    if retry_count < max_retries:
                        time.sleep(2 ** retry_count)
                else:
                    logger.error(f"Ошибка API SuperJob {response.status_code} для {url}: {response.text}")
                    return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка при выполнении запроса к {url}: {str(e)}")

            retry_count += 1
            if retry_count > max_retries:
                logger.error(f"Превышено максимальное количество попыток ({max_retries}) для запроса к {url}")
                return None
        return None

    def search_internships(self, keywords_query=None, town=None, page=0, per_page=20, **kwargs):
        search_keyword_parts = ['стажировка']

        actual_keywords_query = keywords_query
        if not actual_keywords_query and 'keywords' in kwargs:
            actual_keywords_query = kwargs.get('keywords')

        if actual_keywords_query:
            search_keyword_parts.append(str(actual_keywords_query))

        params = {
            'keyword': ' '.join(search_keyword_parts),
            'experience': 1,
            'page': page,
            'count': per_page,
            'order_field': 'date',
            'order_direction': 'desc',
            'no_agreement': 1
        }

        if town:
            params['town'] = town

        allowed_kwargs_for_api = {
            'catalogues', 'payment_from', 'payment_to',
            'type_of_work', 'place_of_work', 'gender', 'education',
            'period',
            'town'
        }

        internal_params_handled_elsewhere = {'website_obj', 'max_pages', 'max_results', 'keywords'}

        for key, value in kwargs.items():
            if key in allowed_kwargs_for_api and value is not None:
                if key == 'town' and params.get('town') is not None and params.get('town') != value:
                    logger.warning(f"Параметр 'town' для SuperJob был передан и как именованный аргумент ('{params.get('town')}'), и через kwargs ('{value}'). Будет использовано значение из kwargs.")
                params[key] = value
            elif key not in allowed_kwargs_for_api and key not in internal_params_handled_elsewhere:
                 logger.warning(f"Параметр '{key}' (значение: '{value}') не поддерживается для API SuperJob в search_internships и будет проигнорирован.")

        logger.info(f"Отправка запроса к SuperJob API с параметрами: {params}")
        response_data = self.make_request('vacancies', params=params)

        if response_data:
            return {
                'items': response_data.get('objects', []),
                'found': response_data.get('total', 0),
                'pages': (response_data.get('total', 0) + per_page -1) // per_page if per_page > 0 else 0,
                'per_page': per_page,
                'page': page,
                'more': response_data.get('more', False)
            }
        return {'items': [], 'found': 0, 'pages': 0, 'per_page': per_page, 'page': page, 'more': False}

    def get_all_internships(self, keywords_query=None, town=None, max_results=200, max_pages=None, website_obj=None, **kwargs):
        all_vacancies = []
        page = 0
        per_page = 100

        base_delay = 1

        api_passthrough_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ['website_obj', 'max_pages', 'max_results', 'keywords']
        }
        if town:
            api_passthrough_kwargs['town'] = town

        current_keywords_query = keywords_query
        if not current_keywords_query and 'keywords' in kwargs:
            current_keywords_query = kwargs.get('keywords')

        vacancies_to_process = []

        while True:
            if max_pages is not None and page >= max_pages:
                logger.info(f"Достигнуто максимальное количество запрошенных страниц ({max_pages}) для SuperJob.")
                break

            logger.info(f"Загрузка стажировок с SuperJob: страница {page + 1}")
            result = self.search_internships(keywords_query=current_keywords_query,
                                           page=page,
                                           per_page=per_page,
                                           **api_passthrough_kwargs)

            if result and result.get('items'):
                for vacancy in result['items']:
                    basic_info = {
                        'external_id': str(vacancy.get('id')),
                        'title': vacancy.get('profession', 'Не указано'),
                        'company': vacancy.get('firm_name', 'Не указано'),
                        'url': vacancy.get('link', '')
                    }

                    existing = None
                    if website_obj and basic_info.get('external_id'):
                        existing = InternshipService.get_existing_by_external_id(basic_info['external_id'], website_obj)

                    if not existing or (website_obj and InternshipService.should_update_internship(existing)):
                        internship_data = self.convert_to_internship_data(vacancy)
                        if internship_data:
                            vacancies_to_process.append(internship_data)
                    else:
                        logger.info(f"Пропуск обновления для вакансии {basic_info.get('title')} (ID: {basic_info.get('external_id')}) - обновлена недавно")

                logger.info(f"Обработано {len(result['items'])} стажировок с страницы {page + 1} (SuperJob), для сохранения отобрано {len(vacancies_to_process)}")
                logger.info(f"Всего найдено по запросу (SuperJob): {result.get('found')}")

                if len(vacancies_to_process) >= max_results:
                    logger.info(f"Достигнуто максимальное количество результатов ({max_results}) для SuperJob.")
                    break

                if not result.get('more', False):
                    logger.info("Больше нет страниц для загрузки с SuperJob.")
                    break
                page += 1
            else:
                logger.warning(f"Не удалось получить данные со страницы {page + 1} (SuperJob) или страница пуста.")
                if page == 0 and not vacancies_to_process:
                    logger.error("Не удалось получить ни одной стажировки с SuperJob по текущему запросу.")
                break

            if page * per_page >= result.get('found', 0) and result.get('found',0) > 0 :
                 logger.info("Достигнут конец данных по общему количеству вакансий SuperJob.")
                 break

            jitter = random.uniform(0.8, 1.2)
            delay = base_delay * jitter
            logger.info(f"Ожидание {delay:.2f} секунд перед следующим запросом к SuperJob...")
            time.sleep(delay)

        logger.info(f"Отобрано {len(vacancies_to_process)} стажировок SuperJob для сохранения/обновления")
        return vacancies_to_process[:max_results]

    def convert_to_internship_data(self, vacancy):
        if not vacancy:
            return None
        try:
            vacancy_id = vacancy.get('id', 'unknown')
            logger.debug(f"[SuperJob convert_to_internship_data - ID: {vacancy_id}] Сырые данные для описания: work='{vacancy.get('work')}', candidat='{vacancy.get('candidat')}', compensation='{vacancy.get('compensation')}'")

            employment_type = 'office'
            description_text = f"{vacancy.get('work', '') or ''}\n{vacancy.get('candidat', '') or ''}\n{vacancy.get('compensation', '') or ''}"
            logger.debug(f"[SuperJob convert_to_internship_data - ID: {vacancy_id}] Сформированный description_text (до очистки): '{description_text[:200]}...'")

            cleaned_description = self.clean_description(description_text)
            logger.debug(f"[SuperJob convert_to_internship_data - ID: {vacancy_id}] Очищенный description (после clean_description): '{cleaned_description[:200]}...'")

            place_of_work_title = (vacancy.get('place_of_work', {}).get('title') or '').lower()
            profession_text = vacancy.get('profession', '')
            profession_lower = (profession_text or '').lower()

            work_text = vacancy.get('work', '')
            work_lower = (work_text or '').lower()

            if 'удаленн' in profession_lower or 'удаленн' in work_lower or 'на дому' in place_of_work_title:
                employment_type = 'remote'
            elif 'гибрид' in profession_lower or 'гибрид' in work_lower or 'разъездного характера' in place_of_work_title :
                 employment_type = 'hybrid'

            keywords_list = []
            if vacancy.get('profession'):
                keywords_list.append(vacancy.get('profession'))
            if vacancy.get('catalogues'):
                for cat in vacancy.get('catalogues', []):
                    keywords_list.append(cat.get('title'))
                    if cat.get('positions'):
                        for pos in cat.get('positions', []):
                            keywords_list.append(pos.get('title'))

            keywords_list = list(set(filter(None, keywords_list)))
            if not keywords_list:
                keywords_list = ['стажировка']

            city = vacancy.get('town', {}).get('title')

            selection_start_date = None
            selection_end_date = None
            if vacancy.get('date_published'):
                try:
                    published_timestamp = vacancy.get('date_published')
                    published_date = datetime.fromtimestamp(published_timestamp)
                    selection_start_date = published_date.date()
                    selection_end_date = (published_date + timedelta(days=30)).date()
                except (ValueError, TypeError):
                    logger.warning(f"Не удалось распарсить дату публикации для вакансии SJ {vacancy.get('id')}")
                    pass

            salary_str = None
            payment_from = vacancy.get('payment_from', 0)
            payment_to = vacancy.get('payment_to', 0)
            currency = vacancy.get('currency', 'rub').upper()
            agreement = vacancy.get('agreement', False)

            if not agreement:
                if payment_from > 0 and payment_to > 0:
                    salary_str = f"{payment_from} - {payment_to} {currency}"
                elif payment_from > 0:
                    salary_str = f"от {payment_from} {currency}"
                elif payment_to > 0:
                    salary_str = f"до {payment_to} {currency}"

            result = {
                'external_id': str(vacancy.get('id')),
                'title': vacancy.get('profession', 'Не указано'),
                'company': vacancy.get('firm_name', 'Не указано'),
                'position': vacancy.get('profession', 'Стажер'),
                'description': cleaned_description.strip(),
                'selection_status': 'open',
                'employment_type': employment_type,
                'url': vacancy.get('link'),
                'source': 'SuperJob',
                'salary': salary_str,
                'city': city,
                'keywords': ', '.join(keywords_list),
                'selection_start_date': selection_start_date,
                'selection_end_date': selection_end_date,
            }
            logger.debug(f"[SuperJob convert_to_internship_data - ID: {vacancy_id}] Итоговое поле description в result: '{result.get('description', '')[:200]}...'")
            return result
        except Exception as e:
            logger.error(f"Ошибка при преобразовании данных вакансии SuperJob {vacancy.get('id', 'unknown')}: {str(e)}", exc_info=True)
            return None

    def create_internship(self, internship_data, website):
        if not internship_data:
            logger.warning("Попытка создать/обновить стажировку с пустыми данными (SuperJob).")
            return None, False

        if isinstance(internship_data, Internship):
            logger.info(f"Возвращаем существующий объект Internship: {internship_data.title} (ID: {internship_data.id})")
            return internship_data, False

        if not internship_data.get('url'):
            logger.error(f"Отсутствует URL для вакансии SuperJob с external_id {internship_data.get('external_id')}. Сохранение невозможно.")
            return None, False

        original_url = internship_data['url']

        valid_keys = {f.name for f in Internship._meta.get_fields()}

        defaults_data = {k: v for k, v in internship_data.items() if k != 'url' and k != 'source_website' and k in valid_keys}
        defaults_data['source_website'] = website

        try:
            internship, created = Internship.objects.update_or_create(
                url=original_url,
                source_website=website,
                defaults=defaults_data
            )
            action = "Создана" if created else "Обновлена"
            logger.info(f"{action} стажировка (SuperJob): '{internship.title}' по URL {internship.url}")
            return internship, created
        except IntegrityError as e:
            if 'parser_internship_source_website_id_content_hash' in str(e):
                logger.warning(
                    f"Ошибка дублирования content_hash при попытке update_or_create для URL {original_url} (SuperJob). "
                    f"Возможно, стажировка с таким же контентом уже существует с другим URL или хеш рассчитан некорректно. "
                    f"Детали ошибки: {str(e)}"
                )
                return None, False
            else:
                logger.error(f"Неперехваченная ошибка IntegrityError при update_or_create стажировки (SuperJob) для URL {original_url}: {e}", exc_info=True)
                raise
        except Exception as e:
            logger.error(f"Общая ошибка при update_or_create стажировки (SuperJob) для URL {original_url}: {e}", exc_info=True)
            return None, False

def fetch_superjob_internships(keywords_query=None, city=None, max_results=200, **kwargs):
    try:
        logger.info(f"Запуск поиска стажировок на SuperJob с ключевыми словами '{keywords_query}' и городом '{city}'")

        website_obj = kwargs.pop('website_obj', None)
        if not website_obj:
            website_obj, _ = Website.objects.get_or_create(
                name="SuperJob",
                defaults={"url": "https://www.superjob.ru/"}
            )

        sj_parser = SuperJobParser()

        town_id = None
        if city:
            pass

        internships_data = sj_parser.get_all_internships(
            keywords_query=keywords_query,
            town=town_id if town_id else city,
            max_results=max_results,
            website_obj=website_obj,
            **kwargs
        )

        processed_internships = []
        for internship_data in internships_data:
            if isinstance(internship_data, dict):
                internship, created = sj_parser.create_internship(internship_data, website_obj)
                if internship:
                    processed_internships.append(internship)
            elif isinstance(internship_data, Internship):
                processed_internships.append(internship_data)

        logger.info(f"Завершено получение стажировок с SuperJob. Обработано {len(processed_internships)} стажировок.")
        return processed_internships

    except Exception as e:
        logger.error(f"Ошибка при получении стажировок с SuperJob: {str(e)}", exc_info=True)
        return []
