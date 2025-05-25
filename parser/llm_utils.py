import requests
import json
import os
import logging
import re
import ast
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

prompt_template = f"""
Извлеки информацию о вакансии/стажировке из следующего текста HTML-страницы.
Представь результат в формате JSON со следующими полями:
- title: Название вакансии/стажировки (string, обязательное поле)
- company: Название компании (string, обязательное поле)
- position: Должность (string, если применимо, иначе null)
- salary: Зарплата (string, если указана, иначе null)
- selection_start_date: Дата начала отбора (string в формате YYYY-MM-DD, если указана, иначе null)
- selection_end_date: Дата окончания отбора (string в формате YYYY-MM-DD, если указана, иначе null)
- duration: Продолжительность стажировки (string, если указана, иначе null)
- description: **Очень подробное и полное** описание вакансии/стажировки. Извлеки всю доступную информацию, включая (но не ограничиваясь): обязанности, задачи, основные требования к кандидату (опыт, навыки, образование), желательные требования, предлагаемые условия (график, льготы, возможности роста), информацию о проекте или команде, если она есть. Не сокращай и не обобщай текст, если он релевантен. (string, обязательное поле)
- employment_type: Формат работы. Если работа удаленная, верни "remote". Если гибридный формат, верни "hybrid". Если не указано явно, попробуй определить из контекста, если не удается, верни null. (string)
- city: Город (string, если указан, иначе null)

Верни **только** JSON объект без каких-либо дополнительных пояснений или текста до/после него.

Вот текст HTML:
{{cleaned_text}}
"""

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

YOUR_SITE_URL = "http://localhost:8000"
YOUR_SITE_NAME = "Internship Parser"

MAX_CHARS_LIMIT = 400000

def parse_with_openrouter(cleaned_text):
    if not OPENROUTER_API_KEY:
        logger.error("API ключ OpenRouter не настроен (OPENROUTER_API_KEY).")
        return None

    original_length = len(cleaned_text)
    logger.info(f"Размер исходного текста: {original_length} символов")

    if original_length > MAX_CHARS_LIMIT:
        logger.warning(f"Текст для LLM слишком длинный ({original_length} символов), обрезаем до {MAX_CHARS_LIMIT} (Gemini 2.0 Flash имеет большой контекст).")
        cleaned_text = cleaned_text[:MAX_CHARS_LIMIT]
        logger.info(f"Размер текста после обрезки: {len(cleaned_text)} символов")
    else:
        logger.info(f"Размер текста в пределах лимита модели ({original_length} < {MAX_CHARS_LIMIT})")

    prompt_content = prompt_template.format(cleaned_text=cleaned_text)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": YOUR_SITE_URL,
        "X-Title": YOUR_SITE_NAME,
    }

    data_dict = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [
            {
                "role": "system",
                "content": "Ты являешься высококвалифицированным экспертом по извлечению структурированных данных из веб-страниц. Твоя задача — максимально точно и полно извлечь информацию о стажировках и вакансиях из предоставленного HTML-текста. Результат должен быть представлен в формате JSON. Для поля 'description' особенно важно извлечь как можно больше деталей, не упуская важные аспекты обязанностей, требований и условий. ОЧЕНЬ ВАЖНО: возвращай ТОЛЬКО валидный JSON-объект без каких-либо префиксов, суффиксов или символов markdown. Не используй тройные обратные кавычки, звездочки, маркеры списка или другие markdown-символы. Начинай ответ с символа { и заканчивай символом }. Убедись, что все ключи и значения в JSON корректны и заключены в двойные кавычки там, где это необходимо. Не добавляй никаких комментариев к JSON. Поля, для которых не найдена информация, должны иметь значение null."
            },
            {
                "role": "user",
                "content": prompt_content
            }
        ],
        "response_format": { "type": "json_object" },
        "temperature": 0.1
    }

    data = json.dumps(data_dict)

    try:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)

        logger.info(f"Отправка запроса к OpenRouter API (модель: {data_dict['model']})")
        response = session.post(OPENROUTER_API_URL, headers=headers, data=data, timeout=120)
        response.raise_for_status()

        api_response_json = response.json()

        if not api_response_json.get('choices') or not api_response_json['choices'][0].get('message') or not api_response_json['choices'][0]['message'].get('content'):
             logger.error(f"OpenRouter API вернул неожиданный формат ответа: {api_response_json}")
             return None

        content_str = api_response_json['choices'][0]['message']['content']

        json_match = re.search(r"```json\s*(\{.*?\})\s*```", content_str, re.DOTALL)

        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = content_str

            if '*' in json_str:
                json_str = re.sub(r'^\s*\*\s*', '', json_str, flags=re.MULTILINE)

            if not json_str.strip().startswith('{') and re.search(r'^\s*"[a-zA-Z_]+":', json_str.strip()):
                json_str = '{' + json_str + '}'

            json_start = json_str.find('{')
            if json_start != -1:
                json_end = json_str.rfind('}')
                if json_end > json_start:
                    json_str = json_str[json_start:json_end+1]

            if not ('{' in json_str and '}' in json_str):
                logger.warning(f"Не удалось найти JSON структуру в ответе: {content_str[:100]}...")

        try:
            parsed_data = json.loads(json_str)
            logger.info("OpenRouter успешно извлек данные.")
            return parsed_data
        except json.JSONDecodeError as json_e:
            logger.error(f"Не удалось распарсить JSON из ответа OpenRouter. Ошибка: {json_e}. Ответ модели (после возможного извлечения): {json_str}")

            try:
                fixed_json_str = json_str

                quotes_count = fixed_json_str.count('"')
                if quotes_count % 2 != 0:
                    fixed_json_str += '"'

                if fixed_json_str.count('{') > fixed_json_str.count('}'):
                    fixed_json_str += '}' * (fixed_json_str.count('{') - fixed_json_str.count('}'))

                fixed_json_str = fixed_json_str.replace("'", '"')

                try:
                    fixed_data = ast.literal_eval(fixed_json_str)
                    if isinstance(fixed_data, dict):
                        logger.info("Удалось восстановить данные с помощью ast.literal_eval")
                        return fixed_data
                except:
                    pass

                required_fields = ['title', 'company', 'description']
                manual_data = {}

                for field in required_fields:
                    pattern = fr'"({field})"\s*:\s*"([^"]*)"'
                    match = re.search(pattern, content_str)
                    if match:
                        manual_data[match.group(1)] = match.group(2)

                if all(field in manual_data for field in required_fields):
                    logger.info("Удалось извлечь обязательные поля с помощью регулярных выражений")
                    return manual_data

                logger.error("Все попытки восстановить JSON не удались")
            except Exception as recovery_e:
                logger.error(f"Ошибка при попытке восстановления JSON: {recovery_e}")

            return None

    except requests.exceptions.Timeout:
        logger.error(f"Таймаут при запросе к OpenRouter API: {OPENROUTER_API_URL}")
        return None
    except requests.exceptions.RequestException as req_e:
        logger.error(f"Ошибка при запросе к OpenRouter API: {req_e}")

        try:
            error_details = response.json()
            logger.error(f"Детали ошибки от API: {error_details}")
        except Exception:
            logger.error(f"Не удалось получить детали ошибки из ответа API. Статус код: {response.status_code if 'response' in locals() else 'N/A'}")
        return None
    except Exception as e:
        logger.exception(f"Непредвиденная ошибка при работе с OpenRouter API: {e}")
        return None
