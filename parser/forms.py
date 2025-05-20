from django import forms
from .models import Website, Internship

class WebsiteForm(forms.ModelForm):
    """Заглушка формы для добавления нового сайта"""
    class Meta:
        model = Website
        fields = ['name', 'url']

class InternshipFilterForm(forms.Form):
    """Заглушка формы для фильтрации стажировок"""
    keywords = forms.CharField(required=False)
    start_date = forms.DateField(required=False)
    end_date = forms.DateField(required=False)
    city = forms.CharField(required=False)
    format = forms.CharField(required=False) 