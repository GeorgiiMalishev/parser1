import requests
import json
import os
import logging
import re

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
- description: **Подробное** описание вакансии/стажировки. Постарайся извлечь как можно больше релевантной информации об обязанностях, требованиях и условиях. (string, обязательное поле)
- employment_type: Тип занятости (например, 'full_time', 'part_time', 'internship', 'project'). Если не указано явно, попробуй определить из контекста или установи null. (string)
- city: Город (string, если указан, иначе null)

Верни **только** JSON объект без каких-либо дополнительных пояснений или текста до/после него.

Вот текст HTML:
{{cleaned_text}}
"""


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") # Рекомендуемый способ

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def parse_with_openrouter(cleaned_text):
    """Отправляет текст в OpenRouter API и парсит JSON из ответа."""
    if not OPENROUTER_API_KEY:
        logger.error("API ключ OpenRouter не настроен (OPENROUTER_API_KEY).")
        return None
        

    prompt_content = prompt_template.format(cleaned_text=cleaned_text)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = json.dumps({
        "model": "deepseek/deepseek-chat-v3-0324:free", 
        "messages": [
            {
                "role": "user",
                "content": prompt_content
            }
        ],
        "response_format": { "type": "json_object" }
    })

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, data=data, timeout=60)
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
            json_start = json_str.find('{')
            if json_start != -1:
                json_str = json_str[json_start:]
        try:
            parsed_data = json.loads(json_str)
            logger.info("OpenRouter успешно извлек данные.")
            return parsed_data
        except json.JSONDecodeError as json_e:
            logger.error(f"Не удалось распарсить JSON из ответа OpenRouter. Ошибка: {json_e}. Ответ модели (после возможного извлечения): {json_str}")
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

