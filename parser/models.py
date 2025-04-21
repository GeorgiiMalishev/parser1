from django.db import models
from django.utils import timezone
import hashlib

class Website(models.Model):
    """Сайт-источник стажировок"""
    name = models.CharField(max_length=100, verbose_name="Название сайта")
    url = models.URLField(verbose_name="Ссылка на сайт")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Сайт"
        verbose_name_plural = "Сайты"

class Internship(models.Model):
    """Информация о стажировке"""
    TYPE_CHOICES = (
        ('remote', 'Удаленно'),
        ('office', 'Очно'),
        ('hybrid', 'Гибридный'),
        ('full_time', 'Полный день'),
        ('part_time', 'Неполный день'),
        ('flexible', 'Гибкий график')
    )
    
    external_id = models.CharField(max_length=255, verbose_name="Идентификатор стажировки", blank=True, null=True)
    
    title = models.CharField(max_length=255, verbose_name="Название стажировки")
    company = models.CharField(max_length=100, verbose_name="Название компании")
    position = models.CharField(max_length=200, verbose_name="Название должности")
    salary = models.CharField(max_length=100, verbose_name="Заработная плата", blank=True, null=True)
    
    selection_start_date = models.DateField(verbose_name="Дата начала отбора", blank=True, null=True)
    duration = models.CharField(max_length=100, verbose_name="Длительность стажировки", blank=True, null=True)
    selection_end_date = models.DateField(verbose_name="Дата окончания отбора", blank=True, null=True)
    
    description = models.TextField(verbose_name="Описание")
    employment_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Тип занятости", blank=True, null=True)
    city = models.CharField(max_length=100, verbose_name="Город", blank=True, null=True)
    keywords = models.TextField(verbose_name="Ключевые слова", blank=True, null=True)
    
    source_website = models.ForeignKey(Website, on_delete=models.CASCADE, verbose_name="Сайт-источник")
    url = models.URLField(verbose_name="Ссылка на стажировку")
    
    is_archived = models.BooleanField(default=False, verbose_name="В архиве")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    content_hash = models.CharField(max_length=64, verbose_name="Хеш содержимого", blank=True, null=True, db_index=True)
    
    def __str__(self):
        return f"{self.title} ({self.company})"
    
    def save(self, *args, **kwargs):
        content = f"{self.title}|{self.company}|{self.position}|{self.description}"
        self.content_hash = hashlib.sha256(content.encode()).hexdigest()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Стажировка"
        verbose_name_plural = "Стажировки"
        unique_together = [['source_website', 'content_hash']]
