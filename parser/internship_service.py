import hashlib
import logging
from datetime import timedelta
from django.utils import timezone
from .models import Internship

logger = logging.getLogger('parser')

class InternshipService:
    @staticmethod
    def is_duplicate(internship_data, website):
        """Проверяет, существует ли уже такая стажировка в базе данных
        
        Args:
            internship_data (dict): Данные стажировки
            website (Website): Объект сайта-источника
        
        Returns:
            Internship or None: Существующая стажировка если найдена, иначе None
        """
        if internship_data.get('external_id'):
            existing = Internship.objects.filter(
                external_id=internship_data['external_id'],
                source_website=website
            ).first()
            if existing:
                return existing
            return None
        
        temp_internship = Internship(
            title=internship_data.get('title', ''),
            company=internship_data.get('company', ''),
            position=internship_data.get('position', ''),
            description=internship_data.get('description', ''),
            source_website=website
        )
        
        content = f"{temp_internship.title}|{temp_internship.company}|{temp_internship.position}|{temp_internship.description}"
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        existing = Internship.objects.filter(
            content_hash=content_hash,
            source_website=website
        ).first()
        
        return existing
    
    @staticmethod
    def get_existing_by_external_id(external_id, website):
        """Получает существующую стажировку по external_id
        
        Args:
            external_id (str): Внешний идентификатор стажировки
            website (Website): Объект сайта-источника
            
        Returns:
            Internship or None: Существующая стажировка если найдена, иначе None
        """
        if not external_id:
            return None
            
        return Internship.objects.filter(
            external_id=external_id,
            source_website=website
        ).first()
    
    @staticmethod
    def should_update_internship(existing_internship):
        """Проверяет, нужно ли обновлять информацию о стажировке
        
        Args:
            existing_internship (Internship): Существующая стажировка
            
        Returns:
            bool: True, если стажировку нужно обновить (её нет в БД или прошло более 7 дней с момента последнего обновления)
        """
        if not existing_internship:
            logger.debug("should_update_internship: Стажировка не найдена в БД")
            return True
            
        seven_days_ago = timezone.now() - timedelta(days=7)
        needs_update = existing_internship.updated_at <= seven_days_ago
        
        if needs_update:
            logger.debug(f"should_update_internship: Требуется обновление, последнее обновление {existing_internship.updated_at} раньше порога {seven_days_ago}")
        else:
            logger.debug(f"should_update_internship: Обновление не требуется, последнее обновление {existing_internship.updated_at} позже порога {seven_days_ago}")
            
        return needs_update
    
    @staticmethod
    def create_or_update(internship_data, website):
        """Создает новую стажировку или обновляет существующую
        
        Args:
            internship_data (dict): Данные стажировки
            website (Website): Объект сайта-источника
        
        Returns:
            tuple: (Internship, bool) - объект стажировки и флаг создания новой
        """
        existing = InternshipService.is_duplicate(internship_data, website)
        
        if existing:
            new_external_id = internship_data.get('external_id')
            
            if new_external_id and not existing.external_id:
                logger.info(f"Обновление external_id для стажировки (ID: {existing.id}): {new_external_id}")
                existing.external_id = new_external_id
            
            for key, value in internship_data.items():
                if key == 'source_website':
                    continue
                if key == 'external_id' and value and existing.external_id and value != existing.external_id:
                    logger.warning(f"Конфликт external_id: существующий {existing.external_id}, новый {value} для стажировки ID: {existing.id}")
                    continue
                elif hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            
            content = f"{existing.title}|{existing.company}|{existing.position}|{existing.description}"
            new_hash = hashlib.sha256(content.encode()).hexdigest()
            if existing.content_hash != new_hash:
                existing.content_hash = new_hash
                
            existing.save()
            logger.info(f"Обновлена существующая стажировка (ID: {existing.id}): {existing.title} ({existing.company})")
            return existing, False
        else:
            if 'external_id' in internship_data and not internship_data['external_id']:
                del internship_data['external_id']

            required_fields = ['title']
            for field in required_fields:
                if field not in internship_data or not internship_data[field]:
                     logger.error(f"Невозможно создать стажировку, отсутствует обязательное поле: {field}. Данные: {internship_data}")
                     return None, False

            temp_internship = Internship(**internship_data, source_website=website)
            content = f"{temp_internship.title}|{temp_internship.company}|{temp_internship.position}|{temp_internship.description}"
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            duplicates = Internship.objects.filter(
                content_hash=content_hash,
                source_website=website
            ).exclude(external_id=internship_data.get('external_id'))
            
            if duplicates.exists():
                duplicate_count = duplicates.count()
                duplicate_ids = list(duplicates.values_list('id', flat=True))
                logger.warning(f"Найдено {duplicate_count} стажировок с одинаковым хешем. Удаляем дубликаты с ID: {duplicate_ids}")
                duplicates.delete()
                logger.info(f"Удалено {duplicate_count} дубликатов стажировок с хешем {content_hash[:10]}...")
            
            new_internship = Internship(**internship_data, source_website=website)
            new_internship.content_hash = content_hash
            try:
                new_internship.save()
                logger.info(f"Создана новая стажировка (ID: {new_internship.id}): {new_internship.title} ({new_internship.company})")
                return new_internship, True
            except Exception as e:
                if "unique constraint" in str(e) and "content_hash" in str(e):
                    try:
                        existing_by_hash = Internship.objects.get(content_hash=content_hash, source_website=website)
                        logger.warning(f"Конфликт при сохранении: найдена другая стажировка с таким же хешем (ID: {existing_by_hash.id})")
                        
                        for key, value in internship_data.items():
                            if key != 'source_website' and hasattr(existing_by_hash, key) and value is not None:
                                setattr(existing_by_hash, key, value)
                        
                        existing_by_hash.save()
                        logger.info(f"Обновлена существующая стажировка вместо создания новой (ID: {existing_by_hash.id})")
                        return existing_by_hash, False
                    except Exception as inner_e:
                        logger.error(f"Не удалось обработать конфликт хешей: {str(inner_e)}")
                        raise
                else:
                    logger.error(f"Ошибка при сохранении новой стажировки: {str(e)}")
                    raise 