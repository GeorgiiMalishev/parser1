from django.shortcuts import render, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from .models import Website, Internship
from .forms import WebsiteForm, InternshipFilterForm
from .tasks import run_hh_api_parser
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from dotenv import load_dotenv
from .hh_api_parser import HeadHunterAPI
import os
import json

load_dotenv()

def index(request):
    """Главная страница с вкладками"""
    websites = Website.objects.all()
    return render(request, 'parser/main-page/main-page.html', {'websites': websites})

class WebsiteListView(ListView):
    """Отображение списка сайтов"""
    model = Website
    template_name = 'parser/website_list.html'
    context_object_name = 'websites'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hh_enabled'] = True
        return context

class WebsiteCreateView(CreateView):
    """Создание нового сайта"""
    model = Website
    form_class = WebsiteForm
    template_name = 'parser/modal-pages/add-site/add-site.html'
    success_url = reverse_lazy('parser:main_page')
    
    def form_valid(self, form):
        messages.success(self.request, f'Сайт "{form.instance.name}" успешно добавлен')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Ошибка при добавлении сайта')
        return super().form_invalid(form)

def parse_website_preview(request):
    """Предпросмотр результатов парсинга сайта"""
    return JsonResponse({
        'success': False, 
        'error': 'Функциональность парсинга веб-сайтов временно недоступна. Используйте API HeadHunter.'
    })

def save_internship(request):
    """Сохранение стажировки после предпросмотра"""
    if request.method == 'POST':
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

def run_hh_parser(request):
    """Ручной запуск парсера HeadHunter"""
    if request.method == 'POST':
        try:
            result = run_hh_api_parser()
            if result:
                messages.success(request, 'Парсер HeadHunter успешно выполнен')
            else:
                messages.warning(request, 'Парсер HeadHunter не нашел новых стажировок')
        except Exception as e:
            messages.error(request, f'Ошибка при запуске парсера HeadHunter: {str(e)}')
        
        return redirect('parser:internship_list')
    
    return redirect('parser:website_list')

class InternshipListView(ListView):
    """Отображение списка стажировок с фильтрами"""
    model = Internship
    template_name = 'parser/second-page/second-page.html'
    context_object_name = 'internships'
    
    def get_queryset(self):
        queryset = Internship.objects.filter(is_archived=False)
        
        filter_form = InternshipFilterForm(self.request.GET)
        if filter_form.is_valid():
            queryset = self.apply_filters(queryset, filter_form.cleaned_data)
        
        return queryset
    
    def apply_filters(self, queryset, filter_data):
        """Применение фильтров к запросу"""
        keywords = filter_data.get('keywords')
        if keywords:
            queryset = queryset.filter(keywords__icontains=keywords)
        
        start_date = filter_data.get('start_date')
        if start_date:
            queryset = queryset.filter(selection_start_date__gte=start_date)
        
        format_type = filter_data.get('format')
        if format_type:
            queryset = queryset.filter(employment_type=format_type)
        
        city = filter_data.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = InternshipFilterForm(self.request.GET)
        
        # Получаем уникальные города из базы для фильтра
        context['cities'] = Internship.objects.values_list('city', flat=True).distinct()
        
        return context

class ArchivedInternshipListView(InternshipListView):
    """Отображение архивных стажировок"""
    def get_queryset(self):
        return Internship.objects.filter(is_archived=True)

def archive_internship(request, pk):
    """Перемещение стажировки в архив"""
    if request.method == 'POST':
        try:
            internship = Internship.objects.get(pk=pk)
            internship.is_archived = True
            internship.save()
            return JsonResponse({'success': True})
        except Internship.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Internship not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

class MainPageView(TemplateView):
    template_name = 'parser/main-page/main-page.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['websites'] = Website.objects.all()
        return context

class SecondPageView(InternshipListView):
    template_name = 'parser/second-page/second-page.html'

class AddSiteModalView(TemplateView):
    template_name = 'parser/modal-pages/add-site/add-site.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['websites'] = Website.objects.all()
        return context
