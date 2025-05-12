import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import json 
import re
from html_text import extract_text 

from .models import Internship, Website
from .llm_utils import parse_with_openrouter 

logger = logging.getLogger(__name__)

class UniversalParser:
    """
    Универсальный парсер для извлечения информации о стажировках с произвольных URL.
    """

    def __init__(self):
        logger.info("Инициализирован UniversalParser")

    def fetch_html(self, url):
        """Загружает HTML-контент по указанному URL."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            if response.encoding.lower() == 'iso-8859-1':
                encoding = response.apparent_encoding
                if encoding:
                    response.encoding = encoding
                    logger.info(f"Переопределена кодировка для {url}: {encoding} (была ISO-8859-1)")
            
            logger.info(f"Успешно загружен HTML с {url}, кодировка: {response.encoding}")
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при загрузке URL {url}: {e}")
            return None

    def _extract_from_json_ld(self, soup, url):
        """Пытается извлечь данные из JSON-LD (Schema.org/JobPosting)."""
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
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
                    logger.info(f"Найден JSON-LD JobPosting на {url}")

                    title = job_data.get('title')
                    description_html = job_data.get('description')
                    company_data = job_data.get('hiringOrganization')
                    company_name = company_data.get('name') if isinstance(company_data, dict) else None
                    
                    location_data = job_data.get('jobLocation')
                    city = None
                    if isinstance(location_data, dict):
                        address_data = location_data.get('address')
                        if isinstance(address_data, dict):
                            city = address_data.get('addressLocality')

                    salary_data = job_data.get('baseSalary')
                    salary_str = None
                    if isinstance(salary_data, dict):
                        value = salary_data.get('value')
                        currency = salary_data.get('currency')
                        unit = salary_data.get('unitText')
                        if value and currency:
                             salary_str = f"{value} {currency}"
                             if unit:
                                 salary_str += f" per {unit}"
                        elif isinstance(value, str):
                             salary_str = value
    
                    description = description_html

                    return {
                        'title': title,
                        'description': description,
                        'company': company_name,
                        'city': city,
                        'salary': salary_str,
                    }
            except json.JSONDecodeError:
                logger.warning(f"Ошибка декодирования JSON-LD на {url}", exc_info=False)
            except Exception as e:
                logger.error(f"Неожиданная ошибка при обработке JSON-LD на {url}: {e}", exc_info=True)
        return None

    def _extract_from_meta_tags(self, soup, url):
        """Извлекает данные о стажировке из мета-тегов HTML-страницы."""
        logger.info(f"Пытаемся извлечь данные из мета-тегов для {url}")
        
        result = {}
        
        meta_charset = soup.find('meta', charset=True)
        encoding = None
        if meta_charset:
            encoding = meta_charset.get('charset')
            logger.info(f"Обнаружена кодировка из meta charset: {encoding}")
        
        if not encoding:
            meta_content_type = soup.find('meta', attrs={'http-equiv': 'Content-Type'})
            if meta_content_type and 'charset=' in meta_content_type.get('content', ''):
                encoding = meta_content_type.get('content').split('charset=')[-1].strip()
                logger.info(f"Обнаружена кодировка из Content-Type: {encoding}")
        
        def ensure_text_encoding(text):
            if not text:
                return None
            if encoding and encoding.lower() == 'utf-8':
                return text
            if encoding and any(ord(c) > 191 and ord(c) < 256 for c in text):
                try:
                    binary_data = text.encode('latin1')
                    decoded_text = binary_data.decode(encoding)
                    return decoded_text
                except (UnicodeError, LookupError):
                    logger.warning(f"Не удалось перекодировать текст с использованием {encoding}")
            return text
        
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            title_text = title_tag.string.strip()
            result['title'] = ensure_text_encoding(title_text)
        
        description_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
        if description_meta and description_meta.get('content'):
            desc_text = description_meta['content'].strip()
            result['description'] = ensure_text_encoding(desc_text)
        
        company_meta = soup.find('meta', attrs={'property': 'og:site_name'})
        if company_meta and company_meta.get('content'):
            company_text = company_meta['content'].strip()
            result['company'] = ensure_text_encoding(company_text)
        
        location_meta = soup.find('meta', attrs={'name': 'geo.placename'})
        if location_meta and location_meta.get('content'):
            location_text = location_meta['content'].strip()
            result['city'] = ensure_text_encoding(location_text)
        
        if result.get('title') and (result.get('description') or result.get('company')):
            logger.info(f"Удалось извлечь базовые данные из мета-тегов для {url}")
            return result
        
        logger.warning(f"Недостаточно данных из мета-тегов для {url}")
        return None

    def _clean_text(self, html_content):
        """Очищает HTML и возвращает основной текстовый контент с помощью html_text."""
        try:
            clean_text = extract_text(html_content)
            clean_text = re.sub(r'\s{2,}', '\n', clean_text).strip() 
            logger.info("Текст успешно очищен с помощью html_text.")
            return clean_text
        except Exception as e:
            logger.error(f"Ошибка при очистке текста с помощью html_text: {e}", exc_info=True)
            return None

    def _normalize_text(self, text):
        """
        Нормализует текст, исправляя проблемы с кодировкой и убирая некорректные символы.
        """
        if not text:
            return None
            
        try:
            if any('\xd0' in c or '\xd1' in c for c in text):
                try:
                    binary = text.encode('latin1')
                    return binary.decode('utf-8')
                except (UnicodeError, UnicodeDecodeError):
                    pass
                    
            normalized = text.replace('\xa0', ' ')
            normalized = ''.join(c for c in normalized if c.isprintable() or c.isspace())
            
            return normalized.strip()
        except Exception as e:
            logger.error(f"Ошибка при нормализации текста: {e}")
            return text

    def parse_internship_details(self, html_content, url):
        """
        Парсит HTML для извлечения деталей стажировки, используя Ollama LLM.
        """
        if not html_content:
            logger.warning(f"Пустой HTML контент для URL: {url}")
            return None

        logger.info(f"Начинаем парсинг {url} с использованием LLM.")
        
        clean_text = self._clean_text(html_content)
        if not clean_text:
            logger.error(f"Не удалось очистить текст для URL: {url}")
            return None
        
        llm_extracted_data = parse_with_openrouter(clean_text)

        if not llm_extracted_data or not isinstance(llm_extracted_data, dict):
            logger.error(f"LLM не смогла извлечь данные или вернула неверный формат для {url}. Ответ: {llm_extracted_data}")
            
            meta_data = self._extract_from_meta_tags(BeautifulSoup(html_content, 'html.parser'), url)
            if meta_data:
                logger.info(f"Удалось извлечь метаданные из HTML для {url}")
                llm_extracted_data = meta_data
            else:
                json_ld_data = self._extract_from_json_ld(BeautifulSoup(html_content, 'html.parser'), url)
                if json_ld_data:
                    logger.info(f"Удалось извлечь данные из JSON-LD для {url}")
                    llm_extracted_data = json_ld_data
                else:
                    return None
        
        logger.info(f"LLM успешно вернула данные для {url}.")

        required_fields = ['title', 'company', 'description']
        missing_fields = [field for field in required_fields if not llm_extracted_data.get(field)]
        
        if missing_fields:
            logger.warning(f"Отсутствуют обязательные поля ({', '.join(missing_fields)}) для {url}")
            
            if 'title' in missing_fields:
                parsed_url = urlparse(url)
                path_segments = parsed_url.path.strip('/').split('/')
                if path_segments:
                    llm_extracted_data['title'] = ' '.join(word.capitalize() for word in path_segments[-1].replace('-', ' ').replace('_', ' ').split())
                    logger.info(f"Заполнено поле 'title' на основе URL: {llm_extracted_data['title']}")
            
            if 'company' in missing_fields:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc
                if domain:
                    llm_extracted_data['company'] = domain.split('.')[0].capitalize()
                    logger.info(f"Заполнено поле 'company' на основе URL: {llm_extracted_data['company']}")
        
        extracted_data = {
            'url': url,
            'title': self._normalize_text(llm_extracted_data.get('title')),
            'company': self._normalize_text(llm_extracted_data.get('company')),
            'position': self._normalize_text(llm_extracted_data.get('position')),
            'salary': self._normalize_text(llm_extracted_data.get('salary')),
            'selection_start_date': llm_extracted_data.get('selection_start_date'), 
            'duration': self._normalize_text(llm_extracted_data.get('duration')),
            'selection_end_date': llm_extracted_data.get('selection_end_date'), 
            'description': self._normalize_text(llm_extracted_data.get('description')),
            'employment_type': llm_extracted_data.get('employment_type'),
            'city': self._normalize_text(llm_extracted_data.get('city')),
            'external_id': None, 
            'is_archived': False, 
        }

        if not extracted_data.get('position') or extracted_data.get('position') == extracted_data.get('title'):
            extracted_data['position'] = extracted_data.get('title')
            
        if not extracted_data.get('company'):
             parsed_url = urlparse(url)
             extracted_data['company'] = parsed_url.netloc
             logger.warning(f"LLM не извлекла компанию для {url}, используется домен: {extracted_data['company']}")
             
    

        extracted_data['title'] = str(extracted_data.get('title', ''))[:255] if extracted_data.get('title') else 'Заголовок не извлечен'
        extracted_data['company'] = str(extracted_data.get('company', ''))[:100] if extracted_data.get('company') else None
        extracted_data['position'] = str(extracted_data.get('position', ''))[:200] if extracted_data.get('position') else extracted_data['title']
        extracted_data['salary'] = str(extracted_data.get('salary', ''))[:100] if extracted_data.get('salary') else None
        extracted_data['city'] = str(extracted_data.get('city', ''))[:100] if extracted_data.get('city') else None
        extracted_data['duration'] = str(extracted_data.get('duration', ''))[:100] if extracted_data.get('duration') else None
        if extracted_data.get('description'):
            extracted_data['description'] = '\n'.join(line for line in str(extracted_data['description']).splitlines() if line.strip())
        else:
            extracted_data['description'] = 'Описание не извлечено'
            
        if not extracted_data.get('title') or extracted_data['title'] == 'Заголовок не извлечен' or not extracted_data.get('description') or extracted_data['description'] == 'Описание не извлечено':
             logger.error(f"LLM не смогла извлечь обязательные поля (title/description) для {url}")
             return None

        logger.info(f"Данные для {url} подготовлены к сохранению: Название='{extracted_data.get('title')}', Компания='{extracted_data.get('company')}'")
        
        return {k: v for k, v in extracted_data.items() if v is not None}

    def create_or_update_internship(self, internship_data, website):
        """
        Создает или обновляет запись Internship в базе данных,
        используя `update_or_create` для атомарности.
        Модель Internship сама обрабатывает `content_hash` при сохранении.
        """
        if not internship_data:
            logger.warning("Попытка создать/обновить стажировку с пустыми данными.")
            return None, False

        lookup_params = {
            'url': internship_data['url'],
            'source_website': website
        }
        
        valid_keys = {f.name for f in Internship._meta.get_fields()}
        defaults_data = {k: v for k, v in internship_data.items() if k not in lookup_params and k in valid_keys}

        try:
            internship, created = Internship.objects.update_or_create(
                **lookup_params,
                defaults=defaults_data
            )

            action = "Создана" if created else "Обновлена"
            logger.info(f"{action} стажировка: '{internship.title}' по URL {internship.url}")
            return internship, created

        except Exception as e:
            logger.error(f"Ошибка при update_or_create стажировки для URL {internship_data.get('url')}: {e}", exc_info=True)
            return None, False

    def process_url(self, url):
        """Полный цикл обработки одного URL."""
        logger.info(f"Начало обработки URL: {url}")
        html_content = self.fetch_html(url)
        if not html_content:
            return None, False

        internship_data = self.parse_internship_details(html_content, url)
        if not internship_data:
            logger.warning(f"Не удалось извлечь данные для URL: {url}")
            return None, False

        parsed_url = urlparse(url)
        website_name = parsed_url.netloc
        website_url_base = f"{parsed_url.scheme}://{parsed_url.netloc}"

        website, _ = Website.objects.get_or_create(
            name=website_name,
            defaults={'url': website_url_base}
        )

        internship, created = self.create_or_update_internship(internship_data, website)
        
        if internship:
            status_msg = "создана" if created else "обновлена/найдена"
            logger.info(f"Обработка URL {url} завершена. Стажировка '{internship.title}' {status_msg}.")
        else:
             logger.error(f"Не удалось сохранить стажировку для URL: {url}")

        return internship, created

