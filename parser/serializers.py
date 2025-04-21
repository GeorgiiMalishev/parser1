from rest_framework import serializers
from .models import Internship, Website

class WebsiteSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Website"""
    
    class Meta:
        model = Website
        fields = ['id', 'name', 'url', 'created_at', 'updated_at']

class InternshipSerializer(serializers.ModelSerializer):
    """Сериализатор для модели Internship"""
    source_website = WebsiteSerializer(read_only=True)
    
    class Meta:
        model = Internship
        fields = [
            'id', 'external_id', 'title', 'company', 'position',
            'salary', 'selection_start_date', 'duration',
            'selection_end_date', 'description', 'employment_type',
            'city', 'keywords', 'source_website', 'url',
            'is_archived', 'created_at', 'updated_at'
        ] 