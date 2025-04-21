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
    format = forms.ChoiceField(
        choices=[('', '---')] + list(Internship.TYPE_CHOICES),
        required=False
    )
    city = forms.CharField(required=False) 