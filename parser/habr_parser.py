import requests
import logging
import time
import random
import json
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

from .base_parser import BaseParser
from .models import Internship, Website
from bs4 import BeautifulSoup
from .internship_service import InternshipService

logger = logging.getLogger('parser')

class HabrCareerParser(BaseParser):
    BASE_API_URL = 'https://career.habr.com/api/frontend'
    BASE_VACANCIES_URL = 'https://career.habr.com/'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        }

    def _make_request(self, url, params=None, method='get', data=None, max_retries=3, is_json=True):
        retry_count = 0
        current_headers = self.headers.copy()
        if not is_json:
            current_headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'

        while retry_count <= max_retries:
            try:
                if method.lower() == 'get':
                    response = requests.get(url, params=params, headers=current_headers, timeout=15)
                elif method.lower() == 'post':
                    response = requests.post(url, json=data if is_json else data, headers=current_headers, params=params, timeout=15)
                else:
                    logger.error(f"Неподдерживаемый метод запроса: {method}")
                    return None

                response.raise_for_status()

                if is_json:
                    return response.json()
                else:
                    return response.text

            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP ошибка для {url} с параметрами {params}: {e.response.status_code} - {e.response.text}")
                if e.response.status_code in [401, 403, 404, 429]:
                    break
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка запроса для {url}: {str(e)}")

            retry_count += 1
            if retry_count <= max_retries:
                delay = random.uniform(1, 3) * (2 ** (retry_count -1))
                logger.info(f"Повторный запрос к {url} через {delay:.2f} секунд... (Попытка {retry_count}/{max_retries})")
                time.sleep(delay)
            else:
                logger.error(f"Превышено максимальное количество попыток ({max_retries}) для запроса к {url}")
                return None
        return None

    def get_area_id_by_city(self, city_name):
        if not city_name:
            logger.warning("Название города не указано для поиска ID региона HabrCareer.")
            return None

        url = f"{self.BASE_API_URL}/suggestions/locations"
        params = {'term': city_name}

        logger.info(f"Получение ID региона для города '{city_name}' с HabrCareer.")
        response_data = self._make_request(url, params=params)

        if response_data and 'list' in response_data and response_data['list']:
            for suggestion in response_data['list']:
                if suggestion.get('title', '').lower() == city_name.lower():
                    area_id = suggestion.get('value')
                    if area_id:
                        logger.info(f"Найден точный ID региона HabrCareer '{area_id}' для города '{city_name}'.")
                        return area_id

            logger.info(f"Точное совпадение для города '{city_name}' не найдено, используется первое предложение.")
            first_suggestion = response_data['list'][0]
            area_id = first_suggestion.get('value')
            if area_id:
                logger.info(f"Найден ID региона HabrCareer '{area_id}' для города '{city_name}' (первое предложение).")
                return area_id
            else:
                logger.warning(f"Не удалось извлечь ID региона ('value') из первого предложения для города '{city_name}'. Предложение: {first_suggestion}")
        else:
            logger.warning(f"Ключ 'list' не найден или список пуст в ответе API для города '{city_name}' от HabrCareer. Ответ: {response_data}")
        return None

    def search_internships(self, keywords_query=None, area_id=None, page=0, per_page=25):
        url = f"{self.BASE_API_URL}/vacancies"
        params = {
            'q': keywords_query if keywords_query else '',
            'type': 'all',
            'qid': '1',
            'sort': 'date',
            'currency': 'RUR',
            'page': page + 1,
            'per_page': per_page
        }
        if area_id:
            params['locations[]'] = area_id

        logger.info(f"Поиск стажировок на HabrCareer с параметрами: {params}")
        response_data = self._make_request(url, params=params)

        if response_data and 'list' in response_data and 'meta' in response_data:
            return {
                'items': response_data.get('list', []),
                'found': response_data.get('meta', {}).get('totalResults', 0),
                'pages': response_data.get('meta', {}).get('totalPages', 0),
                'per_page': response_data.get('meta', {}).get('perPage', per_page),
                'page': response_data.get('meta', {}).get('currentPage', page + 1) -1
            }
        logger.error(f"Ошибка разбора ответа search_internships от HabrCareer или пустые данные. Параметры: {params}, Ответ: {str(response_data)[:200]}")
        return {'items': [], 'found': 0, 'pages': 0, 'per_page': per_page, 'page': page}

    def get_all_internships(self, keywords_query=None, area_id=None, max_pages=10, per_page=25, website_obj=None):
        all_vacancies = []
        current_page = 0
        max_results_cap = 500

        if per_page > 25:
            logger.warning(f"HabrCareer per_page установлено значение {per_page}. Стандартное значение 25. API может не поддерживать это.")

        while True:
            if current_page >= max_pages:
                logger.info(f"Достигнуто максимальное количество страниц ({max_pages}) для HabrCareer.")
                break
            if len(all_vacancies) >= max_results_cap:
                logger.info(f"Достигнут лимит ({max_results_cap}) на количество результатов для HabrCareer.")
                break

            logger.info(f"Загрузка стажировок с HabrCareer: страница {current_page + 1}")
            result = self.search_internships(keywords_query, area_id, current_page, per_page)

            if result and result.get('items'):
                for vacancy_item in result['items']:
                    basic_data = self.convert_to_internship_data(vacancy_item, full_description=None)

                    existing = None
                    if website_obj and basic_data.get('external_id'):
                        from .internship_service import InternshipService
                        existing = InternshipService.get_existing_by_external_id(basic_data['external_id'], website_obj)

                    if not existing or (website_obj and InternshipService.should_update_internship(existing)):
                        if basic_data.get('url'):
                            logger.info(f"Загрузка полного описания для вакансии {basic_data.get('title')}...")
                            parsed_details = self.parse_vacancy_details_html(basic_data['url'])
                            
                            if parsed_details:
                                if parsed_details.get('description'):
                                    basic_data['description'] = parsed_details['description']
                                else:
                                    logger.warning(f"Не удалось получить описание для вакансии {basic_data.get('title')}. Будет использовано краткое описание.")
                                    if not basic_data.get('description'): 
                                        basic_data['description'] = "Описание не найдено"

                                if parsed_details.get('company_name') and not basic_data.get('company'):
                                    basic_data['company'] = parsed_details['company_name']
                                    logger.info(f"Название компании '{parsed_details['company_name']}' для вакансии '{basic_data.get('title')}' было взято из HTML.")
                                elif parsed_details.get('company_name') and basic_data.get('company') and parsed_details.get('company_name') != basic_data.get('company'):
                                    logger.info(f"Название компании из API ('{basic_data.get('company')}') и HTML ('{parsed_details['company_name']}') для '{basic_data.get('title')}' различаются. Приоритет у API.")

                                all_vacancies.append(basic_data)
                            else:
                                logger.warning(f"Не удалось получить HTML-детали для вакансии {basic_data.get('title')}. Будет использовано краткое описание.")
                                if not basic_data.get('description'):
                                    basic_data['description'] = "Описание не найдено"
                                all_vacancies.append(basic_data)
                        else:
                            logger.warning(f"URL не найден для вакансии {basic_data.get('title')}, пропускаем загрузку полного описания.")
                            all_vacancies.append(basic_data)
                    else:
                        logger.info(f"Пропуск обновления для вакансии {basic_data.get('title')} - обновлена недавно")

                total_api_pages = result.get('pages', 0)

                if (current_page + 1) >= total_api_pages:
                    logger.info("Достигнута последняя страница результатов HabrCareer.")
                    break
                current_page += 1
            else:
                logger.warning(f"Не найдено вакансий на странице {current_page + 1} HabrCareer или ошибка в ответе.")
                if current_page == 0 and not all_vacancies:
                    logger.error("Не удалось получить стажировки с HabrCareer при первой попытке.")
                break

            time.sleep(random.uniform(1.0, 2.5))

        logger.info(f"Завершена загрузка с HabrCareer. Всего найдено стажировок: {len(all_vacancies)}")
        return all_vacancies

    def parse_vacancy_details_html(self, vacancy_url):
        logger.info(f"Загрузка HTML для деталей вакансии с: {vacancy_url}")
        html_content = self._make_request(vacancy_url, is_json=False)
        if not html_content:
            logger.error(f"Не удалось загрузить HTML контент для {vacancy_url}")
            return {'description': None, 'company_name': None}

        soup = BeautifulSoup(html_content, 'html.parser')
        parsed_data = {'description': None, 'company_name': None}
        cleaned_desc_json_ld = None
        cleaned_desc_html = None

        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                job_postings = []
                if isinstance(data, list):
                    job_postings.extend(item for item in data if item.get('@type') == 'JobPosting')
                elif isinstance(data, dict):
                    if data.get('@type') == 'JobPosting':
                        job_postings.append(data)
                    elif '@graph' in data and isinstance(data['@graph'], list):
                         job_postings.extend(item for item in data['@graph'] if item.get('@type') == 'JobPosting')

                if job_postings:
                    job_data = job_postings[0]
                    company_name_json_ld = job_data.get('hiringOrganization', {}).get('name')
                    if company_name_json_ld and not parsed_data.get('company_name'):
                        parsed_data['company_name'] = company_name_json_ld.strip()
                        logger.info(f"Название компании извлечено из JSON-LD: {parsed_data['company_name']}")
            except Exception as e:
                logger.warning(f"Ошибка обработки JSON-LD на {vacancy_url}: {e}", exc_info=False)

        logger.info(f"Попытка извлечения описания из HTML CSS селекторов для {vacancy_url}")
        selectors_to_try = [
            'div[class*="vacancy-description-template"] div[class*="style-ugc"]',
            'div.vacancy-description__text',
            'div[class*="vacancy-detail-text__content"]',
            '.job_show_description__vacancy_description .style-ugc',
            'div[class*="vacancy-description__vacancy_description"]'
        ]
        
        description_content_tag_html = None
        found_selector_html = None
        for selector in selectors_to_try:
            tag = soup.select_one(selector)
            if tag:
                description_content_tag_html = tag
                found_selector_html = selector
                logger.info(f"Найден тег для HTML описания с селектором '{selector}' для {vacancy_url}")
                break
        
        if description_content_tag_html:
            description_html_css = description_content_tag_html.decode_contents()
            temp_cleaned_html_desc = self.clean_description(description_html_css)
            if temp_cleaned_html_desc:
                cleaned_desc_html = temp_cleaned_html_desc
                logger.info(f"HTML описание найдено и очищено (селектор: '{found_selector_html}') для {vacancy_url} (длина: {len(cleaned_desc_html)})")
            else:
                logger.warning(f"HTML описание (селектор: '{found_selector_html}') для {vacancy_url} стало пустым после очистки.")
        else:
            logger.warning(f"Не удалось найти тег с HTML описанием с помощью CSS селекторов для {vacancy_url}")

        final_description = None
        json_ld_len = len(cleaned_desc_json_ld) if cleaned_desc_json_ld else 0
        html_len = len(cleaned_desc_html) if cleaned_desc_html else 0
        MIN_FULL_DESC_LENGTH = 300

        if json_ld_len >= MIN_FULL_DESC_LENGTH:
            final_description = cleaned_desc_json_ld
            logger.info(f"Выбрано описание из JSON-LD (длина {json_ld_len} >= {MIN_FULL_DESC_LENGTH}).")
        elif html_len >= MIN_FULL_DESC_LENGTH:
            final_description = cleaned_desc_html
            logger.info(f"Выбрано описание из HTML (длина {html_len} >= {MIN_FULL_DESC_LENGTH}), т.к. JSON-LD был короче или отсутствовал.")
        elif json_ld_len > 0 and json_ld_len >= html_len:
            final_description = cleaned_desc_json_ld
            logger.info(f"Выбрано короткое описание из JSON-LD (длина {json_ld_len}), т.к. оно длиннее или равно HTML (длина {html_len}) или HTML отсутствует.")
        elif html_len > 0:
            final_description = cleaned_desc_html
            logger.info(f"Выбрано короткое описание из HTML (длина {html_len}), т.к. JSON-LD короче или отсутствует.")
        
        parsed_data['description'] = final_description

        if not parsed_data.get('company_name'):
            company_tag_html = soup.select_one('.company_name.company_name--with-icon')
            if company_tag_html:
                parsed_data['company_name'] = company_tag_html.text.strip()
                logger.info(f"Название компании извлечено из HTML: {parsed_data['company_name']}")

        if not parsed_data.get('description'):
            parsed_data['description'] = "Описание не найдено"
            logger.warning(f"Итоговое описание для {vacancy_url} не найдено, установлено значение по умолчанию.")
        
        if not parsed_data.get('company_name'):
             logger.warning(f"Итоговое название компании для {vacancy_url} не найдено.")

        return parsed_data

    def convert_to_internship_data(self, vacancy_item, full_description=None):
        try:
            data = {}

            data['external_id'] = str(vacancy_item.get('id'))

            title = vacancy_item.get('title')
            company_name = vacancy_item.get('company', {}).get('name', '')

            data['title'] = title
            data['position'] = title
            data['company'] = company_name

            vacancy_url = vacancy_item.get('href')
            if vacancy_url:
                data['url'] = urljoin(self.BASE_VACANCIES_URL, vacancy_url)

            salary_text = None
            if vacancy_item.get('salary'):
                salary = vacancy_item.get('salary', {})
                if isinstance(salary, dict):
                    currency = salary.get('currency', '')
                    if currency and salary.get('from') and salary.get('to'):
                        salary_text = f"от {salary['from']} до {salary['to']} {currency}"
                    elif currency and salary.get('from'):
                        salary_text = f"от {salary['from']} {currency}"
                    elif currency and salary.get('to'):
                        salary_text = f"до {salary['to']} {currency}"
                elif isinstance(salary, str):
                    salary_text = salary
            data['salary'] = salary_text

            location = None
            location_items = vacancy_item.get('locations')
            if isinstance(location_items, list) and location_items:
                location = ", ".join([loc.get('title', '') for loc in location_items if loc.get('title')])
            data['city'] = location

            employment_text = None
            employment = vacancy_item.get('employment')
            if employment:
                employment_text = employment
            remote = vacancy_item.get('remote')
            if remote:
                if employment_text:
                    employment_text += ", удаленно"
                else:
                    employment_text = "удаленно"
            data['employment_type'] = self._map_employment_type(employment_text)

            data['selection_start_date'] = None
            data['selection_end_date'] = None

            if full_description:
                data['description'] = full_description
            else:
                preview = vacancy_item.get('snippet', {}).get('text', '')
                description = vacancy_item.get('snippet', {}).get('requirements', '')
                short_description = f"{preview}\n\n{description}" if preview or description else None
                data['description'] = short_description or "Описание загружается..."

            skills = []
            for skill in vacancy_item.get('skills', []):
                skill_name = skill.get('title')
                if skill_name:
                    skills.append(skill_name)
            data['keywords'] = ", ".join(skills) if skills else None

            return data

        except Exception as e:
            logger.error(f"Ошибка преобразования данных вакансии Habr Career: {e}", exc_info=True)
            return {}

    def _map_employment_type(self, employment_text):
        if not employment_text:
            return None

        employment_lower = employment_text.lower()

        if 'удаленно' in employment_lower or 'удаленная' in employment_lower:
            return 'remote'
        elif 'гибрид' in employment_lower:
            return 'hybrid'
        elif 'полный день' in employment_lower or 'полная' in employment_lower:
            return 'full_time'
        elif 'частичная' in employment_lower or 'неполный' in employment_lower:
            return 'part_time'
        elif 'гибкий' in employment_lower:
            return 'flexible'
        else:
            return 'office'

    def create_internship(self, data, website_obj):
        if not data:
            logger.warning("Попытка создать/обновить стажировку с пустыми данными.")
            return None, False

        from .models import Internship
        if isinstance(data, Internship):
            return data, data.id is None

        valid_keys = {f.name for f in Internship._meta.get_fields()}
        internship_data = {k: v for k, v in data.items() if k in valid_keys}

        return InternshipService.create_or_update(internship_data, website_obj)

def fetch_habr_career_internships(keywords_query=None, city_name=None, max_pages=5, location_id=None, website_obj=None, **kwargs):
    logger.info(f"Запуск поиска стажировок на Habr Career с ключевыми словами '{keywords_query}' и городом '{city_name}'")

    parser = HabrCareerParser()

    if not website_obj:
        from .models import Website
        website_obj, _ = Website.objects.get_or_create(
            name="Habr Career",
            defaults={"url": "https://career.habr.com/"}
        )

    if not location_id and city_name:
        location_id = parser.get_area_id_by_city(city_name)

    vacancies_data = parser.get_all_internships(
        keywords_query=keywords_query,
        area_id=location_id,
        max_pages=max_pages,
        website_obj=website_obj
    )

    processed_internships = []
    for vacancy_data in vacancies_data:
        internship, created = parser.create_internship(vacancy_data, website_obj)
        if internship:
            processed_internships.append(internship)

    logger.info(f"Завершено получение стажировок с Habr Career. Обработано {len(processed_internships)} стажировок.")
    return processed_internships
